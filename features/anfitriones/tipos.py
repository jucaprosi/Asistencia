# ¤anfitriones
# ¤¤backend-developer
"""Tipos del dominio de la sala anfitriones."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


# ¤anfitriones
class EstadoAnfitrion(str, Enum):
    ACTIVO = "activo"
    SUSPENDIDO = "suspendido"


# ¤anfitriones
class EstadoHospedaje(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    PAUSADO = "pausado"


# ¤anfitriones
class EstadoSolicitud(str, Enum):
    SOLICITADA = "solicitada"
    CONFIRMADA = "confirmada"
    RECHAZADA = "rechazada"
    EXPIRADA = "expirada"
    CANCELADA = "cancelada"
    NO_SHOW = "no_show"
    COMPLETADA = "completada"


# ¤anfitriones
class EstadoCuenta(str, Enum):
    EMITIDO = "emitido"
    PAGADO = "pagado"
    VENCIDO = "vencido"


# ¤anfitriones
@dataclass(frozen=True)
class Anfitrion:
    anfitrion_id: str
    nombre_comercial: str
    comision_porcentaje: Decimal
    terminos_version: str
    estado: EstadoAnfitrion = EstadoAnfitrion.ACTIVO


# ¤anfitriones
@dataclass(frozen=True)
class Hospedaje:
    propiedad_id: str
    anfitrion_id: str
    estado: EstadoHospedaje


# ¤anfitriones
@dataclass(frozen=True)
class Solicitud:
    solicitud: str
    codigo_reserva: str
    propiedad_id: str
    anfitrion_id: str
    desde: date
    hasta: date
    total: Decimal
    comision_porcentaje: Decimal
    estado: EstadoSolicitud
    vence_en: datetime


# ¤anfitriones
@dataclass(frozen=True)
class LineaCuenta:
    solicitud: str
    base: Decimal
    porcentaje: Decimal
    comision: Decimal
    tipo: str = "cargo"


# ¤anfitriones
@dataclass(frozen=True)
class EstadoDeCuenta:
    estado_cuenta_id: str
    anfitrion_id: str
    periodo: str
    total: Decimal
    estado: EstadoCuenta
    vence_en: date
    lineas: tuple[LineaCuenta, ...] = field(default_factory=tuple)
