# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""r2 del dictamen K2 (ADR-0021): el candado no puede quedar atrás de pyproject.toml ni de construccion.in."""
from __future__ import annotations

from pathlib import Path

from scripts.verificar_candado import derivas, derivas_del_repositorio

RAIZ = Path(__file__).resolve().parents[2]

_CANDADO = """\
# comentario
fastapi==0.165.0 \\
    --hash=sha256:{h}
    # via glamping
setuptools==84.2.1 \\
    --hash=sha256:{h}
""".format(h="0" * 64)


# ¤inferencia
def test_r2_el_repositorio_no_tiene_deriva() -> None:
    assert derivas_del_repositorio(RAIZ) == []


# ¤inferencia
def test_r2_sin_deriva_cuando_las_versiones_cumplen() -> None:
    assert derivas(["fastapi>=0.110", "setuptools>=69"], _CANDADO) == []


# ¤inferencia
def test_r2_detecta_una_version_que_no_cumple_el_especificador() -> None:
    resultado = derivas(["fastapi>=0.200"], _CANDADO)
    assert len(resultado) == 1 and "fastapi" in resultado[0] and "0.165.0" in resultado[0]


# ¤inferencia
def test_r2_detecta_una_dependencia_nueva_sin_fijar() -> None:
    resultado = derivas(["fastapi>=0.110", "Nueva_Lib[extra]>=1"], _CANDADO)
    assert len(resultado) == 1 and "nueva-lib" in resultado[0]


# ¤inferencia
def test_r2_ignora_extras_y_normaliza_nombres() -> None:
    assert derivas(["FastAPI[standard] >=0.110 ; python_version >= '3.12'"], _CANDADO) == []


# ¤inferencia
def test_r2_evalua_marcadores_contra_la_imagen_y_no_contra_el_host() -> None:
    # La imagen es Linux x86_64 con Python 3.12: lo de Windows no entra al candado; lo de Linux sí.
    assert derivas(["solo-windows>=1 ; sys_platform == 'win32'"], _CANDADO) == []
    assert len(derivas(["solo-linux>=1 ; sys_platform == 'linux'"], _CANDADO)) == 1
