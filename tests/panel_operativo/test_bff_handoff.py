"""Árbitro de RF-PAN-07, RF-PAN-08, INV_PANEL_POR_ROL e INV_ACCION_IDEMPOTENTE.

Verifica la bandeja de handoffs por zona, aislamiento estricto (403 para otras zonas),
tomar (silencia agente), responder por WhatsApp, devolver al asistente e incidencias con resolución notificada.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleAgenteService,
    DobleCanalWhatsappService,
    DobleObservabilidadService,
    DoblePMSConectorService,
    DobleSeguridadService,
)


def _preparar_entorno() -> tuple[TestClient, PanelOperativoService, DobleAgenteService, DobleCanalWhatsappService, str, str]:
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    agente = DobleAgenteService()
    canal = DobleCanalWhatsappService()
    pms = DoblePMSConectorService()
    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        agente=agente,
        canal=canal,
        pms=pms,
        observabilidad=DobleObservabilidadService(),
    )

    # Registrar handoff de zona A y de zona B
    servicio.registrar_handoff_interno(
        conversacion_id="conv_a1",
        propiedad="Domo Lago",
        zona_id="zona_a",
        motivo="Duda check-in",
        resumen="Huésped pregunta por clave de acceso",
        huesped_nombre="Ana Gómez",
        huesped_telefono="+593991234567",
    )
    servicio.registrar_handoff_interno(
        conversacion_id="conv_b1",
        propiedad="Cabaña Bosque",
        zona_id="zona_b",
        motivo="Incidencia ducha",
        resumen="No sale agua caliente",
        huesped_nombre="Pedro Picapiedra",
        huesped_telefono="+593997654321",
    )

    # Registrar incidencias
    servicio.registrar_incidencia_interna(
        incidencia_id="inc_a1",
        propiedad_id="Domo Lago",
        zona_id="zona_a",
        categoria="Mantenimiento",
        prioridad="alta",
        descripcion="Fuga de gas en calefactor",
        huesped_telefono="+593991234567",
    )
    servicio.registrar_incidencia_interna(
        incidencia_id="inc_b1",
        propiedad_id="Cabaña Bosque",
        zona_id="zona_b",
        categoria="Limpieza",
        prioridad="media",
        descripcion="Toallas adicionales solicitadas",
        huesped_telefono="+593997654321",
    )

    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión como gestor A (zonas: ["zona_a"])
    servicio.solicitar_codigo("gestor_a@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp_login = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo})
    csrf = resp_login.json()["csrf"]
    cookie = resp_login.cookies.get("panel_session")

    return client, servicio, agente, canal, csrf, cookie


def test_bandeja_por_zona_y_aislamiento_403() -> None:
    # Dado un gestor de la zona A
    client, _, _, _, _, _ = _preparar_entorno()

    # Cuando abre la bandeja
    resp = client.get("/panel/api/handoffs")
    assert resp.status_code == 200
    handoffs = resp.json()

    # Entonces ve los handoffs de zona_a y no los de zona_b
    assert len(handoffs) == 1
    assert handoffs[0]["zona_id"] == "zona_a"
    assert handoffs[0]["conversacion_id"] == "conv_a1"

    # Y una petición explícita a otra zona responde 403 Forbidden (INV_PANEL_POR_ROL)
    resp_otra_zona = client.get("/panel/api/handoffs?zona=zona_b")
    assert resp_otra_zona.status_code == 403
    assert "permisos" in resp_otra_zona.json()["detail"]["mensaje_usuario"].lower()

    # Y una petición al detalle de otra zona responde 403
    resp_detalle_prohibido = client.get("/panel/api/handoffs/conv_b1")
    assert resp_detalle_prohibido.status_code == 403


def test_tomar_responder_y_devolver_al_asistente() -> None:
    # Dado un gestor en su zona con handoff activo
    client, servicio, agente, canal, csrf, _ = _preparar_entorno()
    cabeceras = {"X-CSRF-Token": csrf, "Idempotency-Key": "key-tomar-1"}

    # Cuando pulsa Tomar
    resp_tomar = client.post("/panel/api/handoffs/conv_a1/tomar", headers=cabeceras)
    assert resp_tomar.status_code == 200
    # Entonces el agente queda en silencio
    assert agente.silenciadas.get("conv_a1") == "tomado_por_gestor"

    # Cuando responde al huésped
    cabeceras_resp = {"X-CSRF-Token": csrf, "Idempotency-Key": "key-responder-1"}
    resp_msg = client.post(
        "/panel/api/handoffs/conv_a1/responder",
        json={"texto": "Estimada Ana, la clave de acceso es 9876."},
        headers=cabeceras_resp,
    )
    assert resp_msg.status_code == 200
    assert len(canal.enviados) >= 1
    assert "9876" in canal.enviados[-1].texto

    # Cuando pulsa Devolver
    cabeceras_dev = {"X-CSRF-Token": csrf, "Idempotency-Key": "key-devolver-1"}
    resp_dev = client.post("/panel/api/handoffs/conv_a1/devolver", headers=cabeceras_dev)
    assert resp_dev.status_code == 200

    # Entonces el agente se reanuda y el handoff queda devuelto
    assert "conv_a1" in agente.reanudadas
    assert "conv_a1" not in agente.silenciadas
    detalle = servicio.detalle_conversacion(servicio.validar_sesion(client.cookies.get("panel_session")), "conv_a1")
    assert detalle["estado"] == "devuelto"


def test_resolver_incidencia() -> None:
    # Dado una incidencia abierta en la zona del gestor
    client, servicio, _, canal, csrf, _ = _preparar_entorno()
    cabeceras = {"X-CSRF-Token": csrf, "Idempotency-Key": "key-resolver-inc-1"}

    # Cuando la resuelve con nota
    resp = client.post(
        "/panel/api/incidencias/inc_a1/resolver",
        json={"nota": "Se cambió la válvula del calefactor. Operativo."},
        headers=cabeceras,
    )
    assert resp.status_code == 200
    datos = resp.json()
    assert datos["estado"] == "resuelta"

    # Entonces el huésped recibe aviso por WhatsApp y quedan registrados actor y hora
    assert len(canal.enviados) >= 1
    assert "resuelta" in canal.enviados[-1].texto.lower()

    # Intentar resolver incidencia de otra zona responde 403
    resp_b = client.post(
        "/panel/api/incidencias/inc_b1/resolver",
        json={"nota": "Intento en otra zona"},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "key-resolver-inc-2"},
    )
    assert resp_b.status_code == 403


def test_inv_accion_idempotente_reintento_devuelve_resultado_cacheado() -> None:
    client, _, _, _, csrf, _ = _preparar_entorno()
    clave_idemp = "idemp-uuid-fijo-123"
    cabeceras = {"X-CSRF-Token": csrf, "Idempotency-Key": clave_idemp}

    # Primera llamada
    resp1 = client.post("/panel/api/handoffs/conv_a1/tomar", headers=cabeceras)
    assert resp1.status_code == 200

    # Segunda llamada con misma clave: devuelve la respuesta registrada sin efectos adicionales
    resp2 = client.post("/panel/api/handoffs/conv_a1/tomar", headers=cabeceras)
    assert resp2.status_code == 200
    assert resp2.json() == resp1.json()
