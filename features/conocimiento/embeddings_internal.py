# ¤conocimiento-rag
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Generación de embeddings deterministas de 1024 dimensiones y cálculo de similitud (RF-RAG-03)."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

DIMENSION_EMBEDDING = 1024

STOP_WORDS = {
    "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las", "por", "un", "para", "con",
    "no", "una", "su", "al", "lo", "como", "mas", "pero", "sus", "le", "ya", "o", "este", "si",
    "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "tambien", "me", "hasta", "hay",
    "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra",
    "otros", "ese", "eso", "es", "son", "cual", "cuales", "cuanto", "cuanta", "cuantos", "cuantas",
}

SINONIMOS_HOSPEDAJE = {
    "admit": "permit", "acept": "permit", "prohib": "permit", "permit": "permit",
    "adentr": "dentr", "dentro": "dentr", "interior": "dentr",
    "afuer": "exterior", "fuer": "exterior",
    "automovil": "vehicul", "auto": "vehicul", "carr": "vehicul", "transitable": "vehicul",
    "hospedaj": "alojamient", "alojamient": "alojamient", "estanci": "alojamient", "estadi": "alojamient",
    "registr": "identid", "cedul": "identid", "pasaport": "identid", "document": "identid",
    "inspeccion": "inspeccion", "revision": "inspeccion", "inventari": "inspeccion",
    "abrig": "clima_frio", "abrigad": "clima_frio", "chaquet": "clima_frio", "frio": "clima_frio", "dorm": "clima_frio",
    "cuest": "preci", "cost": "preci", "tarif": "preci", "val": "preci", "cobr": "preci", "dolar": "preci", "usd": "preci",
    "cancel": "cancelac", "anul": "cancelac", "reembols": "cancelac", "devoluc": "cancelac",
    "cen": "comid", "desayun": "comid", "aliment": "comid", "restaurant": "comid",
    "perr": "mascot", "gat": "mascot", "pet": "mascot", "animal": "mascot",
    "llegad": "checkin", "ingres": "checkin", "arrib": "checkin", "entr": "checkin",
    "salid": "checkout", "partid": "checkout", "ir": "checkout",
    "atractiv": "turism", "visit": "turism", "pase": "turism", "conoc": "turism", "lug": "turism", "caminat": "turism",
}


# ¤conocimiento-rag
def normalizar_y_tokenizar(texto: str) -> list[str]:
    """Tokeniza texto aplicando normalización de acentos, minúsculas, lematización y sinónimos."""
    limpio = texto.lower()
    for o, r in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ñ", "n")):
        limpio = limpio.replace(o, r)
    tokens = re.findall(r"\b[a-z0-9]+\b", limpio)
    resultado: list[str] = []
    for t in tokens:
        if t in STOP_WORDS:
            continue
        if len(t) > 3:
            if t.endswith("mente"):
                t = t[:-5]
            if t.endswith("es"):
                t = t[:-2]
            elif t.endswith("s") and not t.endswith("is") and not t.endswith("us"):
                t = t[:-1]
        resultado.append(t)
        # Expandir sinónimo canónico si aplica
        for raiz, canonico in SINONIMOS_HOSPEDAJE.items():
            if t.startswith(raiz) or raiz.startswith(t):
                resultado.append(canonico)
                break
    return resultado


# ¤conocimiento-rag
def generar_embedding(texto: str, dimension: int = DIMENSION_EMBEDDING, es_consulta: bool = False) -> list[float]:
    """Genera un vector determinista unitario de 1024 dimensiones con hashing ponderado."""
    if not texto.strip():
        return [0.0] * dimension

    tokens = normalizar_y_tokenizar(texto)
    pesos: dict[int, float] = {}
    frecuencias: dict[str, int] = {}
    for t in tokens:
        frecuencias[t] = frecuencias.get(t, 0) + 1

    for token, conteo in frecuencias.items():
        tf = 1.0 if es_consulta else (1.0 + math.log(conteo))
        peso_base = tf * 3.0

        # Hash del token a cubeta
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        cubeta = int.from_bytes(digest, "big") % dimension
        pesos[cubeta] = pesos.get(cubeta, 0.0) + peso_base

        # Trigramas de caracteres para robustez morfológica
        if len(token) >= 3:
            for j in range(len(token) - 2):
                tri = token[j : j + 3]
                d_tri = hashlib.blake2b(tri.encode("utf-8"), digest_size=8).digest()
                c_tri = int.from_bytes(d_tri, "big") % dimension
                pesos[c_tri] = pesos.get(c_tri, 0.0) + (peso_base * 0.25)

    vector = [pesos.get(i, 0.0) for i in range(dimension)]
    norma = math.sqrt(sum(v * v for v in vector))
    if norma > 0.0:
        return [v / norma for v in vector]
    return [0.0] * dimension


# ¤conocimiento-rag
def similitud_coseno(v1: Sequence[float], v2: Sequence[float]) -> float:
    """Calcula la similitud coseno entre dos vectores normalizados."""
    if len(v1) != len(v2) or not v1:
        return 0.0
    producto = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, min(1.0, float(producto)))
