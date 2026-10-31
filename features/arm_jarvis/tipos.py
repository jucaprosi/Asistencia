# ¤arm-jarvis
# ¤¤backend-developer
"""Tipos del dominio de la sala arm_jarvis."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


# ¤arm-jarvis
class EstadoVenta(str, Enum):
    POR_VALIDAR = "por_validar"
    VALIDADA = "validada"
    RECHAZADA = "rechazada"
    PUBLICADA = "publicada"
    NO_PUBLICADA = "no_publicada"
    ANULADA = "anulada"


# ¤arm-jarvis
@dataclass(frozen=True)
class Vendedor:
    vendedor_id: str
    telefono_token: str
    nombre: str
    activo: bool
    regla_comision_default_id: str | None = None


# ¤arm-jarvis
@dataclass(frozen=True)
class VentaExtraida:
    cliente_token: str | None
    telefono_cliente_token: str | None
    producto: str | None
    propiedad_id: str | None
    monto: Decimal | None
    moneda: str
    fecha_venta: date | None
    confianza: float
    campos_faltantes: tuple[str, ...] = ()
    es_venta: bool = True


# ¤arm-jarvis
@dataclass(frozen=True)
class Venta:
    venta_id: str
    ticket: str
    vendedor_id: str
    extraida: VentaExtraida
    texto_original_token: str
    estado: EstadoVenta
    creada: datetime
    actualizada: datetime
    comision_estimada: Decimal | None = None
    comision_fijada: Decimal | None = None
    reserva_ref: str | None = None


# ¤arm-jarvis
@dataclass(frozen=True)
class Transicion:
    venta_id: str
    de: EstadoVenta
    a: EstadoVenta
    actor_id: str
    rol: str
    motivo: str | None
    timestamp: datetime


# ¤arm-jarvis
@dataclass(frozen=True)
class ResumenComision:
    vendedor_id: str
    periodo: str
    validada: Decimal
    pendiente: Decimal
    ventas: int


# ¤arm-jarvis
@dataclass(frozen=True)
class Tablero:
    periodo: str
    ventas_por_mes: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
    ventas_por_vendedor: tuple[tuple[str, Decimal, int], ...] = field(default_factory=tuple)
    ventas_por_propiedad: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
    comisiones_validadas: Decimal = Decimal("0")
    comisiones_pendientes: Decimal = Decimal("0")
    por_validar: int = 0
