# ¤arm-jarvis
# ¤¤backend-developer
"""Dobles propios para pruebas aisladas de comisiones, crm, canal y seguridad."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

__all__ = [
    "DobleComisiones",
    "DobleCrm",
    "DobleCanalWhatsApp",
    "DobleSeguridad",
    "DobleObservabilidad",
    "ComisionSimulada",
]


# ¤arm-jarvis
@dataclass(frozen=True)
class ComisionSimulada:
    comision_id: str
    venta_id: str
    vendedor_id: str
    monto: Decimal
    porcentaje_aplicado: Decimal
    version_regla: str
    estado: str = "estimada"


# ¤arm-jarvis
class DobleComisiones:
    """Doble de prueba para comisiones_service (RF-COM-01)."""

    def __init__(self, porcentaje: Decimal = Decimal("0.10")) -> None:
        self.porcentaje = porcentaje
        self.calculadas: list[ComisionSimulada] = []
        self.fijadas: list[ComisionSimulada] = []
        self.bases_por_vendedor: dict[str, Decimal] = {}

    # ¤arm-jarvis
    def calcular(
        self,
        venta_id: str,
        vendedor_id: str,
        propiedad_id: str | None,
        producto: str,
        monto: Decimal,
        fecha_venta: date,
    ) -> ComisionSimulada:
        comision_monto = (monto * self.porcentaje).quantize(Decimal("0.01"))
        c = ComisionSimulada(
            comision_id=f"com_{venta_id}",
            venta_id=venta_id,
            vendedor_id=vendedor_id,
            monto=comision_monto,
            porcentaje_aplicado=self.porcentaje,
            version_regla="v1.0",
            estado="estimada",
        )
        self.calculadas.append(c)
        return c

    # ¤arm-jarvis
    def fijar(self, comision_id: str) -> ComisionSimulada:
        # Buscar en calculadas o generar
        c = next((item for item in self.calculadas if item.comision_id == comision_id), None)
        if not c:
            c = ComisionSimulada(
                comision_id=comision_id,
                venta_id="v_unknown",
                vendedor_id="vend_unknown",
                monto=Decimal("45.00"),
                porcentaje_aplicado=self.porcentaje,
                version_regla="v1.0",
                estado="fijada",
            )
        fijada = ComisionSimulada(
            comision_id=c.comision_id,
            venta_id=c.venta_id,
            vendedor_id=c.vendedor_id,
            monto=c.monto,
            porcentaje_aplicado=c.porcentaje_aplicado,
            version_regla=c.version_regla,
            estado="fijada",
        )
        self.fijadas.append(fijada)
        return fijada

    # ¤arm-jarvis
    def resumen(self, vendedor_id: str | None, periodo_id: str) -> Mapping[str, Any]:
        if self.fijadas or self.calculadas:
            fij = [c for c in self.fijadas if (not vendedor_id or c.vendedor_id == vendedor_id)]
            fij_ids = {c.comision_id for c in fij}
            pend = [
                c
                for c in self.calculadas
                if (not vendedor_id or c.vendedor_id == vendedor_id) and c.comision_id not in fij_ids
            ]
            val_monto = sum((c.monto for c in fij), Decimal("0.00"))
            pend_monto = sum((c.monto for c in pend), Decimal("0.00"))
            return {
                "vendedor_id": vendedor_id or "",
                "periodo_id": periodo_id,
                "validada": val_monto,
                "pendiente": pend_monto,
                "ventas": len(fij),
            }
        return {
            "vendedor_id": vendedor_id or "",
            "periodo_id": periodo_id,
            "validada": Decimal("350.00"),
            "pendiente": Decimal("120.00"),
            "ventas": 5,
        }


# ¤arm-jarvis
class DobleCrm:
    """Doble de prueba para crm_conector_service."""

    def __init__(self, simular_fallo: bool = False) -> None:
        self.simular_fallo = simular_fallo
        self.ventas_publicadas: list[Any] = []
        self.ventas_anuladas: list[Any] = []

    # ¤arm-jarvis
    def publicar_venta(self, venta: Any) -> bool:
        if self.simular_fallo:
            raise RuntimeError("Fallo de red en CRM")
        self.ventas_publicadas.append(venta)
        return True

    # ¤arm-jarvis
    def publicar_anulacion(self, venta: Any) -> bool:
        self.ventas_anuladas.append(venta)
        return True


# ¤arm-jarvis
class DobleCanalWhatsApp:
    """Doble de prueba para canal_whatsapp_service."""

    def __init__(self, simular_fallo: bool = False) -> None:
        self.simular_fallo = simular_fallo
        self.mensajes_enviados: list[dict[str, Any]] = []
        self.plantillas_enviadas: list[dict[str, Any]] = []

    # ¤arm-jarvis
    def enviar(self, destinatario: str, texto: str) -> None:
        if self.simular_fallo:
            raise RuntimeError("Error al enviar mensaje WhatsApp")
        self.mensajes_enviados.append({"destinatario": destinatario, "texto": texto})

    # ¤arm-jarvis
    def enviar_plantilla(self, destinatario: str, plantilla: str, parametros: Sequence[str]) -> None:
        if self.simular_fallo:
            raise RuntimeError("Error al enviar plantilla WhatsApp")
        self.plantillas_enviadas.append({
            "destinatario": destinatario,
            "plantilla": plantilla,
            "parametros": tuple(parametros),
        })


# ¤arm-jarvis
class DobleSeguridad:
    """Doble de prueba para seguridad_service."""

    def __init__(self) -> None:
        self.auditorias: list[Any] = []

    # ¤arm-jarvis
    def auditar(self, evento: Any) -> None:
        self.auditorias.append(evento)

    # ¤arm-jarvis
    def rehidratar(self, texto: str, conversacion_id: str = "") -> str:
        return texto


# ¤arm-jarvis
class DobleObservabilidad:
    """Doble de prueba para observabilidad_service."""

    def __init__(self) -> None:
        self.alertas: list[dict[str, Any]] = []

    # ¤arm-jarvis
    def alertar(self, tipo: str, mensaje: str, datos: Mapping[str, Any] | None = None) -> None:
        self.alertas.append({
            "tipo": tipo,
            "mensaje": mensaje,
            "datos": dict(datos or {}),
            "timestamp": datetime.now(timezone.utc),
        })
