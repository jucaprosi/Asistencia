# ¤herramientas-mcp
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala herramientas_glamping (RF-MCP-01..07)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.herramientas_glamping.herramientas_internal import EjecutorHerramientas
from features.herramientas_glamping.tipos import (
    DefinicionHerramienta,
    EntradaInvalida,
    ErrorHerramientas,
    HerramientaDeshabilitada,
    HerramientaNoAutorizada,
    ReservaNoAutorizada,
    ResultadoHerramienta,
    SalaDestinoFallida,
)

__all__ = [
    "DefinicionHerramienta",
    "ResultadoHerramienta",
    "ErrorHerramientas",
    "EntradaInvalida",
    "HerramientaNoAutorizada",
    "HerramientaDeshabilitada",
    "SalaDestinoFallida",
    "ReservaNoAutorizada",
    "HerramientasGlampingService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_herramientas_glamping.yaml")


# ¤herramientas-mcp
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤herramientas-mcp
class HerramientasGlampingService:
    """Cada herramienta valida su entrada, pide autorización a seguridad y llama a la compuerta dueña del dato."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any,
        pms: Any,
        conocimiento: Any,
        crm: Any,
        arm: Any = None,
        comisiones: Any = None,
        anfitriones: Any = None,
        observabilidad: Any = None,
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
        self._ejecutor = EjecutorHerramientas(
            config,
            seguridad=seguridad,
            pms=pms,
            conocimiento=conocimiento,
            crm=crm,
            arm=arm,
            comisiones=comisiones,
            anfitriones=anfitriones,
            observabilidad=observabilidad,
        )

    # ¤herramientas-mcp
    def catalogo_declarado(self) -> tuple[str, ...]:
        """Nombres de herramientas declaradas en la configuración (sin ejecutar nada)."""
        return tuple(str(h.get("nombre")) for h in self._config.get("herramientas", []))

    # ¤herramientas-mcp
    def listar(self, rol: str, propiedad_id: str | None = None) -> tuple[DefinicionHerramienta, ...]:
        """Lista las herramientas habilitadas y autorizadas para el rol consultado."""
        return self._ejecutor.listar(rol, propiedad_id)

    # ¤herramientas-mcp
    def ejecutar(
        self,
        nombre: str,
        entrada: Mapping[str, Any],
        identidad: Any,
        conversacion_id: str,
    ) -> ResultadoHerramienta:
        """Valida argumentos, verifica autorización con seguridad y despacha a la sala correspondiente."""
        return self._ejecutor.ejecutar(nombre, entrada, identidad, conversacion_id)

    # ¤herramientas-mcp
    def esquema(self, nombre: str) -> DefinicionHerramienta:
        """Devuelve la definición y esquemas JSON (entrada y salida) de una herramienta."""
        return self._ejecutor.obtener_definicion(nombre)
