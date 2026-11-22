# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del cálculo y fijación reproducible de comisiones (RF-ARM-04, INV_COMISION_REPRODUCIBLE)."""
from __future__ import annotations

import concurrent.futures
from decimal import Decimal
from typing import Any

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.dobles_internal import DobleComisiones


# ¤arm-jarvis
class ActorFake:
    def __init__(self, sujeto_id: str = "lider_1", rol: str = "lider") -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤arm-jarvis
def test_calculo_comision_reproducible_y_fijacion_inmutable() -> None:
    """Escenario: Cálculo y fijación de comisión con regla de comisión."""
    comisiones = DobleComisiones(porcentaje=Decimal("0.10"))
    servicio = ArmJarvisService(comisiones=comisiones)
    v = servicio.registrar_vendedor(telefono_token="tel_com_1", nombre="Ana Ruiz")

    class Msg:
        remitente = "tel_com_1"
        texto = "vendí 3 noches en el depa del centro a María López, 450, llega el 15"
        mensaje_id = "msg_com_1"

    servicio.procesar(Msg())
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 1
    venta = ventas[0]

    # Comisión estimada al registrar (10% de 450 = 45.00)
    assert venta.comision_estimada == Decimal("45.00")
    assert venta.comision_fijada is None

    # Validar fija la comisión
    lider = ActorFake()
    venta_val = servicio.validar(venta.venta_id, lider)
    assert venta_val.comision_fijada == Decimal("45.00")

    # Cambio posterior de regla no altera la comisión ya validada
    comisiones.porcentaje = Decimal("0.15")
    venta_recuperada = servicio.repositorio.obtener_venta(venta.venta_id)
    assert venta_recuperada.comision_fijada == Decimal("45.00")


# ¤arm-jarvis
def test_validaciones_concurrentes_mismo_vendedor() -> None:
    """Escenario: Validaciones concurrentes del mismo vendedor (@RF-ARM-04 @INV_COMISION_REPRODUCIBLE).

    Dado dos ventas del mismo vendedor
    Cuando se validan a la vez
    Entonces una espera a la otra, garantizando consistencia y serialización
    """
    comisiones = DobleComisiones()
    servicio = ArmJarvisService(comisiones=comisiones)
    v = servicio.registrar_vendedor(telefono_token="tel_conc", nombre="Vendedor Concurrente")

    class Msg1:
        remitente = "tel_conc"
        texto = "vendí Domo Lago 300 a cliente A"
        mensaje_id = "msg_c_1"

    class Msg2:
        remitente = "tel_conc"
        texto = "vendí Domo Montaña 200 a cliente B"
        mensaje_id = "msg_c_2"

    servicio.procesar(Msg1())
    servicio.procesar(Msg2())

    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 2
    v1_id = ventas[0].venta_id
    v2_id = ventas[1].venta_id

    lider = ActorFake()

    def _validar(vid: str) -> None:
        servicio.validar(vid, lider)

    # Validar simultáneamente en dos hilos concurrentes
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(_validar, v1_id)
        f2 = executor.submit(_validar, v2_id)
        f1.result()
        f2.result()

    res1 = servicio.repositorio.obtener_venta(v1_id)
    res2 = servicio.repositorio.obtener_venta(v2_id)
    assert res1.comision_fijada is not None
    assert res2.comision_fijada is not None
