# ¤panel-operativo
# ¤¤frontend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PAN-04, RF-PAN-05, RF-ANF-08, US-08, US-14 e INV_PANEL_SIN_LOGICA."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient
import jsonschema
import pytest

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.componentes_internal import GraficoBarras, TablaDensa, TarjetaMetrica
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleAnfitrionesService,
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleSeguridadService,
)

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_ESQUEMA_EXPORTACION = RAIZ / "features" / "comisiones" / "esquema_exportacion.json"


@pytest.fixture
def setup_panel():
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    comisiones = DobleComisionesService()
    arm = DobleArmJarvisService(comisiones=comisiones, canal=canal)
    anfitriones = DobleAnfitrionesService()

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        comisiones=comisiones,
        arm=arm,
        anfitriones=anfitriones,
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    def login(correo: str) -> str:
        servicio.solicitar_codigo(correo)
        codigo = canal.plantillas_enviadas[-1][1].variables[0]
        resp = client.post("/panel/api/sesion", json={"correo": correo, "codigo": codigo})
        assert resp.status_code == 200
        return resp.json()["csrf"]

    return client, servicio, login, comisiones, anfitriones, arm


# RF-PAN-04: Tablero de ventas y comisiones
def test_tablero_aislamiento_rol_y_datos_generales(setup_panel) -> None:
    client, servicio, login, comisiones, _, _ = setup_panel

    # Gestor recibe 403 Forbidden
    csrf_gestor = login("gestor_a@glamping.ec")
    resp_gestor = client.get("/panel/api/comisiones/tablero")
    assert resp_gestor.status_code == 403

    # Líder recibe 200 OK con datos completos
    csrf_lider = login("lider@glamping.ec")
    resp_lider = client.get("/panel/api/comisiones/tablero?periodo=2026-10")
    assert resp_lider.status_code == 200
    datos = resp_lider.json()

    assert datos["periodo_id"] == "2026-10"
    assert "ventas_mes" in datos
    assert "comisiones_validadas" in datos
    assert "comisiones_pendientes" in datos
    assert "ventas_por_vendedor" in datos
    assert "ventas_por_propiedad" in datos
    assert "ventas_por_mes" in datos

    # Validación de montos y totales sin lógica propia en panel
    assert Decimal(datos["ventas_mes"]) == Decimal("850.00")
    assert Decimal(datos["comisiones_validadas"]) == Decimal("65.00")
    assert Decimal(datos["comisiones_pendientes"]) == Decimal("45.00")
    assert len(datos["ventas_por_vendedor"]) == 2
    assert len(datos["ventas_por_propiedad"]) == 2


# RF-PAN-04 Criterio (a): Estado de cuenta por vendedor
def test_estado_cuenta_vendedor_detalle_y_totales(setup_panel) -> None:
    client, servicio, login, comisiones, _, _ = setup_panel

    # Gestor 403
    csrf_gestor = login("gestor_a@glamping.ec")
    assert client.get("/panel/api/comisiones/vendedores/usr_vendedor_juan/estado_cuenta").status_code == 403

    # Líder 200
    csrf_lider = login("lider@glamping.ec")
    resp = client.get("/panel/api/comisiones/vendedores/usr_vendedor_juan/estado_cuenta?periodo=2026-10")
    assert resp.status_code == 200
    ec = resp.json()

    assert ec["vendedor_id"] == "usr_vendedor_juan"
    assert ec["periodo_id"] == "2026-10"
    assert ec["numero_ventas"] == 2
    assert ec["numero_ajustes"] == 1
    assert Decimal(ec["total_ventas"]) == Decimal("650.00")
    assert Decimal(ec["total_comisiones"]) == Decimal("45.00")

    # Verificar que contiene una línea por venta y por ajuste
    tipos = [l["tipo"] for l in ec["lineas"]]
    assert "venta" in tipos
    assert "ajuste" in tipos

    linea_ajuste = next(l for l in ec["lineas"] if l["tipo"] == "ajuste")
    assert linea_ajuste["motivo"] == "Ajuste por anulación parcial"
    assert Decimal(linea_ajuste["monto_comision"]) == Decimal("-10.00")


# RF-PAN-05: Cierre de período y confirmación escrita
def test_cierre_periodo_confirmacion_escrita_e_inmutabilidad(setup_panel) -> None:
    client, servicio, login, comisiones, _, arm = setup_panel
    csrf_lider = login("lider@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf_lider}

    # Resumen previo
    resp_res = client.get("/panel/api/comisiones/periodos/2026-10/resumen_cierre")
    assert resp_res.status_code == 200
    resumen = resp_res.json()
    assert Decimal(resumen["comisiones_validadas"]) == Decimal("65.00")
    assert Decimal(resumen["comisiones_pendientes"]) == Decimal("45.00")
    assert resumen["pendientes_quedaran_fuera"] == 1

    # Confirmación errónea responde 400
    resp_bad = client.post(
        "/panel/api/comisiones/periodos/2026-10/cerrar",
        json={"confirmacion_escrita": "CONFIRMO"},
        headers=cabeceras,
    )
    assert resp_bad.status_code == 400

    # Confirmación correcta ejecuta el cierre
    resp_ok = client.post(
        "/panel/api/comisiones/periodos/2026-10/cerrar",
        json={"confirmacion_escrita": "2026-10"},
        headers=cabeceras,
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["ok"] is True
    assert "cerrado_en" in resp_ok.json()

    # Segundo intento de cierre responde 409 Conflict (período cerrado e inmutable)
    resp_conflicto = client.post(
        "/panel/api/comisiones/periodos/2026-10/cerrar",
        json={"confirmacion_escrita": "2026-10"},
        headers=cabeceras,
    )
    assert resp_conflicto.status_code == 409


# RF-PAN-05 Criterio (a): Acciones de edición reciben 409 tras el cierre del período
def test_acciones_de_edicion_reciben_409_tras_cierre(setup_panel) -> None:
    client, servicio, login, comisiones, _, arm = setup_panel
    csrf_lider = login("lider@glamping.ec")
    cabeceras_lider = {"X-CSRF-Token": csrf_lider}

    # Cerrar período 2026-10
    resp_cierre = client.post(
        "/panel/api/comisiones/periodos/2026-10/cerrar",
        json={"confirmacion_escrita": "2026-10"},
        headers=cabeceras_lider,
    )
    assert resp_cierre.status_code == 200

    # Intentar validar una venta de ese período responde 409
    resp_val = client.post(
        "/panel/api/ventas/V-2026-0107/validar",
        json={},
        headers=cabeceras_lider,
    )
    assert resp_val.status_code == 409
    assert resp_val.json()["codigo"] == "periodo_cerrado"

    # Intentar rechazar una venta de ese período responde 409
    resp_rech = client.post(
        "/panel/api/ventas/V-2026-0107/rechazar",
        json={"motivo": "Rechazo tardío"},
        headers=cabeceras_lider,
    )
    assert resp_rech.status_code == 409
    assert resp_rech.json()["codigo"] == "periodo_cerrado"

    # Intentar anular con admin responde 409
    csrf_admin = login("admin@glamping.ec")
    cabeceras_admin = {"X-CSRF-Token": csrf_admin}
    resp_anul = client.post(
        "/panel/api/ventas/V-2026-0001/anular",
        json={"motivo": "Anulación extemporánea"},
        headers=cabeceras_admin,
    )
    assert resp_anul.status_code == 409
    assert resp_anul.json()["codigo"] == "periodo_cerrado"


# RF-PAN-05 Criterio (b): Exportación CSV y validación JSON contra esquema_exportacion.json
def test_exportacion_csv_y_json_valida_contra_esquema(setup_panel) -> None:
    client, servicio, login, comisiones, _, _ = setup_panel
    csrf_lider = login("lider@glamping.ec")

    # Exportación CSV
    resp_csv = client.get("/panel/api/comisiones/periodos/2026-10/exportar?formato=csv")
    assert resp_csv.status_code == 200
    assert resp_csv.headers["content-type"].startswith("text/csv")
    csv_lineas = resp_csv.text.strip().splitlines()
    assert len(csv_lineas) == 5  # 1 cabecera + 4 registros (3 fijadas + 1 ajuste)
    assert "comision_id,venta_id,vendedor_id" in csv_lineas[0]

    # Exportación JSON
    resp_json = client.get("/panel/api/comisiones/periodos/2026-10/exportar?formato=json")
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"].startswith("application/json")
    datos_json = resp_json.json()

    # Validar contra esquema_exportacion.json
    assert RUTA_ESQUEMA_EXPORTACION.is_file(), f"Falta {RUTA_ESQUEMA_EXPORTACION}"
    esquema = json.loads(RUTA_ESQUEMA_EXPORTACION.read_text(encoding="utf-8"))
    jsonschema.validate(instance=datos_json, schema=esquema)

    assert datos_json["periodo_id"] == "2026-10"
    assert datos_json["totales"]["total_ventas"] == "850.00"
    assert datos_json["totales"]["total_comisiones"] == "65.00"
    assert datos_json["totales"]["numero_lineas"] == 4


# RF-PAN-04 Criterio (b): Gráficos tienen tabla alternativa accesible
def test_componente_grafico_barras_incluye_tabla_alternativa_accesible() -> None:
    datos = [
        {"mes": "2026-08", "total_ventas": "10200.00"},
        {"mes": "2026-09", "total_ventas": "11500.00"},
        {"mes": "2026-10", "total_ventas": "850.00"},
    ]
    html_grafico = GraficoBarras("Ventas por mes", datos, eje_x="mes", eje_y="total_ventas", tabla_accesible=True)

    assert '<div class="grafico-barras-tarjeta tarjeta">' in html_grafico
    assert '<table class="tabla-densa tabla-accesible"' in html_grafico
    assert "Ver datos como tabla accesible" in html_grafico
    assert "2026-10" in html_grafico
    assert "850.00" in html_grafico


# RF-ANF-08: Cobro de anfitriones, registro de pago y pausa por vencimiento
def test_cobro_anfitriones_pago_y_pausa_vencidos(setup_panel) -> None:
    client, servicio, login, _, anfitriones, _ = setup_panel
    csrf_admin = login("admin@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf_admin}

    # Listar estados de cuenta de anfitriones
    resp_ecs = client.get("/panel/api/admin/anfitriones/estados_cuenta")
    assert resp_ecs.status_code == 200
    ecs = resp_ecs.json()
    assert len(ecs) >= 2

    # Registrar pago
    resp_pago = client.post(
        "/panel/api/admin/anfitriones/estados_cuenta/ec_octubre/pago",
        headers=cabeceras,
    )
    assert resp_pago.status_code == 200
    assert resp_pago.json()["estado"] == "pagado"
    assert "fecha_pago" in resp_pago.json()
    assert resp_pago.json()["actor_id"] == "usr_admin"

    # Pausar vencidos (> 15 días)
    resp_pausa = client.post(
        "/panel/api/admin/anfitriones/pausar_vencidos",
        headers=cabeceras,
    )
    assert resp_pausa.status_code == 200
    assert "pausados" in resp_pausa.json()
