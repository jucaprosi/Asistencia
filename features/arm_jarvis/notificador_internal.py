# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Notificaciones privadas a vendedores vía WhatsApp (RF-ARM-06)."""
from __future__ import annotations

from typing import Any, Mapping

from features.arm_jarvis.tipos import Vendedor, Venta

__all__ = ["NotificadorVendedor"]


# ¤arm-jarvis
class NotificadorVendedor:
    """Envía notificaciones privadas a los vendedores al validar o rechazar ventas."""

    def __init__(self, canal_whatsapp: Any, config: Mapping[str, Any] | None = None) -> None:
        self._canal = canal_whatsapp
        self._config = config or {}
        self.notificaciones_fallidas: list[dict[str, Any]] = []

    # ¤arm-jarvis
    def notificar_validacion(
        self,
        venta: Venta,
        vendedor: Vendedor,
        fuera_de_ventana_24h: bool = False,
    ) -> bool:
        """Envía notificación privada al vendedor con la comisión fijada."""
        comision_txt = f"{venta.comision_fijada:.2f} USD" if venta.comision_fijada else "0.00 USD"
        telefono = vendedor.telefono_token

        try:
            if fuera_de_ventana_24h and hasattr(self._canal, "enviar_plantilla"):
                self._canal.enviar_plantilla(
                    destinatario=telefono,
                    plantilla="comision_validada",
                    parametros=(venta.ticket, comision_txt),
                )
            elif hasattr(self._canal, "enviar"):
                texto = (
                    f"¡Tu venta fue validada con éxito!\n"
                    f"Ticket: {venta.ticket}\n"
                    f"Producto: {venta.extraida.producto}\n"
                    f"Comisión: {comision_txt}"
                )
                self._canal.enviar(destinatario=telefono, texto=texto)
            return True
        except Exception as exc:
            self.notificaciones_fallidas.append({
                "venta_id": venta.venta_id,
                "vendedor_id": vendedor.vendedor_id,
                "tipo": "validacion",
                "error": str(exc),
            })
            return False

    # ¤arm-jarvis
    def notificar_rechazo(
        self,
        venta: Venta,
        vendedor: Vendedor,
        motivo: str,
        fuera_de_ventana_24h: bool = False,
    ) -> bool:
        """Envía notificación privada al vendedor indicando el motivo de rechazo."""
        telefono = vendedor.telefono_token

        try:
            if fuera_de_ventana_24h and hasattr(self._canal, "enviar_plantilla"):
                self._canal.enviar_plantilla(
                    destinatario=telefono,
                    plantilla="venta_rechazada",
                    parametros=(venta.ticket, motivo),
                )
            elif hasattr(self._canal, "enviar"):
                texto = (
                    f"Tu venta {venta.ticket} no pudo ser validada.\n"
                    f"Motivo: {motivo}"
                )
                self._canal.enviar(destinatario=telefono, texto=texto)
            return True
        except Exception as exc:
            self.notificaciones_fallidas.append({
                "venta_id": venta.venta_id,
                "vendedor_id": vendedor.vendedor_id,
                "tipo": "rechazo",
                "motivo": motivo,
                "error": str(exc),
            })
            return False
