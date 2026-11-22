# ¤anfitriones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Dobles de prueba para compuertas consumidas por la sala anfitriones."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping


# ¤anfitriones
@dataclass(frozen=True)
class ReservaDoble:
    codigo: str
    propiedad_id: str
    unidad_id: str
    huesped_token: str
    desde: date
    hasta: date
    huespedes: int
    estado: str = "confirmada"
    total: Decimal = Decimal("300.00")
    expira_en: datetime | None = None
    pms_ref: str = "PMS-REF-01"


# ¤anfitriones
class DobleSeguridad:
    """Doble de seguridad_service."""

    def __init__(self) -> None:
        self.eventos: list[Any] = []
        self.tokens_generados: list[tuple[str, str]] = []

    def tokenizar(self, texto: str, conversacion_id: str = "", titular_hash: str | None = None) -> str:
        token = f"[[TOKEN:tel_{abs(hash(texto)) % 1000000:06d}]]"
        self.tokens_generados.append((texto, token))
        return token

    def auditar(self, evento: Any) -> None:
        self.eventos.append(evento)


# ¤anfitriones
class DobleCanalWhatsApp:
    """Doble de canal_whatsapp_service."""

    def __init__(self) -> None:
        self.plantillas_enviadas: list[tuple[str, Any]] = []

    def enviar_plantilla(self, destinatario: str, plantilla: Any) -> Any:
        self.plantillas_enviadas.append((destinatario, plantilla))
        return None


# ¤anfitriones
class DoblePMS:
    """Doble de pms_conector_service."""

    def __init__(self) -> None:
        self.reservas: dict[str, ReservaDoble] = {}

    def agregar_reserva(self, reserva: ReservaDoble) -> None:
        self.reservas[reserva.codigo] = reserva

    def obtener_reserva(self, codigo: str) -> ReservaDoble:
        from features.pms_conector.tipos import ReservaInexistente
        if codigo not in self.reservas:
            raise ReservaInexistente(f"Reserva con código '{codigo}' no encontrada")
        return self.reservas[codigo]


# ¤anfitriones
class DobleObservabilidad:
    """Doble de observabilidad_service."""

    def __init__(self) -> None:
        self.logs: list[tuple[str, str, Mapping[str, Any]]] = []

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append((nivel, evento, campos))
