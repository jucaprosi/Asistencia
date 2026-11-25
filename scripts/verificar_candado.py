# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""r2 (ADR-0021, K2): árbitro de deriva entre pyproject.toml/construccion.in y requirements.lock.

Cada requisito directo que aplica a la imagen (Linux x86_64, Python 3.12) debe estar fijado en el
candado con una versión que cumpla su especificador. Sale con 1 y lista las derivas si las hay.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

_FIJADO = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;\\]+)", re.M)
# Entorno de la imagen para la que se genera el candado (ver su encabezado).
_ENTORNO_IMAGEN = {
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "os_name": "posix",
    "python_version": "3.12",
    "python_full_version": "3.12.0",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
    "extra": "",
}


# ¤inferencia
def _fijadas(candado: str) -> dict[str, Version]:
    return {canonicalize_name(m.group(1)): Version(m.group(2)) for m in _FIJADO.finditer(candado)}


# ¤inferencia
def derivas(requisitos: list[str], candado: str) -> list[str]:
    """Describe cada requisito que el candado no satisface; lista vacía si no hay deriva."""
    fijadas = _fijadas(candado)
    problemas: list[str] = []
    for texto in requisitos:
        req = Requirement(texto)
        if req.marker is not None and not req.marker.evaluate(_ENTORNO_IMAGEN):
            continue
        nombre = canonicalize_name(req.name)
        version = fijadas.get(nombre)
        if version is None:
            problemas.append(f"{nombre}: no está fijado en requirements.lock")
        elif not req.specifier.contains(version, prereleases=True):
            problemas.append(f"{nombre}: el candado fija {version}, que no cumple '{req.specifier}'")
    return problemas


# ¤inferencia
def _requisitos_de_construccion(texto: str) -> list[str]:
    return [l.split("#", 1)[0].strip() for l in texto.splitlines() if l.split("#", 1)[0].strip()]


# ¤inferencia
def derivas_del_repositorio(raiz: Path) -> list[str]:
    proyecto = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    requisitos = list(proyecto["project"]["dependencies"])
    requisitos += _requisitos_de_construccion((raiz / "construccion.in").read_text(encoding="utf-8"))
    return derivas(requisitos, (raiz / "requirements.lock").read_text(encoding="utf-8"))


# ¤inferencia
def main() -> int:
    problemas = derivas_del_repositorio(Path(__file__).resolve().parents[1])
    for p in problemas:
        print(f"DERIVA {p}")
    print("candado al día" if not problemas else "regenera requirements.lock (comando en su encabezado)")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
