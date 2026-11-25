# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""K2 del dictamen del paso 4 (ADR-0021): candado completo con hashes y la imagen instala desde él."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_REQUISITO = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==([^\s;\\]+)", re.M)


# ¤inferencia
def _normalizar(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).lower()


# ¤inferencia
def _bloques(texto: str) -> list[str]:
    """Cada requisito con sus líneas de continuación (``\\``) y sin comentarios."""
    lineas = [l for l in texto.splitlines() if not l.lstrip().startswith("#")]
    return [b for b in re.split(r"\n(?=\S)", "\n".join(lineas)) if b.strip()]


# ¤inferencia
def test_k2_cada_requisito_del_candado_esta_fijado_y_con_hash() -> None:
    bloques = _bloques((RAIZ / "requirements.lock").read_text(encoding="utf-8"))
    assert len(bloques) > 10, "el candado debe incluir las dependencias transitivas"
    for bloque in bloques:
        assert _REQUISITO.match(bloque), f"sin versión exacta: {bloque.splitlines()[0]}"
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", bloque), f"sin hash: {bloque.splitlines()[0]}"


# ¤inferencia
def test_k2_el_candado_cubre_las_dependencias_directas_y_el_backend() -> None:
    fijadas = {_normalizar(m.group(1)) for m in _REQUISITO.finditer((RAIZ / "requirements.lock").read_text(encoding="utf-8"))}
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    directas = {_normalizar(re.split(r"[<>=\[ ;]", d, maxsplit=1)[0]) for d in proyecto["project"]["dependencies"]}
    faltan = (directas | {"setuptools", "google-auth", "pydantic"}) - fijadas
    assert not faltan, f"faltan en el candado: {sorted(faltan)}"


# ¤inferencia
def test_k2_el_dockerfile_instala_desde_el_candado_con_hashes() -> None:
    docker = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY requirements.lock" in docker
    assert re.search(r"pip install[^\n]*--require-hashes[^\n]*-r requirements\.lock", docker)
    # El paquete propio se instala sin resolver dependencias ni bajar el backend de construcción.
    assert re.search(r"pip install[^\n]*--no-deps[^\n]*--no-build-isolation[^\n]* \.", docker)
    assert not re.search(r"pip install (--upgrade pip|\.)\s*$", docker, re.M)
