# ¤persistencia-sql
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de migraciones de ADR-0023.

Reglas:
- nombres ``AAAAMMDDHHMM_<sala>_<slug>.sql`` con sala ADPA existente, salvo los heredados;
- una sola migración por marca de tiempo;
- una migración nueva no se ordena antes que la última de la rama base;
- ``esquema.sql`` y las migraciones de la rama base no cambian;
- cada migración toca solo los schemas de su sala, salvo los de las salas de las que declara ``-- depende:``;
- toda dependencia existe y se aplica antes.

Uso: ``python scripts/verificar_migraciones.py [--base origin/main]`` (Exit Code 0 si cumple).
"""
from __future__ import annotations

import argparse
import re
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
    "inferencia": frozenset(),
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
_PATRON_SCHEMA = re.compile(r"\b(" + "|".join(sorted(TODOS_LOS_SCHEMAS)) + r")\.[a-z_]", re.IGNORECASE)


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
def _schemas_tocados(sql: str) -> set[str]:
    sin_comentarios = "\n".join(linea.split("--", 1)[0] for linea in _normalizar(sql).splitlines())
    return {m.lower() for m in _PATRON_SCHEMA.findall(sin_comentarios)}


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
    opciones = analizador.parse_args(argumentos)
    base = cargar_base(opciones.base)
    if base is None:
        print(f"[AVISO] {opciones.base} no disponible: se omiten orden e inmutabilidad contra la base")
    violaciones = verificar_migraciones(CARPETA_MIGRACIONES, RUTA_ESQUEMA, base)
    for violacion in violaciones:
        print(f"[FALLO] {violacion}")
    if not violaciones:
        print("[OK] Migraciones conformes con ADR-0023")
    return 1 if violaciones else 0


if __name__ == "__main__":
    raise SystemExit(main())
