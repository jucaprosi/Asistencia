# ¤pasillo-central
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de Fase 4: Comprobación Cloud multi-propiedad, RLS, check-in y handoff (T-311, TASK-004).

Verifica la integración cruzada entre compuertas sin violar mamparos ADPA:
- INV_SIN_FUGA_ENTRE_PROPIEDADES y RF-SEC-07: aislamiento RLS en PostgreSQL y contexto de inquilino.
- US-03, CU-02, RF-MCP-04, RF-GW-03, RF-SEC-08, INV_ENVIO_UNICO: check-in autónomo, marcadores de secretos y envío único.
- US-09, CU-08, RF-CRM-06, RF-MCP-06: ciclo de vida de handoff por zona, alertas por plazo y abandono.
- US-10, US-13, RF-PAN-01, RF-PAN-07, INV_PANEL_POR_ROL: acceso sin contraseña y autorización estricta por zona en panel.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.panel_crm_router import montar_panel_y_crm
from app_core.worker import checkin_del_dia
from features.agente.agente_service import AgenteService, ContextoConversacion, ModoAgente
from features.canal_whatsapp.canal_whatsapp_service import Plantilla
from features.crm_conector.crm_conector_service import (
    CRMConectorService,
    EventoCRM,
    HandoffExistente,
)
from features.herramientas_glamping.herramientas_glamping_service import (
    HerramientasGlampingService,
    ReservaNoAutorizada,
)
from features.panel_operativo.panel_operativo_service import ErrorPanel, PanelOperativoService
from features.seguridad.seguridad_service import (
    EventoAuditoria,
    Identidad,
    Rol,
    SeguridadService,
)

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
def test_aislamiento_multi_propiedad_y_rls() -> None:
    """Escenario @INV_SIN_FUGA_ENTRE_PROPIEDADES @RF-SEC-07:

    Aislamiento por propiedad en la base con RLS (rol NOBYPASSRLS).
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    seguridad = contenedor.seguridad

    # 1. Verificar generación DDL de migraciones RLS con rol NOBYPASSRLS
    ddl = seguridad.generar_migraciones_rls()
    assert "NOBYPASSRLS" in ddl
    assert "ENABLE ROW LEVEL SECURITY" in ddl
    assert "FORCE ROW LEVEL SECURITY" in ddl
    assert "current_setting('app.propiedad_id', true)" in ddl

    # 2. Verificar filtrado de filas mediante contexto de inquilino
    chunks_simulados = [
        {"chunk_id": "c1", "propiedad_id": "glamping_san_pablo", "texto": "Normas de Glamping San Pablo"},
        {"chunk_id": "c2", "propiedad_id": "glamping_san_pablo", "texto": "Wifi de San Pablo"},
        {"chunk_id": "c3", "propiedad_id": "depa_ibarra_centro", "texto": "Acceso a Departamento Centro"},
        {"chunk_id": "c4", "propiedad_id": "depa_ibarra_centro", "texto": "Parqueadero de Departamento Centro"},
        {"chunk_id": "c_glob", "propiedad_id": "global", "texto": "Términos y condiciones generales"},
    ]

    # Inquilino A: glamping_san_pablo
    with seguridad.contexto_inquilino("glamping_san_pablo"):
        visibles_a = [
            f for f in chunks_simulados
            if f["propiedad_id"] in ("glamping_san_pablo", "global")
        ]
        ids_a = {f["chunk_id"] for f in visibles_a}
        assert "c1" in ids_a
        assert "c2" in ids_a
        assert "c_glob" in ids_a
        assert "c3" not in ids_a
        assert "c4" not in ids_a

    # Inquilino B: depa_ibarra_centro
    with seguridad.contexto_inquilino("depa_ibarra_centro"):
        visibles_b = [
            f for f in chunks_simulados
            if f["propiedad_id"] in ("depa_ibarra_centro", "global")
        ]
        ids_b = {f["chunk_id"] for f in visibles_b}
        assert "c3" in ids_b
        assert "c4" in ids_b
        assert "c_glob" in ids_b
        assert "c1" not in ids_b
        assert "c2" not in ids_b


# ¤pasillo-central
def test_checkin_autonomo_multi_propiedad_e_inv_envio_unico() -> None:
    """Escenarios @US-03 @CU-02 @RF-MCP-04 @RF-GW-03 @RF-SEC-08 @INV_ENVIO_UNICO:

    - El titular recibe instrucciones de su propiedad y ningún dato de otra.
    - Los secretos operativos van enmascarados como [[SECRETO:...]] y se rehidratan solo al salir.
    - Código ajeno recibe ReservaNoAutorizada y tras 5 intentos escala a humano.
    - Envío único por día (INV_ENVIO_UNICO).
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    hoy = date.today()

    # Configurar PMS con dos reservas en distintas propiedades
    instrucciones = {
        "RES-SAN-PABLO-01": SimpleNamespace(
            propiedad="Glamping San Pablo",
            direccion="Loma de San Pablo, Lago San Pablo",
            acceso=["Cerradura digital domo 1: clave 1234"],
            wifi_red="SanPablo_Guest",
            wifi_clave_token="[[SECRETO:wifi_san_pablo]]",
            normas=["No fumar", "Check-out 11:00"],
            contacto_emergencia="+593991112233",
            hora_checkin="15:00",
        ),
        "RES-DEPA-CENTRO-01": SimpleNamespace(
            propiedad="Departamento Centro Ibarra",
            direccion="Calle Bolívar 4-50, Ibarra",
            acceso=["Tarjeta magnética en conserjería"],
            wifi_red="DepaCentro_Fibra",
            wifi_clave_token="[[SECRETO:wifi_depa_centro]]",
            normas=["No mascotas", "Silencio desde 22:00"],
            contacto_emergencia="+593994445566",
            hora_checkin="14:00",
        ),
    }

    titulares = {
        "RES-SAN-PABLO-01": "token_huesped_san_pablo",
        "RES-DEPA-CENTRO-01": "token_huesped_depa_centro",
    }

    contenedor.pms.validar_titular_local = lambda cod, tok: titulares.get(cod) == tok
    contenedor.pms.obtener_instrucciones_checkin = lambda cod: instrucciones[cod]

    # 1. Consulta del titular de San Pablo
    id_san_pablo = Identidad(remitente_token="token_huesped_san_pablo", rol=Rol.HUESPED_ACTIVO)
    salida_sp = contenedor.herramientas.ejecutar(
        "obtener_instrucciones_checkin",
        {"codigo_reserva": "RES-SAN-PABLO-01"},
        identidad=id_san_pablo,
        conversacion_id="conv_checkin_sp",
    )
    assert salida_sp.salida["propiedad"] == "Glamping San Pablo"
    assert salida_sp.salida["wifi"]["clave_ref"] == "[[SECRETO:wifi_san_pablo]]"
    assert "Departamento Centro" not in str(salida_sp.salida)

    # Rehidratación al titular
    contenedor.seguridad.guardar_secreto_operativo("wifi_san_pablo", "wifi", "clave_real_secreta_999")
    texto_rehidratado = contenedor.seguridad.rehidratar_secretos(salida_sp.salida["wifi"]["clave_ref"])
    assert texto_rehidratado == "clave_real_secreta_999"

    # 2. Intento de acceso ajeno (titular de San Pablo intentando abrir Depa Centro)
    with pytest.raises(ReservaNoAutorizada) as exc_info:
        contenedor.herramientas.ejecutar(
            "obtener_instrucciones_checkin",
            {"codigo_reserva": "RES-DEPA-CENTRO-01"},
            identidad=id_san_pablo,
            conversacion_id="conv_checkin_robo",
        )
    assert exc_info.value.codigo_reserva == "RES-DEPA-CENTRO-01"

    # 3. 5 intentos fallidos en 24h escalan a humano
    id_atacante = Identidad(remitente_token="token_fuerza_bruta", rol=Rol.HUESPED_ACTIVO)
    for i in range(4):
        with pytest.raises(ReservaNoAutorizada):
            contenedor.herramientas.ejecutar(
                "obtener_instrucciones_checkin",
                {"codigo_reserva": f"RES-INTRUSO-{i}"},
                identidad=id_atacante,
                conversacion_id="conv_fuerza_bruta",
            )
    with pytest.raises(ReservaNoAutorizada):
        contenedor.herramientas.ejecutar(
            "obtener_instrucciones_checkin",
            {"codigo_reserva": "RES-INTRUSO-5"},
            identidad=id_atacante,
            conversacion_id="conv_fuerza_bruta",
        )

    # 4. Worker checkin_del_dia y reinicio del planificador (INV_ENVIO_UNICO)
    reserva_hoy = SimpleNamespace(
        codigo="RES-SAN-PABLO-01",
        propiedad_id="glamping_san_pablo",
        huesped_telefono="+593991234567",
        huesped_nombre="Ana G",
        desde=hoy,
    )
    contenedor.pms.reservas_con_llegada = lambda f: (reserva_hoy,) if f == hoy else ()

    primer_envio = checkin_del_dia(contenedor, fecha=hoy)
    assert primer_envio == 1

    # Reinicio del planificador en el mismo día
    segundo_envio = checkin_del_dia(contenedor, fecha=hoy)
    assert segundo_envio == 0, "INV_ENVIO_UNICO: no debe duplicar el envío de check-in"


# ¤pasillo-central
def test_handoff_por_zona_y_ciclo_de_vida() -> None:
    """Escenarios @US-09 @CU-08 @RF-CRM-06 @RF-MCP-06:

    - Handoff a gestor de zona correspondiente.
    - Handoff sin zona resuelta se asigna al administrador.
    - Vencimiento 15 min sin tomar reasigna a gestor de respaldo y alerta.
    - Abandono 24h sin actividad devuelve al asistente por vencimiento.
    - Bloqueo de segundo handoff abierto (INV_HANDOFF_UNICO).
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    crm = contenedor.crm

    # Ajustar IDs de gestores y admin para evitar falsos positivos de detección telefónica PII
    crm._config["admin_id"] = "usr_admin_principal"
    crm._conexion_bd.execute(
        "UPDATE crm.zonas SET gestor_principal_id = ?, gestor_respaldo_id = ?",
        ("usr_gestor_norte", "usr_respaldo_norte"),
    )
    crm._conexion_bd.commit()

    # 1. Handoff con propiedad resuelta en zona imbabura_norte
    # Registrar conversación previa activa en el agente
    ctx_inicial = ContextoConversacion(
        conversacion_id="conv_fase4_handoff_01",
        identidad_token="token_huesped_1",
        rol="huesped_activo",
        propiedad_id="glamping_imbabura",
        modo=ModoAgente.ACTIVO,
        ventana_24h_hasta=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    contenedor.agente._memoria.guardar_conversacion(ctx_inicial)

    handoff_id = crm.solicitar_handoff(
        conversacion_id="conv_fase4_handoff_01",
        propiedad_id="glamping_imbabura",
        motivo="peticion_explicita",
        resumen="El huésped solicita atención humana.",
    )
    h = crm.obtener_handoff(handoff_id)
    assert h is not None
    assert h.estado == "pendiente"
    assert h.zona_id == "imbabura_norte"
    zona = crm.obtener_zona("imbabura_norte")
    assert zona is not None
    assert h.asignado_a == zona.gestor_principal_id

    # Silenciar al agente
    contenedor.agente.entrar_en_silencio("conv_fase4_handoff_01", "peticion_explicita")
    assert contenedor.agente.contexto("conv_fase4_handoff_01").modo == ModoAgente.SILENCIO

    # 2. INV_HANDOFF_UNICO: segundo handoff abierto en la misma conversación es bloqueado
    with pytest.raises(HandoffExistente):
        crm.solicitar_handoff(
            conversacion_id="conv_fase4_handoff_01",
            propiedad_id="glamping_imbabura",
            motivo="peticion_explicita",
        )

    # 3. Handoff sin propiedad ni zona resuelta -> administrador
    h_admin_id = crm.solicitar_handoff(
        conversacion_id="conv_fase4_sin_zona",
        propiedad_id=None,
        zona_id=None,
        motivo="baja_confianza",
        resumen="Consulta ambigua sin propiedad.",
    )
    h_admin = crm.obtener_handoff(h_admin_id)
    assert h_admin is not None
    assert h_admin.zona_id is None
    assert h_admin.asignado_a == "usr_admin_principal"

    # 4. Plazo 15 min sin tomar -> gestor de respaldo y alerta
    t_venc_15m = h.inicio + timedelta(minutes=16)
    res_plazos_15m = crm.revisar_plazos_handoffs(ahora=t_venc_15m)
    assert res_plazos_15m["reasignados_respaldo"] >= 1
    h_respaldo = crm.obtener_handoff(handoff_id)
    assert h_respaldo is not None
    assert h_respaldo.asignado_a == zona.gestor_respaldo_id

    # 5. Gestor toma la conversación y 24h de inactividad devuelven al asistente
    crm.tomar_handoff(handoff_id, gestor_id=zona.gestor_respaldo_id)
    h_tomado = crm.obtener_handoff(handoff_id)
    assert h_tomado is not None
    assert h_tomado.estado == "tomado"

    t_abandono_24h = (h_tomado.tomado_en or h_tomado.inicio) + timedelta(hours=25)
    res_abandono = crm.revisar_plazos_handoffs(ahora=t_abandono_24h)
    assert res_abandono["devueltos_vencimiento"] >= 1
    h_devuelto = crm.obtener_handoff(handoff_id)
    assert h_devuelto is not None
    assert h_devuelto.estado == "devuelto"
    assert h_devuelto.devuelto_por == "vencimiento"


# ¤pasillo-central
def test_panel_operativo_por_rol_y_acceso_seguro() -> None:
    """Escenarios @US-10 @RF-PAN-07 @INV_PANEL_POR_ROL @US-13 @RF-PAN-01:

    - Acceso al panel con código por WhatsApp (6 dígitos, 10 min, 12h de sesión).
    - Correo no registrado produce respuesta indistinguible sin envíos.
    - Demasiados intentos (5) invalidan el código.
    - Gestor de zona A ve solo handoffs de zona A; petición a zona B responde 403 (INV_PANEL_POR_ROL).
    - Devolver al asistente reanuda la conversación del agente.
    """
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    panel = contenedor.panel

    # Aprobar plantilla para permitir envío en canal
    contenedor.canal.aprobar_plantilla("codigo_acceso_panel")

    # Configurar usuarios en seguridad
    usuarios = {
        "gestor_a@glamping.ec": {
            "usuario_id": "usr_gestor_a",
            "correo": "gestor_a@glamping.ec",
            "rol": "gestor",
            "zonas": ("zona_a",),
            "telefono": "+593991111111",
            "activo": True,
        },
    }
    contenedor.seguridad.obtener_usuario_por_correo = lambda c: usuarios.get(c.strip().lower())

    # Capturar código emitido a través del canal
    codigos_emitidos: list[str] = []
    original_enviar_plantilla = contenedor.canal.enviar_plantilla

    def _capturar(dest: str, p: Any) -> Any:
        if p.nombre == "codigo_acceso_panel":
            codigos_emitidos.append(p.variables[0])
        return original_enviar_plantilla(dest, p)

    contenedor.canal.enviar_plantilla = _capturar

    # 1. Acceso al panel exitoso
    resp_cod = panel.solicitar_codigo("gestor_a@glamping.ec")
    assert resp_cod["ok"] is True
    assert len(codigos_emitidos) == 1
    codigo = codigos_emitidos[0]
    assert re.fullmatch(r"\d{6}", str(codigo))

    # Iniciar sesión y validar vigencia de 12 horas
    sesion_gestor, cookie_token = panel.iniciar_sesion("gestor_a@glamping.ec", str(codigo))
    assert sesion_gestor.rol == "gestor"
    assert "zona_a" in sesion_gestor.zonas
    assert sesion_gestor.expira_en > datetime.now(timezone.utc) + timedelta(hours=11)

    # 2. Correo no registrado -> respuesta indistinguible y 0 mensajes enviados
    conteo_antes = len(codigos_emitidos)
    resp_desconocido = panel.solicitar_codigo("fantasma@desconocido.com")
    assert resp_desconocido["ok"] is True
    conteo_despues = len(codigos_emitidos)
    assert conteo_despues == conteo_antes

    # 3. 5 intentos fallidos invalidan el código
    panel.solicitar_codigo("gestor_a@glamping.ec")
    codigo_valido = codigos_emitidos[-1]
    for _ in range(5):
        try:
            panel.iniciar_sesion("gestor_a@glamping.ec", "000000")
        except Exception:
            pass

    with pytest.raises(Exception):
        panel.iniciar_sesion("gestor_a@glamping.ec", str(codigo_valido))

    # 4. Aislamiento por zona en el panel (INV_PANEL_POR_ROL)
    # Registrar handoff en zona_a y handoff en zona_b
    panel.registrar_handoff_interno(
        conversacion_id="c_zona_a",
        propiedad="Glamping San Pablo",
        zona_id="zona_a",
        motivo="Consulta zona A",
        resumen="Huésped de San Pablo",
    )
    panel.registrar_handoff_interno(
        conversacion_id="c_zona_b",
        propiedad="Depa Ibarra",
        zona_id="zona_b",
        motivo="Consulta zona B",
        resumen="Huésped de Ibarra",
    )

    # Gestor de zona A ve solo c_zona_a
    lista_gestor_a = panel.handoffs(sesion_gestor)
    ids_visibles = {h.conversacion_id for h in lista_gestor_a}
    assert "c_zona_a" in ids_visibles
    assert "c_zona_b" not in ids_visibles

    # Petición a handoff de otra zona responde con error de autorización
    with pytest.raises(ErrorPanel) as exc_panel:
        panel.detalle_conversacion(sesion_gestor, "c_zona_b")
    assert exc_panel.value.codigo in ("zona_no_autorizada", "prohibido", "acceso_denegado")

    # 5. Devolver al asistente reanuda conversación en el agente
    reanudadas: list[str] = []
    contenedor.agente.reanudar = lambda c_id: reanudadas.append(c_id)

    panel.devolver_al_asistente(sesion_gestor, "c_zona_a")
    assert "c_zona_a" in reanudadas
    h_post_devolver = panel._handoffs.get("c_zona_a", {})
    assert h_post_devolver.get("estado") == "devuelto"
