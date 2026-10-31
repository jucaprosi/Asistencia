# ¤observabilidad
# ¤¤devops-engineer
"""Tipos del dominio de la sala observabilidad."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Mapping


# ¤observabilidad
@dataclass(frozen=True)
class Span:
    span_id: str
    traza_id: str
    sala: str
    nombre: str
    inicio: datetime
    duracion_ms: int
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
