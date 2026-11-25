# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""r1 del dictamen K2 (ADR-0021): el CI instala desde el candado con hashes, como la imagen; K1 corre en PostgreSQL."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CI = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


# ¤inferencia
def _pasos_de_instalacion() -> list[str]:
    return [b for b in re.split(r"\n\s*- name: ", CI) if "pip install" in b]


# ¤inferencia
def test_r1_cada_instalacion_de_python_parte_del_candado() -> None:
    pasos = _pasos_de_instalacion()
    assert len(pasos) >= 2, "los dos trabajos instalan dependencias de Python"
    for paso in pasos:
        candado = re.search(r"pip install[^\n]*--require-hashes[^\n]*-r requirements\.lock", paso)
        proyecto = re.search(r"pip install[^\n]*-e \"?\.(\[dev\])?\"?", paso)
        assert candado, f"no instala desde el candado: {paso.splitlines()[0]}"
        assert proyecto is None or candado.start() < proyecto.start(), "el candado va antes del paquete"


# ¤inferencia
def test_r1_las_dependencias_resueltas_son_coherentes() -> None:
    for paso in _pasos_de_instalacion():
        assert "pip check" in paso


# ¤inferencia
def test_k1_el_ci_corre_la_cuota_en_postgresql_despues_de_migrar() -> None:
    migrar = CI.find("scripts/migrar_db.py")
    prueba = CI.find("tests/observabilidad/test_k1_cuota_postgresql.py")
    assert 0 < migrar < prueba
    assert re.search(r"TEST_DATABASE_URL:\s*postgresql://", CI[migrar:])
