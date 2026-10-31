# ¤herramientas-mcp
# ¤¤backend-developer
"""Tipos del dominio de la sala herramientas_glamping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


# ¤herramientas-mcp
@dataclass(frozen=True)
class DefinicionHerramienta:
    nombre: str
    descripcion: str
    esquema_entrada: Mapping[str, Any]
    esquema_salida: Mapping[str, Any]
    roles: tuple[str, ...]
    sala_destino: str


# ¤herramientas-mcp
@dataclass(frozen=True)
class ResultadoHerramienta:
    nombre: str
    salida: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    duracion_ms: int = 0
