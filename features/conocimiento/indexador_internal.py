# ¤conocimiento-rag
# ¤¤data-engineer
"""Indexador idempotente de corpus Markdown con seguimiento de version_hash (RF-RAG-01)."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from features.conocimiento.chunker_internal import extraer_metadatos_cabecera, fragmentar_documento
from features.conocimiento.embeddings_internal import generar_embedding
from features.conocimiento.persistencia_internal import RepositorioConocimiento
from features.conocimiento.tipos import CorpusVacio, ResumenIndexacion


# ¤conocimiento-rag
def calcular_hash_contenido(contenido: str) -> str:
    """Calcula el hash SHA-256 determinista del contenido del documento."""
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()


# ¤conocimiento-rag
class IndexadorCorpus:
    """Indexador idempotente de documentos Markdown con regeneración selectiva de fragmentos."""

    def __init__(
        self,
        repositorio: RepositorioConocimiento,
        tokens_min: int = 400,
        tokens_max: int = 600,
        solapamiento: float = 0.10,
    ) -> None:
        self._repo = repositorio
        self._tokens_min = tokens_min
        self._tokens_max = tokens_max
        self._solapamiento = solapamiento

    # ¤conocimiento-rag
    def indexar_directorio(self, raiz: Path) -> ResumenIndexacion:
        """Indexa todos los archivos Markdown de la ruta especificada. Falla con CorpusVacio si no hay."""
        inicio = time.time()
        raiz = raiz.resolve()
        if not raiz.is_dir():
            raise CorpusVacio(str(raiz))

        archivos_md = sorted(list(raiz.glob("*.md")) + list(raiz.glob("**/*.md")))
        # Filtrar duplicados si globbing recursivo capturó dos veces
        rutas_unicas = sorted(list({p.resolve() for p in archivos_md if p.is_file()}))

        if not rutas_unicas:
            raise CorpusVacio(str(raiz))

        chunks_nuevos = 0
        chunks_reemplazados = 0
        total_documentos = 0

        for ruta_archivo in rutas_unicas:
            contenido = ruta_archivo.read_text(encoding="utf-8")
            version_hash = calcular_hash_contenido(contenido)
            ruta_relativa = str(ruta_archivo.relative_to(raiz))

            # Extraer cabecera para metadatos
            metadatos, _ = extraer_metadatos_cabecera(contenido, ruta_relativa)

            # Verificar si ya existe sin cambios
            doc_existente = self._repo.obtener_documento_por_ruta(ruta_relativa)
            if doc_existente and doc_existente.version_hash == version_hash:
                total_documentos += 1
                continue

            # Segmentar en fragmentos
            chunks_crudos = fragmentar_documento(
                contenido=contenido,
                ruta=ruta_relativa,
                tokens_min=self._tokens_min,
                tokens_max=self._tokens_max,
                solapamiento=self._solapamiento,
            )

            # Enriquecer con embeddings deterministas
            chunks_procesados = []
            for c in chunks_crudos:
                texto_completo = f"{c['encabezado']}\n{c['texto']}"
                emb = generar_embedding(texto_completo)
                c_copia = dict(c)
                c_copia["embedding"] = emb
                chunks_procesados.append(c_copia)

            _, es_nuevo, insertados = self._repo.guardar_documento(
                ruta=ruta_relativa,
                propiedad_id=metadatos["propiedad_id"],
                tipo=metadatos["tipo"],
                dueno=metadatos["dueno"],
                revisado=metadatos["revisado"],
                version_hash=version_hash,
                chunks=chunks_procesados,
            )

            if es_nuevo:
                chunks_nuevos += insertados
            else:
                chunks_reemplazados += insertados
            total_documentos += 1

        duracion_ms = int((time.time() - inicio) * 1000)
        return ResumenIndexacion(
            documentos=total_documentos,
            chunks_nuevos=chunks_nuevos,
            chunks_reemplazados=chunks_reemplazados,
            duracion_ms=duracion_ms,
        )
