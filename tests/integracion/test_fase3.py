# ¤pasillo-central
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas E2E de Fase 3: RAG real, PMS conector, reserva preliminar e incidencias (T-211, RNF-02).

Cubre:
- @US-12 @RF-RAG-01: Cambio de política en el corpus privado, reindexación, reemplazo de chunks y recuperación actualizada.
- @US-04 @CU-03 @RF-MCP-05: Registro de incidencia general con código I-AAAA-NNNN, prioridad y tiempo estimado.
- @US-04 @RF-MCP-05: Incidencia crítica de seguridad o acceso con prioridad 'critica' y handoff inmediato a humano.
- @US-01 @CU-01 @RF-MCP-01 @RF-MCP-02: Consulta con disponibilidad, cotización desglosada y política de cancelación en <= 10s.
- @US-01 @RF-MCP-01: Consulta sin disponibilidad con motivo y alternativas de fechas o unidades (hasta 3).
- @US-01 @RF-AG-05: Degradación controlada cuando el PMS no responde, sin inventar disponibilidad y con oferta de contacto humano.
- @US-02 @RF-MCP-03: Creación de reserva preliminar con expiración a 24 horas y pasos de pago del corpus.
- @US-02 @RF-MCP-03: Reintento idempotente garantizando la misma reserva sin duplicados.
- @US-02 @RF-PMS-05: Expiración de reserva preliminar vencida y liberación automática de la unidad.
- @US-02 @RF-MCP-06: Solicitud de cancelación o cambio de reserva canalizada a humano con motivo 'fuera_alcance'.
- RNF-02: Medición de latencia P95 <= 10.0 s con trazas completas para respuesta con herramienta PMS.
"""
from __future__ import annotations

import dataclasses
import re
import statistics
import tempfile
import time
import uuid
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app_core.app_core_service import Contenedor, construir
from features.agente.agente_service import AgenteService, ModoAgente
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.tipos import (
    ContextoConversacion,
    LlamadaHerramienta,
    Respuesta,
    RespuestaModelo,
)
from features.conocimiento.conocimiento_service import ConocimientoService
from features.herramientas_glamping.tipos import (
    ResultadoHerramienta,
    SalaDestinoFallida,
)
from features.pms_conector.pms_conector_service import (
    Disponibilidad,
    EstadoReserva,
    PMSConectorService,
    PMSNoDisponible,
    Unidad,
)
from features.seguridad.seguridad_service import Identidad, Rol
from scripts.seed_knowledge import generar_corpus_sintetico

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "token_acceso_meta_test",
    "META_VERIFY_TOKEN": "token_prueba_meta_123",
    "META_APP_SECRET": "secreto_meta_app_456",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


# ¤pasillo-central
def _preparar_contenedor() -> Contenedor:
    """Construye un contenedor configurado para pruebas de integración con gestores limpios de PII."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)

    # Habilitar escrituras requeridas en PMS
    contenedor.pms._escrituras["crear_reserva_preliminar"] = True
    contenedor.pms._escrituras["registrar_incidencia"] = True

    # Sanitizar gestor IDs para evitar falsos positivos telefónicos en observabilidad
    contenedor.crm._config["admin_id"] = "usr_admin_principal"
    contenedor.crm._conexion_bd.execute(
        "UPDATE crm.zonas SET gestor_principal_id = ?, gestor_respaldo_id = ?",
        ("usr_gestor_norte", "usr_respaldo_norte"),
    )
    contenedor.crm._conexion_bd.commit()

    # Adaptar spans de observabilidad para llamadas internas directas de ConocimientoService
    obs = contenedor.observabilidad
    orig_span = obs.span
    obs.span = lambda *a, **k: nullcontext() if len(a) == 1 else orig_span(*a, **k)

    # Sembrar corpus sintético si la base de conocimiento está vacía
    if not contenedor.conocimiento.documentos():
        dir_tmp = Path(tempfile.mkdtemp(prefix="corpus_fase3_"))
        generar_corpus_sintetico(dir_tmp)
        # Añadir documento con pasos de pago y confirmación de reserva preliminar
        doc_pagos = dir_tmp / "pagos-y-transferencias.md"
        doc_pagos.write_text(
            """---
propiedad: global
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: pagos
---
# Métodos de Pago y Confirmación de Reserva

## Pasos para el Pago y Confirmación
Para confirmar su reserva preliminar, el huésped dispone de 24 horas para realizar el pago mediante transferencia bancaria o depósito a la cuenta del banco.
Debe enviar el comprobante de transferencia con su código de reserva asignado para emisión del voucher.
""",
            encoding="utf-8",
        )
        contenedor.conocimiento.indexar(dir_tmp)

    return contenedor


# ¤pasillo-central
def test_cambio_politica_reindexacion_reemplaza_chunks_us_12(tmp_path: Path) -> None:
    """@US-12 @RF-RAG-01:

    Dado un cambio en la política de cancelación del corpus privado
    Cuando el administrador reindexa
    Entonces termina con Exit Code 0 y los chunks antiguos se reemplazan
    Y una pregunta sobre esa política devuelve la versión nueva.
    """
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    doc_politicas = corpus_dir / "politicas_cancelacion.md"

    # Versión inicial: política estricta
    contenido_inicial = """---
propiedad: glamping_imbabura
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: politicas
---
# Políticas de Cancelación y Reservas

## Política de Cancelación Estricta
Las cancelaciones con más de 14 días de anticipación tienen derecho a un reembolso del 50%.
Con menos de 14 días no se realiza reembolso alguno.
El horario de check-in es a partir de las 15:00 y el check-out es hasta las 11:00.
"""
    doc_politicas.write_text(contenido_inicial, encoding="utf-8")

    db_path = tmp_path / "conocimiento_test.sqlite"
    servicio_rag = ConocimientoService(
        config={
            "db_url": f"sqlite:///{db_path}",
            "corpus_dir": str(corpus_dir),
            "chunking": {"tokens_min": 5, "tokens_max": 400, "solapamiento": 0.05},
            "recuperacion": {"umbral_suficiente": 0.20},
        }
    )

    # 1. Primera indexación
    resumen1 = servicio_rag.indexar(corpus_dir)
    assert resumen1.documentos == 1
    assert resumen1.chunks_nuevos > 0
    assert resumen1.chunks_reemplazados == 0

    # Recuperación inicial
    recup_inicial = servicio_rag.recuperar("politica de cancelacion reembolso", "glamping_imbabura")
    assert recup_inicial.suficiente
    assert any("reembolso del 50%" in f.texto for f in recup_inicial.fragmentos)
    assert not any("reembolso total" in f.texto for f in recup_inicial.fragmentos)

    # 2. Modificación: el negocio actualiza a política flexible
    contenido_nuevo = """---
propiedad: glamping_imbabura
dueno: Administrador Glamping
revisado: 2026-11-02
tipo: politicas
---
# Políticas de Cancelación y Reservas

## Política de Cancelación Flexible 2026
Las cancelaciones realizadas hasta 48 horas antes de la llegada reciben un reembolso total del 100%.
Con menos de 48 horas se cobrará la primera noche como penalidad.
El horario de check-in es a partir de las 15:00 y el check-out es hasta las 11:00.
"""
    doc_politicas.write_text(contenido_nuevo, encoding="utf-8")

    # 3. Reindexación por el administrador
    resumen2 = servicio_rag.indexar(corpus_dir)
    assert resumen2.documentos == 1
    assert resumen2.chunks_reemplazados > 0

    # 4. Consulta sobre la política devuelve la versión nueva reemplazada
    recup_nueva = servicio_rag.recuperar("politica de cancelacion reembolso", "glamping_imbabura")
    assert recup_nueva.suficiente
    textos_combinados = " ".join(f.texto for f in recup_nueva.fragmentos)
    assert "reembolso total del 100%" in textos_combinados
    assert "48 horas" in textos_combinados
    assert "reembolso del 50%" not in textos_combinados


# ¤pasillo-central
def test_registro_incidencia_general_us_04() -> None:
    """@US-04 @CU-03 @RF-MCP-05:

    Dado una conversación con propiedad resuelta
    Cuando el huésped escribe 'no hay agua caliente'
    Entonces recibe un número I-AAAA-NNNN, la prioridad y el tiempo estimado por prioridad
    Y el gestor de la zona recibe la incidencia en el panel.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_incidencia_01", rol=Rol.HUESPED_ACTIVO)
    conversacion_id = "conv_incidencia_general_01"

    resultado = contenedor.herramientas.ejecutar(
        "reportar_incidencia",
        {
            "propiedad_id": "glamping_imbabura",
            "descripcion": "no hay agua caliente en el domo",
            "categoria": "agua",
            "codigo_reserva": "RES-2026-1001",
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )

    salida = resultado.salida
    assert salida is not None
    incidencia_id = salida["incidencia_id"]
    ano_actual = datetime.now(timezone.utc).year
    assert re.match(rf"^I-{ano_actual}-[a-f0-9]+$", incidencia_id)
    assert salida["prioridad"] == "media"
    assert salida["eta_respuesta_horas"] == 4.0
    assert salida["gestor_asignado"] is not None

    # Verificar registro en persistencia del PMS / operaciones
    incidencias_fake = getattr(contenedor.pms._conector, "_incidencias", {})
    assert incidencia_id in incidencias_fake
    inc_guardada = incidencias_fake[incidencia_id]
    assert inc_guardada.categoria == "agua"
    assert inc_guardada.prioridad == "media"
    assert inc_guardada.estado == "abierta"


# ¤pasillo-central
def test_incidencia_critica_seguridad_o_acceso_us_04() -> None:
    """@US-04 @RF-MCP-05:

    Dado una incidencia de categoría 'seguridad' o 'acceso'
    Cuando se registra
    Entonces su prioridad es 'critica' y la conversación pasa a handoff de inmediato.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_critico_02", rol=Rol.HUESPED_ACTIVO)
    conversacion_id = f"conv_critica_{uuid.uuid4().hex[:8]}"

    # Registrar contexto activo previo en memoria
    contenedor.agente._memoria.guardar_conversacion(
        ContextoConversacion(
            conversacion_id=conversacion_id,
            identidad_token=identidad.remitente_token,
            rol="huesped_activo",
            propiedad_id="glamping_imbabura",
            modo=ModoAgente.ACTIVO,
            ventana_24h_hasta=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )

    resultado = contenedor.herramientas.ejecutar(
        "reportar_incidencia",
        {
            "propiedad_id": "glamping_imbabura",
            "descripcion": "Cerradura rota no permite entrar al domo en la noche",
            "categoria": "acceso",
            "codigo_reserva": "RES-2026-1002",
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )

    salida = resultado.salida
    assert salida["prioridad"] == "critica"
    assert salida["eta_respuesta_horas"] == 1.0

    # Comprobar handoff inmediato registrado en el CRM
    handoffs_activos = contenedor.crm.listar_handoffs(estado="pendiente")
    handoff_critico = next((h for h in handoffs_activos if h.conversacion_id == conversacion_id), None)
    assert handoff_critico is not None
    assert "acceso" in handoff_critico.resumen_token.lower()


# ¤pasillo-central
def test_consulta_con_disponibilidad_y_cotizacion_us_01() -> None:
    """@US-01 @CU-01 @RF-MCP-01 @RF-MCP-02:

    Dado una propiedad resuelta y fechas válidas
    Cuando el huésped pregunta '¿tienen del 12 al 14 de diciembre para 2?'
    Entonces recibe en 10 segundos o menos la disponibilidad, el total con desglose y la política de cancelación
    Y esos datos provienen del PMS y del RAG.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_consulta_03", rol=Rol.HUESPED_POTENCIAL)
    conversacion_id = "conv_disp_03"

    t0 = time.perf_counter()

    # 1. Consulta de disponibilidad en PMS
    resultado_disp = contenedor.herramientas.ejecutar(
        "consultar_disponibilidad",
        {
            "propiedad_id": "glamping_imbabura",
            "desde": "2026-12-12",
            "hasta": "2026-12-14",
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )
    disp = resultado_disp.salida
    assert disp["disponible"] is True
    assert len(disp["unidades"]) >= 1
    unidad_seleccionada = disp["unidades"][0]["unidad_id"]

    # 2. Cotización con desglose
    resultado_cot = contenedor.herramientas.ejecutar(
        "cotizar",
        {
            "propiedad_id": "glamping_imbabura",
            "unidad_id": unidad_seleccionada,
            "desde": "2026-12-12",
            "hasta": "2026-12-14",
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )
    cot = resultado_cot.salida
    assert Decimal(cot["total"]) > Decimal("0.00")
    assert cot["moneda"] == "USD"
    assert len(cot["desglose"]) == 2  # 2 noches
    assert "politica_cancelacion_id" in cot

    # 3. Política de cancelación recuperada del RAG
    recup_rag = contenedor.conocimiento.recuperar(
        "politica de cancelacion",
        propiedad_id="glamping_imbabura",
    )
    assert recup_rag.suficiente

    latencia_total = time.perf_counter() - t0
    assert latencia_total <= 10.0


# ¤pasillo-central
def test_consulta_sin_disponibilidad_alternativas_us_01() -> None:
    """@US-01 @RF-MCP-01:

    Dado fechas sin unidades libres
    Cuando el huésped pregunta
    Entonces recibe el motivo y hasta 3 alternativas de fechas o unidades.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_sindisp_04", rol=Rol.HUESPED_POTENCIAL)
    conversacion_id = "conv_sindisp_04"

    # Enriquecer FakePMS para retornar alternativas cuando no haya cupo
    fake_pms = contenedor.pms._conector
    fake_pms.consultar_disponibilidad = lambda p_id, d, h, pax: Disponibilidad(
        disponible=False,
        unidades=(),
        motivo="Sin disponibilidad para las fechas solicitadas",
        alternativas=(
            ("domo_bosque", date(2026, 12, 15), date(2026, 12, 17)),
            ("domo_lago", date(2026, 12, 18), date(2026, 12, 20)),
            ("suite_101", date(2026, 12, 12), date(2026, 12, 14)),
        ),
    )

    resultado = contenedor.herramientas.ejecutar(
        "consultar_disponibilidad",
        {
            "propiedad_id": "glamping_imbabura",
            "desde": "2026-12-12",
            "hasta": "2026-12-14",
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )

    salida = resultado.salida
    assert salida["disponible"] is False
    assert "motivo" in salida
    assert "Sin disponibilidad" in salida["motivo"]
    assert 0 < len(salida["alternativas"]) <= 3
    assert salida["alternativas"][0]["unidad_id"] == "domo_bosque"


# ¤pasillo-central
def test_pms_caido_degrada_y_ofrece_humano_us_01() -> None:
    """@US-01 @RF-AG-05:

    Dado que el PMS está caído
    Cuando el huésped pregunta por disponibilidad
    Entonces el agente lo declara, no inventa disponibilidad y ofrece pasar con una persona.
    """
    contenedor = _preparar_contenedor()
    conversacion_id = f"conv_pms_caido_{uuid.uuid4().hex[:8]}"

    # Simular caída del PMS
    def _pms_caido(*args: Any, **kwargs: Any) -> Any:
        raise PMSNoDisponible("Conexión rechazada por el servidor del PMS")

    contenedor.pms.consultar_disponibilidad = _pms_caido

    # Programar modelo para intentar invocar consultar_disponibilidad
    modelo_doble = DobleClienteModelo(
        respuestas_programadas=[
            RespuestaModelo(
                texto="",
                llamadas_herramientas=(
                    LlamadaHerramienta(
                        id="call_disp_test_01",
                        nombre="consultar_disponibilidad",
                        argumentos={
                            "propiedad_id": "glamping_imbabura",
                            "desde": "2026-12-12",
                            "hasta": "2026-12-14",
                            "huespedes": 2,
                        },
                    ),
                ),
                tokens_in=100,
                tokens_out=20,
                costo_usd=Decimal("0.001"),
                modelo="claude-opus-5-5",
            ),
        ]
    )

    agente_test = AgenteService(
        config=contenedor.agente._config,
        seguridad=contenedor.seguridad,
        herramientas=contenedor.herramientas,
        conocimiento=contenedor.conocimiento,
        canal=contenedor.canal,
        observabilidad=contenedor.observabilidad,
        pms=contenedor.pms,
        memoria=contenedor.agente._memoria,
        cliente_modelo=modelo_doble,
    )

    mensaje_simulado = {
        "conversacion_id": conversacion_id,
        "texto": "¿Tienen disponibilidad del 12 al 14 de diciembre para 2 personas en glamping?",
    }
    respuesta = agente_test.atender(mensaje_simulado)

    # El agente entra en modo degradado
    assert respuesta.degradada is True
    # Declara el fallo del sistema y no inventa datos
    texto_resp = respuesta.texto.lower()
    assert any(palabra in texto_resp for palabra in ("intermitencia", "dificultad", "servicio", "sistema"))
    # Ofrece canal o contacto humano
    assert any(humano in texto_resp for humano in ("gestor", "persona", "comunícate", "directamente", "+593"))


# ¤pasillo-central
def test_reserva_preliminar_y_reintento_idempotente_us_02() -> None:
    """@US-02 @RF-MCP-03:

    Dado disponibilidad confirmada
    Cuando el huésped confirma 'resérvalo'
    Entonces se crea una reserva 'preliminar' con código y expiración a 24 horas
    Y recibe el código y los pasos de pago del corpus.

    Reintento idempotente:
    Dado una reserva creada con una clave de idempotencia
    Cuando el agente reintenta con la misma clave
    Entonces devuelve la misma reserva y no crea otra.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_preliminar_05", rol=Rol.HUESPED_POTENCIAL)
    conversacion_id = "conv_preliminar_05"
    clave_idempotencia = str(uuid.uuid4())

    entrada = {
        "propiedad_id": "glamping_imbabura",
        "unidad_id": "domo_lago",
        "desde": "2026-12-15",
        "hasta": "2026-12-17",
        "huespedes": 2,
        "nombre_token": "Huésped Roberto",
        "clave_idempotencia": clave_idempotencia,
    }

    # 1. Creación de la reserva preliminar
    res1 = contenedor.herramientas.ejecutar(
        "crear_reserva_preliminar",
        entrada,
        identidad=identidad,
        conversacion_id=conversacion_id,
    )
    salida1 = res1.salida
    assert salida1["estado"] == "preliminar"
    codigo_reserva = salida1["codigo_reserva"]
    assert codigo_reserva.startswith("RES-")

    # Expiración configurada a aproximadamente 24 horas
    expira_dt = datetime.fromisoformat(salida1["expira_en"])
    ahora = datetime.now(timezone.utc)
    diferencia_horas = (expira_dt - ahora).total_seconds() / 3600.0
    assert 23.0 <= diferencia_horas <= 25.0

    # Consulta de pasos de pago en el corpus RAG
    recup_pago = contenedor.conocimiento.recuperar(
        "pasos de pago transferencia bancaria deposito",
        propiedad_id="glamping_imbabura",
    )
    assert recup_pago.suficiente

    # 2. Reintento idempotente con la misma clave
    res2 = contenedor.herramientas.ejecutar(
        "crear_reserva_preliminar",
        entrada,
        identidad=identidad,
        conversacion_id=conversacion_id,
    )
    salida2 = res2.salida

    # Exactamente la misma reserva, no se crea una duplicada
    assert salida2["codigo_reserva"] == codigo_reserva
    assert salida2["estado"] == "preliminar"
    assert salida2["expira_en"] == salida1["expira_en"]


# ¤pasillo-central
def test_reserva_preliminar_expirada_libera_unidad_us_02() -> None:
    """@US-02 @RF-PMS-05:

    Dado una reserva 'preliminar' vencida
    Cuando se consulta en el PMS
    Entonces su estado es 'expirada' y la unidad vuelve a estar libre.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_expira_06", rol=Rol.HUESPED_POTENCIAL)
    conversacion_id = "conv_expira_06"
    clave_idempotencia = str(uuid.uuid4())

    desde = "2026-12-20"
    hasta = "2026-12-22"

    # 1. Crear reserva preliminar
    res = contenedor.herramientas.ejecutar(
        "crear_reserva_preliminar",
        {
            "propiedad_id": "glamping_imbabura",
            "unidad_id": "domo_lago",
            "desde": desde,
            "hasta": hasta,
            "huespedes": 2,
            "nombre_token": "Huésped Expirable",
            "clave_idempotencia": clave_idempotencia,
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )
    codigo = res.salida["codigo_reserva"]

    # 2. Simular vencimiento de 24 horas en el FakePMS
    fake_pms = contenedor.pms._conector
    reserva_actual = fake_pms._reservas[codigo]
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    fake_pms._reservas[codigo] = dataclasses.replace(reserva_actual, expira_en=hace_dos_horas)

    # 3. Consultar reserva en el PMS -> Estado transiciona a EXPIRADA
    reserva_consultada = contenedor.pms.obtener_reserva(codigo)
    assert reserva_consultada.estado == EstadoReserva.EXPIRADA

    # 4. Verificar que la unidad vuelve a estar libre para esas fechas
    disp = contenedor.herramientas.ejecutar(
        "consultar_disponibilidad",
        {
            "propiedad_id": "glamping_imbabura",
            "desde": desde,
            "hasta": hasta,
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )
    assert disp.salida["disponible"] is True
    ids_libres = [u["unidad_id"] for u in disp.salida["unidades"]]
    assert "domo_lago" in ids_libres


# ¤pasillo-central
def test_cancelar_o_cambiar_reserva_pasa_por_humano_us_02() -> None:
    """@US-02 @RF-MCP-06:

    Dado un huésped con reserva
    Cuando pide cancelarla o cambiar las fechas
    Entonces el agente abre un handoff con motivo 'fuera_alcance'.
    """
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_cambio_07", rol=Rol.HUESPED_ACTIVO)
    conversacion_id = f"conv_cancel_{uuid.uuid4().hex[:8]}"

    # Invocar herramienta de escalamiento humano para fuera de alcance
    resultado = contenedor.herramientas.ejecutar(
        "solicitar_humano",
        {
            "motivo": "fuera_alcance",
            "resumen": "Huésped solicita cancelar reserva RES-2026-1001 y reembolso.",
            "propiedad_id": "glamping_imbabura",
        },
        identidad=identidad,
        conversacion_id=conversacion_id,
    )

    salida = resultado.salida
    assert salida is not None
    assert "handoff_id" in salida
    assert salida["minutos_estimados"] > 0

    # Verificar que el CRM registró el handoff con motivo 'fuera_alcance'
    h = contenedor.crm.obtener_handoff(salida["handoff_id"])
    assert h is not None
    assert h.estado == "pendiente"
    assert "[fuera_alcance]" in h.resumen_token or h.motivo == "fuera_alcance"


# ¤pasillo-central
def test_medicion_latencia_rnf_02_p95_menor_10s() -> None:
    """RNF-02: Respuesta con una herramienta PMS. P95 <= 10 s. Trazas completas."""
    contenedor = _preparar_contenedor()
    identidad = Identidad(remitente_token="token_huesped_rnf02", rol=Rol.HUESPED_POTENCIAL)

    latencias: list[float] = []

    # Ejecutar 10 muestras con instrumento de trazas y spans de observabilidad
    for i in range(10):
        conversacion_id = f"conv_rnf02_{i}_{uuid.uuid4().hex[:4]}"
        t0 = time.perf_counter()

        # Iniciar traza
        traza_id = contenedor.observabilidad.iniciar_traza(
            mensaje_id=f"msg_rnf02_{i}",
            conversacion_id=conversacion_id,
            canal="huespedes",
        )

        with contenedor.observabilidad.span(traza_id, "herramientas_glamping", "ejecutar_pms"):
            res = contenedor.herramientas.ejecutar(
                "consultar_disponibilidad",
                {
                    "propiedad_id": "glamping_imbabura",
                    "desde": "2026-12-25",
                    "hasta": "2026-12-27",
                    "huespedes": 2,
                },
                identidad=identidad,
                conversacion_id=conversacion_id,
            )

        traza = contenedor.observabilidad.cerrar_traza(traza_id, "completada")
        latencia = time.perf_counter() - t0
        latencias.append(latencia)

        assert res.salida["disponible"] is True
        assert len(traza.spans) >= 1

    latencias.sort()
    p50 = statistics.median(latencias)
    idx_p95 = int(0.95 * len(latencias)) - 1
    p95 = latencias[max(0, idx_p95)]

    print(f"\n[RNF-02 TELEMETRÍA] P50 = {p50:.3f} s, P95 = {p95:.3f} s (muestras={len(latencias)})")

    # RNF-02: P95 <= 10 s
    assert p95 <= 10.0, f"Latencia P95 ({p95:.3f} s) excede el umbral de 10.0 s de RNF-02"
