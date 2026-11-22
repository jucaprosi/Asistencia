# ¤panel-operativo
# ¤¤frontend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PAN-02, RF-PAN-03, US-06, CU-05 e invariantes de ventas en panel_operativo."""
from __future__ import annotations

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

    # Iniciar sesión como líder
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo})
    csrf = resp.json()["csrf"]

    return client, csrf, servicio, arm, canal, comisiones


@pytest.fixture
def cliente_admin():
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

    # Iniciar sesión como administrador
    servicio.solicitar_codigo("admin@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": "admin@glamping.ec", "codigo": codigo})
    csrf = resp.json()["csrf"]

    return client, csrf, servicio, arm, canal, comisiones


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

    # Iniciar sesión como gestor
    servicio.solicitar_codigo("gestor_a@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo})
    csrf = resp.json()["csrf"]

    return client, csrf


def test_aislamiento_rol_gestor_no_puede_acceder_a_ventas(cliente_gestor) -> None:
    """INV_PANEL_POR_ROL: Gestores no tienen acceso a ventas (403 Forbidden)."""
    client, csrf = cliente_gestor
    resp = client.get("/panel/api/ventas/por_validar")
    assert resp.status_code == 403


def test_listar_ventas_por_validar_lider(cliente_lider) -> None:
    """RF-PAN-02: Lista de ventas por validar con campos extraídos, confianza y texto original."""
    client, csrf, _, arm, _, _ = cliente_lider

    resp = client.get("/panel/api/ventas/por_validar")
    assert resp.status_code == 200
    ventas = resp.json()

    assert len(ventas) >= 2
    tickets = [v["ticket"] for v in ventas]
    assert "V-2026-0106" in tickets
    assert "V-2026-0107" in tickets

    # Verificar estructura completa de la vista
    v106 = next(v for v in ventas if v["ticket"] == "V-2026-0106")
    assert v106["cliente"] == "Carlos Soto"
    assert v106["confianza"] == 0.98
    assert v106["campos_dudosos"] == []
    assert "reserva domo 200 usd" in v106["texto_original"]


def test_validar_venta_sin_dudas_un_toque(cliente_lider) -> None:
    """Escenario: Validar una venta (@US-06 @CU-05 @RF-ARM-03 @RF-PAN-02).

    Dado una venta "por_validar" sin campos dudosos
    Cuando el líder la valida con una acción
    Entonces pasa a "validada", la comisión se fija y el vendedor recibe la notificación privada
    Y la publicación al CRM se encola firmada e idempotente.
    """
    client, csrf, _, arm, canal, comisiones = cliente_lider

    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf, "idempotency-key": idemp_key}

    resp = client.post("/panel/api/ventas/V-2026-0106/validar", headers=headers)
    assert resp.status_code == 200
    datos = resp.json()

    assert datos["ok"] is True
    assert datos["estado"] == "validada"
    assert datos["notificacion"] == "notificado"
    assert datos["publicacion"] == "encolada"

    # Verificación en el estado del modelo
    venta = arm.ventas["V-2026-0106"]
    assert venta.estado == EstadoVenta.VALIDADA
    assert venta.comision_fijada == Decimal("20.00")

    # Verificación de notificación privada al vendedor
    assert len(arm.notificaciones_vendedor) == 1
    assert arm.notificaciones_vendedor[0]["ticket"] == "V-2026-0106"

    # Verificación de publicación encolada en CRM
    assert len(arm.publicaciones_crm) == 1
    assert arm.publicaciones_crm[0]["ticket"] == "V-2026-0106"
    assert arm.publicaciones_crm[0]["estado"] == "encolada"


def test_validar_venta_con_correcciones(cliente_lider) -> None:
    """RF-PAN-02: Validación aplicando correcciones a campos dudosos."""
    client, csrf, _, arm, _, _ = cliente_lider

    headers = {"x-csrf-token": csrf}
    correcciones = {
        "monto": "480.00",
        "producto": "Depa Centro Premium",
    }
    resp = client.post(
        "/panel/api/ventas/V-2026-0107/validar",
        headers=headers,
        json={"correcciones": correcciones},
    )
    assert resp.status_code == 200

    venta = arm.ventas["V-2026-0107"]
    assert venta.estado == EstadoVenta.VALIDADA
    assert venta.extraida.monto == Decimal("480.00")
    assert venta.extraida.producto == "Depa Centro Premium"


def test_rechazar_venta_con_motivo_obligatorio(cliente_lider) -> None:
    """Escenario: Rechazar una venta (@US-06 @RF-ARM-03 @RF-ARM-06).

    Dado una venta "por_validar"
    Cuando el líder la rechaza con motivo
    Entonces pasa a "rechazada", no genera comisión y el vendedor recibe el motivo
    Y fuera de ventana se usa la plantilla "venta_rechazada".
    """
    client, csrf, _, arm, canal, _ = cliente_lider

    canal.en_ventana = False  # Simular fuera de ventana de 24h
    headers = {"x-csrf-token": csrf}
    motivo = "Comprobante ilegible y fecha fuera de rango"

    resp = client.post(
        "/panel/api/ventas/V-2026-0107/rechazar",
        headers=headers,
        json={"motivo": motivo},
    )
    assert resp.status_code == 200
    datos = resp.json()

    assert datos["ok"] is True
    assert datos["estado"] == "rechazada"

    venta = arm.ventas["V-2026-0107"]
    assert venta.estado == EstadoVenta.RECHAZADA
    assert venta.comision_fijada == Decimal("0")

    # Vendedor recibe el motivo
    assert len(arm.notificaciones_vendedor) == 1
    assert arm.notificaciones_vendedor[0]["motivo"] == motivo

    # Fuera de ventana se usa la plantilla venta_rechazada
    assert len(canal.plantillas_enviadas) >= 1
    dest, plantilla = canal.plantillas_enviadas[-1]
    assert plantilla.nombre == "venta_rechazada"
    assert motivo in plantilla.variables


def test_rechazar_venta_sin_motivo_falla(cliente_lider) -> None:
    """RF-PAN-02: Rechazo sin motivo es rechazado con 400 Bad Request."""
    client, csrf, _, _, _, _ = cliente_lider
    headers = {"x-csrf-token": csrf}

    resp = client.post("/panel/api/ventas/V-2026-0107/rechazar", headers=headers, json={"motivo": ""})
    assert resp.status_code == 400
    assert "motivo" in resp.json()["mensaje_usuario"].lower()


def test_conflicto_entre_dos_usuarios(cliente_lider) -> None:
    """Escenario: Conflicto entre dos usuarios (@US-06 @RF-PAN-02).

    Dado dos líderes sobre la misma venta
    Cuando el segundo intenta validar
    Entonces recibe conflicto (409) y la tarjeta se recarga sin doble transición.
    """
    client, csrf, _, arm, _, _ = cliente_lider
    headers = {"x-csrf-token": csrf}

    # Primer líder valida exitosamente
    resp1 = client.post("/panel/api/ventas/V-2026-0106/validar", headers=headers)
    assert resp1.status_code == 200

    # Segundo líder intenta validar la misma venta que ya no está por_validar
    resp2 = client.post("/panel/api/ventas/V-2026-0106/validar", headers=headers)
    assert resp2.status_code == 409
    datos = resp2.json()
    assert datos["codigo"] == "conflicto_estado"
    assert "procesada" in datos["mensaje_usuario"].lower()


def test_venta_validada_no_se_edita(cliente_lider) -> None:
    """Escenario: Una venta validada no se edita (@US-06 @RF-ARM-03).

    Dado una venta "validada"
    Cuando alguien intenta editar el monto
    Entonces el sistema lo impide y ofrece anulación con motivo al administrador.
    """
    client, csrf, _, arm, _, _ = cliente_lider
    headers = {"x-csrf-token": csrf}

    # Intentar validar/editar la venta validada V-2026-0001
    resp = client.post(
        "/panel/api/ventas/V-2026-0001/validar",
        headers=headers,
        json={"correcciones": {"monto": "500.00"}},
    )
    assert resp.status_code == 409
    assert resp.json()["codigo"] == "conflicto_estado"


def test_sin_regla_vigente_falla_y_permanece_por_validar(cliente_lider) -> None:
    """Escenario: Sin regla vigente (@US-06 @RF-COM-01).

    Dado una venta sin regla de comisión aplicable
    Cuando el líder intenta validar
    Entonces recibe SinReglaVigente y la venta sigue "por_validar".
    """
    client, csrf, _, arm, _, _ = cliente_lider
    headers = {"x-csrf-token": csrf}

    arm.sin_regla.add("V-2026-0106")

    resp = client.post("/panel/api/ventas/V-2026-0106/validar", headers=headers)
    assert resp.status_code == 422
    assert resp.json()["codigo"] == "sin_regla_vigente"

    # La venta permanece en POR_VALIDAR
    assert arm.ventas["V-2026-0106"].estado == EstadoVenta.POR_VALIDAR


def test_detalle_venta_y_linea_tiempo(cliente_lider) -> None:
    """Escenario: Detalle de venta (@RF-PAN-03).

    Dado una venta con transiciones
    Cuando el líder abre el detalle
    Entonces la línea de tiempo coincide con arm_jarvis.detalle.
    """
    client, csrf, _, arm, _, _ = cliente_lider

    resp = client.get("/panel/api/ventas/V-2026-0001")
    assert resp.status_code == 200
    datos = resp.json()

    assert datos["ticket"] == "V-2026-0001"
    assert datos["estado"] == "validada"
    assert datos["cliente"] == "Pedro Gómez"
    assert "linea_tiempo" in datos
    assert len(datos["linea_tiempo"]) >= 1
    assert datos["linea_tiempo"][0]["actor"] == "sistema"


def test_anular_venta_publicada_solo_administrador(cliente_lider, cliente_admin) -> None:
    """Escenario: Anular una venta publicada (@US-06 @RF-COM-04 @RF-CRM-03).

    Dado una venta "publicada" con comisión en un período cerrado
    Cuando el administrador la anula con motivo
    Entonces pasa a "anulada" y se crea un ajuste negativo en el período abierto
    Y se publica el evento "venta_anulada" al CRM.
    """
    client_lider, csrf_lider, _, _, _, _ = cliente_lider
    client_admin, csrf_admin, _, arm, _, comisiones = cliente_admin

    # 1. Un líder intenta anular -> 403 Forbidden
    resp_lider = client_lider.post(
        "/panel/api/ventas/V-2026-0002/anular",
        headers={"x-csrf-token": csrf_lider},
        json={"motivo": "Cancelación por fuerza mayor"},
    )
    assert resp_lider.status_code == 403

    # 2. El administrador la anula con motivo
    resp_admin = client_admin.post(
        "/panel/api/ventas/V-2026-0002/anular",
        headers={"x-csrf-token": csrf_admin},
        json={"motivo": "Cancelación por fuerza mayor"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["estado"] == "anulada"

    venta = arm.ventas["V-2026-0002"]
    assert venta.estado == EstadoVenta.ANULADA

    # Ajuste negativo en comisiones
    assert len(comisiones.ajustes) == 1
    assert comisiones.ajustes[0]["nuevo_monto"] == Decimal("-30.00")

    # Evento venta_anulada publicado al CRM
    anulaciones_crm = [p for p in arm.publicaciones_crm if p.get("evento") == "venta_anulada"]
    assert len(anulaciones_crm) == 1
    assert anulaciones_crm[0]["venta_id"] == "V-2026-0002"


def test_reintentar_publicacion_crm(cliente_lider) -> None:
    """Escenario: El CRM no acepta la venta (@US-06 @RF-CRM-04 @INV_VENTA_NO_SE_PIERDE).

    Dado una publicación que falla (venta no_publicada)
    El panel ofrece reintentar
    Y un reintento exitoso la pasa a "publicada".
    """
    client, csrf, _, arm, _, _ = cliente_lider
    headers = {"x-csrf-token": csrf}

    assert arm.ventas["V-2026-0003"].estado == EstadoVenta.NO_PUBLICADA

    resp = client.post("/panel/api/ventas/V-2026-0003/reintentar_publicacion", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["estado"] == "publicada"

    assert arm.ventas["V-2026-0003"].estado == EstadoVenta.PUBLICADA


def test_idempotencia_en_validacion_de_venta(cliente_lider) -> None:
    """INV_ACCION_IDEMPOTENTE: Mismo Idempotency-Key devuelve respuesta sin duplicar."""
    client, csrf, _, arm, _, _ = cliente_lider
    idemp_key = str(uuid.uuid4())
    headers = {"x-csrf-token": csrf, "idempotency-key": idemp_key}

    # Primera validación
    resp1 = client.post("/panel/api/ventas/V-2026-0106/validar", headers=headers)
    assert resp1.status_code == 200

    # Segunda validación con la misma clave idempotente
    resp2 = client.post("/panel/api/ventas/V-2026-0106/validar", headers=headers)
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()

    # No se duplicaron transiciones ni notificaciones
    assert len(arm.notificaciones_vendedor) == 1
