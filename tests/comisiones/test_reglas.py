# ¤comisiones
# ¤¤backend-developer
"""Pruebas unitarias y de contrato para reglas de comisiones (RF-COM-01, INV_COMISION_REPRODUCIBLE)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from itertools import permutations
import pytest

from features.comisiones.comisiones_service import (
    ComisionesService,
    ReglaSolapada,
    SinReglaVigente,
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
def servicio() -> ComisionesService:
    persistencia = PersistenciaComisiones(":memory:")
    seguridad = DobleSeguridad()
    observabilidad = DobleObservabilidad()
    config = {"moneda": "USD", "periodo": "mensual"}
    return ComisionesService(config, seguridad=seguridad, observabilidad=observabilidad, persistencia=persistencia)


# ¤comisiones
def test_regla_versionada_e_inmutable(servicio: ComisionesService) -> None:
    """Verifica que las reglas sean versionadas y que no se puedan sobrescribir."""
    regla_v1 = ReglaComision(
        regla_id="regla-general",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("5.0"),
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 6, 30),
    )
    servicio.crear_regla("admin-token", regla_v1)

    reglas = servicio.reglas()
    assert len(reglas) == 1
    assert reglas[0].version == 1

    # Intentar duplicar la versión 1 debe fallar
    with pytest.raises(ValueError, match="ya existe"):
        servicio.crear_regla("admin-token", regla_v1)

    # Crear versión 2 con nueva vigencia
    regla_v2 = ReglaComision(
        regla_id="regla-general",
        version=2,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("7.0"),
        vigente_desde=date(2026, 7, 1),
    )
    servicio.crear_regla("admin-token", regla_v2)

    assert len(servicio.reglas()) == 2
    assert {r.version for r in servicio.reglas()} == {1, 2}


# ¤comisiones
def test_vigencia_a_fecha_de_venta(servicio: ComisionesService) -> None:
    """Verifica que se use la regla vigente a fecha_venta, no a la fecha de cálculo."""
    servicio.crear_regla(
        "admin",
        ReglaComision(
            regla_id="regla-antigua",
            version=1,
            tipo=TipoRegla.PORCENTAJE,
            valor=Decimal("5.0"),
            vigente_desde=date(2026, 1, 1),
            vigente_hasta=date(2026, 5, 31),
        ),
    )
    servicio.crear_regla(
        "admin",
        ReglaComision(
            regla_id="regla-nueva",
            version=1,
            tipo=TipoRegla.PORCENTAJE,
            valor=Decimal("10.0"),
            vigente_desde=date(2026, 6, 1),
        ),
    )

    # Venta de mayo debe usar regla de 5%
    c_mayo = servicio.calcular(
        venta_id="v-mayo-1",
        vendedor_id="vend-1",
        propiedad_id="prop-1",
        producto="noche",
        monto=Decimal("100.00"),
        fecha_venta=date(2026, 5, 15),
    )
    assert c_mayo.regla_id == "regla-antigua"
    assert c_mayo.monto == Decimal("5.00")

    # Venta de junio debe usar regla de 10%
    c_junio = servicio.calcular(
        venta_id="v-junio-1",
        vendedor_id="vend-1",
        propiedad_id="prop-1",
        producto="noche",
        monto=Decimal("100.00"),
        fecha_venta=date(2026, 6, 15),
    )
    assert c_junio.regla_id == "regla-nueva"
    assert c_junio.monto == Decimal("10.00")


# ¤comisiones
def test_sin_regla_vigente_falla(servicio: ComisionesService) -> None:
    """Sin regla aplicable falla con SinReglaVigente."""
    with pytest.raises(SinReglaVigente):
        servicio.calcular(
            venta_id="v-sin-regla",
            vendedor_id="vend-1",
            propiedad_id=None,
            producto="servicio",
            monto=Decimal("200.00"),
            fecha_venta=date(2026, 1, 10),
        )


# ¤comisiones
def test_escalon_graduado_invariante_de_orden(servicio: ComisionesService) -> None:
    """Verifica que en modo graduado el total del mes sea 110.00 en cualquier orden de validación."""
    regla = ReglaComision(
        regla_id="regla-graduada",
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

    ventas_montos = [Decimal("333.33"), Decimal("700.10"), Decimal("566.57")]

    # Probar todas las permutaciones de orden de fijación
    for orden in permutations(ventas_montos):
        # Crear un nuevo servicio aislado para cada permutación
        srv = ComisionesService(
            {"moneda": "USD"},
            seguridad=DobleSeguridad(),
            observabilidad=DobleObservabilidad(),
            persistencia=PersistenciaComisiones(":memory:"),
        )
        srv.crear_regla("admin", regla)

        comisiones = []
        for i, monto in enumerate(orden):
            c = srv.calcular(
                venta_id=f"v-{i}",
                vendedor_id="vend-1",
                propiedad_id="prop-1",
                producto="hospedaje",
                monto=monto,
                fecha_venta=date(2026, 10, 10),
            )
            c_fijada = srv.fijar(c.comision_id)
            assert c_fijada.estado == EstadoComision.FIJADA
            comisiones.append(c_fijada)

        total_mes = sum((c.monto for c in comisiones), Decimal("0.00"))
        assert total_mes == Decimal("110.00")


# ¤comisiones
def test_escalon_volumen_invariante_de_orden(servicio: ComisionesService) -> None:
    """Verifica que en modo volumen el total del mes sea 160.00 en cualquier orden de validación."""
    regla = ReglaComision(
        regla_id="regla-volumen",
        version=1,
        tipo=TipoRegla.ESCALONADA,
        valor=Decimal("0.0"),
        modo_escalon=ModoEscalon.VOLUMEN,
        vigente_desde=date(2026, 1, 1),
        escalones=(
            Escalon(desde_monto=Decimal("0.0"), porcentaje=Decimal("5.0")),
            Escalon(desde_monto=Decimal("1000.0"), porcentaje=Decimal("10.0")),
        ),
    )
    servicio.crear_regla("admin", regla)

    ventas_montos = [Decimal("333.33"), Decimal("700.10"), Decimal("566.57")]

    for orden in permutations(ventas_montos):
        srv = ComisionesService(
            {"moneda": "USD"},
            seguridad=DobleSeguridad(),
            observabilidad=DobleObservabilidad(),
            persistencia=PersistenciaComisiones(":memory:"),
        )
        srv.crear_regla("admin", regla)

        comisiones = []
        for i, monto in enumerate(orden):
            c = srv.calcular(
                venta_id=f"v-{i}",
                vendedor_id="vend-1",
                propiedad_id="prop-1",
                producto="hospedaje",
                monto=monto,
                fecha_venta=date(2026, 10, 10),
            )
            c_fijada = srv.fijar(c.comision_id)
            comisiones.append(c_fijada)

        total_mes = sum((c.monto for c in comisiones), Decimal("0.00"))
        assert total_mes == Decimal("160.00")


# ¤comisiones
def test_desglose_tramos_panel(servicio: ComisionesService) -> None:
    """Verifica el desglose transparente de tramos para el panel (RF-PAN-03, ADR-0015)."""
    regla = ReglaComision(
        regla_id="regla-graduada",
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

    # Venta 1 de 600
    c1 = servicio.calcular("v-1", "v-1", None, "prod", Decimal("600.00"), date(2026, 10, 5))
    servicio.fijar(c1.comision_id)

    # Venta 2 de 800 (cruza de 600 a 1400: 400 al 5% y 400 al 10%)
    c2 = servicio.calcular("v-2", "v-1", None, "prod", Decimal("800.00"), date(2026, 10, 12))
    c2_fijada = servicio.fijar(c2.comision_id)

    desglose = servicio.desglose(c2_fijada.comision_id)
    assert desglose["comision_id"] == c2_fijada.comision_id
    assert desglose["modo_escalon"] == "graduado"
    assert desglose["base_acumulada"] == "600.00"
    assert desglose["monto_venta"] == "800.00"
    assert len(desglose["tramos"]) == 2

    # Tramo 1: 400 al 5% = 20.00
    assert desglose["tramos"][0]["base_en_tramo"] == "400.00"
    assert desglose["tramos"][0]["porcentaje"] == "5.0"
    assert desglose["tramos"][0]["comision_tramo"] == "20.00"

    # Tramo 2: 400 al 10% = 40.00
    assert desglose["tramos"][1]["base_en_tramo"] == "400.00"
    assert desglose["tramos"][1]["porcentaje"] == "10.0"
    assert desglose["tramos"][1]["comision_tramo"] == "40.00"

    assert c2_fijada.monto == Decimal("60.00")
