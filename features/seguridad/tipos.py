# ¤seguridad-canal
# ¤¤security-engineer
"""Tipos del dominio de la sala seguridad."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ¤seguridad-canal
class Rol(str, Enum):
    HUESPED = "huesped"
    VENDEDOR = "vendedor"
    LIDER = "lider"
    GESTOR = "gestor"
    ADMINISTRADOR = "administrador"
    DESCONOCIDO = "desconocido"


# ¤seguridad-canal
@dataclass(frozen=True)
class Identidad:
    remitente_token: str
    rol: Rol
    sujeto_id: str | None = None


# ¤seguridad-canal
@dataclass(frozen=True)
class MensajeLimpio:
    identidad: Identidad
    texto_tokenizado: str
    marcas: tuple[str, ...]
    conversacion_id: str


# ¤seguridad-canal
@dataclass(frozen=True)
class Veredicto:
    permitido: bool
    motivo: str | None = None
    escalar: bool = False


# ¤seguridad-canal
@dataclass(frozen=True)
class EventoAuditoria:
    actor_token: str
    rol: Rol
    accion: str
    herramienta: str | None
    propiedad_id: str | None
    resultado: str
    hash_prompt: str | None
    traza_id: str
