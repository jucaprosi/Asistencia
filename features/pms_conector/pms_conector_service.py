# ¤pms-conector
# ¤¤integration-engineer
"""Compuerta pública de la sala pms_conector (RF-PMS-01..04). Fase 0: interfaz; lógica y FakePMS en TASK-003."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.pms_conector.tipos import (
    Cotizacion, Disponibilidad, EstadoReserva, Incidencia, InstruccionesCheckin, Propiedad, Reserva, TipoPropiedad,
    Unidad,
)

__all__ = [
    "Cotizacion", "Disponibilidad", "EstadoReserva", "Incidencia", "InstruccionesCheckin", "Propiedad", "Reserva",
    "TipoPropiedad", "Unidad", "ErrorPMS", "PMSConectorService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_pms_conector.yaml")


# ¤pms-conector
class ErrorPMS(Exception):
    """Error tipado de la sala pms_conector (PMSNoDisponible, SinDisponibilidad, EscrituraDeshabilitada...)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤pms-conector
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤pms-conector
class PMSConectorService:
    """Lecturas libres; escrituras deshabilitadas por defecto y con clave de idempotencia."""

    def __init__(self, config: Mapping[str, Any], *, observabilidad: Any) -> None:
        self._config = config
        self._observabilidad = observabilidad

    def proveedor(self) -> str:
        return str(self._config.get("proveedor", "fake"))

    def listar_propiedades(self) -> tuple[Propiedad, ...]:
        raise NotImplementedError("TASK-003 RF-PMS-01")

    def consultar_disponibilidad(self, propiedad_id: str, desde: date, hasta: date, huespedes: int) -> Disponibilidad:
        raise NotImplementedError("TASK-003 RF-PMS-01")

    def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int) -> Cotizacion:
        raise NotImplementedError("TASK-003 RF-PMS-01")

    def crear_reserva_preliminar(
        self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int, huesped_token: str,
        clave_idempotencia: str,
    ) -> Reserva:
        raise NotImplementedError("TASK-003 RF-PMS-02")

    def confirmar_reserva(self, codigo: str, clave_idempotencia: str) -> Reserva:
        raise NotImplementedError("T-212 RF-PMS-07")

    def guardar_tarifas(self, unidad_id: str, desde: date, hasta: date, precio: Any, minimo_noches: int, actor_id: str) -> int:
        raise NotImplementedError("T-212 RF-PMS-08")

    def actualizar_calendario(self, unidad_id: str, desde: date, hasta: date, accion: str, actor_id: str) -> tuple[int, int]:
        raise NotImplementedError("T-212 RF-PMS-08")

    def obtener_reserva(self, codigo: str) -> Reserva:
        raise NotImplementedError("TASK-003 RF-PMS-01")

    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]:
        raise NotImplementedError("TASK-003 RF-PMS-01")

    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva:
        raise NotImplementedError("TASK-003 RF-PMS-02")

    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin:
        raise NotImplementedError("TASK-003 RF-MCP-04")

    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia:
        raise NotImplementedError("TASK-003 RF-MCP-05")

    def registrar_tarea_housekeeping(
        self, propiedad_id: str, unidad_id: str, fecha: date, nota: str, clave_idempotencia: str,
    ) -> str:
        raise NotImplementedError("TASK-003 RF-PMS-01")
