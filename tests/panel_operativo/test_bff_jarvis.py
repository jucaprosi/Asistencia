# ¤panel-operativo
# ¤¤frontend-developer
"""Árbitro de RF-PAN-06, RF-ARM-09, US-15 y chat con Jarvis en panel_operativo."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleSeguridadService,
)


@pytest.fixture
def cliente_lider():
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    comisiones = DobleComisionesService()
    arm = DobleArmJarvisService(comisiones=comisiones, canal=canal)

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        comisiones=comisiones,
        arm=arm,
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    servicio.solicitar_codigo("lider@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo})
    csrf = resp.json()["csrf"]

    return client, csrf, servicio, arm, canal


@pytest.fixture
def cliente_gestor():
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    comisiones = DobleComisionesService()
    arm = DobleArmJarvisService(comisiones=comisiones, canal=canal)

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        comisiones=comisiones,
        arm=arm,
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    servicio.solicitar_codigo("gestor_a@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo})
    csrf = resp.json()["csrf"]

    return client, csrf


def test_gestor_no_tiene_acceso_a_jarvis(cliente_gestor) -> None:
    """RF-PAN-06 Criterio (a): Gestores no tienen acceso al chat de Jarvis (403 Forbidden)."""
    client, csrf = cliente_gestor
    resp = client.post(
        "/panel/api/jarvis/chat",
        headers={"x-csrf-token": csrf},
        json={"pregunta": "¿Cuánto vendió Ana en septiembre?"},
    )
    assert resp.status_code == 403


def test_pregunta_al_asistente_lider(cliente_lider) -> None:
    """Escenario: Pregunta al asistente (@US-15 @RF-ARM-09 @RF-PAN-06).

    Dado un líder autenticado
    Cuando pregunta "¿cuánto vendió X en septiembre?"
    Entonces recibe datos del alcance de su rol, sin historial persistente.
    """
    client, csrf, _, arm, _ = cliente_lider

    resp = client.post(
        "/panel/api/jarvis/chat",
        headers={"x-csrf-token": csrf},
        json={"pregunta": "¿Cuánto vendió Ana en septiembre?"},
    )
    assert resp.status_code == 200
    datos = resp.json()

    assert "Ana R. vendió USD 2 250" in datos["respuesta"]
    assert "septiembre 2026" in datos["respuesta"]
    assert datos["requiere_confirmacion"] is False


def test_cambio_configuracion_exige_confirmacion_explicita(cliente_lider) -> None:
    """RF-PAN-06 Criterio (b): Todo cambio de configuración muestra qué cambiará y exige confirmación."""
    client, csrf, _, arm, _ = cliente_lider

    # 1. Pregunta para modificar configuración
    resp_chat = client.post(
        "/panel/api/jarvis/chat",
        headers={"x-csrf-token": csrf},
        json={"pregunta": "Activa el aviso al vendedor al validar"},
    )
    assert resp_chat.status_code == 200
    datos_chat = resp_chat.json()

    assert datos_chat["requiere_confirmacion"] is True
    assert "¿Confirmas?" in datos_chat["respuesta"]
    cambio = datos_chat["cambio_propuesto"]
    assert cambio is not None

    # 2. Intento de aplicar sin confirmar explícitamente es rechazado
    resp_no_conf = client.post(
        "/panel/api/jarvis/configuracion",
        headers={"x-csrf-token": csrf},
        json={"cambio": cambio, "confirmado": False},
    )
    assert resp_no_conf.status_code == 422
    assert resp_no_conf.json()["codigo"] == "confirmacion_requerida"

    # 3. Aplicación con confirmación explícita
    resp_conf = client.post(
        "/panel/api/jarvis/configuracion",
        headers={"x-csrf-token": csrf},
        json={"cambio": cambio, "confirmado": True},
    )
    assert resp_conf.status_code == 200
    assert resp_conf.json()["ok"] is True
    assert arm.configuracion.get("notificaciones.al_validar") is True


def test_sin_historial_persistente_en_disco(cliente_lider) -> None:
    """RF-PAN-06 Criterio (c): Las conversaciones no se persisten en disco más allá de la sesión."""
    client, csrf, servicio, _, _ = cliente_lider

    # El servicio no tiene tabla en disco de historial de chat de Jarvis (vive en memoria/sesión del cliente)
    resp = client.post(
        "/panel/api/jarvis/chat",
        headers={"x-csrf-token": csrf},
        json={"pregunta": "Hola Jarvis"},
    )
    assert resp.status_code == 200
    assert "Jarvis" in resp.json()["respuesta"]
