# ¤persistencia-sql
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de migraciones de ADR-0023.

Reglas:
- nombres ``AAAAMMDDHHMM_<sala>_<slug>.sql`` con sala ADPA existente, salvo los heredados;
- una sola migración por marca de tiempo;
- una migración nueva no se ordena antes que la última de la rama base;
- ``esquema.sql`` y las migraciones de la rama base no cambian;
- la marca de tiempo es una fecha real y no está a más de un día en el futuro;
- una sala sin schema no tiene migraciones;
- una migración solo escribe (DDL o DML) en los schemas de su sala; ``-- depende:`` ordena y permite
  referenciar el schema de la sala dependida, nunca escribir en él;
- no se usa ``search_path`` y solo persistencia_sql crea schemas;
- toda dependencia existe y se aplica antes.

La detección es léxica (sin parser SQL) y falla hacia el lado seguro: se quitan comillas dobles y
comentarios, y una mención dudosa hace fallar la migración.

Uso: ``python scripts/verificar_migraciones.py [--base origin/main]`` (Exit Code 0 si cumple).
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_MIGRACIONES = RAIZ / "docs" / "spec" / "migraciones"
RUTA_ESQUEMA = RAIZ / "docs" / "spec" / "esquema.sql"

# Archivos anteriores a ADR-0023: no se renombran porque su nombre está registrado en las bases.
HEREDADAS = frozenset({"001_alinear_esquema_con_codigo.sql"})

# Sala ADPA → schemas SQL que le pertenecen. Una sala sin schema no puede tocar ninguno sin declararlo.
SCHEMAS_POR_SALA: dict[str, frozenset[str]] = {
    "agente": frozenset({"agente"}),
    "anfitriones": frozenset({"anfitriones"}),
    "arm_jarvis": frozenset({"arm"}),
    "canal_whatsapp": frozenset({"canal"}),
    "comisiones": frozenset({"comisiones"}),
    "conocimiento": frozenset({"conocimiento"}),
    "crm_conector": frozenset({"crm"}),
    "herramientas_glamping": frozenset(),
    "observabilidad": frozenset({"observabilidad"}),
    "panel_operativo": frozenset({"panel"}),
    "persistencia_sql": frozenset({"public"}),
    "pms_conector": frozenset({"pms"}),
    "seguridad": frozenset({"seguridad"}),
    "web_huespedes": frozenset({"web"}),
}
TODOS_LOS_SCHEMAS = frozenset().union(*SCHEMAS_POR_SALA.values())

_PATRON_NOMBRE = re.compile(r"^(\d{12})_([a-z][a-z0-9_]*?)_([a-z0-9][a-z0-9_]*)\.sql$")
_PATRON_DEPENDE = re.compile(r"^--\s*depende:\s*(\S+)\s*$", re.MULTILINE)
_ID = r"[a-z_][a-z0-9_$]*"
_PATRON_SCHEMA = re.compile(r"\b(" + "|".join(sorted(TODOS_LOS_SCHEMAS)) + r")\.[a-z_]")
# Objetos sobre los que una sentencia escribe; grupo 1 = schema (None si no está calificado → public).
_PATRONES_ESCRITURA = [
    re.compile(
        r"\b(?:create|alter|drop)\s+(?:or\s+replace\s+)?(?:unlogged\s+|temporary\s+|temp\s+)?(?:materialized\s+)?"
        r"(?:table|view|function|procedure|sequence|type|domain)\s+(?:if\s+(?:not\s+)?exists\s+)?(?:only\s+)?"
        rf"(?:({_ID})\.)?{_ID}"
    ),
    re.compile(rf"\bdrop\s+(?:index|trigger)\s+(?:concurrently\s+)?(?:if\s+exists\s+)?({_ID})\.{_ID}"),
    re.compile(rf"\bon\s+(?:only\s+)?({_ID})\.{_ID}"),
    re.compile(rf"\balter\s+index\s+(?:if\s+exists\s+)?({_ID})\.{_ID}"),
    re.compile(rf"\binto\s+(?:({_ID})\.)?{_ID}"),  # INSERT INTO, SELECT INTO, MERGE INTO
    re.compile(rf"\bcopy\s+(?:({_ID})\.)?{_ID}"),
    re.compile(rf"\bcomment\s+on\s+(?:materialized\s+)?\w+\s+({_ID})\.{_ID}"),
    re.compile(rf"\bupdate\s+(?:only\s+)?(?:({_ID})\.)?{_ID}\s+(?:as\s+)?(?:{_ID}\s+)?set\b"),
    re.compile(rf"\bdelete\s+from\s+(?:only\s+)?(?:({_ID})\.)?{_ID}"),
    re.compile(rf"\btruncate\s+(?:table\s+)?(?:only\s+)?(?:({_ID})\.)?{_ID}"),
]
_PATRON_REFERENCIA = re.compile(rf"\breferences\s+({_ID})\.{_ID}")


# ¤persistencia-sql
def _normalizar(texto: str) -> str:
    """Contenido comparable entre Windows (CRLF) y Linux (LF)."""
    return texto.replace("\r\n", "\n")


# ¤persistencia-sql
def dependencias(sql: str) -> list[str]:
    """Archivos que una migración declara con ``-- depende: <archivo>``."""
    return _PATRON_DEPENDE.findall(_normalizar(sql))


# ¤persistencia-sql
def _sala_de(nombre: str) -> str | None:
    """Sala ADPA del nombre de archivo; la más larga que encaje, porque hay salas con guion bajo."""
    coincidencia = _PATRON_NOMBRE.match(nombre)
    if not coincidencia:
        return None
    resto = nombre[13:-4]
    candidatas = [s for s in SCHEMAS_POR_SALA if resto.startswith(s + "_")]
    return max(candidatas, key=len) if candidatas else coincidencia.group(2)


# ¤persistencia-sql
def _limpiar(sql: str) -> str:
    """SQL en minúsculas, sin comentarios, literales ni comillas dobles, para el análisis léxico.

    Recorre el texto una vez: un ``--`` o ``/*`` dentro de un literal no corta nada, y cada literal
    ``'…'`` (con ``''`` escapado) queda como ``''``.
    """
    texto, salida, i = _normalizar(sql), [], 0
    while i < len(texto):
        if texto.startswith("--", i):
            fin = texto.find("\n", i)
            i = len(texto) if fin < 0 else fin
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            salida.append(" ")
            i = len(texto) if fin < 0 else fin + 2
        elif texto[i] == "'":
            i += 1
            while i < len(texto):
                if texto[i] == "'" and texto.startswith("''", i):
                    i += 2
                elif texto[i] == "'":
                    break
                else:
                    i += 1
            salida.append("''")
            i += 1
        else:
            salida.append(texto[i])
            i += 1
    return "".join(salida).replace('"', "").lower()


# ¤persistencia-sql
def _schemas_tocados(sql: str) -> set[str]:
    return set(_PATRON_SCHEMA.findall(_limpiar(sql)))


# ¤persistencia-sql
def _violaciones_de_contenido(nombre: str, sala: str, sql: str) -> list[str]:
    """Escritura fuera de la sala, schemas desconocidos, search_path y CREATE SCHEMA."""
    limpio = _limpiar(sql)
    propios = SCHEMAS_POR_SALA[sala]
    violaciones: list[str] = []
    if not propios:
        violaciones.append(f"{nombre}: la sala {sala} no tiene schema y no puede tener migraciones")
    if "search_path" in limpio or re.search(r"\bset_config\b", limpio):
        violaciones.append(f"{nombre}: usa search_path; califique cada objeto con su schema")
    if re.search(r"\b(?:create|alter|drop)\s+schema\b", limpio) and sala != "persistencia_sql":
        violaciones.append(f"{nombre}: solo persistencia_sql crea, altera o elimina schemas (o un ADR)")
    if re.search(r"\bdo\s*(?:\$|'')", limpio) or re.search(r"\bexecute\b(?!\s+(?:function|procedure)\b)", limpio):
        violaciones.append(f"{nombre}: SQL dinámico (DO / EXECUTE) no auditable; requiere un ADR")
    if re.search(r"\b(?:grant|revoke)\b", limpio) and sala not in {"seguridad", "persistencia_sql"}:
        violaciones.append(f"{nombre}: GRANT/REVOKE solo desde seguridad o persistencia_sql")
    escritos = {m.group(1) or "public" for patron in _PATRONES_ESCRITURA for m in patron.finditer(limpio)}
    for schema in sorted(escritos - propios):
        violaciones.append(f"{nombre}: escribe en el schema '{schema}', que no es de la sala {sala}")
    for schema in sorted({m.group(1) for m in _PATRON_REFERENCIA.finditer(limpio)} - TODOS_LOS_SCHEMAS):
        violaciones.append(f"{nombre}: referencia el schema desconocido '{schema}'")
    return violaciones


# ¤persistencia-sql
def cargar_base(ref: str = "origin/main") -> dict[str, str] | None:
    """Contenido de ``esquema.sql`` y de las migraciones en la rama base, o None si no está disponible."""
    def git(*argumentos: str) -> str:
        return subprocess.run(
            ["git", "-C", str(RAIZ), *argumentos], capture_output=True, check=True, encoding="utf-8"
        ).stdout

    try:
        git("rev-parse", "--verify", "--quiet", ref)
        base = {"esquema.sql": git("show", f"{ref}:docs/spec/esquema.sql")}
        for ruta in git("ls-tree", "--name-only", ref, "docs/spec/migraciones/").split():
            if ruta.endswith(".sql"):
                base[Path(ruta).name] = git("show", f"{ref}:{ruta}")
        return base
    except (OSError, subprocess.CalledProcessError):
        return None


# ¤persistencia-sql
def verificar_migraciones(carpeta: Path, ruta_esquema: Path, base: dict[str, str] | None) -> list[str]:
    """Lista de violaciones de ADR-0023 (vacía si todo cumple). Sin base, omite orden e inmutabilidad."""
    locales = {p.name: p.read_text(encoding="utf-8") for p in sorted(carpeta.glob("*.sql"))}
    violaciones: list[str] = []

    marcas: dict[str, str] = {}
    for nombre in locales:
        if nombre in HEREDADAS:
            continue
        coincidencia = _PATRON_NOMBRE.match(nombre)
        if not coincidencia:
            violaciones.append(f"{nombre}: no cumple el formato AAAAMMDDHHMM_<sala>_<slug>.sql")
            continue
        sala = _sala_de(nombre)
        if sala not in SCHEMAS_POR_SALA:
            violaciones.append(f"{nombre}: la sala '{sala}' no existe")
        marca = coincidencia.group(1)
        try:
            if datetime.strptime(marca, "%Y%m%d%H%M") > datetime.now() + timedelta(days=1):
                violaciones.append(f"{nombre}: la marca de tiempo está en el futuro")
        except ValueError:
            violaciones.append(f"{nombre}: la marca de tiempo no es una fecha real")
        if marca in marcas:
            violaciones.append(f"{nombre}: repite la marca de tiempo de {marcas[marca]}")
        marcas[marca] = nombre

    ordenadas = sorted(locales)
    for nombre, sql in locales.items():
        for dependencia in dependencias(sql):
            if dependencia not in locales:
                violaciones.append(f"{nombre}: depende de {dependencia}, que no existe")
            elif ordenadas.index(dependencia) > ordenadas.index(nombre):
                violaciones.append(f"{nombre}: depende de {dependencia}, que es posterior y se aplicaría después")
        if nombre in HEREDADAS:
            continue
        sala = _sala_de(nombre)
        if sala not in SCHEMAS_POR_SALA:
            continue
        violaciones += _violaciones_de_contenido(nombre, sala, sql)
        permitidos = set(SCHEMAS_POR_SALA[sala])
        for dependencia in dependencias(sql):
            sala_dependencia = _sala_de(dependencia)
            permitidos |= SCHEMAS_POR_SALA.get(sala_dependencia or "", frozenset())
        for schema in sorted(_schemas_tocados(sql) - permitidos):
            violaciones.append(
                f"{nombre}: toca el schema '{schema}', ajeno a la sala {sala}, sin declarar '-- depende:'"
            )

    if base is not None:
        if _normalizar(ruta_esquema.read_text(encoding="utf-8")) != _normalizar(base.get("esquema.sql", "")):
            violaciones.append("esquema.sql: la línea base cambió; los cambios van en una migración nueva")
        fusionadas = sorted(n for n in base if n != "esquema.sql")
        for nombre in fusionadas:
            if nombre not in locales:
                violaciones.append(f"{nombre}: migración de la rama base eliminada")
            elif _normalizar(locales[nombre]) != _normalizar(base[nombre]):
                violaciones.append(f"{nombre}: migración de la rama base cambió; cree una nueva")
        if fusionadas:
            ultima = fusionadas[-1]
            for nombre in sorted(set(locales) - set(base)):
                if nombre < ultima:
                    violaciones.append(
                        f"{nombre}: se ordena antes que {ultima}, la última de la rama base; renómbrela con una "
                        "marca de tiempo posterior"
                    )
    return violaciones


# ¤persistencia-sql
def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Árbitro de migraciones (ADR-0023)")
    analizador.add_argument("--base", default="origin/main", help="Rama base contra la que se compara")
    analizador.add_argument("--exigir-base", action="store_true", help="Falla si la rama base no está disponible (CI)")
    opciones = analizador.parse_args(argumentos)
    base = cargar_base(opciones.base)
    if base is None:
        if opciones.exigir_base:
            print(f"[FALLO] {opciones.base} no disponible y --exigir-base está activo")
            return 1
        print(f"[AVISO] {opciones.base} no disponible: se omiten orden e inmutabilidad contra la base")
    violaciones = verificar_migraciones(CARPETA_MIGRACIONES, RUTA_ESQUEMA, base)
    for violacion in violaciones:
        print(f"[FALLO] {violacion}")
    if not violaciones:
        print("[OK] Migraciones conformes con ADR-0023")
    return 1 if violaciones else 0


if __name__ == "__main__":
    raise SystemExit(main())
