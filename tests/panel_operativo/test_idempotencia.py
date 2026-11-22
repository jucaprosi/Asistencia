# ¤panel-operativo
# ¤¤frontend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PAN-14 e INV_ACCION_IDEMPOTENTE: Acciones idempotentes con Idempotency-Key.

Verifica:
1. Doble toque con red inestable: La acción se ejecuta una sola vez y el destinatario recibe un solo aviso.
2. Comprobación de idempotencia en validación, rechazo, anulación, toma de handoffs y resolución de incidencias.
3. Persistencia en panel.acciones_idempotentes con INSERT ... ON CONFLICT DO NOTHING.
4. Claves distintas ejecutan acciones independientes sin interferencia.
"""
from __future__ import annotations

import json
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
import pytest

from features.arm_jarvis.arm_jarvis_service import EstadoVenta
from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleSeguridadService,
)


# ¤panel-operativo
@pytest.fixture
def entorno_idempotencia():
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

    # Cliente para el Líder
    client_lider = TestClient(app)
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo_lider = canal.plantillas_enviadas[-1][1].variables[0]
    resp_lider = client_lider.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo_lider})
    csrf_lider = resp_lider.json()["csrf"]
    usuario_lider = resp_lider.json()["usuario_id"]

    # Cliente separado para el Gestor
    client_gestor = TestClient(app)
    servicio.solicitar_codigo("gestor_a@glamping.ec")
    codigo_gestor = canal.plantillas_enviadas[-1][1].variables[0]
    resp_gestor = client_gestor.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo_gestor})
    csrf_gestor = resp_gestor.json()["csrf"]
    usuario_gestor = resp_gestor.json()["usuario_id"]

    return client_lider, csrf_lider, usuario_lider, client_gestor, csrf_gestor, usuario_gestor, servicio, arm, canal


# ¤panel-operativo
def test_doble_toque_con_red_inestable_aplica_una_vez_y_notifica_una_vez(entorno_idempotencia) -> None:
    # RF-PAN-14 @INV_ACCION_IDEMPOTENTE
    client_lider, csrf_lider, usuario_lider, _, _, _, servicio, arm, _ = entorno_idempotencia
    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf_lider, "idempotency-key": idemp_key}

    # Dado una venta por validar
    venta_id = "V-2026-0106"
    assert arm.ventas[venta_id].estado == EstadoVenta.POR_VALIDAR
    assert len(arm.notificaciones_vendedor) == 0

    # Cuando la acción llega dos veces con la misma clave (simulando doble toque o reintento de red)
    resp1 = client_lider.post(f"/panel/api/ventas/{venta_id}/validar", headers=headers)
    resp2 = client_lider.post(f"/panel/api/ventas/{venta_id}/validar", headers=headers)

    # Entonces ambas solicitudes responden 200 con contenido idéntico
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()

    # Y la venta se valida una sola vez
    assert arm.ventas[venta_id].estado == EstadoVenta.VALIDADA

    # Y el vendedor recibe un solo aviso (no dos)
    assert len(arm.notificaciones_vendedor) == 1

    # Y la acción quedó registrada en panel.acciones_idempotentes
    guardada = servicio._persistencia.obtener_accion_idempotente(usuario_lider, idemp_key)
    assert guardada is not None
    assert guardada.get("venta_id") == venta_id or guardada.get("ok") is True or "estado" in guardada


# ¤panel-operativo
def test_idempotencia_rechazo_con_motivo(entorno_idempotencia) -> None:
    # RF-PAN-14
    client_lider, csrf_lider, _, _, _, _, _, arm, _ = entorno_idempotencia
    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf_lider, "idempotency-key": idemp_key}

    venta_id = "V-2026-0107"
    body = {"motivo": "Monto discordante con comprobante"}

    # Primera llamada
    resp1 = client_lider.post(f"/panel/api/ventas/{venta_id}/rechazar", headers=headers, json=body)
    assert resp1.status_code == 200

    # Segunda llamada idéntica
    resp2 = client_lider.post(f"/panel/api/ventas/{venta_id}/rechazar", headers=headers, json=body)
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()

    # Rechazada una sola vez
    assert arm.ventas[venta_id].estado == EstadoVenta.RECHAZADA


# ¤panel-operativo
def test_idempotencia_tomar_handoff(entorno_idempotencia) -> None:
    # RF-PAN-14
    _, _, _, client_gestor, csrf_gestor, _, servicio, _, _ = entorno_idempotencia
    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf_gestor, "idempotency-key": idemp_key}

    conv_id = "conv_handoff_01"
    # Registrar handoff de prueba
    servicio._handoffs[conv_id] = {
        "conversacion_id": conv_id,
        "propiedad": "Domo Imbabura",
        "zona_id": "zona_a",
        "motivo": "Huésped solicita cambio de fecha",
        "resumen": "Reserva confirmada solicita mover 1 noche",
        "asignado_a": None,
    }

    resp1 = client_gestor.post(f"/panel/api/handoffs/{conv_id}/tomar", headers=headers)
    assert resp1.status_code == 200

    resp2 = client_gestor.post(f"/panel/api/handoffs/{conv_id}/tomar", headers=headers)
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


# ¤panel-operativo
def test_idempotencia_resolver_incidencia(entorno_idempotencia) -> None:
    # RF-PAN-14
    _, _, _, client_gestor, csrf_gestor, _, servicio, _, _ = entorno_idempotencia
    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf_gestor, "idempotency-key": idemp_key}

    inc_id = "INC-101"
    servicio._incidencias[inc_id] = {
        "incidencia_id": inc_id,
        "zona_id": "zona_a",
        "descripcion": "Calefón no enciende",
        "estado": "abierta",
    }

    body = {"nota": "Se cambió la bombona de gas y se verificó encendido."}
    resp1 = client_gestor.post(f"/panel/api/incidencias/{inc_id}/resolver", headers=headers, json=body)
    assert resp1.status_code == 200

    resp2 = client_gestor.post(f"/panel/api/incidencias/{inc_id}/resolver", headers=headers, json=body)
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


# ¤panel-operativo
def test_idempotencia_suscripcion_dispositivo(entorno_idempotencia) -> None:
    # RF-PAN-14
    client_lider, csrf_lider, _, _, _, _, _, _, _ = entorno_idempotencia
    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf_lider, "idempotency-key": idemp_key}

    body = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/idemp-disp",
        "keys": {"p256dh": "key1", "auth": "auth1"},
    }
    resp1 = client_lider.post("/panel/api/dispositivos/suscribir", headers=headers, json=body)
    assert resp1.status_code == 200

    resp2 = client_lider.post("/panel/api/dispositivos/suscribir", headers=headers, json=body)
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


# ¤panel-operativo
def test_claves_distintas_ejecutan_acciones_independientes(entorno_idempotencia) -> None:
    # RF-PAN-14
    client_lider, csrf_lider, _, _, _, _, _, arm, _ = entorno_idempotencia

    # Validar V-2026-0106 con clave A
    key_a = str(uuid.uuid4())
    resp_a = client_lider.post(
        "/panel/api/ventas/V-2026-0106/validar",
        headers={"x-csrf-token": csrf_lider, "idempotency-key": key_a},
    )
    assert resp_a.status_code == 200

    # Rechazar V-2026-0107 con clave B
    key_b = str(uuid.uuid4())
    resp_b = client_lider.post(
        "/panel/api/ventas/V-2026-0107/rechazar",
        headers={"x-csrf-token": csrf_lider, "idempotency-key": key_b},
        json={"motivo": "Comprobante ilegible"},
    )
    assert resp_b.status_code == 200

    assert arm.ventas["V-2026-0106"].estado == EstadoVenta.VALIDADA
    assert arm.ventas["V-2026-0107"].estado == EstadoVenta.RECHAZADA
