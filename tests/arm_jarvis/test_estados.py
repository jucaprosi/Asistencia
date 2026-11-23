# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de la máquina de estados de las ventas (RF-ARM-03, INV_ESTADOS_VENTA)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.tipos import EstadoVenta, TransicionInvalida


# ¤arm-jarvis
class ActorFake:
    def __init__(self, sujeto_id: str, rol: str) -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤arm-jarvis
def _crear_servicio_con_venta() -> tuple[ArmJarvisService, str]:
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_1", nombre="Vendedor 1")

    class Msg:
        remitente = "tel_1"
        texto = "vendí 3 noches en el depa del centro a María López, 450, llega el 15"
        mensaje_id = "msg_est_1"

    servicio.procesar(Msg())
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 1
    return servicio, ventas[0].venta_id


# ¤arm-jarvis
def test_validar_venta_correcta() -> None:
    """Escenario: Validar una venta (@US-06 @CU-05 @RF-ARM-03 @RF-PAN-02).

    Dado una venta 'por_validar' sin campos dudosos
    Cuando el líder la valida con una acción
    Entonces pasa a 'validada', la comisión se fija y la publicación al CRM se realiza
    """
    servicio, venta_id = _crear_servicio_con_venta()
    lider = ActorFake("lider_1", "lider")

    venta_val = servicio.validar(venta_id, lider)

    # Validada o publicada tras encolar en CRM
    assert venta_val.estado in (EstadoVenta.VALIDADA, EstadoVenta.PUBLICADA)
    assert venta_val.comision_fijada is not None
    assert venta_val.comision_fijada > 0

    # Comprobar historial de transiciones
    _, transiciones = servicio.detalle(venta_id)
    assert len(transiciones) >= 1
    assert transiciones[0].de == EstadoVenta.POR_VALIDAR
    assert transiciones[0].a == EstadoVenta.VALIDADA
    assert transiciones[0].actor_id == "lider_1"


# ¤arm-jarvis
def test_rechazar_venta_con_motivo_obligatorio() -> None:
    """Escenario: Rechazar una venta (@US-06 @RF-ARM-03 @RF-ARM-06).

    Dado una venta 'por_validar'
    Cuando el líder la rechaza con motivo
    Entonces pasa a 'rechazada', no genera comisión y el vendedor recibe el motivo
    """
    servicio, venta_id = _crear_servicio_con_venta()
    lider = ActorFake("lider_1", "lider")

    # Rechazar sin motivo debe fallar
    with pytest.raises(TransicionInvalida):
        servicio.rechazar(venta_id, lider, motivo="")

    # Rechazar con motivo exitoso
    venta_rech = servicio.rechazar(venta_id, lider, motivo="Comprobante de depósito adulterado")
    assert venta_rech.estado == EstadoVenta.RECHAZADA
    assert venta_rech.comision_fijada == Decimal("0.00")


# ¤arm-jarvis
def test_transicion_invalida_desde_anulada_rechazada() -> None:
    """Escenario: Transición inválida (@RF-ARM-03 @INV_ESTADOS_VENTA).

    Dado una venta 'anulada'
    Cuando alguien intenta cambiar su estado
    Entonces la base de datos la rechaza
    """
    servicio, venta_id = _crear_servicio_con_venta()
    admin = ActorFake("admin_1", "administrador")
    lider = ActorFake("lider_1", "lider")

    # Anulación por admin con motivo
    servicio.anular(venta_id, admin, motivo="Error de digitación")

    # Intentar transicionar de nuevo desde 'anulada' a cualquier estado
    with pytest.raises(TransicionInvalida):
        servicio.validar(venta_id, lider)

    with pytest.raises(TransicionInvalida):
        servicio.rechazar(venta_id, lider, motivo="intento")


# ¤arm-jarvis
def test_anular_requiere_rol_administrador() -> None:
    """Solo el administrador puede anular una venta."""
    servicio, venta_id = _crear_servicio_con_venta()
    lider = ActorFake("lider_1", "lider")

    with pytest.raises(TransicionInvalida):
        servicio.anular(venta_id, lider, motivo="Intento por líder")


# ¤arm-jarvis
def test_una_venta_validada_no_se_edita() -> None:
    """Escenario: Una venta validada no se edita (@US-06 @RF-ARM-03).

    Dado una venta 'validada'
    Cuando alguien intenta editar el monto
    Entonces el sistema lo impide y ofrece anulación con motivo al administrador
    """
    servicio, venta_id = _crear_servicio_con_venta()
    lider = ActorFake("lider_1", "lider")
    servicio.validar(venta_id, lider)

    with pytest.raises(TransicionInvalida) as exc:
        servicio.editar_venta(venta_id, lider, nuevo_monto=Decimal("500.00"))

    assert "no se puede editar" in str(exc.value)
