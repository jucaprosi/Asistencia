# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Tipos del dominio de la sala agente."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal


# ¤agente-enrutador
class ModoAgente(str, Enum):
    ACTIVO = "activo"
    SILENCIO = "silencio"


# ¤agente-enrutador
@dataclass(frozen=True)
class ContextoConversacion:
    conversacion_id: str
    identidad_token: str
    rol: str
    propiedad_id: str | None
    modo: ModoAgente
    ventana_24h_hasta: datetime | None


# ¤agente-enrutador
@dataclass(frozen=True)
class Respuesta:
    texto: str
    botones: tuple[tuple[str, str], ...] = ()
    lista: tuple[tuple[str, str], ...] = ()
    herramientas_usadas: tuple[str, ...] = ()
    chunks_citados: tuple[str, ...] = ()
    modelo: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: Decimal = Decimal("0")
    degradada: bool = False


# ¤agente-enrutador
@dataclass(frozen=True)
class ResolucionPropiedad:
    propiedad_id: str | None
    metodo: Literal["codigo_reserva", "nombre", "direccion", "contexto", "pregunta"]
    candidatas: tuple[str, ...] = ()
