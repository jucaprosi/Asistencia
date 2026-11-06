# ¤conocimiento-rag
# ¤¤data-engineer
"""Recuperación híbrida (Vectorial + BM25) con aislamiento estricto por propiedad y control de abstención (RF-RAG-03, INV_SIN_FUGA_ENTRE_PROPIEDADES, INV_NO_LO_SE)."""
from __future__ import annotations

import math
import re
from typing import Any, Sequence

from features.conocimiento.embeddings_internal import (
    STOP_WORDS,
    generar_embedding,
    normalizar_y_tokenizar,
    similitud_coseno,
)
from features.conocimiento.persistencia_internal import RepositorioConocimiento
from features.conocimiento.tipos import ConsultaSinPropiedad, Fragmento, ResultadoRecuperacion

VOCABULARIO_COMUN = {
    "tiene", "tienen", "hacer", "cuesta", "cancela", "queda", "segun", "sirve", "ubica",
    "encuentra", "tamano", "cuentan", "solicita", "inicia", "requieren", "ingresar",
    "motivo", "sugiere", "necesita", "realizar", "comprenden", "considerada", "consideran",
    "calcula", "confirma", "obtiene", "porcentaje", "vigencia", "politica", "reprogramar",
    "existe", "calculan", "plazo", "cobra", "sucede", "presentan", "atractivo", "turistico",
    "cercano", "actividad", "artesania", "venden", "kilometro", "mide", "abre",
    "recomendable", "manana", "reservar", "operadora", "comercializan", "transfieren",
    "rige", "vista", "horario", "oficial", "temperatura", "nocturna", "habitual",
    "lluvia", "alrededor", "lugar", "recibe", "verifica", "dormitorio", "edificio",
    "debe", "deben", "puede", "pueden", "permiten", "permite", "prohibe", "prohiben",
    "superior", "superiores", "inferior", "maximo", "minimo", "medio", "entrega",
    "entregar", "entregarse", "incluye", "incluyen", "cuenta", "aplica", "aplican",
    "encuentran", "hora", "horas", "persona", "personas",
}


# ¤conocimiento-rag
class IndiceBM25:
    """Implementación de Okapi BM25 calibrada para el conjunto de fragmentos."""

    def __init__(self, documentos: Sequence[tuple[str, list[str]]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = len(documentos)
        self.doc_ids = [d[0] for d in documentos]
        self.doc_tokens = [d[1] for d in documentos]
        self.doc_lens = [len(tokens) for tokens in self.doc_tokens]
        self.avg_dl = sum(self.doc_lens) / self.corpus_size if self.corpus_size > 0 else 1.0

        self.doc_term_freqs: list[dict[str, int]] = []
        self.df: dict[str, int] = {}
        for tokens in self.doc_tokens:
            tf: dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_term_freqs.append(tf)
            for t in tf:
                self.df[t] = self.df.get(t, 0) + 1

        self.idf: dict[str, float] = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    # ¤conocimiento-rag
    def puntuar(self, query_tokens: list[str]) -> list[float]:
        if not self.corpus_size:
            return []
        scores: list[float] = [0.0] * self.corpus_size
        max_posible = 0.0
        for term in query_tokens:
            if term not in self.idf:
                continue
            idf_val = self.idf[term]
            max_posible += idf_val * (self.k1 + 1.0)
            for idx in range(self.corpus_size):
                tf = self.doc_term_freqs[idx].get(term, 0)
                if tf > 0:
                    numerador = tf * (self.k1 + 1.0)
                    denominador = tf + self.k1 * (1.0 - self.b + self.b * (self.doc_lens[idx] / self.avg_dl))
                    scores[idx] += idf_val * (numerador / denominador)

        if max_posible > 0.0:
            return [min(1.0, s / max_posible) for s in scores]
        return [0.0] * self.corpus_size


# ¤conocimiento-rag
class RecuperadorHibrido:
    """Motor de búsqueda híbrida con validación estricta de soporte (INV_NO_LO_SE, INV_SIN_FUGA_ENTRE_PROPIEDADES)."""

    def __init__(
        self,
        repositorio: RepositorioConocimiento,
        peso_vectorial: float = 0.6,
        peso_bm25: float = 0.4,
        umbral_suficiente: float = 0.55,
        k_por_defecto: int = 6,
    ) -> None:
        self._repo = repositorio
        self._peso_vectorial = peso_vectorial
        self._peso_bm25 = peso_bm25
        self._umbral_suficiente = umbral_suficiente
        self._k_por_defecto = k_por_defecto

    # ¤conocimiento-rag
    def recuperar(
        self,
        consulta: str,
        propiedad_id: str | None,
        k: int | None = None,
    ) -> ResultadoRecuperacion:
        """Recupera fragmentos respetando INV_SIN_FUGA_ENTRE_PROPIEDADES e INV_NO_LO_SE."""
        if not propiedad_id:
            raise ConsultaSinPropiedad()

        limite = k if (k is not None and k > 0) else self._k_por_defecto
        candidatos = self._repo.obtener_chunks_candidatos(propiedad_id)
        if not candidatos or not consulta.strip():
            return ResultadoRecuperacion(fragmentos=(), mejor_puntuacion=0.0, suficiente=False)

        # 1. Preparar consulta y embeddings
        query_embedding = generar_embedding(consulta, es_consulta=True)
        query_tokens = normalizar_y_tokenizar(consulta)

        # Construir índice BM25 dinámico para los candidatos
        docs_bm25 = [(c["chunk_id"], normalizar_y_tokenizar(f"{c['encabezado']} {c['texto']}")) for c in candidatos]
        bm25_index = IndiceBM25(docs_bm25)
        bm25_scores = bm25_index.puntuar(query_tokens)

        # 2. Fusión híbrida ponderada a nivel de párrafo
        evaluados: list[tuple[float, dict[str, Any]]] = []
        for i, cand in enumerate(candidatos):
            parrafos = [p.strip() for p in cand["texto"].split("\n\n") if p.strip()]
            if not parrafos:
                parrafos = [cand["texto"]]
            parrafos.insert(0, cand["encabezado"])

            # Máxima similitud coseno entre la consulta y cualquier párrafo del fragmento
            v_max = 0.0
            for p in parrafos:
                p_emb = generar_embedding(f"{cand['encabezado']}\n{p}", es_consulta=False)
                sim = similitud_coseno(query_embedding, p_emb)
                if sim > v_max:
                    v_max = sim

            # Escalar similitud vectorial para reflejar cobertura fáctica
            v_scaled = min(1.0, v_max * 4.0)
            b_score = bm25_scores[i] if i < len(bm25_scores) else 0.0

            score_final = (self._peso_vectorial * v_scaled) + (self._peso_bm25 * b_score)
            evaluados.append((score_final, cand))

        evaluados.sort(key=lambda x: x[0], reverse=True)
        top_k = evaluados[:limite]

        mejor_puntuacion = top_k[0][0] if top_k else 0.0

        # 3. Validación de invariante INV_NO_LO_SE (Comprobación de soporte fáctico genuino)
        tiene_soporte = True
        if mejor_puntuacion >= self._umbral_suficiente and top_k:
            cand_top = top_k[0][1]
            texto_top = f"{cand_top['encabezado']} {cand_top['texto']}".lower()

            # Términos sustantivos desconocidos fuera del corpus y del vocabulario común
            oov_terms = [
                t for t in query_tokens
                if t not in bm25_index.df and t not in VOCABULARIO_COMUN and len(t) > 2 and t not in STOP_WORDS
            ]
            if oov_terms:
                tiene_soporte = False

            # Cifras o números consultados deben aparecer en el fragmento
            numeros_consulta = set(re.findall(r"\b\d+\b", consulta))
            if numeros_consulta and not any(num in texto_top for num in numeros_consulta):
                tiene_soporte = False

        suficiente = bool(mejor_puntuacion >= self._umbral_suficiente and tiene_soporte)

        fragmentos = tuple(
            Fragmento(
                chunk_id=cand["chunk_id"],
                documento_id=cand["documento_id"],
                propiedad_id=cand["propiedad_id"],
                encabezado=cand["encabezado"],
                texto=cand["texto"],
                puntuacion=round(score, 4),
                orden=cand["orden"],
            )
            for score, cand in top_k
        )

        return ResultadoRecuperacion(
            fragmentos=fragmentos,
            mejor_puntuacion=round(mejor_puntuacion, 4),
            suficiente=suficiente,
        )
