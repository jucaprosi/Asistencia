# ¤arm-jarvis
# ¤¤backend-developer
"""Máquina de estados y auditoría de transiciones para ventas (RF-ARM-03, INV_ESTADOS_VENTA)."""
from __future__ import annotations

from typing import Any, Mapping

from features.arm_jarvis.persistencia_internal import RepositorioArm
from features.arm_jarvis.tipos import EstadoVenta, TransicionInvalida, Venta

__all__ = ["GestorEstados", "TRANSICIONES_PERMITIDAS"]

# Matriz canónica de transiciones permitidas
TRANSICIONES_PERMITIDAS: Mapping[EstadoVenta, tuple[EstadoVenta, ...]] = {
    EstadoVenta.POR_VALIDAR: (EstadoVenta.VALIDADA, EstadoVenta.RECHAZADA, EstadoVenta.ANULADA),
    EstadoVenta.VALIDADA: (EstadoVenta.PUBLICADA, EstadoVenta.NO_PUBLICADA, EstadoVenta.ANULADA),
    EstadoVenta.NO_PUBLICADA: (EstadoVenta.PUBLICADA, EstadoVenta.ANULADA),
    EstadoVenta.PUBLICADA: (EstadoVenta.ANULADA,),
    EstadoVenta.RECHAZADA: (),
    EstadoVenta.ANULADA: (),
}


# ¤arm-jarvis
class GestorEstados:
    """Gobierna las transiciones entre estados de una venta asegurando reglas e invariantes."""

    def __init__(self, repositorio: RepositorioArm) -> None:
        self._repo = repositorio

    # ¤arm-jarvis
    def validar_transicion(
        self,
        venta: Venta,
        nuevo_estado: EstadoVenta,
        actor_rol: str,
        motivo: str | None = None,
    ) -> None:
        """Comprueba si la transición es válida y autorizada para el rol."""
        actual = venta.estado

        # 1. Verificar si la transición existe en la matriz canónica
        permitidos = TRANSICIONES_PERMITIDAS.get(actual, ())
        if nuevo_estado not in permitidos:
            raise TransicionInvalida(
                estado_actual=actual.value,
                estado_nuevo=nuevo_estado.value,
                motivo=f"No se permite transitar de {actual.value} a {nuevo_estado.value}",
            )

        # 2. Reglas para pasar a 'rechazada'
        if nuevo_estado == EstadoVenta.RECHAZADA:
            if not motivo or not motivo.strip():
                raise TransicionInvalida(
                    estado_actual=actual.value,
                    estado_nuevo=nuevo_estado.value,
                    motivo="Rechazar una venta requiere motivo obligatorio.",
                )

        # 3. Reglas para pasar a 'anulada': solo administrador y con motivo
        if nuevo_estado == EstadoVenta.ANULADA:
            if actor_rol != "administrador":
                raise TransicionInvalida(
                    estado_actual=actual.value,
                    estado_nuevo=nuevo_estado.value,
                    motivo="Solo el rol administrador puede anular una venta.",
                )
            if not motivo or not motivo.strip():
                raise TransicionInvalida(
                    estado_actual=actual.value,
                    estado_nuevo=nuevo_estado.value,
                    motivo="Anular una venta requiere un motivo explícito.",
                )

        # 4. Reglas para pasar a 'validada': solo líder o administrador
        if nuevo_estado == EstadoVenta.VALIDADA:
            if actor_rol not in ("lider", "administrador", "sistema"):
                raise TransicionInvalida(
                    estado_actual=actual.value,
                    estado_nuevo=nuevo_estado.value,
                    motivo=f"El rol {actor_rol} no está autorizado para validar ventas.",
                )

    # ¤arm-jarvis
    def ejecutar_transicion(
        self,
        venta_id: str,
        nuevo_estado: EstadoVenta,
        actor_id: str,
        actor_rol: str,
        motivo: str | None = None,
        comision_fijada: Any = None,
        reserva_ref: str | None = None,
    ) -> Venta:
        """Aplica la transición en la base de datos tras verificar permisos."""
        venta = self._repo.obtener_venta(venta_id)
        self.validar_transicion(venta, nuevo_estado, actor_rol, motivo)

        return self._repo.actualizar_estado(
            venta_id=venta_id,
            nuevo_estado=nuevo_estado,
            estado_esperado=venta.estado,
            actor_id=actor_id,
            rol=actor_rol,
            motivo=motivo,
            comision_fijada=comision_fijada,
            reserva_ref=reserva_ref,
        )
