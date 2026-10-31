# ¤pms-conector
# ¤¤integration-engineer
"""Tipos del dominio de la sala pms_conector. Nunca objetos del SDK del proveedor."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


# ¤pms-conector
class TipoPropiedad(str, Enum):
    GLAMPING = "glamping"
    CABANA = "cabana"
    CASA = "casa"
    DEPARTAMENTO = "departamento"
    HABITACION = "habitacion"
    HOSTAL = "hostal"
    HOSTERIA = "hosteria"
    HOTEL = "hotel"
    HACIENDA = "hacienda"
    OTRO = "otro"


# ¤pms-conector
class EstadoReserva(str, Enum):
    PRELIMINAR = "preliminar"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    COMPLETADA = "completada"


# ¤pms-conector
@dataclass(frozen=True)
class Propiedad:
    propiedad_id: str
    tipo: TipoPropiedad
    nombre: str
    zona_id: str
    direccion: str
    activa: bool
    pms_ref: str


# ¤pms-conector
@dataclass(frozen=True)
class Unidad:
    unidad_id: str
    propiedad_id: str
    nombre: str
    capacidad: int


# ¤pms-conector
@dataclass(frozen=True)
class Disponibilidad:
    disponible: bool
    unidades: tuple[Unidad, ...]
    motivo: str | None = None


# ¤pms-conector
@dataclass(frozen=True)
class Cotizacion:
    total: Decimal
    moneda: str
    desglose: tuple[tuple[str, Decimal], ...]
    politica_cancelacion_id: str


# ¤pms-conector
@dataclass(frozen=True)
class Reserva:
    codigo: str
    propiedad_id: str
    unidad_id: str
    huesped_token: str
    desde: date
    hasta: date
    huespedes: int
    estado: EstadoReserva
    total: Decimal
    expira_en: datetime | None
    pms_ref: str


# ¤pms-conector
@dataclass(frozen=True)
class InstruccionesCheckin:
    propiedad: str
    direccion: str
    hora_checkin: str
    acceso: tuple[str, ...]
    wifi_red: str
    wifi_clave_token: str
    normas: tuple[str, ...]
    contacto_emergencia: str


# ¤pms-conector
@dataclass(frozen=True)
class Incidencia:
    incidencia_id: str
    propiedad_id: str
    unidad_id: str | None
    reserva_codigo: str | None
    categoria: str
    prioridad: str
    descripcion_token: str
    estado: str
    gestor_id: str | None
