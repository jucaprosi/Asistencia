# ¤canal-whatsapp
# ¤¤integration-engineer
"""Tipos del dominio de la sala canal_whatsapp. Solo estos tipos cruzan la compuerta."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


# ¤canal-whatsapp
class Canal(str, Enum):
    HUESPEDES = "huespedes"
    VENDEDORES = "vendedores"


# ¤canal-whatsapp
class TipoContenido(str, Enum):
    TEXTO = "texto"
    BOTON = "boton"
    LISTA = "lista"
    IMAGEN = "imagen"
    AUDIO = "audio"
    DOCUMENTO = "documento"
    UBICACION = "ubicacion"
    DESCONOCIDO = "desconocido"


# ¤canal-whatsapp
@dataclass(frozen=True)
class MensajeEntrante:
    mensaje_id: str
    remitente: str
    canal: Canal
    tipo: TipoContenido
    texto: str | None
    medio_ref: str | None
    ubicacion: tuple[float, float] | None
    recibido_en: datetime
    contexto_respuesta_a: str | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class Boton:
    id: str
    titulo: str


# ¤canal-whatsapp
@dataclass(frozen=True)
class OpcionLista:
    id: str
    titulo: str
    descripcion: str | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class MensajeSaliente:
    destinatario: str
    texto: str
    botones: tuple[Boton, ...] = ()
    lista: tuple[OpcionLista, ...] = ()
    medio_ref: str | None = None
    en_respuesta_a: str | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class Plantilla:
    nombre: str
    idioma: str
    variables: tuple[str, ...]


# ¤canal-whatsapp
@dataclass(frozen=True)
class ResultadoEnvio:
    mensaje_id: str
    estado: Literal["sent", "delivered", "read", "failed"]
    detalle: str | None = None
