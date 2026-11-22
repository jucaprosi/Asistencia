# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Caché semántico y enrutamiento de modelos (RF-AG-07, INV_CACHE_SIN_PRECIOS, RNF-16).

Implementa la exclusión estricta de precios y disponibilidad antes de escribir o servir del caché,
y el enrutamiento inteligente entre modelo principal y económico según el riesgo de la consulta.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Mapping, Sequence
from features.persistencia_sql.persistencia_sql_service import envolver

__all__ = [
    "PATRONES_PRECIO_DISPONIBILIDAD",
    "contiene_precio_o_disponibilidad",
    "calcular_embedding",
    "similitud_coseno",
    "seleccionar_modelo",
    "CacheSemantico",
]

# Invariante INV_CACHE_SIN_PRECIOS: términos que prohíben el almacenamiento o despacho desde caché
PATRONES_PRECIO_DISPONIBILIDAD = [
    re.compile(r"\bprecios?\b", re.IGNORECASE),
    re.compile(r"\btarifas?\b", re.IGNORECASE),
    re.compile(r"\bcost[oa]s?\b", re.IGNORECASE),
    re.compile(r"\bcuest[an]?\b", re.IGNORECASE),
    re.compile(r"\bcobr[ao]s?\b", re.IGNORECASE),
    re.compile(r"\bdisponib\w*\b", re.IGNORECASE),
    re.compile(r"\bcupos?\b", re.IGNORECASE),
    re.compile(r"\breserv\w*\b", re.IGNORECASE),
    re.compile(r"\bcotiz\w*\b", re.IGNORECASE),
    re.compile(r"\bcancel\w*\b", re.IGNORECASE),
    re.compile(r"\breembols\w*\b", re.IGNORECASE),
    re.compile(r"\bpol[ií]ticas?\b", re.IGNORECASE),
    re.compile(r"\bdesgloses?\b", re.IGNORECASE),
    re.compile(r"\b(?:usd|d[oó]lares?)\b", re.IGNORECASE),
    re.compile(r"\$\s*\d+", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:usd|d[oó]lares|\$)\b", re.IGNORECASE),
]

PALABRAS_BAJO_RIESGO = {
    "horario", "checkin", "check-in", "checkout", "check-out",
    "llegada", "salida", "ubicacion", "ubicación", "direccion", "dirección",
    "llegar", "donde", "dónde", "queda", "wifi", "internet", "clave",
    "normas", "reglas", "mascotas", "pet", "animales", "frio", "frío",
    "clima", "turismo", "atractivos", "caminar", "laguna", "san pablo",
}

SINONIMOS_HOTELEROS = {
    "internet": "wifi",
    "red": "wifi",
    "contrasena": "clave",
    "contrasenya": "clave",
    "password": "clave",
    "llegada": "checkin",
    "salida": "checkout",
    "direccion": "ubicacion",
    "donde": "ubicacion",
    "queda": "ubicacion",
    "llegar": "ubicacion",
}

STOPWORDS = {
    "de", "la", "el", "los", "las", "un", "una", "unos", "unas", "por",
    "en", "para", "al", "del", "es", "son", "me", "te", "nos", "pueden",
    "dar", "favor", "hola", "buenos", "dias", "tardes", "noches", "a", "que",
    "cual", "cuales", "como", "y", "o", "mi", "tu", "su",
}


# ¤agente-enrutador
def _resolver_valor_config(valor: Any, defecto: str = "") -> str:
    if not isinstance(valor, str):
        return defecto
    if valor.startswith("${") and ":-" in valor and valor.endswith("}"):
        var_name, default_val = valor[2:-1].split(":-", 1)
        return os.environ.get(var_name, default_val)
    return valor


# ¤agente-enrutador
def contiene_precio_o_disponibilidad(texto: str) -> bool:
    """Verifica si el texto contiene términos o montos de precios, tarifas, disponibilidad o políticas."""
    if not texto:
        return False
    for patron in PATRONES_PRECIO_DISPONIBILIDAD:
        if patron.search(texto):
            return True
    return False


# ¤agente-enrutador
def normalizar_texto(texto: str) -> str:
    limpio = texto.lower()
    for o, r in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        limpio = limpio.replace(o, r)
    return limpio


# ¤agente-enrutador
def calcular_embedding(
    texto: str,
    dimension: int = 1024,
    conocimiento_service: Any = None,
) -> list[float]:
    """Genera vector de embedding determinista de 1024 dimensiones para similitud semántica.

    Usa la compuerta conocimiento_service si expone generación de embeddings, o un fallback determinista.
    """
    if conocimiento_service is not None:
        if hasattr(conocimiento_service, "generar_embedding"):
            try:
                emb = conocimiento_service.generar_embedding(texto)
                if isinstance(emb, (list, tuple)) and len(emb) == dimension:
                    return [float(x) for x in emb]
            except Exception:
                pass
        if hasattr(conocimiento_service, "embeddings"):
            try:
                emb = conocimiento_service.embeddings(texto)
                if isinstance(emb, (list, tuple)) and len(emb) == dimension:
                    return [float(x) for x in emb]
            except Exception:
                pass

    # Generación limpia y determinista basada en n-gramas y proyecciones hash
    tokens_crudos = re.findall(r"\b[a-z0-9]+\b", normalizar_texto(texto))
    tokens_filtrados: list[str] = []
    for t in tokens_crudos:
        if t in STOPWORDS:
            continue
        canon = SINONIMOS_HOTELEROS.get(t, t)
        if not tokens_filtrados or tokens_filtrados[-1] != canon:
            tokens_filtrados.append(canon)

    tokens = tokens_filtrados if tokens_filtrados else [SINONIMOS_HOTELEROS.get(t, t) for t in tokens_crudos]

    vector = [0.0] * dimension
    if not tokens:
        return vector

    # Bigramas y unigramas
    terminos = list(tokens)
    for i in range(len(tokens) - 1):
        terminos.append(f"{tokens[i]}_{tokens[i+1]}")

    for t in terminos:
        h = int(hashlib.sha256(t.encode("utf-8")).hexdigest(), 16)
        indice = h % dimension
        signo = 1.0 if (h >> 8) % 2 == 0 else -1.0
        peso = 1.5 if "_" in t else 1.0
        vector[indice] += signo * peso

    # Normalización L2
    norma = math.sqrt(sum(x * x for x in vector))
    if norma > 0:
        vector = [x / norma for x in vector]
    return vector


# ¤agente-enrutador
def similitud_coseno(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Calcula la similitud de coseno entre dos vectores numéricos."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


# ¤agente-enrutador
def seleccionar_modelo(
    texto: str,
    herramientas_requeridas: Sequence[Any] = (),
    config: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    """Determina si la consulta debe despacharse al modelo principal o al económico (RF-AG-07)."""
    cfg = config or {}
    modelos = cfg.get("modelos", {})
    modelo_principal = _resolver_valor_config(modelos.get("principal"), "claude-opus-5-5")
    modelo_economico = _resolver_valor_config(modelos.get("economico"), "claude-haiku-5-5")

    # 1. Si contiene precios, cotizaciones, políticas o disponibilidad, siempre modelo principal
    if contiene_precio_o_disponibilidad(texto):
        return modelo_principal, "pregunta_critica_precio_o_disponibilidad"

    # 2. Si requiere herramientas, siempre modelo principal
    if herramientas_requeridas:
        return modelo_principal, "requiere_herramientas"

    # 3. Preguntas frecuentes de bajo riesgo (horario, ubicación, wifi, atractivos)
    texto_norm = normalizar_texto(texto)
    palabras = set(re.findall(r"\b[a-z0-9-]+\b", texto_norm))
    if palabras & PALABRAS_BAJO_RIESGO:
        return modelo_economico, "pregunta_frecuente_bajo_riesgo"

    # Por defecto, consulta general
    return modelo_principal, "consulta_general"


# ¤agente-enrutador
class CacheSemantico:
    """Caché semántico persistente con verificación estricta de INV_CACHE_SIN_PRECIOS."""

    def __init__(
        self,
        conexion: sqlite3.Connection | None = None,
        db_path: str | None = None,
        config: Mapping[str, Any] | None = None,
        conocimiento_service: Any = None,
    ) -> None:
        self._config = config or {}
        self._conocimiento_service = conocimiento_service
        cfg_cache = self._config.get("cache_semantico", {})
        self._activo = bool(cfg_cache.get("activo", True))
        self._umbral = float(cfg_cache.get("umbral_similitud", 0.92))
        self._dimension = 1024

        if conexion is not None:
            self._con_memoria = conexion
            self._ruta_db = None
        elif db_path is None or str(db_path) == ":memory:":
            # None: DATABASE_URL (PostgreSQL, esquema agente) o SQLite en memoria; ":memory:" fuerza SQLite.
            self._con_memoria = envolver(None if db_path is None else ":memory:", ruta_busqueda="agente")
            self._ruta_db = None
        else:
            self._con_memoria = None
            self._ruta_db = str(db_path)

        if not getattr(self._con_memoria, "es_postgres", False):
            self._inicializar_tabla()  # en PostgreSQL el esquema lo aplica scripts/migrar_db.py

    # ¤agente-enrutador
    @contextmanager
    def _con(self) -> Iterator[sqlite3.Connection]:
        if self._con_memoria is not None:
            with self._con_memoria:
                yield self._con_memoria
        else:
            con = sqlite3.connect(self._ruta_db or ":memory:")
            try:
                with con:
                    yield con
            finally:
                con.close()

    def _inicializar_tabla(self) -> None:
        with self._con() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_semantico (
                  hash_consulta    TEXT PRIMARY KEY,
                  propiedad_id     TEXT NOT NULL DEFAULT 'glamping',
                  embedding        TEXT NOT NULL,
                  respuesta        TEXT NOT NULL,
                  creado_en        TEXT NOT NULL,
                  expira_en        TEXT NOT NULL
                );
                """
            )
            try:
                con.execute("ALTER TABLE cache_semantico ADD COLUMN propiedad_id TEXT NOT NULL DEFAULT 'glamping';")
            except Exception:
                pass

    # ¤agente-enrutador
    def buscar(
        self,
        consulta: str,
        umbral: float | None = None,
        propiedad_id: str | None = None,
        conocimiento_service: Any = None,
    ) -> tuple[str | None, float]:
        """Busca una respuesta en caché semántico garantizando INV_CACHE_SIN_PRECIOS."""
        if not self._activo:
            return None, 0.0

        # Si la consulta misma pregunta por precios o disponibilidad, no se busca en caché
        if contiene_precio_o_disponibilidad(consulta):
            return None, 0.0

        svc_conocimiento = conocimiento_service or self._conocimiento_service
        umbral_aplicar = umbral if umbral is not None else self._umbral
        emb_consulta = calcular_embedding(consulta, self._dimension, svc_conocimiento)
        ahora = datetime.now(timezone.utc).isoformat()

        mejor_respuesta: str | None = None
        mejor_similitud = 0.0

        query = "SELECT embedding, respuesta FROM cache_semantico WHERE expira_en > ?"
        params: list[Any] = [ahora]
        if propiedad_id:
            query += " AND (propiedad_id = ? OR propiedad_id = 'glamping')"
            params.append(propiedad_id)

        with self._con() as con:
            cursor = con.execute(query, tuple(params))
            for fila in cursor.fetchall():
                try:
                    vec_guardado = json.loads(fila[0])
                    sim = similitud_coseno(emb_consulta, vec_guardado)
                    if sim > mejor_similitud:
                        mejor_similitud = sim
                        # INV_CACHE_SIN_PRECIOS: descartar respuesta si contiene precios/disponibilidad
                        if not contiene_precio_o_disponibilidad(fila[1]):
                            mejor_respuesta = fila[1]
                        else:
                            mejor_respuesta = None
                except Exception:
                    continue

        if mejor_similitud >= umbral_aplicar and mejor_respuesta is not None:
            return mejor_respuesta, mejor_similitud

        return None, mejor_similitud

    # ¤agente-enrutador
    def guardar(
        self,
        consulta: str,
        respuesta: str,
        ttl_horas: int = 24,
        propiedad_id: str = "glamping",
        conocimiento_service: Any = None,
    ) -> bool:
        """Guarda en caché semántico respetando la invariante INV_CACHE_SIN_PRECIOS."""
        if not self._activo:
            return False

        # Invariante INV_CACHE_SIN_PRECIOS: no guardar si la consulta o la respuesta contienen precio o disponibilidad
        if contiene_precio_o_disponibilidad(respuesta) or contiene_precio_o_disponibilidad(consulta):
            return False

        svc_conocimiento = conocimiento_service or self._conocimiento_service
        clave_hash = f"{propiedad_id}:{normalizar_texto(consulta)}"
        hash_c = hashlib.sha256(clave_hash.encode("utf-8")).hexdigest()
        emb = calcular_embedding(consulta, self._dimension, svc_conocimiento)
        ahora_dt = datetime.now(timezone.utc)
        expira_dt = ahora_dt + timedelta(hours=ttl_horas)

        with self._con() as con:
            con.execute(
                """
                INSERT INTO cache_semantico (hash_consulta, propiedad_id, embedding, respuesta, creado_en, expira_en)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(hash_consulta) DO UPDATE SET
                  propiedad_id = excluded.propiedad_id,
                  embedding = excluded.embedding,
                  respuesta = excluded.respuesta,
                  creado_en = excluded.creado_en,
                  expira_en = excluded.expira_en
                """,
                (hash_c, propiedad_id, json.dumps(emb), respuesta, ahora_dt.isoformat(), expira_dt.isoformat()),
            )
        return True

    # ¤agente-enrutador
    def tamano(self) -> int:
        with self._con() as con:
            cursor = con.execute("SELECT COUNT(*) FROM cache_semantico")
            fila = cursor.fetchone()
            return int(fila[0]) if fila else 0

    # ¤agente-enrutador
    def limpiar(self) -> None:
        with self._con() as con:
            con.execute("DELETE FROM cache_semantico")
