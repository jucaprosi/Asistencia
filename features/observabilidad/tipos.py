# ¤observabilidad
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio y errores de la sala observabilidad."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Mapping

__all__ = [
    "Span",
    "Traza",
    "Metrica",
    "Alerta",
    "ErrorObservabilidad",
    "TrazaDesconocida",
    "LogConPII",
    "SuiteNoEncontrada",
]


# ¤observabilidad
@dataclass(frozen=True)
class Span:
    span_id: str
    traza_id: str
    sala: str
    nombre: str
    inicio: datetime
    duracion_ms: int
    modelo: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    costo_usd: Decimal | None = None
    atributos: Mapping[str, Any] = field(default_factory=dict)


# ¤observabilidad
@dataclass(frozen=True)
class Traza:
    traza_id: str
    mensaje_id: str | None
    conversacion_id: str | None
    canal: str
    inicio: datetime
    fin: datetime | None = None
    resultado: str | None = None
    spans: tuple[Span, ...] = field(default_factory=tuple)


# ¤observabilidad
@dataclass(frozen=True)
class Metrica:
    nombre: str
    valor: float
    unidad: str
    ventana: str
    calculada_en: datetime


# ¤observabilidad
@dataclass(frozen=True)
class Alerta:
    nombre: str
    severidad: Literal["aviso", "critica"]
    mensaje: str
    disparada_en: datetime


# ¤observabilidad
class ErrorObservabilidad(Exception):
    """Error base tipado de la sala observabilidad."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤observabilidad
class TrazaDesconocida(ErrorObservabilidad):
    """La traza solicitada no existe o no ha sido iniciada."""

    def __init__(self, traza_id: str) -> None:
        super().__init__(
            codigo="traza_desconocida",
            mensaje_usuario=f"La traza '{traza_id}' no existe en el registro.",
            detalle_tecnico=f"Traza ID {traza_id} no encontrada",
        )
        self.traza_id = traza_id


# ¤observabilidad
class LogConPII(ErrorObservabilidad):
    """El registro de log fue rechazado por contener PII en claro (INV_PII_FUERA_DEL_MODELO)."""

    def __init__(self, motivo: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="log_con_pii",
            mensaje_usuario="El log contiene información personal identificable en claro y fue rechazado.",
            detalle_tecnico=detalle_tecnico or motivo,
        )
        self.motivo = motivo


# ¤observabilidad
class SuiteNoEncontrada(ErrorObservabilidad):
    """La suite de evaluación solicitada no existe."""

    def __init__(self, suite: str) -> None:
        super().__init__(
            codigo="suite_no_encontrada",
            mensaje_usuario=f"La suite de evaluación '{suite}' no está configurada.",
            detalle_tecnico=f"Suite {suite} desconocida",
        )
        self.suite = suite
