# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Bloqueantes 1, 2 y 7 del ADR-0021, contra la sala agente tal como está (paso 2 del Orden: en rojo)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from features.agente.cliente_modelo_internal import ClienteModelo
from features.agente.tipos import ModeloNoDisponible

RAIZ = Path(__file__).resolve().parents[2]
_IMPORT_GENAI = re.compile(r"^\s*(?:import\s+google\.genai|from\s+google\.genai\b|from\s+google\s+import\s+genai)", re.M)


# ¤inferencia
def _fuentes() -> list[Path]:
    rutas = [*RAIZ.joinpath("features").rglob("*.py"), *RAIZ.joinpath("features").rglob("*.yaml")]
    rutas += [*RAIZ.joinpath("app_core").rglob("*.py")]
    return sorted(r for r in rutas if "__pycache__" not in r.parts)


# ¤inferencia
def test_b1_sin_conector_no_hay_respuesta_simulada() -> None:
    """Bloqueante 1 (INV_MODELO_FALLA_CERRADA): sin proveedor no se inventa texto."""
    cliente = ClienteModelo({"timeout_modelo_s": 5, "modelos": {"principal": "gemini-3.8-flash"}})
    with pytest.raises(ModeloNoDisponible):
        cliente.generar([{"role": "user", "content": "hola"}], system_prompt="s")


# ¤inferencia
def test_b2_config_agente_sin_modelos_region_ni_claves() -> None:
    """Bloqueante 2 y C3: modelos, región, proyecto y claves no viven en agente ni tienen valores por defecto."""
    texto = (RAIZ / "features" / "agente" / "config_agente.yaml").read_text(encoding="utf-8")
    datos = yaml.safe_load(texto)
    for clave in ("proveedor", "modelos", "clave_api", "gcp"):
        assert clave not in datos, f"config_agente.yaml no debe declarar '{clave}' (ADR-0021)"
    for prohibido in ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "us-central1"):
        assert prohibido not in texto, f"config_agente.yaml menciona {prohibido}"


# ¤inferencia
def test_b2_precios_de_modelo_fuera_de_agente() -> None:
    """C3: la tabla de precios y los nombres de modelo pasan a inferencia."""
    fuente = (RAIZ / "features" / "agente" / "cliente_modelo_internal.py").read_text(encoding="utf-8")
    assert "PRECIOS_POR_MILLON" not in fuente
    assert "gemini-" not in fuente


# ¤inferencia
def test_b7_sin_claude_ni_anthropic_en_codigo_ni_config() -> None:
    """Bloqueante 7 (INV_MODELO_EN_LISTA_BLANCA): proveedor único, sin rama de respaldo a Claude."""
    hallazgos = [
        str(r.relative_to(RAIZ))
        for r in _fuentes()
        if re.search(r"claude-|anthropic", r.read_text(encoding="utf-8"), re.I)
    ]
    assert hallazgos == [], hallazgos


# ¤inferencia
def test_b7_google_genai_solo_en_la_sala_inferencia() -> None:
    """INV_MODELO_EN_LISTA_BLANCA y C2: ningún tipo del SDK cruza la compuerta."""
    fuera = [
        str(r.relative_to(RAIZ))
        for r in _fuentes()
        if r.suffix == ".py" and _IMPORT_GENAI.search(r.read_text(encoding="utf-8"))
        and "inferencia" not in r.relative_to(RAIZ).parts[:2]
    ]
    assert fuera == [], fuera
