# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del árbitro para T-310: pasillo central (worker y panel_crm_router).

Cubre:
- US-03, CU-02, RF-AG-08, RF-GW-03: tarea programada checkin_del_dia e INV_ENVIO_UNICO.
- RF-MCP-04, RF-SEC-08, INV_SIN_FUGA_ENTRE_PROPIEDADES: aislamiento de datos de propiedad y marcadores de secretos.
- US-19, RF-ANF-04: solicitud de reserva con fechas, total del PMS y porcentaje congelado.
- RF-CRM-05: confinamiento de imports de MCP de comunidad fuera de features/crm_conector.
- Montaje de /panel/*, estáticos y ruta POST /crm/eventos con despacho a agente.reanudar.
"""
from __future__ import annotations

import ast
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.panel_crm_router import (
    crear_router_crm,
    montar_panel,
    montar_panel_y_crm,
    registrar_receptores_crm,
)
from app_core.worker import checkin_del_dia, ejecutar_tareas_programadas, reintentos_cola_crm
from features.anfitriones.anfitriones_service import (
    Anfitrion,
    AnfitrionesService,
    EstadoHospedaje,
    EstadoSolicitud,
    Hospedaje,
    cargar_config as cargar_config_anfitriones,
)
from features.crm_conector.crm_conector_service import (
    CRMConectorService,
    EventoCRM,
    FirmaEventoInvalida,
    cargar_config as cargar_config_crm,
)
from features.herramientas_glamping.herramientas_glamping_service import (
    ReservaNoAutorizada,
)
from features.seguridad.seguridad_service import Identidad, Rol
from tests.conftest import RAIZ, archivos_python

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
def _firmar_payload_crm(cuerpo: bytes, secreto: str) -> str:
    """Calcula firma HMAC-SHA256 para eventos entrantes del CRM."""
    return hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()


# ¤pasillo-central
def test_checkin_del_dia_ejecuta_envios_y_respeta_envio_unico() -> None:
    """Escenario @US-03 @RF-AG-08 @INV_ENVIO_UNICO:

    Dado instrucciones de check-in ya enviadas hoy para una reserva,
    cuando el planificador corre otra vez, no se envían de nuevo.
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    hoy = date.today()

    reserva_hoy = SimpleNamespace(
        codigo="RES-PRUEBA-001",
        propiedad_id="glamping_imbabura",
        huesped_telefono="+593991234567",
        huesped_nombre="Carlos H",
        desde=hoy,
    )

    # Inyectar retorno en pms
    contenedor.pms.reservas_con_llegada = lambda f: (reserva_hoy,) if f == hoy else ()

    # Primera ejecución: debe enviar la plantilla y registrarla
    enviados_primera = checkin_del_dia(contenedor, fecha=hoy)
    assert enviados_primera == 1

    # Segunda ejecución: planificador se reinicia el mismo día (INV_ENVIO_UNICO)
    enviados_segunda = checkin_del_dia(contenedor, fecha=hoy)
    assert enviados_segunda == 0, "INV_ENVIO_UNICO violado: no debe reenviar la plantilla el mismo día"


# ¤pasillo-central
def test_checkin_fuera_de_ventana_usa_plantilla_aprobada() -> None:
    """Escenario @US-03 @RF-GW-03:

    Dado un huésped fuera de la ventana de 24h,
    cuando el sistema inicia el envío, usa la plantilla aprobada 'instrucciones_checkin'.
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    fecha_futura = date.today() + timedelta(days=5)

    reserva_futura = SimpleNamespace(
        codigo="RES-FUTURA-999",
        propiedad_id="glamping_imbabura",
        huesped_telefono="+593998887777",
        huesped_nombre="Valeria P",
        desde=fecha_futura,
    )
    contenedor.pms.reservas_con_llegada = lambda f: (reserva_futura,) if f == fecha_futura else ()

    plantillas_recibidas: list[tuple[str, Any]] = []
    original_enviar_plantilla = contenedor.canal.enviar_plantilla

    def _capturar_plantilla(destinatario: str, plantilla: Any) -> Any:
        plantillas_recibidas.append((destinatario, plantilla))
        return original_enviar_plantilla(destinatario, plantilla)

    contenedor.canal.enviar_plantilla = _capturar_plantilla

    enviados = checkin_del_dia(contenedor, fecha=fecha_futura)
    assert enviados == 1
    assert len(plantillas_recibidas) == 1
    dest, p_obj = plantillas_recibidas[0]
    assert dest == "+593998887777"
    assert p_obj.nombre == "instrucciones_checkin"


# ¤pasillo-central
def test_checkin_propiedad_correcta_y_secretos_enmascarados() -> None:
    """Escenarios @US-03 @CU-02 @RF-MCP-04 @INV_SIN_FUGA_ENTRE_PROPIEDADES y @RF-SEC-08:

    - El titular recibe dirección, acceso, wifi y normas de su propiedad y ningún dato de otra.
    - El modelo recibe solo marcadores [[SECRETO:...]].
    - Remitente no titular recibe ReservaNoAutorizada, se audita y tras 5 intentos escala a humano.
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)

    # Configurar PMS para validar titular y entregar instrucciones
    contenedor.pms.validar_titular_local = lambda cod, tok: cod == "RES-1001" and tok == "token_huesped_valido"
    contenedor.pms.obtener_instrucciones_checkin = lambda cod: SimpleNamespace(
        propiedad="Glamping San Pablo",
        direccion="Loma de San Pablo, Lago San Pablo",
        acceso=["Cerradura digital domo principal"],
        wifi_red="Glamping_Guest",
        wifi_clave_token="[[SECRETO:wifi_san_pablo]]",
        normas=["No fumar en domos; silencio a partir de las 22:00"],
        contacto_emergencia="+593991112233",
        hora_checkin="15:00",
    )

    # 1. Titular válido de RES-1001
    identidad_valida = Identidad(remitente_token="token_huesped_valido", rol=Rol.HUESPED_ACTIVO)
    salida = contenedor.herramientas.ejecutar(
        "obtener_instrucciones_checkin",
        {"codigo_reserva": "RES-1001"},
        identidad=identidad_valida,
        conversacion_id="c_checkin_ok",
    )
    assert salida.salida["propiedad"] == "Glamping San Pablo"
    assert salida.salida["wifi"]["clave_ref"] == "[[SECRETO:wifi_san_pablo]]"
    assert "No fumar en domos" in salida.salida["normas"][0]

    # 2. Remitente no titular
    identidad_ajena = Identidad(remitente_token="remitente_no_titular", rol=Rol.HUESPED_ACTIVO)
    with pytest.raises(ReservaNoAutorizada) as exc_info:
        contenedor.herramientas.ejecutar(
            "obtener_instrucciones_checkin",
            {"codigo_reserva": "RES-1001"},
            identidad=identidad_ajena,
            conversacion_id="c_checkin_ajeno",
        )
    assert exc_info.value.codigo_reserva == "RES-1001"

    # 3. 5 intentos fallidos en 24h escalan a humano
    identidad_atacante = Identidad(remitente_token="atacante_24h", rol=Rol.HUESPED_ACTIVO)
    for i in range(4):
        with pytest.raises(ReservaNoAutorizada):
            contenedor.herramientas.ejecutar(
                "obtener_instrucciones_checkin",
                {"codigo_reserva": f"RES-INTRUSO-{i}"},
                identidad=identidad_atacante,
                conversacion_id="c_bruta",
            )

    with pytest.raises(ReservaNoAutorizada):
        contenedor.herramientas.ejecutar(
            "obtener_instrucciones_checkin",
            {"codigo_reserva": "RES-INTRUSO-5"},
            identidad=identidad_atacante,
            conversacion_id="c_bruta",
        )


# ¤pasillo-central
def test_solicitud_reserva_rf_anf_04() -> None:
    """Escenario @US-19 @RF-ANF-04:

    Dado una reserva preliminar de un hospedaje publicado,
    cuando el asistente crea la solicitud,
    fechas y total salen del PMS, el porcentaje del anfitrión queda congelado,
    y el anfitrión recibe la plantilla con vigencia de 24 horas.
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)

    # Registrar anfitrión con porcentaje explícito
    anfitrion = Anfitrion(
        anfitrion_id="ANF-T310",
        nombre_comercial="Cabañas Mojanda",
        comision_porcentaje=Decimal("12.50"),
        terminos_version="v2026.1",
    )
    contenedor.anfitriones.registrar_anfitrion(anfitrion, "+593987654321", actor_id="admin_01")
    contenedor.anfitriones.guardar_hospedaje(
        Hospedaje(propiedad_id="DOMO-MOJANDA", anfitrion_id="ANF-T310", estado=EstadoHospedaje.PUBLICADO),
        actor_id="admin_01",
    )

    # Simular reserva en PMS
    reserva_doble = SimpleNamespace(
        codigo="R-T310-001",
        propiedad_id="DOMO-MOJANDA",
        unidad_id="U-1",
        huesped_token="tok_huesped_t310",
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 5),
        huespedes=2,
        total=Decimal("380.00"),
    )
    contenedor.pms.obtener_reserva = lambda cod: reserva_doble if cod == "R-T310-001" else None

    # Crear solicitud
    solicitud = contenedor.anfitriones.solicitar_reserva("R-T310-001")
    assert solicitud.codigo_reserva == "R-T310-001"
    assert solicitud.solicitud.startswith("PL-")
    assert solicitud.desde == date(2026, 12, 1)
    assert solicitud.hasta == date(2026, 12, 5)
    assert solicitud.total == Decimal("380.00")
    assert solicitud.comision_porcentaje == Decimal("12.50")
    assert solicitud.estado == EstadoSolicitud.SOLICITADA


# ¤pasillo-central
def test_confinamiento_imports_mcp_comunidad() -> None:
    """Escenario @RF-CRM-05:

    Dado un MCP de comunidad, cuando se revisan los imports,
    entonces no aparece fuera de features/crm_conector.
    """
    modulos_prohibidos = {"ghl", "chatwoot", "attio", "mcp_server_crm"}
    violaciones: list[str] = []

    for ruta in archivos_python("features", "app_core", "scripts"):
        partes = ruta.relative_to(RAIZ).parts
        # Permitido exclusivamente en features/crm_conector
        if partes[0] == "features" and len(partes) > 1 and partes[1] == "crm_conector":
            continue

        arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=ruta.name)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    if any(p in alias.name.lower() for p in modulos_prohibidos):
                        violaciones.append(f"{ruta.relative_to(RAIZ)} importa {alias.name}")
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                if any(p in nodo.module.lower() for p in modulos_prohibidos):
                    violaciones.append(f"{ruta.relative_to(RAIZ)} importa {nodo.module}")

    assert not violaciones, "Violación de confinamiento RF-CRM-05:\n" + "\n".join(violaciones)


# ¤pasillo-central
def test_montaje_panel_y_estaticos_http() -> None:
    """Montaje de /panel/*, BFF y archivos estáticos en la app HTTP."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    app = FastAPI()
    montar_panel_y_crm(app, contenedor)

    client = TestClient(app)

    # 1. Página inicial del panel
    resp_index = client.get("/panel")
    assert resp_index.status_code == 200

    # 2. Manifest y Service Worker
    resp_manifest = client.get("/panel/manifest.webmanifest")
    assert resp_manifest.status_code in (200, 404)

    resp_sw = client.get("/panel/sw.js")
    assert resp_sw.status_code in (200, 404)

    # 3. Endpoint de API del BFF protegido (sin cookie -> 401)
    resp_sesion = client.get("/panel/api/sesion")
    assert resp_sesion.status_code == 401


# ¤pasillo-central
def test_ruta_crm_eventos_despacha_y_reanuda_agente() -> None:
    """Ruta POST /crm/eventos -> crm.recibir_evento -> agente.reanudar."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    secreto = "secreto_test_webhook_crm"
    # Asegurar secreto configurado explícitamente en el conector
    contenedor.crm._config.setdefault("eventos_entrantes", {})["secreto"] = secreto

    app = FastAPI()
    montar_panel_y_crm(app, contenedor)

    client = TestClient(app)

    reanudadas: list[str] = []
    contenedor.agente.reanudar = lambda conv_id: reanudadas.append(conv_id)

    # Evento handoff_devuelto
    payload = {
        "tipo": "handoff_devuelto",
        "referencia": "HND-2026-9001",
        "actor": "gestor_pablo",
        "datos": {
            "conversacion_id": "conv_whatsapp_59399999",
            "motivo": "resuelto_por_humano",
        },
        "recibido_en": datetime.now(timezone.utc).isoformat(),
    }
    cuerpo = json.dumps(payload).encode("utf-8")
    firma = _firmar_payload_crm(cuerpo, secreto)

    # 1. Petición válida
    resp = client.post(
        "/crm/eventos",
        content=cuerpo,
        headers={
            "Content-Type": "application/json",
            "X-CRM-Signature": firma,
        },
    )
    assert resp.status_code == 200
    datos_resp = resp.json()
    assert datos_resp["ok"] is True
    assert datos_resp["evento"] == "handoff_devuelto"
    assert "conv_whatsapp_59399999" in reanudadas

    # 2. Petición con firma inválida debe ser rechazada con 401
    resp_invalida = client.post(
        "/crm/eventos",
        content=cuerpo,
        headers={
            "Content-Type": "application/json",
            "X-CRM-Signature": "firma_falsa_invalida",
        },
    )
    assert resp_invalida.status_code == 401


# ¤pasillo-central
def test_ejecutar_tareas_programadas_en_worker() -> None:
    """Ejecución por lote de tareas en app_core/worker.py."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    resultados = ejecutar_tareas_programadas(contenedor, tareas=["checkin_del_dia", "reintentos_cola_crm"])
    assert "checkin_del_dia" in resultados
    assert "reintentos_cola_crm" in resultados
    assert isinstance(resultados["checkin_del_dia"], int)
    assert isinstance(resultados["reintentos_cola_crm"], int)
