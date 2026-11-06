# ¤pms-conector
# ¤¤integration-engineer
"""Interfaz abstracta canónica del conector PMS (RF-PMS-01).

Define el contrato puro que cualquier proveedor (FakePMS, plataforma local, etc.)
debe implementar, usando únicamente tipos propios del dominio y jamás objetos de SDKs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from features.pms_conector.tipos import (
    Cotizacion,
    Disponibilidad,
    Incidencia,
    InstruccionesCheckin,
    Propiedad,
    Reserva,
)


# ¤pms-conector
class PMSConnector(ABC):
    """Contrato base para interactuar con sistemas de gestión de propiedades y calendarios."""

    @abstractmethod
    def listar_propiedades(self) -> tuple[Propiedad, ...]:
        """Retorna las propiedades registradas y activas."""
        raise NotImplementedError

    @abstractmethod
    def consultar_disponibilidad(
        self, propiedad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Disponibilidad:
        """Verifica disponibilidad y devuelve unidades aptas o alternativas."""
        raise NotImplementedError

    @abstractmethod
    def cotizar(
        self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Cotizacion:
        """Calcula el total y desglose de precio para la estancia solicitada."""
        raise NotImplementedError

    @abstractmethod
    def crear_reserva_preliminar(
        self,
        propiedad_id: str,
        unidad_id: str,
        desde: date,
        hasta: date,
        huespedes: int,
        huesped_token: str,
        clave_idempotencia: str,
    ) -> Reserva:
        """Bloquea temporalmente las fechas (vigencia 24h) y crea la reserva preliminar."""
        raise NotImplementedError

    @abstractmethod
    def confirmar_reserva(self, codigo: str, clave_idempotencia: str) -> Reserva:
        """Confirma una reserva preliminar vigente tras aceptación del anfitrión."""
        raise NotImplementedError

    @abstractmethod
    def obtener_reserva(self, codigo: str) -> Reserva:
        """Consulta el estado y datos de una reserva por su código identificador."""
        raise NotImplementedError

    @abstractmethod
    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]:
        """Obtiene todas las reservas con check-in programado para la fecha indicada."""
        raise NotImplementedError

    @abstractmethod
    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva:
        """Cancela una reserva y libera las fechas en el calendario."""
        raise NotImplementedError

    @abstractmethod
    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin:
        """Retorna las instrucciones de acceso, wifi tokenizado y normas para huéspedes confirmados."""
        raise NotImplementedError

    @abstractmethod
    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia:
        """Registra una incidencia de mantenimiento o soporte con identificador único."""
        raise NotImplementedError

    @abstractmethod
    def registrar_tarea_housekeeping(
        self,
        propiedad_id: str,
        unidad_id: str,
        fecha: date,
        nota: str,
        clave_idempotencia: str,
    ) -> str:
        """Crea una tarea de limpieza o mantenimiento preventivo."""
        raise NotImplementedError

    @abstractmethod
    def guardar_tarifas(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        precio: Decimal,
        minimo_noches: int,
        actor_id: str,
    ) -> int:
        """Establece las tarifas por noche para la unidad y rango de fechas."""
        raise NotImplementedError

    @abstractmethod
    def actualizar_calendario(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        accion: str,
        actor_id: str,
    ) -> tuple[int, int]:
        """Bloquea o libera fechas en el calendario. Retorna (noches_procesadas, omitidas)."""
        raise NotImplementedError
