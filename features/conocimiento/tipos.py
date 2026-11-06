# ¤conocimiento-rag
# ¤¤data-engineer
"""Tipos del dominio y excepciones de la sala conocimiento."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


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


# ¤conocimiento-rag
class ErrorConocimiento(Exception):
    """Error tipado base de la sala conocimiento."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤conocimiento-rag
class CorpusVacio(ErrorConocimiento):
    """El directorio de corpus no contiene documentos Markdown indexables."""

    def __init__(self, ruta: str) -> None:
        super().__init__(
            codigo="corpus_vacio",
            mensaje_usuario="El directorio del corpus está vacío o no contiene archivos Markdown.",
            detalle_tecnico=f"Ruta: {ruta}",
        )


# ¤conocimiento-rag
class DocumentoSinCabecera(ErrorConocimiento):
    """El documento Markdown no incluye el frontmatter YAML obligatorio."""

    def __init__(self, ruta: str, campo_faltante: str) -> None:
        super().__init__(
            codigo="documento_sin_cabecera",
            mensaje_usuario=f"El documento '{ruta}' carece del campo obligatorio '{campo_faltante}' en su cabecera.",
            detalle_tecnico=f"Falta {campo_faltante} en {ruta}",
        )


# ¤conocimiento-rag
class IndiceNoDisponible(ErrorConocimiento):
    """El índice vectorial o el motor de búsqueda no están disponibles."""

    def __init__(self, motivo: str) -> None:
        super().__init__(
            codigo="indice_no_disponible",
            mensaje_usuario="El índice de conocimiento no se encuentra disponible.",
            detalle_tecnico=motivo,
        )


# ¤conocimiento-rag
class ConsultaSinPropiedad(ErrorConocimiento):
    """Se intentó una recuperación sin especificar la propiedad obligatoria."""

    def __init__(self) -> None:
        super().__init__(
            codigo="consulta_sin_propiedad",
            mensaje_usuario="La consulta requiere un identificador de propiedad para evitar fugas de información.",
            detalle_tecnico="propiedad_id es None y la política exige filtrado estricto",
        )
