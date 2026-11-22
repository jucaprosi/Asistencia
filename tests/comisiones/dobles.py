# ¤comisiones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Dobles de prueba para la sala comisiones (seguridad y observabilidad)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ¤comisiones
@dataclass(frozen=True)
class VeredictoDoble:
    permitido: bool = True
    motivo: str | None = None


# ¤comisiones
class DobleSeguridad:
    """Doble de seguridad para pruebas de comisiones."""

    def __init__(self) -> None:
        self.autorizaciones: list[tuple[Any, str, str]] = []
        self.auditorias: list[tuple[Any, str, str, Any]] = []

    def autorizar(self, actor: Any, accion: str, recurso: str) -> VeredictoDoble:
        self.autorizaciones.append((actor, accion, recurso))
        return VeredictoDoble(permitido=True)

    def auditar(self, actor: Any, accion: str, recurso: str, detalle: Any = None) -> None:
        self.auditorias.append((actor, accion, recurso, detalle))


# ¤comisiones
class DobleObservabilidad:
    """Doble de observabilidad para registrar eventos y trazas."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def registrar_evento(self, nombre: str, datos: dict[str, Any]) -> None:
        self.eventos.append((nombre, datos))
