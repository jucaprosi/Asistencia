# ¤conocimiento-rag
# ¤¤data-engineer
"""Segmentación de documentos Markdown por secciones preservando encabezados y metadatos (RF-RAG-02)."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import yaml

from features.conocimiento.tipos import DocumentoSinCabecera

TIPOS_VALIDOS = {"politicas", "precios", "checkin", "atractivos", "faq", "pagos", "privacidad"}


# ¤conocimiento-rag
def _inferir_tipo_por_nombre(nombre_archivo: str) -> str:
    nombre = nombre_archivo.lower()
    if "precio" in nombre or "temporada" in nombre or "tarifa" in nombre:
        return "precios"
    if "politica" in nombre or "cancelacion" in nombre or "norma" in nombre:
        return "politicas"
    if "checkin" in nombre or "checkout" in nombre or "llegada" in nombre:
        return "checkin"
    if "atractivo" in nombre or "turism" in nombre or "guia" in nombre:
        return "atractivos"
    if "pago" in nombre or "banco" in nombre or "transferencia" in nombre:
        return "pagos"
    if "privacidad" in nombre or "aviso" in nombre or "datos" in nombre:
        return "privacidad"
    return "faq"


# ¤conocimiento-rag
def extraer_metadatos_cabecera(contenido: str, ruta_archivo: str = "") -> tuple[dict[str, Any], str]:
    """Extrae el frontmatter YAML y valida campos obligatorios (propiedad, dueno, revisado)."""
    patron = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    coincidencia = re.search(patron, contenido, flags=re.DOTALL)
    if not coincidencia:
        raise DocumentoSinCabecera(ruta_archivo or "documento", "frontmatter")

    bloque_yaml, cuerpo = coincidencia.group(1), coincidencia.group(2)
    try:
        datos = yaml.safe_load(bloque_yaml) or {}
    except Exception as exc:
        raise DocumentoSinCabecera(ruta_archivo or "documento", f"yaml_invalido: {exc}") from exc

    if not isinstance(datos, dict):
        raise DocumentoSinCabecera(ruta_archivo or "documento", "formato_invalido")

    propiedad = datos.get("propiedad") or datos.get("propiedad_id")
    if not propiedad:
        raise DocumentoSinCabecera(ruta_archivo or "documento", "propiedad")

    dueno = datos.get("dueno")
    if not dueno:
        raise DocumentoSinCabecera(ruta_archivo or "documento", "dueno")

    revisado_raw = datos.get("revisado")
    if not revisado_raw:
        raise DocumentoSinCabecera(ruta_archivo or "documento", "revisado")

    if isinstance(revisado_raw, date):
        fecha_revisado = revisado_raw
    else:
        try:
            fecha_revisado = datetime.strptime(str(revisado_raw).strip(), "%Y-%m-%d").date()
        except ValueError:
            fecha_revisado = date.today()

    tipo = datos.get("tipo")
    if not tipo or tipo not in TIPOS_VALIDOS:
        tipo = _inferir_tipo_por_nombre(ruta_archivo)

    metadatos = {
        "propiedad_id": str(propiedad).strip(),
        "dueno": str(dueno).strip(),
        "revisado": fecha_revisado,
        "tipo": tipo,
    }
    return metadatos, cuerpo.strip()


# ¤conocimiento-rag
def _estimar_tokens(texto: str) -> int:
    """Estima tokens contando palabras y caracteres (~0.75 tokens por palabra o 1 token / 4 chars)."""
    palabras = len(texto.split())
    chars = len(texto) // 4
    return max(palabras, chars, 1)


# ¤conocimiento-rag
def fragmentar_documento(
    contenido: str,
    ruta: str = "",
    tokens_min: int = 400,
    tokens_max: int = 600,
    solapamiento: float = 0.10,
) -> list[dict[str, Any]]:
    """Fragmenta por secciones Markdown conservando encabezado, con límites de tokens y solapamiento."""
    metadatos, cuerpo = extraer_metadatos_cabecera(contenido, ruta)
    propiedad_id = metadatos["propiedad_id"]

    # Separar en secciones basadas en encabezados Markdown (#, ##, ###)
    lineas = cuerpo.splitlines()
    secciones: list[tuple[str, list[str]]] = []
    encabezado_actual = "General"
    lineas_actuales: list[str] = []

    for linea in lineas:
        match_encabezado = re.match(r"^(#{1,6})\s+(.*)$", linea)
        if match_encabezado:
            if lineas_actuales:
                secciones.append((encabezado_actual, lineas_actuales))
                lineas_actuales = []
            encabezado_actual = match_encabezado.group(2).strip()
        else:
            lineas_actuales.append(linea)

    if lineas_actuales:
        secciones.append((encabezado_actual, lineas_actuales))

    if not secciones:
        secciones = [("General", lineas)]

    fragmentos: list[dict[str, Any]] = []
    orden_global = 0

    for encabezado, lineas_seccion in secciones:
        texto_seccion = "\n".join(lineas_seccion).strip()
        if not texto_seccion:
            continue

        parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto_seccion) if p.strip()]
        if not parrafos:
            parrafos = [texto_seccion]

        buffer_parrafos: list[str] = []
        tokens_acumulados = 0

        for parrafo in parrafos:
            tokens_p = _estimar_tokens(parrafo)
            if tokens_acumulados + tokens_p > tokens_max and buffer_parrafos:
                # Emitir chunk actual
                texto_chunk = "\n\n".join(buffer_parrafos)
                fragmentos.append({
                    "encabezado": encabezado,
                    "texto": texto_chunk,
                    "propiedad_id": propiedad_id,
                    "orden": orden_global,
                })
                orden_global += 1

                # Calcular solapamiento (10% de tokens del chunk actual conservados)
                tokens_solapamiento = int(tokens_acumulados * solapamiento)
                buffer_overlap: list[str] = []
                tokens_overlap = 0
                for rev_p in reversed(buffer_parrafos):
                    tok_rev = _estimar_tokens(rev_p)
                    buffer_overlap.insert(0, rev_p)
                    tokens_overlap += tok_rev
                    if tokens_overlap >= tokens_solapamiento:
                        break

                buffer_parrafos = list(buffer_overlap)
                tokens_acumulados = tokens_overlap

            buffer_parrafos.append(parrafo)
            tokens_acumulados += tokens_p

        if buffer_parrafos:
            texto_chunk = "\n\n".join(buffer_parrafos)
            fragmentos.append({
                "encabezado": encabezado,
                "texto": texto_chunk,
                "propiedad_id": propiedad_id,
                "orden": orden_global,
            })
            orden_global += 1

    return fragmentos
