# ¤spec-glamping
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de forma de las especificaciones de tarea (G-2, playbook SDD del CTO).

Cada ficha no sellada de ``governance/tareas/TASKS.md`` fuera de ``SIN_SPEC`` tiene su
``docs/spec/tareas/<id>.md``, y esa especificación cumple:

- E1: existe;
- E2: tiene los títulos ``## Datos``, ``## API``, ``## Reglas``, ``## Interfaz``, ``## Aceptación`` y
  ``## Trazabilidad``, en ese orden y una vez cada uno (las líneas en bloques de código no cuentan);
- E3: ninguna de esas seis secciones está vacía («No aplica.» con su motivo vale);
- E4: Datos nombra la base medida, ``origin/main <sha>``;
- E5: Aceptación es una tabla ``Caso | Dado/entonces | Prueba | Mutación`` con casos ``A<n>`` únicos,
  pruebas ``<ruta>::<función>`` de la ficha y mutaciones ``m<n>:`` únicas;
- E6: Trazabilidad nombra un rastro ``¤<nombre>``.

E7 (``SIN_SPEC`` es cerrada y solo se achica) se verifica en ``tests/test_verificar_especificaciones.py``.
No mide la calidad del contenido: eso lo revisan el Arquitecto, el Tech Lead y el CTO.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Callable

SECCIONES: tuple[str, ...] = ("Datos", "API", "Reglas", "Interfaz", "Aceptación", "Trazabilidad")
# E7: fichas que arrancaron antes del playbook SDD. Lista cerrada: solo se le sacan miembros.
# T-406-b salió: se fusionó sin ficha (PR #8) y nunca entra a TASKS.md.
SIN_SPEC: frozenset[str] = frozenset({
    "T-111", "T-211", "T-311", "T-410", "T-411", "T-511", "T-610", "T-810", "T-611", "T-701",
})

RAIZ = Path(__file__).resolve().parent.parent
TASKS = Path("governance/tareas/TASKS.md")
CARPETA = Path("docs/spec/tareas")
COLUMNAS = ("Caso", "Dado/entonces", "Prueba", "Mutación")

_RE_FICHA = re.compile(r"```toml\n(.*?)```", re.S)
_RE_SHA = re.compile(r"origin/main\W{0,3}[0-9a-f]{7,40}\b")
_RE_RASTRO = re.compile(r"¤[a-z0-9-]+")
_RE_CASO = re.compile(r"A\d+")
_RE_MUTACION = re.compile(r"(m\d+):\s*\S")
_RE_BARRA = re.compile(r"(?<!\\)\|")


# ¤spec-glamping
def fichas(raiz: Path) -> list[dict]:
    """Bloques ``toml`` de TASKS.md, con la misma regex que ``tests/test_tareas_sin_colision.py``."""
    texto = (raiz / TASKS).read_text(encoding="utf-8")
    return [tomllib.loads(bloque) for bloque in _RE_FICHA.findall(texto)]


# ¤spec-glamping
def _secciones(texto: str) -> list[tuple[str, list[str]]]:
    """Títulos de nivel 2 fuera de bloques de código, cada uno con las líneas que lo siguen."""
    secciones: list[tuple[str, list[str]]] = []
    en_codigo = False
    for linea in texto.splitlines():
        if linea.lstrip().startswith("```"):
            en_codigo = not en_codigo
        elif not en_codigo and linea.startswith("## "):
            secciones.append((linea[3:].strip(), []))
            continue
        if secciones:
            secciones[-1][1].append(linea)
    return secciones


# ¤spec-glamping
def _violaciones_e2(id_: str, titulos: list[str]) -> list[str]:
    violaciones = []
    for seccion in SECCIONES:
        veces = titulos.count(seccion)
        if veces == 0:
            violaciones.append(f"{id_}: E2 falta la sección «## {seccion}»")
        elif veces > 1:
            violaciones.append(f"{id_}: E2 la sección «## {seccion}» aparece {veces} veces")
    vistos = list(dict.fromkeys(t for t in titulos if t in SECCIONES))
    if vistos != [s for s in SECCIONES if s in vistos]:
        violaciones.append(f"{id_}: E2 secciones fuera de orden: {', '.join(vistos)}")
    return violaciones


# ¤spec-glamping
def _celdas(linea: str) -> list[str]:
    """Celdas de una fila Markdown: un ``\\|`` escapado no parte la celda y se quitan las comillas invertidas."""
    partes = _RE_BARRA.split(linea.strip())
    if partes and partes[0] == "":
        partes = partes[1:]
    if partes and partes[-1] == "":
        partes = partes[:-1]
    celdas = []
    for parte in partes:
        celda = parte.replace("\\|", "|").strip()
        if len(celda) >= 2 and celda.startswith("`") and celda.endswith("`"):
            celda = celda[1:-1].strip()
        celdas.append(celda)
    return celdas


# ¤spec-glamping
def _filas_de_aceptacion(lineas: list[str]) -> list[list[str]] | None:
    """Filas de la tabla ``Caso | Dado/entonces | Prueba | Mutación``, o None si no hay tabla."""
    for i, linea in enumerate(lineas):
        if linea.lstrip().startswith("|") and tuple(_celdas(linea)) == COLUMNAS:
            filas = []
            for fila in lineas[i + 2:]:
                if not fila.lstrip().startswith("|"):
                    break
                filas.append(_celdas(fila))
            return filas
    return None


# ¤spec-glamping
def _violaciones_e5(ficha: dict, lineas: list[str], leer: Callable[[str], str | None]) -> list[str]:
    id_ = ficha["id"]
    filas = _filas_de_aceptacion(lineas)
    if filas is None:
        return [f"{id_}: E5 Aceptación no tiene la tabla «{' | '.join(COLUMNAS)}»"]
    if not filas:
        return [f"{id_}: E5 la tabla de Aceptación no tiene filas"]
    de_la_ficha = set(ficha.get("propiedad", [])) | set(ficha.get("crea", []))
    violaciones: list[str] = []
    casos: set[str] = set()
    mutaciones: set[str] = set()
    for fila in filas:
        if len(fila) != len(COLUMNAS):
            violaciones.append(f"{id_}: E5 la fila «{' | '.join(fila)}» no tiene {len(COLUMNAS)} celdas")
            continue
        caso, _dado, prueba, mutacion = fila
        if not _RE_CASO.fullmatch(caso):
            violaciones.append(f"{id_}: E5 el caso «{caso}» no tiene la forma A<n>")
        elif caso in casos:
            violaciones.append(f"{id_}: E5 el caso {caso} se repite")
        casos.add(caso)
        ruta, separador, funcion = prueba.partition("::")
        if not separador or not ruta or not funcion.isidentifier():
            violaciones.append(f"{id_}: E5 {caso} la prueba «{prueba}» no tiene la forma <ruta>::<función>")
        elif ruta not in de_la_ficha:
            violaciones.append(f"{id_}: E5 {caso} la prueba {ruta} no está en la propiedad ni en el crea de la ficha")
        else:
            contenido = leer(ruta)
            if contenido is not None and not re.search(rf"^\s*def {re.escape(funcion)}\(", contenido, re.M):
                violaciones.append(f"{id_}: E5 {caso} {ruta} no define {funcion}")
        marca = _RE_MUTACION.match(mutacion)
        if marca is None:
            violaciones.append(f"{id_}: E5 {caso} la mutación «{mutacion}» no empieza con m<n>: y un texto")
        elif marca.group(1) in mutaciones:
            violaciones.append(f"{id_}: E5 {caso} la mutación {marca.group(1)} se repite")
        else:
            mutaciones.add(marca.group(1))
    return violaciones


# ¤spec-glamping
def violaciones_de_especificacion(
    ficha: dict,
    texto: str | None,
    leer: Callable[[str], str | None],
) -> list[str]:
    """E1 a E6 sobre el texto de ``docs/spec/tareas/<id>.md`` (None si no existe)."""
    id_ = ficha["id"]
    if texto is None:
        return [f"{id_}: E1 sin especificación en {CARPETA.as_posix()}/{id_}.md"]
    secciones = _secciones(texto)
    violaciones = _violaciones_e2(id_, [titulo for titulo, _ in secciones])
    contenido: dict[str, list[str]] = {}
    for titulo, lineas in secciones:
        if titulo not in SECCIONES:
            continue
        contenido.setdefault(titulo, lineas)
        if not any(linea.strip() for linea in lineas):
            violaciones.append(f"{id_}: E3 la sección «## {titulo}» está vacía")
    if "Datos" in contenido and not _RE_SHA.search("\n".join(contenido["Datos"])):
        violaciones.append(f"{id_}: E4 Datos no nombra la base medida (origin/main <sha>)")
    if "Aceptación" in contenido:
        violaciones += _violaciones_e5(ficha, contenido["Aceptación"], leer)
    if "Trazabilidad" in contenido and not _RE_RASTRO.search("\n".join(contenido["Trazabilidad"])):
        violaciones.append(f"{id_}: E6 Trazabilidad no nombra ningún rastro")
    return violaciones


# ¤spec-glamping
def violaciones_del_repositorio(raiz: Path, sin_spec: frozenset[str] = SIN_SPEC) -> list[str]:
    """E1 a E6 para cada ficha no sellada cuyo id no esté en ``sin_spec``."""

    def leer(ruta: str) -> str | None:
        archivo = raiz / ruta
        return archivo.read_text(encoding="utf-8") if archivo.is_file() else None

    violaciones: list[str] = []
    for ficha in fichas(raiz):
        if ficha.get("estado") == "sellada" or ficha["id"] in sin_spec:
            continue
        violaciones += violaciones_de_especificacion(ficha, leer(f"{CARPETA.as_posix()}/{ficha['id']}.md"), leer)
    return violaciones


# ¤spec-glamping
def main(argv: list[str] | None = None) -> int:
    """Uso: ``python scripts/verificar_especificaciones.py [raiz]``. Devuelve 1 si hay alguna violación."""
    argv = sys.argv[1:] if argv is None else argv
    raiz = Path(argv[0]) if argv else RAIZ
    violaciones = violaciones_del_repositorio(raiz)
    for violacion in violaciones:
        print(violacion)
    return 1 if violaciones else 0


if __name__ == "__main__":
    sys.exit(main())
