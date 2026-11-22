# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio y excepciones de la sala pms_conector. Nunca objetos del SDK del proveedor."""
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
    EXPIRADA = "expirada"
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
    prompt_variante: str = "glamping"


# ¤pms-conector
@dataclass(frozen=True)
class Unidad:
    unidad_id: str
    propiedad_id: str
    nombre: str
    capacidad: int
    edificio: str | None = None
    piso: str | None = None
    acceso_ref: str | None = None
    wifi_ref: str | None = None


# ¤pms-conector
@dataclass(frozen=True)
class Disponibilidad:
    disponible: bool
    unidades: tuple[Unidad, ...]
    motivo: str | None = None
    alternativas: tuple[tuple[str, date, date], ...] = ()


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


# ¤pms-conector
@dataclass(frozen=True)
class TareaHousekeeping:
    tarea_id: str
    propiedad_id: str
    unidad_id: str
    fecha: date
    nota: str
    estado: str = "pendiente"


# ¤pms-conector
class ErrorPMS(Exception):
    """Error base de la sala pms_conector."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤pms-conector
class PMSNoDisponible(ErrorPMS):
    def __init__(self, mensaje: str = "El servicio de reservas no está disponible", detalle_tecnico: str | None = None) -> None:
        super().__init__("PMSNoDisponible", mensaje, detalle_tecnico)


# ¤pms-conector
class PropiedadInexistente(ErrorPMS):
    def __init__(self, mensaje: str = "La propiedad solicitada no existe", detalle_tecnico: str | None = None) -> None:
        super().__init__("PropiedadInexistente", mensaje, detalle_tecnico)


# ¤pms-conector
class UnidadInexistente(ErrorPMS):
    def __init__(self, mensaje: str = "La unidad solicitada no existe", detalle_tecnico: str | None = None) -> None:
        super().__init__("UnidadInexistente", mensaje, detalle_tecnico)


# ¤pms-conector
class FechasInvalidas(ErrorPMS):
    def __init__(self, mensaje: str = "Rango de fechas inválido para la consulta o reserva", detalle_tecnico: str | None = None) -> None:
        super().__init__("FechasInvalidas", mensaje, detalle_tecnico)


# ¤pms-conector
class SinDisponibilidad(ErrorPMS):
    def __init__(self, mensaje: str = "No hay disponibilidad para las fechas solicitadas", detalle_tecnico: str | None = None) -> None:
        super().__init__("SinDisponibilidad", mensaje, detalle_tecnico)


# ¤pms-conector
class EscrituraDeshabilitada(ErrorPMS):
    def __init__(self, mensaje: str = "Operación de escritura deshabilitada por configuración", detalle_tecnico: str | None = None) -> None:
        super().__init__("EscrituraDeshabilitada", mensaje, detalle_tecnico)


# ¤pms-conector
class ReservaInexistente(ErrorPMS):
    def __init__(self, mensaje: str = "La reserva indicada no fue encontrada", detalle_tecnico: str | None = None) -> None:
        super().__init__("ReservaInexistente", mensaje, detalle_tecnico)


# ¤pms-conector
class IdempotenciaRequerida(ErrorPMS):
    def __init__(self, mensaje: str = "Esta operación de escritura requiere una clave de idempotencia única", detalle_tecnico: str | None = None) -> None:
        super().__init__("IdempotenciaRequerida", mensaje, detalle_tecnico)


# ¤pms-conector
class CapacidadExcedida(ErrorPMS):
    def __init__(self, mensaje: str = "El número de huéspedes excede la capacidad máxima de la unidad", detalle_tecnico: str | None = None) -> None:
        super().__init__("CapacidadExcedida", mensaje, detalle_tecnico)


# ¤pms-conector
class AislamientoAnfitrionError(ErrorPMS):
    def __init__(self, mensaje: str = "El anfitrión no tiene permisos sobre la unidad indicada", detalle_tecnico: str | None = None) -> None:
        super().__init__("AislamientoAnfitrionError", mensaje, detalle_tecnico)

