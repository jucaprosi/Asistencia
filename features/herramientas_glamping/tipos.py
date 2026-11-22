# ¤herramientas-mcp
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio y errores de la sala herramientas_glamping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "DefinicionHerramienta",
    "ResultadoHerramienta",
    "ErrorHerramientas",
    "EntradaInvalida",
    "HerramientaNoAutorizada",
    "HerramientaDeshabilitada",
    "SalaDestinoFallida",
    "ReservaNoAutorizada",
]


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


# ¤herramientas-mcp
class ErrorHerramientas(Exception):
    """Error base tipado de la sala herramientas_glamping."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤herramientas-mcp
class EntradaInvalida(ErrorHerramientas):
    """La entrada no cumple el esquema JSON de la herramienta."""

    def __init__(self, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="entrada_invalida",
            mensaje_usuario=mensaje_usuario,
            detalle_tecnico=detalle_tecnico,
        )


# ¤herramientas-mcp
class HerramientaNoAutorizada(ErrorHerramientas):
    """El rol no tiene autorización para ejecutar la herramienta (INV_ALLOWLIST_POR_ACCION)."""

    def __init__(self, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="herramienta_no_autorizada",
            mensaje_usuario=mensaje_usuario,
            detalle_tecnico=detalle_tecnico,
        )


# ¤herramientas-mcp
class HerramientaDeshabilitada(ErrorHerramientas):
    """La herramienta existe pero está deshabilitada por configuración."""

    def __init__(self, nombre: str) -> None:
        super().__init__(
            codigo="herramienta_deshabilitada",
            mensaje_usuario=f"La herramienta '{nombre}' está deshabilitada en este entorno.",
            detalle_tecnico=f"Herramienta {nombre} deshabilitada",
        )


# ¤herramientas-mcp
class SalaDestinoFallida(ErrorHerramientas):
    """La sala dueña del dato falló al procesar la invocación."""

    def __init__(self, sala: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="sala_destino_fallida",
            mensaje_usuario=mensaje_usuario,
            detalle_tecnico=detalle_tecnico or f"Fallo en sala {sala}",
        )
        self.sala = sala


# ¤herramientas-mcp
class ReservaNoAutorizada(ErrorHerramientas):
    """El remitente no es el titular de la reserva consultada (RF-SEC-08)."""

    def __init__(self, codigo_reserva: str) -> None:
        super().__init__(
            codigo="reserva_no_autorizada",
            mensaje_usuario=f"No autorizado para consultar la reserva '{codigo_reserva}'.",
            detalle_tecnico=f"Titular no coincide para reserva {codigo_reserva}",
        )
        self.codigo_reserva = codigo_reserva
