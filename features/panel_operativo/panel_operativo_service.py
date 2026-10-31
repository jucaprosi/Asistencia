# ¤panel-operativo
# ¤¤frontend-developer
"""Compuerta pública de la sala panel_operativo (RF-PAN-01..10). Fase 0: interfaz; pantallas en TASK-004..007.

El panel no contiene lógica de negocio: cada caso de uso invoca la compuerta de la sala dueña tras autorizar.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.panel_operativo.tipos import EstadoSistema, Sesion, VistaHandoff, VistaVentaPorValidar

__all__ = [
    "EstadoSistema", "Sesion", "VistaHandoff", "VistaVentaPorValidar", "ErrorPanel", "PanelOperativoService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_panel_operativo.yaml")


# ¤panel-operativo
class ErrorPanel(Exception):
    """Error tipado de la sala panel_operativo (CredencialesInvalidas, SesionExpirada, ZonaNoAsignada...)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤panel-operativo
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤panel-operativo
class PanelOperativoService:
    """Casos de uso de la UI del equipo: sesión, ventas, comisiones, Jarvis, handoffs, incidencias, administración."""

    def __init__(
        self, config: Mapping[str, Any], *, seguridad: Any, arm: Any, comisiones: Any, agente: Any, canal: Any,
        crm: Any, pms: Any, conocimiento: Any, observabilidad: Any,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._arm = arm
        self._comisiones = comisiones
        self._agente = agente
        self._canal = canal
        self._crm = crm
        self._pms = pms
        self._conocimiento = conocimiento
        self._observabilidad = observabilidad

    # sesión
    def iniciar_sesion(self, correo: str, codigo_un_uso: str) -> Sesion:
        raise NotImplementedError("TASK-004 RF-PAN-01")

    def cerrar_sesion(self, sesion: Sesion) -> None:
        raise NotImplementedError("TASK-004 RF-PAN-01")

    # ventas y comisiones
    def ventas_por_validar(self, sesion: Sesion, filtros: Mapping[str, Any]) -> tuple[VistaVentaPorValidar, ...]:
        raise NotImplementedError("TASK-006 RF-PAN-02")

    def validar_venta(self, sesion: Sesion, venta_id: str, correcciones: Mapping[str, Any] | None) -> None:
        raise NotImplementedError("TASK-006 RF-PAN-02")

    def rechazar_venta(self, sesion: Sesion, venta_id: str, motivo: str) -> None:
        raise NotImplementedError("TASK-006 RF-PAN-02")

    def detalle_venta(self, sesion: Sesion, venta_id: str) -> Mapping[str, Any]:
        raise NotImplementedError("TASK-006 RF-PAN-03")

    def tablero(self, sesion: Sesion, periodo: str) -> Any:
        raise NotImplementedError("TASK-007 RF-PAN-04")

    def cerrar_periodo(self, sesion: Sesion, periodo: str) -> Any:
        raise NotImplementedError("TASK-007 RF-PAN-05")

    def exportar_periodo(self, sesion: Sesion, periodo: str, formato: str) -> bytes:
        raise NotImplementedError("TASK-007 RF-PAN-05")

    def preguntar_jarvis(self, sesion: Sesion, pregunta: str, conversacion_id: str) -> str:
        raise NotImplementedError("TASK-006 RF-PAN-06")

    # conversaciones
    def handoffs(self, sesion: Sesion) -> tuple[VistaHandoff, ...]:
        raise NotImplementedError("TASK-004 RF-PAN-07")

    def tomar_handoff(self, sesion: Sesion, conversacion_id: str) -> None:
        raise NotImplementedError("TASK-004 RF-PAN-07")

    def responder(self, sesion: Sesion, conversacion_id: str, texto: str) -> None:
        raise NotImplementedError("TASK-004 RF-PAN-07")

    def devolver_al_asistente(self, sesion: Sesion, conversacion_id: str) -> None:
        raise NotImplementedError("TASK-004 RF-PAN-07")

    def incidencias(self, sesion: Sesion, filtros: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        raise NotImplementedError("TASK-004 RF-PAN-08")

    def resolver_incidencia(self, sesion: Sesion, incidencia_id: str, nota: str) -> None:
        raise NotImplementedError("TASK-004 RF-PAN-08")

    # administración
    def whitelist(self, sesion: Sesion) -> tuple[Mapping[str, Any], ...]:
        raise NotImplementedError("TASK-005 RF-PAN-09")

    def editar_whitelist(self, sesion: Sesion, numero: str, rol: str, alta: bool) -> None:
        raise NotImplementedError("TASK-005 RF-PAN-09")

    def propiedades(self, sesion: Sesion) -> tuple[Any, ...]:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def reglas_comision(self, sesion: Sesion) -> tuple[Any, ...]:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def crear_regla_comision(self, sesion: Sesion, regla: Mapping[str, Any]) -> Any:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def plantillas(self, sesion: Sesion) -> tuple[Mapping[str, Any], ...]:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def conocimiento(self, sesion: Sesion) -> tuple[Any, ...]:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def reindexar(self, sesion: Sesion) -> Any:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def auditoria(self, sesion: Sesion, filtros: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
        raise NotImplementedError("TASK-005 RF-PAN-09")

    def estado_sistema(self, sesion: Sesion) -> EstadoSistema:
        raise NotImplementedError("TASK-005 RF-PAN-09")
