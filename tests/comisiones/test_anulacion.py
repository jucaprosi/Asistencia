# ¤comisiones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas para anulación de ventas y efectos en comisiones (RF-COM-04, INV_COMISION_REPRODUCIBLE)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import pytest

from features.comisiones.comisiones_service import (
    ComisionesService,
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
def servicio_con_dobles() -> tuple[ComisionesService, DobleSeguridad, DobleObservabilidad]:
    persistencia = PersistenciaComisiones(":memory:")
    seguridad = DobleSeguridad()
    observabilidad = DobleObservabilidad()
    config = {"moneda": "USD", "periodo": "mensual"}
    srv = ComisionesService(config, seguridad=seguridad, observabilidad=observabilidad, persistencia=persistencia)
    return srv, seguridad, observabilidad


# ¤comisiones
def test_anulacion_crea_ajuste_negativo_sin_alterar_demas(
    servicio_con_dobles: tuple[ComisionesService, DobleSeguridad, DobleObservabilidad],
) -> None:
    """Escenario: Anular una venta no toca a las demás (RF-COM-04).

    Dado ventas por 333.33, 700.10 y 566.57 con escalones de 5 % y 10 % desde 1000.
    Cuando el administrador anula la de 700.10.
    Entonces entra un solo ajuste de -65.00 y el total del mes queda en 45.00.
    """
    servicio, seguridad, observabilidad = servicio_con_dobles

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

    # 1. Tres ventas fijadas en octubre
    c1 = servicio.calcular("v-1", "vend-1", None, "prod", Decimal("333.33"), date(2026, 10, 5))
    c1_f = servicio.fijar(c1.comision_id)

    c2 = servicio.calcular("v-2", "vend-1", None, "prod", Decimal("700.10"), date(2026, 10, 10))
    c2_f = servicio.fijar(c2.comision_id)

    c3 = servicio.calcular("v-3", "vend-1", None, "prod", Decimal("566.57"), date(2026, 10, 15))
    c3_f = servicio.fijar(c3.comision_id)

    total_inicial = c1_f.monto + c2_f.monto + c3_f.monto
    assert total_inicial == Decimal("110.00")

    # 2. El administrador anula la venta de 700.10 (v-2)
    ajuste = servicio.anular_venta("v-2", "admin-token", "Cancelación por cliente")

    # Verificar ajuste generado
    assert ajuste.estado == EstadoComision.AJUSTADA
    assert ajuste.ajuste_de == c2_f.comision_id
    assert ajuste.monto == Decimal("-65.00")
    assert ajuste.periodo_id == "2026-10"

    # Verificar que la comisión original no fue alterada
    c2_despues = servicio._persistencia.obtener_comision(c2_f.comision_id)
    assert c2_despues is not None
    assert c2_despues.monto == c2_f.monto
    assert c2_despues.estado == EstadoComision.FIJADA

    # Verificar que el total neto del mes queda en 45.00
    resumen = servicio.resumen("vend-1", "2026-10")
    assert resumen["validada"] == Decimal("45.00")
    assert resumen["ajustes"] == Decimal("-65.00")

    # Verificar evento emitido a observabilidad
    eventos_anulada = [ev for ev, datos in observabilidad.eventos if ev == "venta_anulada"]
    assert len(eventos_anulada) == 1

    # Verificar auditoría
    auditorias_anulada = [a for a in seguridad.auditorias if a[1] == "anular_venta"]
    assert len(auditorias_anulada) == 1
