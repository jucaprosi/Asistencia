# ¤conocimiento-rag
# ¤¤data-engineer
"""Compuerta pública de la sala conocimiento (RF-RAG-01..06). Fase 0: interfaz; lógica en TASK-002."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.conocimiento.tipos import Documento, Fragmento, ResultadoRecuperacion, ResumenIndexacion

__all__ = [
    "Documento", "Fragmento", "ResultadoRecuperacion", "ResumenIndexacion",
    "ErrorConocimiento", "ConocimientoService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_conocimiento.yaml")


# ¤conocimiento-rag
class ErrorConocimiento(Exception):
    """Error tipado de la sala conocimiento."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤conocimiento-rag
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤conocimiento-rag
class ConocimientoService:
    """Indexa el corpus de CORPUS_DIR y recupera fragmentos con filtro obligatorio por propiedad."""

    def __init__(self, config: Mapping[str, Any], *, observabilidad: Any) -> None:
        self._config = config
        self._observabilidad = observabilidad

    def indexar(self, raiz: Path | None = None) -> ResumenIndexacion:
        raise NotImplementedError("TASK-002 RF-RAG-01")

    def recuperar(self, consulta: str, propiedad_id: str | None, k: int | None = None) -> ResultadoRecuperacion:
        raise NotImplementedError("TASK-002 RF-RAG-03")

    def documentos(self, propiedad_id: str | None = None) -> tuple[Documento, ...]:
        raise NotImplementedError("TASK-002 RF-RAG-01")

    def evaluar(self, set_dorado: Path) -> dict[str, float]:
        raise NotImplementedError("TASK-002 RF-RAG-06")
