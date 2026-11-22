# ¤comisiones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas para el cierre de período y venta tardía (RF-COM-02, INV_COMISION_REPRODUCIBLE)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import sqlite3
import pytest

from features.comisiones.comisiones_service import (
    ComisionesService,
    PeriodoCerrado,
)
from features.comisiones.persistencia_internal import PersistenciaComisiones
from features.comisiones.tipos import (
    Escalon,
    EstadoComision,
    ModoEscalon,
    ReglaComision,
    TipoRegla,
)
from tests.comisiones.dobles import DobleObservabilidad, DobleSeguridad


# ¤comisiones
@pytest.fixture
def servicio_y_db() -> tuple[ComisionesService, sqlite3.Connection]:
    con = sqlite3.connect(":memory:")
    persistencia = PersistenciaComisiones(con)
    seguridad = DobleSeguridad()
    observabilidad = DobleObservabilidad()
    config = {"moneda": "USD", "periodo": "mensual"}
    srv = ComisionesService(config, seguridad=seguridad, observabilidad=observabilidad, persistencia=persistencia)
    return srv, con


# ¤comisiones
def test_cierre_periodo_inmutable(servicio_y_db: tuple[ComisionesService, sqlite3.Connection]) -> None:
    """Verifica que el período cerrado sea inmutable y que disparadores en BD impidan modificaciones."""
    servicio, con = servicio_y_db

    regla = ReglaComision(
        regla_id="regla-5pct",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("5.0"),
        vigente_desde=date(2026, 1, 1),
    )
    servicio.crear_regla("admin", regla)

    # Ventas en octubre 2026
    c1 = servicio.calcular("v-oct-1", "vend-1", None, "prod", Decimal("1000.00"), date(2026, 10, 5))
    servicio.fijar(c1.comision_id)

    c2 = servicio.calcular("v-oct-2", "vend-2", None, "prod", Decimal("2000.00"), date(2026, 10, 10))
    servicio.fijar(c2.comision_id)

    # Cierre de octubre
    periodo = servicio.cerrar_periodo("2026-10", "lider-comercial")
    assert periodo.cerrado_en is not None
    assert periodo.cerrado_por == "lider-comercial"

    # Verificar resumen por vendedor
    resumen = periodo.resumen
    assert "vendedores" in resumen
    assert resumen["vendedores"]["vend-1"]["total"] == "50.00"
    assert resumen["vendedores"]["vend-1"]["ventas"] == 1
    assert resumen["vendedores"]["vend-2"]["total"] == "100.00"
    assert resumen["vendedores"]["vend-2"]["ventas"] == 1

    # Intentar cerrar nuevamente el período cerrado debe fallar
    with pytest.raises(PeriodoCerrado):
        servicio.cerrar_periodo("2026-10", "lider-comercial")

    # Intentar modificar directamente una comisión de octubre mediante SQL debe disparar el trigger
    with pytest.raises(sqlite3.IntegrityError, match="PeriodoCerrado"):
        with con:
            con.execute(
                "UPDATE comisiones SET monto = '999.00' WHERE comision_id = ?",
                (c1.comision_id,),
            )

    # Intentar eliminar directamente una comisión de octubre mediante SQL debe disparar el trigger
    with pytest.raises(sqlite3.IntegrityError, match="PeriodoCerrado"):
        with con:
            con.execute(
                "DELETE FROM comisiones WHERE comision_id = ?",
                (c1.comision_id,),
            )


# ¤comisiones
def test_venta_tardia_con_escalon(servicio_y_db: tuple[ComisionesService, sqlite3.Connection]) -> None:
    """Verifica que una venta de octubre validada cuando octubre ya cerró entre al período abierto

    más antiguo conservando su periodo_origen y usando la base acumulada de octubre (RF-COM-02).
    """
    servicio, _ = servicio_y_db

    # Regla escalonada: 5% hasta 1000, 10% desde 1000
    regla = ReglaComision(
        regla_id="regla-escalonada",
        version=1,
        tipo=TipoRegla.ESCALONADA,
        valor=Decimal("0.0"),
        modo_escalon=ModoEscalon.GRADUADO,
        vigente_desde=date(2026, 1, 1),
        escalones=(
            Escalon(desde_monto=Decimal("0.0"), porcentaje=Decimal("5.0")),
            Escalon(desde_monto=Decimal("1000.0"), porcentaje=Decimal("10.0")),
        ),
    )
    servicio.crear_regla("admin", regla)

    # Venta de octubre de 900.00 fijada
    c_oct = servicio.calcular("v-oct-1", "vend-1", None, "prod", Decimal("900.00"), date(2026, 10, 15))
    c_oct_fijada = servicio.fijar(c_oct.comision_id)
    assert c_oct_fijada.monto == Decimal("45.00")
    assert c_oct_fijada.periodo_id == "2026-10"

    # Se cierra octubre
    servicio.cerrar_periodo("2026-10", "lider")

    # Llega una venta tardía de octubre de 200.00 cuando octubre ya cerró
    c_tardia = servicio.calcular("v-tardia-1", "vend-1", None, "prod", Decimal("200.00"), date(2026, 10, 20))
    c_tardia_fijada = servicio.fijar(c_tardia.comision_id)

    # Debe entrar al período abierto más antiguo (noviembre 2026-11)
    assert c_tardia_fijada.periodo_id == "2026-11"
    # Debe conservar su periodo_origen de octubre
    assert c_tardia_fijada.periodo_origen == "2026-10"
    # Debe usar la base acumulada de octubre (900.00)
    assert c_tardia_fijada.base_acumulada == Decimal("900.00")
    # Comisión: de 900 a 1100 cruza 1000 -> 100 al 5% (5.00) + 100 al 10% (10.00) = 15.00
    assert c_tardia_fijada.monto == Decimal("15.00")

    # Estado de cuenta de noviembre para vend-1
    ec_nov = servicio.estado_cuenta("vend-1", "2026-11")
    assert ec_nov["total_comisiones"] == "15.00"
    assert len(ec_nov["lineas"]) == 1
    assert ec_nov["lineas"][0]["periodo_origen"] == "2026-10"
