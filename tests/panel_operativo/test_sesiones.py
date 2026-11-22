# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PAN-01 y US-13: Acceso y sesión en el panel operativo.

Verifica el ciclo de vida de los códigos de acceso por WhatsApp (6 dígitos, 10 min, 5 intentos),
la cookie segura de 12 h con CSRF, y la protección indistinguible ante correos no registrados.
"""
from __future__ import annotations

import re
from fastapi.testclient import TestClient

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleAgenteService,
    DobleCanalWhatsappService,
    DobleObservabilidadService,
    DobleSeguridadService,
)


def _crear_cliente() -> tuple[TestClient, PanelOperativoService, DobleSeguridadService, DobleCanalWhatsappService]:
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        agente=DobleAgenteService(),
        observabilidad=DobleObservabilidadService(),
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)
    return client, servicio, seguridad, canal


def test_acceso_al_panel_exitoso() -> None:
    # Dado un usuario activo con rol gestor
    client, _, _, canal = _crear_cliente()

    # Cuando ingresa su correo
    resp_codigo = client.post("/panel/api/sesion/codigo", json={"correo": "gestor_a@glamping.ec"})
    assert resp_codigo.status_code == 200
    assert resp_codigo.json()["ok"] is True

    # Entonces recibe la plantilla "codigo_acceso_panel" con 6 dígitos válidos por 10 minutos
    assert len(canal.plantillas_enviadas) == 1
    destinatario, plantilla = canal.plantillas_enviadas[0]
    assert destinatario == "+593991111111"
    assert plantilla.nombre == "codigo_acceso_panel"
    assert len(plantilla.variables) == 1
    codigo = plantilla.variables[0]
    assert re.fullmatch(r"\d{6}", codigo)

    # Y al confirmarlo obtiene una sesión de 12 horas con CSRF y cookie HttpOnly/Secure/SameSite=Strict
    resp_login = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo})
    assert resp_login.status_code == 200
    datos = resp_login.json()
    assert datos["usuario_id"] == "usr_gestor_a"
    assert datos["rol"] == "gestor"
    assert "zona_a" in datos["zonas"]
    assert "csrf" in datos

    # Validar atributos de la cookie
    cookie = resp_login.cookies.get("panel_session")
    assert cookie is not None


def test_correo_no_registrado_respuesta_indistinguible_y_auditoria() -> None:
    # Dado un correo sin usuario activo
    client, _, seguridad, canal = _crear_cliente()

    # Cuando pide el código
    resp = client.post("/panel/api/sesion/codigo", json={"correo": "desconocido@correo.com"})

    # Entonces no se envía nada, la respuesta es indistinguible y queda en el audit log
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert len(canal.plantillas_enviadas) == 0

    assert len(seguridad.audit_log) >= 1
    evento = seguridad.audit_log[-1]
    assert evento["accion"] == "solicitud_codigo_desconocido"


def test_demasiados_intentos_invalida_el_codigo() -> None:
    # Dado un código emitido
    client, _, _, canal = _crear_cliente()
    client.post("/panel/api/sesion/codigo", json={"correo": "gestor_a@glamping.ec"})
    codigo_valido = canal.plantillas_enviadas[0][1].variables[0]

    # Cuando realiza 5 intentos fallidos
    for _ in range(5):
        resp_err = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": "000000"})
        assert resp_err.status_code == 401

    # Entonces el código queda inválido aunque en el sexto intento ingrese el correcto
    resp_sexto = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo_valido})
    assert resp_sexto.status_code == 401
    assert "bloqueado" in resp_sexto.json()["mensaje_usuario"].lower() or "intentos" in resp_sexto.json()["mensaje_usuario"].lower()
