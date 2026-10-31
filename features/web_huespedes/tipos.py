# ¤web-huespedes
# ¤¤frontend-developer
"""Tipos del dominio de la sala web_huespedes."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


# ¤web-huespedes
@dataclass(frozen=True)
class FichaPropiedad:
    propiedad_id: str
    tipo: str
    nombre: str
    zona: str
    capacidad: int
    resumen: str
    comodidades: tuple[str, ...] = field(default_factory=tuple)
    fotos: tuple[str, ...] = field(default_factory=tuple)


# ¤web-huespedes
@dataclass(frozen=True)
class Busqueda:
    desde: date
    hasta: date
    huespedes: int
    tipo: str | None = None
    zona: str | None = None


# ¤web-huespedes
@dataclass(frozen=True)
class OpcionDisponible:
    ficha: FichaPropiedad
    unidad_id: str
    total: Decimal
    moneda: str = "USD"


# ¤web-huespedes
@dataclass(frozen=True)
class EnlaceContacto:
    codigo: str
    propiedad_id: str
    desde: date
    hasta: date
    huespedes: int
