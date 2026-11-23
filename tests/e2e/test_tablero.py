# ¤panel-operativo
# ¤¤frontend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro E2E de tablero de comisiones, estado de cuenta y exportación (RF-PAN-04, US-08, CU-07, RF-ARM-08)."""
from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from fastapi.testclient import TestClient
import pytest

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.componentes_internal import (
    GraficoBarras,
    TablaDensa,
    TarjetaMetrica,
)
from features.panel_operativo.panel_operativo_service import (
    PanelOperativoService,
    cargar_config,
    comprobar_interfaz_purificada,
)
from tests.panel_operativo.dobles import (
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleSeguridadService,
)


@pytest.fixture
def entorno_tablero():
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

    # Iniciar sesión de Líder
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo})
    assert resp.status_code == 200
    csrf = resp.json()["csrf"]

    return client, csrf, servicio, comisiones, arm


def test_e2e_tablero_que_cuadra_con_exportacion_csv(entorno_tablero) -> None:
    """Escenario: Tablero que cuadra (@US-08 @CU-07 @RF-ARM-08 @RF-PAN-04).

    Dado ventas validadas en el mes
    Cuando el líder abre el tablero
    Entonces ve ventas por mes, vendedor y propiedad y comisiones validadas y pendientes
    Y los totales coinciden al centavo con la exportación CSV
    """
    client, csrf, servicio, comisiones, _ = entorno_tablero

    # 1. El líder abre el tablero para octubre 2026 (P-05)
    resp_tablero = client.get("/panel/api/comisiones/tablero?periodo=2026-10")
    assert resp_tablero.status_code == 200
    tablero = resp_tablero.json()

    # Comprobar desglose de ventas por mes, por vendedor y por propiedad
    assert tablero["periodo_id"] == "2026-10"
    assert len(tablero["ventas_por_mes"]) >= 1
    assert len(tablero["ventas_por_vendedor"]) >= 2
    assert len(tablero["ventas_por_propiedad"]) >= 2

    ventas_tablero = Decimal(tablero["ventas_mes"])
    comisiones_validadas_tablero = Decimal(tablero["comisiones_validadas"])
    comisiones_pendientes_tablero = Decimal(tablero["comisiones_pendientes"])

    assert ventas_tablero == Decimal("850.00")
    assert comisiones_validadas_tablero == Decimal("65.00")
    assert comisiones_pendientes_tablero == Decimal("45.00")

    # 2. Descarga la exportación CSV del mismo período
    resp_csv = client.get("/panel/api/comisiones/periodos/2026-10/exportar?formato=csv")
    assert resp_csv.status_code == 200

    csv_reader = csv.DictReader(io.StringIO(resp_csv.text))
    lineas_csv = list(csv_reader)

    # 3. Y los totales coinciden al centavo con la exportación CSV
    total_ventas_csv = sum((Decimal(l["monto_venta"]) for l in lineas_csv), Decimal("0.00"))
    total_comisiones_csv = sum((Decimal(l["monto_comision"]) for l in lineas_csv), Decimal("0.00"))

    assert total_ventas_csv == ventas_tablero
    assert total_comisiones_csv == comisiones_validadas_tablero


def test_e2e_estado_cuenta_por_vendedor_con_ventas_y_ajuste(entorno_tablero) -> None:
    """Escenario: Estado de cuenta por vendedor (@RF-PAN-04).

    Dado un vendedor con ventas y un ajuste en el período
    Cuando el líder abre su estado de cuenta
    Entonces hay una línea por venta y por ajuste
    Y el total coincide al centavo con la exportación
    """
    client, csrf, servicio, comisiones, _ = entorno_tablero

    # 1. El líder abre el estado de cuenta de Juan (P-05b)
    resp_ec = client.get("/panel/api/comisiones/vendedores/usr_vendedor_juan/estado_cuenta?periodo=2026-10")
    assert resp_ec.status_code == 200
    ec = resp_ec.json()

    # Hay una línea por venta y por ajuste
    lineas = ec["lineas"]
    ventas_lineas = [l for l in lineas if l["tipo"] == "venta"]
    ajustes_lineas = [l for l in lineas if l["tipo"] == "ajuste"]

    assert len(ventas_lineas) == 2
    assert len(ajustes_lineas) == 1

    # Verificar datos del ajuste
    ajuste = ajustes_lineas[0]
    assert ajuste["motivo"] == "Ajuste por anulación parcial"
    assert Decimal(ajuste["monto_comision"]) == Decimal("-10.00")

    # Verificar que los totales del estado de cuenta cuadran exactamente
    suma_ventas = sum(Decimal(l["monto_venta"]) for l in lineas)
    suma_comisiones = sum(Decimal(l["monto_comision"]) for l in lineas)

    assert suma_ventas == Decimal(ec["total_ventas"])
    assert suma_comisiones == Decimal(ec["total_comisiones"])
    assert suma_comisiones == Decimal("45.00")

    # Comprobar contra la exportación CSV filtrada por ese vendedor
    resp_csv = client.get("/panel/api/comisiones/periodos/2026-10/exportar?formato=csv")
    csv_reader = csv.DictReader(io.StringIO(resp_csv.text))
    lineas_vendedor_csv = [l for l in csv_reader if l["vendedor_id"] == "usr_vendedor_juan"]

    total_comisiones_vendedor_csv = sum(Decimal(l["monto_comision"]) for l in lineas_vendedor_csv)
    assert total_comisiones_vendedor_csv == suma_comisiones


def test_e2e_render_componentes_tablero_accesibilidad_y_pureza() -> None:
    """Verifica renderizado semántico de TarjetaMetrica, GraficoBarras y TablaDensa."""
    # TarjetaMetrica
    html_tarjeta = TarjetaMetrica("Ventas del Mes", "USD 850.00", "3 ventas validadas", variante="exito")
    assert "Ventas del Mes" in html_tarjeta
    assert "USD 850.00" in html_tarjeta
    assert "variante-exito" in html_tarjeta

    # GraficoBarras con tabla alternativa accesible
    datos_barras = [
        {"mes": "2026-08", "total_ventas": "10200.00"},
        {"mes": "2026-09", "total_ventas": "11500.00"},
        {"mes": "2026-10", "total_ventas": "850.00"},
    ]
    html_grafico = GraficoBarras("Histórico Ventas", datos_barras, eje_x="mes", eje_y="total_ventas")
    assert 'role="img"' in html_grafico
    assert '<table class="tabla-densa tabla-accesible"' in html_grafico
    assert "Ver datos como tabla accesible" in html_grafico

    # TablaDensa
    columnas = [
        {"clave": "vendedor", "titulo": "Vendedor", "alineacion": "izq"},
        {"clave": "comision", "titulo": "Comisión", "alineacion": "der"},
    ]
    filas = [
        {"vendedor": "Juan P.", "comision": "USD 45.00"},
        {"vendedor": "Ana R.", "comision": "USD 20.00"},
    ]
    html_tabla = TablaDensa(columnas, filas, id_tabla="tabla-resumen")
    assert 'id="tabla-resumen"' in html_tabla
    assert "Juan P." in html_tabla
    assert "USD 45.00" in html_tabla

    # Cero violaciones de gobernanza ni marcas
    violaciones = comprobar_interfaz_purificada()
    assert len(violaciones) == 0
