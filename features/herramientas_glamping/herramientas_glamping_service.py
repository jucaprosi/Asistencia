# ¤herramientas-mcp
# ¤¤backend-developer
"""Compuerta pública de la sala herramientas_glamping (RF-MCP-01..09). Fase 0: interfaz; herramientas en TASK-003 y TASK-006."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.herramientas_glamping.tipos import DefinicionHerramienta, ResultadoHerramienta

__all__ = [
    "DefinicionHerramienta", "ResultadoHerramienta", "ErrorHerramientas", "HerramientasGlampingService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_herramientas_glamping.yaml")


# ¤herramientas-mcp
class ErrorHerramientas(Exception):
    """Error tipado de la sala herramientas_glamping (EntradaInvalida, HerramientaNoAutorizada, SalaDestinoFallida)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤herramientas-mcp
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤herramientas-mcp
class HerramientasGlampingService:
    """Cada herramienta valida su entrada, pide autorización a seguridad y llama a la compuerta dueña del dato."""

    def __init__(
        self, config: Mapping[str, Any], *, seguridad: Any, pms: Any, conocimiento: Any, crm: Any, arm: Any,
        comisiones: Any, anfitriones: Any, observabilidad: Any,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._pms = pms
        self._conocimiento = conocimiento
        self._crm = crm
        self._anfitriones = anfitriones
        self._arm = arm
        self._comisiones = comisiones
        self._observabilidad = observabilidad

    def catalogo_declarado(self) -> tuple[str, ...]:
        """Nombres de herramientas declaradas en la configuración (sin ejecutar nada)."""
        return tuple(str(h.get("nombre")) for h in self._config.get("herramientas", []))

    def listar(self, rol: str, propiedad_id: str | None) -> tuple[DefinicionHerramienta, ...]:
        raise NotImplementedError("TASK-003 RF-MCP")

    def ejecutar(
        self, nombre: str, entrada: Mapping[str, Any], identidad: Any, conversacion_id: str,
    ) -> ResultadoHerramienta:
        raise NotImplementedError("TASK-003 RF-MCP")

    def esquema(self, nombre: str) -> DefinicionHerramienta:
        raise NotImplementedError("TASK-003 RF-MCP")
