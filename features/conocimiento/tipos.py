# ¤conocimiento-rag
# ¤¤data-engineer
"""Tipos del dominio de la sala conocimiento."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


# ¤conocimiento-rag
@dataclass(frozen=True)
class Documento:
    documento_id: str
    ruta: str
    propiedad_id: str
    tipo: str
    dueno: str
    revisado: date
    version_hash: str


# ¤conocimiento-rag
@dataclass(frozen=True)
class Fragmento:
    chunk_id: str
    documento_id: str
    propiedad_id: str
    encabezado: str
    texto: str
    puntuacion: float
    orden: int


# ¤conocimiento-rag
@dataclass(frozen=True)
class ResultadoRecuperacion:
    fragmentos: tuple[Fragmento, ...]
    mejor_puntuacion: float
    suficiente: bool


# ¤conocimiento-rag
@dataclass(frozen=True)
class ResumenIndexacion:
    documentos: int
    chunks_nuevos: int
    chunks_reemplazados: int
    duracion_ms: int
