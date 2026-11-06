# ¤anfitriones
# ¤¤backend-developer
"""Compuerta pública de la sala anfitriones (RF-ANF-01..08): publicación, solicitudes y comisión de plataforma."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.anfitriones.estado_cuenta_internal import GestorEstadoCuenta
from features.anfitriones.persistencia_internal import PersistenciaAnfitriones
from features.anfitriones.registro_internal import GestorRegistro
from features.anfitriones.solicitudes_internal import GestorSolicitudes
from features.anfitriones.tipos import (
    Anfitrion,
    EstadoAnfitrion,
    EstadoCuenta,
    EstadoDeCuenta,
    EstadoHospedaje,
    EstadoSolicitud,
    Hospedaje,
    LineaCuenta,
    Solicitud,
)

__all__ = [
    "Anfitrion",
    "EstadoAnfitrion",
    "EstadoCuenta",
    "EstadoDeCuenta",
    "EstadoHospedaje",
    "EstadoSolicitud",
    "Hospedaje",
    "LineaCuenta",
    "Solicitud",
    "ErrorAnfitriones",
    "AnfitrionesService",
    "cargar_config",
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

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any = None,
        canal: Any = None,
        pms: Any = None,
        observabilidad: Any = None,
        persistencia: PersistenciaAnfitriones | None = None,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._canal = canal
        self._pms = pms
        self._observabilidad = observabilidad
        self._persistencia = persistencia or PersistenciaAnfitriones()

        self._gestor_registro = GestorRegistro(
            persistencia=self._persistencia,
            seguridad=self._seguridad,
            observabilidad=self._observabilidad,
        )
        self._gestor_solicitudes = GestorSolicitudes(
            persistencia=self._persistencia,
            config=self._config,
            pms=self._pms,
            canal=self._canal,
            seguridad=self._seguridad,
            observabilidad=self._observabilidad,
        )
        self._gestor_estado_cuenta = GestorEstadoCuenta(
            persistencia=self._persistencia,
            config=self._config,
            seguridad=self._seguridad,
            canal=self._canal,
            observabilidad=self._observabilidad,
        )

    def registrar_anfitrion(self, anfitrion: Anfitrion, telefono_token: str, actor_id: str) -> Anfitrion:
        """RF-ANF-01: Alta de anfitrión con versión de términos y porcentaje pactado."""
        return self._gestor_registro.registrar_anfitrion(anfitrion, telefono_token, actor_id)

    def guardar_hospedaje(self, hospedaje: Hospedaje, actor_id: str) -> Hospedaje:
        """RF-ANF-02: Publicación revisada (borrador, publicado, pausado)."""
        return self._gestor_registro.guardar_hospedaje(hospedaje, actor_id)

    def publicados(self) -> tuple[Hospedaje, ...]:
        """RF-ANF-02, INV_SOLO_PUBLICADO: solo hospedajes publicados de anfitriones activos."""
        return self._gestor_registro.publicados()

    def solicitar_reserva(self, codigo_reserva: str) -> Solicitud:
        """RF-ANF-04: Solicitud de reserva preliminar con código PL- y fechas/total del PMS."""
        return self._gestor_solicitudes.solicitar_reserva(codigo_reserva)

    def responder_solicitud(self, solicitud: str, anfitrion_id: str, acepta: bool, motivo: str | None = None) -> Solicitud:
        """RF-ANF-05: Confirma o rechaza. Entrega contacto solo si confirma (INV_CONTACTO_TRAS_CONFIRMAR)."""
        return self._gestor_solicitudes.responder_solicitud(solicitud, anfitrion_id, acepta, motivo=motivo)

    def reportar_resultado(
        self,
        solicitud: str,
        anfitrion_id: str,
        resultado: EstadoSolicitud | str,
        ahora_fecha: date | None = None,
    ) -> Solicitud:
        """RF-ANF-06: Reporta cancelada o no_show hasta 3 días tras la salida. No generan comisión."""
        return self._gestor_solicitudes.reportar_resultado(
            solicitud,
            anfitrion_id,
            resultado,
            ahora_fecha=ahora_fecha,
        )

    def expirar_solicitudes_vencidas(self, ahora: datetime | None = None) -> tuple[Solicitud, ...]:
        """Proceso periódico que pasa a expiradas las solicitudes sin respuesta."""
        return self._gestor_solicitudes.expirar_solicitudes_vencidas(ahora)

    def procesar_estadias_completadas(self, ahora_fecha: date | None = None) -> tuple[Solicitud, ...]:
        """Proceso diario que completa las estadías confirmadas cuyo plazo de reporte venció."""
        return self._gestor_solicitudes.procesar_estadias_completadas(ahora_fecha)

    def cerrar_periodo(self, periodo: str, ahora: datetime | None = None) -> tuple[EstadoDeCuenta, ...]:
        """RF-ANF-07: Cierre mensual el día 5 agrupando estadías completadas."""
        return self._gestor_estado_cuenta.cerrar_periodo(periodo, ahora=ahora)

    def estado_de_cuenta(self, anfitrion_id: str, periodo: str, actor_id: str | None = None) -> EstadoDeCuenta:
        """RF-ANF-07: Consulta el estado de cuenta mensual con aislamiento de anfitrión."""
        return self._gestor_estado_cuenta.estado_de_cuenta(anfitrion_id, periodo, actor_id=actor_id)

    def registrar_pago(self, estado_cuenta_id: str, actor_id: str, ahora: datetime | None = None) -> EstadoDeCuenta:
        """RF-ANF-08: El administrador registra el pago guardando actor y fecha."""
        return self._gestor_estado_cuenta.registrar_pago(estado_cuenta_id, actor_id, ahora=ahora)

    def agregar_ajuste(
        self,
        anfitrion_id: str,
        periodo: str,
        solicitud: str,
        comision: Decimal,
        base: Decimal = Decimal("0.00"),
        porcentaje: Decimal = Decimal("0.00"),
        actor_id: str = "admin",
    ) -> LineaCuenta:
        """RF-ANF-07: Registra una línea de corrección posterior como ajuste en el período abierto."""
        return self._gestor_estado_cuenta.agregar_ajuste(
            anfitrion_id=anfitrion_id,
            periodo=periodo,
            solicitud=solicitud,
            comision=comision,
            base=base,
            porcentaje=porcentaje,
            actor_id=actor_id,
        )

    def procesar_cuentas_vencidas(self, ahora_fecha: date | None = None) -> tuple[str, ...]:
        """RF-ANF-08: Proceso diario que marca cuentas vencidas y pausa hospedajes tras 15 días."""
        return self._gestor_estado_cuenta.procesar_cuentas_vencidas(ahora_fecha=ahora_fecha)

    def consultar_estado_cuenta(self, anfitrion_id: str, periodo: str, actor_id: str | None = None) -> dict[str, Any]:
        """RF-ANF-07: Atiende consulta del estado de cuenta."""
        return self._gestor_estado_cuenta.consultar_estado_cuenta(anfitrion_id, periodo, actor_id=actor_id)
