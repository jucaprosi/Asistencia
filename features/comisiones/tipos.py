# ¤comisiones
# ¤¤backend-developer
"""Tipos del dominio de la sala comisiones."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping


# ¤comisiones
class TipoRegla(str, Enum):
    PORCENTAJE = "porcentaje"
    FIJO = "fijo"
    ESCALONADA = "escalonada"


# ¤comisiones
class EstadoComision(str, Enum):
    ESTIMADA = "estimada"
    FIJADA = "fijada"
    PAGADA = "pagada"
    AJUSTADA = "ajustada"


# ¤comisiones
@dataclass(frozen=True)
class Escalon:
    desde_monto: Decimal
    porcentaje: Decimal


# ¤comisiones
@dataclass(frozen=True)
class ReglaComision:
    regla_id: str
    version: int
    tipo: TipoRegla
    valor: Decimal
    vigente_desde: date
    vigente_hasta: date | None = None
    vendedor_id: str | None = None
    propiedad_id: str | None = None
    producto_patron: str | None = None
    escalones: tuple[Escalon, ...] = field(default_factory=tuple)


# ¤comisiones
@dataclass(frozen=True)
class Comision:
    comision_id: str
    venta_id: str
    regla_id: str
    regla_version: int
    monto: Decimal
    periodo_id: str
    estado: EstadoComision
    ajuste_de: str | None = None
    base_acumulada: Decimal = Decimal("0")
    periodo_origen: str | None = None


# ¤comisiones
@dataclass(frozen=True)
class Periodo:
    periodo_id: str
    cerrado_en: datetime | None = None
    cerrado_por: str | None = None
    resumen: Mapping[str, Any] = field(default_factory=dict)
