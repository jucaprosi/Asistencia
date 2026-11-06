# ¤panel-operativo
# ¤¤frontend-developer
"""Árbitro E2E de validación de ventas, corrección de campos dudosos y componentes UI (RF-PAN-02, US-06)."""
from __future__ import annotations

import json
from decimal import Decimal
from fastapi.testclient import TestClient
import pytest

from features.arm_jarvis.arm_jarvis_service import EstadoVenta
from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.componentes_internal import (
    ChatJarvis,
    DialogoMotivo,
    HojaCorreccion,
    TarjetaVenta,
)
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleSeguridadService,
)


@pytest.fixture
def entorno_e2e():
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

    # Iniciar sesión de Líder 1
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo1 = canal.plantillas_enviadas[-1][1].variables[0]
    resp1 = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo1})
    csrf1 = resp1.json()["csrf"]

    return client, csrf1, servicio, arm, canal, comisiones


def test_e2e_validar_venta_sin_dudas_un_toque(entorno_e2e) -> None:
    """Flujo E2E: Validar venta sin campos dudosos con un solo toque (US-06)."""
    client, csrf, servicio, arm, canal, _ = entorno_e2e

    # 1. El líder consulta la bandeja de ventas por validar (P-03)
    resp_bandeja = client.get("/panel/api/ventas/por_validar")
    assert resp_bandeja.status_code == 200
    ventas = resp_bandeja.json()
    assert len(ventas) >= 1

    v106 = next(v for v in ventas if v["ticket"] == "V-2026-0106")
    assert v106["campos_dudosos"] == []

    # 2. El líder pulsa directamente 'Validar' (un toque sin corrección)
    headers = {"x-csrf-token": csrf}
    resp_validar = client.post(f"/panel/api/ventas/{v106['venta_id']}/validar", headers=headers)
    assert resp_validar.status_code == 200
    resultado = resp_validar.json()

    assert resultado["ok"] is True
    assert resultado["estado"] == "validada"
    assert resultado["notificacion"] == "notificado"

    # 3. Estado en el ARM actualizado y comisión fijada
    venta_db = arm.ventas[v106["venta_id"]]
    assert venta_db.estado == EstadoVenta.VALIDADA
    assert venta_db.comision_fijada == Decimal("20.00")

    # 4. En la siguiente consulta de por_validar, la venta ya no aparece
    resp_bandeja_act = client.get("/panel/api/ventas/por_validar")
    tickets_act = [v["ticket"] for v in resp_bandeja_act.json()]
    assert "V-2026-0106" not in tickets_act


def test_e2e_correccion_de_campos_dudosos(entorno_e2e) -> None:
    """Flujo E2E: Venta con campos dudosos muestra fragmento original en HojaCorreccion y valida corregida."""
    client, csrf, servicio, arm, _, _ = entorno_e2e

    # 1. Obtener venta con dudas
    resp_bandeja = client.get("/panel/api/ventas/por_validar")
    ventas = resp_bandeja.json()
    v107_datos = next(v for v in ventas if v["ticket"] == "V-2026-0107")
    assert "fecha" in v107_datos["campos_dudosos"]

    # 2. Renderizar componente UI HojaCorreccion y verificar que muestra el fragmento original
    item_ui: dict[str, Any] = {
        "venta_id": v107_datos["venta_id"],
        "ticket": v107_datos["ticket"],
        "vendedor": v107_datos["vendedor"],
        "cliente": v107_datos["cliente"],
        "producto": v107_datos["producto"],
        "monto": v107_datos["monto"],
        "fecha_venta": v107_datos["fecha_venta"],
        "confianza": v107_datos["confianza"],
        "campos_dudosos": v107_datos["campos_dudosos"],
        "texto_original": v107_datos["texto_original"],
        "comision_estimada": v107_datos["comision_estimada"],
        "creada": v107_datos["creada"],
    }
    html_hoja = HojaCorreccion(item_ui)
    assert "Texto original del vendedor" in html_hoja
    assert "vendí 3 noches depa centro a María López" in html_hoja
    assert "corr-cliente-V-2026-0107" in html_hoja

    # 3. Enviar correcciones desde la hoja y validar
    correcciones = {
        "cliente": "María Elena López",
        "monto": "450.00",
        "fecha_venta": "2026-10-15",
    }
    headers = {"x-csrf-token": csrf}
    resp_corr = client.post(
        f"/panel/api/ventas/{v107_datos['venta_id']}/validar",
        headers=headers,
        json={"correcciones": correcciones},
    )
    assert resp_corr.status_code == 200

    # 4. Verificar que se persistieron los campos corregidos
    venta_db = arm.ventas[v107_datos["venta_id"]]
    assert venta_db.estado == EstadoVenta.VALIDADA
    assert venta_db.extraida.cliente_token == "María Elena López"


def test_e2e_conflicto_entre_dos_lideres(entorno_e2e) -> None:
    """Flujo E2E: Conflicto entre dos líderes sobre la misma venta (409 Conflict)."""
    client, csrf1, servicio, arm, canal, _ = entorno_e2e

    # Líder 1 valida V-2026-0106
    resp1 = client.post("/panel/api/ventas/V-2026-0106/validar", headers={"x-csrf-token": csrf1})
    assert resp1.status_code == 200

    # Segundo líder intenta validar la misma venta
    resp2 = client.post("/panel/api/ventas/V-2026-0106/validar", headers={"x-csrf-token": csrf1})
    assert resp2.status_code == 409
    datos_conflicto = resp2.json()

    assert datos_conflicto["codigo"] == "conflicto_estado"
    assert "procesada" in datos_conflicto["mensaje_usuario"].lower()


def test_renderizado_componentes_ui() -> None:
    """Verificación de generación de HTML de TarjetaVenta, DialogoMotivo y ChatJarvis."""
    item: dict[str, Any] = {
        "venta_id": "V-TEST-01",
        "ticket": "V-2026-0999",
        "vendedor": "Ana R.",
        "cliente": "Roberto Dávila",
        "producto": "Domo 1",
        "monto": "150.00",
        "fecha_venta": "2026-10-20",
        "confianza": 0.95,
        "campos_dudosos": [],
        "texto_original": "Domo 150 pagado",
        "comision_estimada": "15.00",
        "creada": "2026-10-20T10:00:00Z",
    }

    # TarjetaVenta
    html_tarjeta = TarjetaVenta(item)
    assert "V-2026-0999" in html_tarjeta
    assert "Roberto Dávila" in html_tarjeta
    assert "USD 150.00" in html_tarjeta
    assert "Validar" in html_tarjeta

    # DialogoMotivo
    html_dialogo = DialogoMotivo("V-TEST-01", "rechazar")
    assert "Rechazar venta" in html_dialogo
    assert "motivo-select-V-TEST-01" in html_dialogo
    assert "Monto incorrecto" in html_dialogo

    # ChatJarvis
    mensajes: list[dict[str, Any]] = [
        {"autor": "usuario", "texto": "¿Cuánto vendió Ana en septiembre?", "hora": "10:30"},
        {"autor": "jarvis", "texto": "Ana vendió USD 2 250.", "hora": "10:31"},
        {
            "autor": "jarvis",
            "texto": "Voy a activar «aviso al validar». ¿Confirmas?",
            "hora": "10:32",
            "requiere_confirmacion": True,
            "cambio_propuesto": {"notificaciones.al_validar": True},
        },
    ]
    html_chat = ChatJarvis(mensajes)
    assert "Ana vendió USD 2 250" in html_chat
    assert "Confirmar" in html_chat
    assert "Cancelar" in html_chat
    assert "form-chat-jarvis" in html_chat
