# ¤conocimiento-rag
# ¤¤data-engineer
"""Compuerta pública de la sala conocimiento (RF-RAG-01..06, INV_SIN_FUGA_ENTRE_PROPIEDADES, INV_NO_LO_SE)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.conocimiento.evaluador_internal import EvaluadorSetDorado
from features.conocimiento.indexador_internal import IndexadorCorpus
from features.conocimiento.persistencia_internal import RepositorioConocimiento
from features.conocimiento.recuperador_internal import RecuperadorHibrido
from features.conocimiento.tipos import (
    ConsultaSinPropiedad,
    CorpusVacio,
    Documento,
    DocumentoSinCabecera,
    ErrorConocimiento,
    Fragmento,
    IndiceNoDisponible,
    ResultadoRecuperacion,
    ResumenIndexacion,
)

__all__ = [
    "Documento",
    "Fragmento",
    "ResultadoRecuperacion",
    "ResumenIndexacion",
    "ErrorConocimiento",
    "CorpusVacio",
    "DocumentoSinCabecera",
    "IndiceNoDisponible",
    "ConsultaSinPropiedad",
    "ConocimientoService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_conocimiento.yaml")


# ¤conocimiento-rag
def _expandir_variables_entorno(valor: Any) -> Any:
    """Expande sintaxis ${VAR:-default} en cadenas de configuración."""
    if isinstance(valor, str):
        patron = r"\$\{([A-Za-z0-9_]+)(?::-([^}]*))?\}"
        def _reemplazar(match: re.Match) -> str:
            var_name, default_val = match.group(1), match.group(2) or ""
            return os.getenv(var_name, default_val)
        return re.sub(patron, _reemplazar, valor)
    if isinstance(valor, dict):
        return {k: _expandir_variables_entorno(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_expandir_variables_entorno(v) for v in valor]
    return valor


# ¤conocimiento-rag
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo) or {}
    return _expandir_variables_entorno(datos)


# ¤conocimiento-rag
class ConocimientoService:
    """Indexa el corpus de CORPUS_DIR y recupera fragmentos con filtro obligatorio por propiedad."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        observabilidad: Any = None,
        ruta_bd: Path | str | None = None,
    ) -> None:
        self._config = dict(config or cargar_config())
        self._observabilidad = observabilidad

        db_url = self._config.get("db_url", "")
        if ruta_bd is None and db_url:
            if db_url.startswith("sqlite:///"):
                ruta_bd = db_url.replace("sqlite:///", "")
            elif db_url.startswith("sqlite://"):
                ruta_bd = db_url.replace("sqlite://", "")
            elif not db_url.startswith("postgresql://") and not db_url.startswith("postgres://"):
                ruta_bd = db_url

        # Inicializar repositorio y componentes internos
        self._repo = RepositorioConocimiento(ruta_bd=ruta_bd)

        chunking_cfg = self._config.get("chunking", {})
        tokens_min = int(chunking_cfg.get("tokens_min", 400))
        tokens_max = int(chunking_cfg.get("tokens_max", 600))
        solapamiento = float(chunking_cfg.get("solapamiento", 0.10))

        self._indexador = IndexadorCorpus(
            repositorio=self._repo,
            tokens_min=tokens_min,
            tokens_max=tokens_max,
            solapamiento=solapamiento,
        )

        recup_cfg = self._config.get("recuperacion", {})
        peso_vectorial = float(recup_cfg.get("peso_vectorial", 0.6))
        peso_bm25 = float(recup_cfg.get("peso_bm25", 0.4))
        umbral_suficiente = float(recup_cfg.get("umbral_suficiente", 0.55))
        k_def = int(recup_cfg.get("k", 6))

        self._recuperador = RecuperadorHibrido(
            repositorio=self._repo,
            peso_vectorial=peso_vectorial,
            peso_bm25=peso_bm25,
            umbral_suficiente=umbral_suficiente,
            k_por_defecto=k_def,
        )

        self._evaluador = EvaluadorSetDorado(self._recuperador)

    @property
    def repositorio(self) -> RepositorioConocimiento:
        return self._repo

    # ¤conocimiento-rag
    def indexar(self, raiz: Path | None = None) -> ResumenIndexacion:
        """Indexa de forma idempotente el directorio de corpus indicado o el configurado."""
        if raiz is None:
            dir_str = self._config.get("corpus_dir", "datos_privados/corpus")
            raiz = Path(dir_str)
        return self._indexador.indexar_directorio(raiz)

    # ¤conocimiento-rag
    def recuperar(self, consulta: str, propiedad_id: str | None, k: int | None = None) -> ResultadoRecuperacion:
        """Recupera fragmentos asegurando que pertenezcan a la propiedad o sean globales."""
        if self._observabilidad and hasattr(self._observabilidad, "span"):
            with self._observabilidad.span("recuperacion_rag", metadata={"propiedad_id": propiedad_id}):
                return self._recuperador.recuperar(consulta=consulta, propiedad_id=propiedad_id, k=k)
        return self._recuperador.recuperar(consulta=consulta, propiedad_id=propiedad_id, k=k)

    # ¤conocimiento-rag
    def documentos(self, propiedad_id: str | None = None) -> tuple[Documento, ...]:
        """Lista los documentos indexados, filtrando opcionalmente por propiedad."""
        return tuple(self._repo.listar_documentos(propiedad_id=propiedad_id))

    # ¤conocimiento-rag
    def evaluar(self, set_dorado: Path) -> dict[str, float]:
        """Evalúa las métricas de calidad (fidelidad, abstención, alucinaciones, P95) con el set dorado."""
        return self._evaluador.evaluar_archivo(set_dorado)
