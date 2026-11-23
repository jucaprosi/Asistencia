# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio y excepciones de la sala seguridad."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


# ¤seguridad-canal
class Rol(str, Enum):
    HUESPED_POTENCIAL = "huesped_potencial"
    HUESPED_ACTIVO = "huesped_activo"
    VENDEDOR = "vendedor"
    LIDER = "lider"
    GESTOR = "gestor"
    ADMINISTRADOR = "administrador"
    ANFITRION = "anfitrion"
    SISTEMA = "sistema"
    DESCONOCIDO = "desconocido"


# ¤seguridad-canal
@dataclass(frozen=True)
class Identidad:
    remitente_token: str
    rol: Rol
    sujeto_id: str | None = None
    numero_hash: str | None = None


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
    herramienta: str | None = None
    propiedad_id: str | None = None
    resultado: str = "ok"
    hash_prompt: str | None = None
    traza_id: str = ""
    audit_id: str | None = None
    instante: datetime | None = None


# ¤seguridad-canal
@dataclass(frozen=True)
class RegistroConsentimiento:
    consentimiento_id: str
    titular_hash: str
    base: str
    version_aviso: str
    otorgado_en: datetime
    revocado_en: datetime | None = None


# ¤seguridad-canal
@dataclass(frozen=True)
class TokenBoveda:
    token: str
    titular_hash: str
    tipo: str
    valor_cifrado: bytes
    creado_en: datetime
    ultimo_uso_en: datetime


# ¤seguridad-canal
class ErrorSeguridad(Exception):
    """Error base de la sala seguridad."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤seguridad-canal
class RemitenteNoAutorizado(ErrorSeguridad):
    def __init__(self, mensaje: str = "Remitente no autorizado en este canal") -> None:
        super().__init__("RemitenteNoAutorizado", mensaje)


# ¤seguridad-canal
class RemitenteBloqueado(ErrorSeguridad):
    def __init__(self, mensaje: str = "Remitente bloqueado por seguridad") -> None:
        super().__init__("RemitenteBloqueado", mensaje)


# ¤seguridad-canal
class LimiteExcedido(ErrorSeguridad):
    def __init__(self, mensaje: str = "Límite de tasa excedido") -> None:
        super().__init__("LimiteExcedido", mensaje)


# ¤seguridad-canal
class AccionNoAutorizada(ErrorSeguridad):
    def __init__(self, mensaje: str = "Acción no autorizada para el rol asignado") -> None:
        super().__init__("AccionNoAutorizada", mensaje)


# ¤seguridad-canal
class InyeccionDetectada(ErrorSeguridad):
    def __init__(self, mensaje: str = "Intento de inyección detectado") -> None:
        super().__init__("InyeccionDetectada", mensaje)


# ¤seguridad-canal
class TokenDesconocido(ErrorSeguridad):
    def __init__(self, mensaje: str = "Token de bóveda desconocido o revocado") -> None:
        super().__init__("TokenDesconocido", mensaje)


# ¤seguridad-canal
class ActorSinPrivilegio(ErrorSeguridad):
    def __init__(self, mensaje: str = "Actor sin privilegios administrativos") -> None:
        super().__init__("ActorSinPrivilegio", mensaje)


# ¤seguridad-canal
class ReservaNoAutorizada(ErrorSeguridad):
    """El remitente no es el titular de la reserva consultada (RF-SEC-08)."""

    def __init__(
        self,
        mensaje: str = "No autorizado para consultar la reserva",
        codigo_reserva: str | None = None,
        escalar: bool = False,
    ) -> None:
        super().__init__("ReservaNoAutorizada", mensaje)
        self.codigo_reserva = codigo_reserva
        self.escalar = escalar

