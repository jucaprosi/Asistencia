# ¤observabilidad
# ¤¤devops-engineer
"""Compuerta pública de la sala observabilidad (RF-OBS-01..04). Fase 0: interfaz; lógica en TASK-001 y TASK-005."""
from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.observabilidad.tipos import Alerta, Metrica, Span, Traza

__all__ = ["Alerta", "Metrica", "Span", "Traza", "ErrorObservabilidad", "ObservabilidadService", "cargar_config"]

RUTA_CONFIG = Path(__file__).with_name("config_observabilidad.yaml")


# ¤observabilidad
class ErrorObservabilidad(Exception):
    """Error tipado de la sala observabilidad (TrazaDesconocida, LogConPII, SuiteNoEncontrada)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤observabilidad
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤observabilidad
class ObservabilidadService:
    """Base de todas las métricas del PRD: una traza por mensaje con spans por sala y por llamada al modelo."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self._config = config

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str:
        raise NotImplementedError("TASK-001 RF-OBS-02")

    def span(self, traza_id: str, sala: str, nombre: str) -> AbstractContextManager[Span]:
        raise NotImplementedError("TASK-001 RF-OBS-02")

    def cerrar_traza(self, traza_id: str, resultado: str) -> Traza:
        raise NotImplementedError("TASK-001 RF-OBS-02")

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        raise NotImplementedError("TASK-001 RF-OBS-01")

    def metricas(self, ventana: str = "7d") -> tuple[Metrica, ...]:
        raise NotImplementedError("TASK-005 RF-OBS-02")

    def evaluar(
        self, suites: tuple[str, ...] = ("rag", "ventas", "inyecciones", "enrutador"),
    ) -> Mapping[str, Mapping[str, float]]:
        raise NotImplementedError("TASK-005 RF-OBS-03")

    def alertas_activas(self) -> tuple[Alerta, ...]:
        raise NotImplementedError("TASK-005 RF-OBS-04")
