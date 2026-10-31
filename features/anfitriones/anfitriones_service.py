# ¤anfitriones
# ¤¤backend-developer
"""Compuerta pública de la sala anfitriones (RF-ANF-01..08): publicación, solicitudes y comisión de plataforma."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.anfitriones.tipos import (
    Anfitrion, EstadoAnfitrion, EstadoCuenta, EstadoDeCuenta, EstadoHospedaje, EstadoSolicitud, Hospedaje, LineaCuenta,
    Solicitud,
)

__all__ = [
    "Anfitrion", "EstadoAnfitrion", "EstadoCuenta", "EstadoDeCuenta", "EstadoHospedaje", "EstadoSolicitud", "Hospedaje",
    "LineaCuenta", "Solicitud", "ErrorAnfitriones", "AnfitrionesService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_anfitriones.yaml")


# ¤anfitriones
class ErrorAnfitriones(Exception):
    """Error tipado: el usuario ve solo mensaje_usuario."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(detalle_tecnico or mensaje_usuario)
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤anfitriones
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


# ¤anfitriones
class AnfitrionesService:
    """Dueña de anfitrión, publicación, solicitud de reserva y comisión de plataforma."""

    def __init__(self, config: Mapping[str, Any], *, seguridad: Any, canal: Any, pms: Any, observabilidad: Any) -> None:
        self._config = config
        self._seguridad = seguridad
        self._canal = canal
        self._pms = pms
        self._observabilidad = observabilidad

    def registrar_anfitrion(self, anfitrion: Anfitrion, telefono_token: str, actor_id: str) -> Anfitrion:
        raise NotImplementedError("T-305 RF-ANF-01")

    def guardar_hospedaje(self, hospedaje: Hospedaje, actor_id: str) -> Hospedaje:
        raise NotImplementedError("T-305 RF-ANF-02")

    def publicados(self) -> tuple[Hospedaje, ...]:
        raise NotImplementedError("T-305 RF-ANF-03")

    def solicitar_reserva(self, codigo_reserva: str) -> Solicitud:
        raise NotImplementedError("T-305 RF-ANF-04")

    def responder_solicitud(self, solicitud: str, anfitrion_id: str, acepta: bool, motivo: str | None) -> Solicitud:
        raise NotImplementedError("T-305 RF-ANF-05")

    def reportar_resultado(self, solicitud: str, anfitrion_id: str, resultado: EstadoSolicitud) -> Solicitud:
        raise NotImplementedError("T-305 RF-ANF-06")

    def cerrar_periodo(self, periodo: str) -> tuple[EstadoDeCuenta, ...]:
        raise NotImplementedError("T-506 RF-ANF-07")

    def estado_de_cuenta(self, anfitrion_id: str, periodo: str) -> EstadoDeCuenta:
        raise NotImplementedError("T-506 RF-ANF-07")

    def registrar_pago(self, estado_cuenta_id: str, actor_id: str) -> EstadoDeCuenta:
        raise NotImplementedError("T-506 RF-ANF-08")
