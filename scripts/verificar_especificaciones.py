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

_RE_FICHA = re.compile(r"```toml\n(.*?)```", re.S)


# ¤spec-glamping
def fichas(raiz: Path) -> list[dict]:
    """Bloques ``toml`` de TASKS.md, con la misma regex que ``tests/test_tareas_sin_colision.py``."""
    texto = (raiz / TASKS).read_text(encoding="utf-8")
    return [tomllib.loads(bloque) for bloque in _RE_FICHA.findall(texto)]


# ¤spec-glamping
def violaciones_de_especificacion(
    ficha: dict,
    texto: str | None,
    leer: Callable[[str], str | None],
) -> list[str]:
    """E1 a E6 sobre el texto de ``docs/spec/tareas/<id>.md`` (None si no existe)."""
    return []  # rojo de G-2: se implementa en el arreglo


# ¤spec-glamping
def violaciones_del_repositorio(raiz: Path, sin_spec: frozenset[str] = SIN_SPEC) -> list[str]:
    """E1 a E6 para cada ficha no sellada cuyo id no esté en ``sin_spec``."""
    return []  # rojo de G-2: se implementa en el arreglo


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
