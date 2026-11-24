# ¤inferencia
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos propios de la compuerta de inferencia (ADR-0021, Decisión 1).

Ningún tipo de ``google-genai`` cruza la compuerta: quien la consume ve solo estos tipos neutros.
``contexto_turno`` es opaco y serializable (JSON): se guarda y se devuelve sin inspeccionarlo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Mapping

__all__ = [
    "EsquemaHerramienta",
    "EstadoInferencia",
    "InferenciaNoDisponible",
    "LlamadaNeutra",
    "MensajeNeutro",
    "PeticionInferencia",
    "RespuestaInferencia",
    "RespuestaNoUtilizable",
    "ResultadoNeutro",
    "TiempoAgotado",
    "UsoTokens",
]


# ¤inferencia
@dataclass(frozen=True)
class EsquemaHerramienta:
    nombre: str
    descripcion: str
    esquema_json: Mapping[str, Any]


# ¤inferencia
@dataclass(frozen=True)
class LlamadaNeutra:
    id: str
    nombre: str
    argumentos: Mapping[str, Any]


# ¤inferencia
@dataclass(frozen=True)
class ResultadoNeutro:
    id: str
    nombre: str
    contenido: Mapping[str, Any]


# ¤inferencia
@dataclass(frozen=True)
class MensajeNeutro:
    """Un turno del historial. ``modelo`` reinyecta su ``contexto_turno``; ``resultados`` agrupa las salidas de herramientas."""

    rol: Literal["usuario", "modelo", "resultados"]
    texto: str = ""
    contexto_turno: Mapping[str, Any] | None = None
    resultados: tuple[ResultadoNeutro, ...] = ()


# ¤inferencia
@dataclass(frozen=True)
class PeticionInferencia:
    """``perfil`` lo resuelve inferencia contra ``modelos_permitidos``: quien consume no conoce nombres de modelo."""

    system: str
    mensajes: tuple[MensajeNeutro, ...]
    perfil: Literal["principal", "economico"]
    plazo_s: float
    herramientas: tuple[EsquemaHerramienta, ...] = ()


# ¤inferencia
@dataclass(frozen=True)
class UsoTokens:
    entrada: int = 0
    salida: int = 0
    costo_usd: Decimal = Decimal("0")


# ¤inferencia
@dataclass(frozen=True)
class RespuestaInferencia:
    texto: str
    llamadas: tuple[LlamadaNeutra, ...]
    uso: UsoTokens
    modelo: str  # nombre concreto, solo para trazas
    contexto_turno: Mapping[str, Any] = field(default_factory=dict)


# ¤inferencia
@dataclass(frozen=True)
class EstadoInferencia:
    disponible: bool
    motivo: str
    region: str
    ubicacion: str
    pais: str = ""


# ¤inferencia
class InferenciaNoDisponible(RuntimeError):
    """Falla cerrada: no se genera respuesta (configuración, lista blanca, cuota o proveedor)."""


# ¤inferencia
class TiempoAgotado(InferenciaNoDisponible):
    """La llamada superó el plazo restante del turno."""


# ¤inferencia
class RespuestaNoUtilizable(InferenciaNoDisponible):
    """Safety, MAX_TOKENS, MALFORMED_FUNCTION_CALL o respuesta vacía: no se entrega texto parcial."""
