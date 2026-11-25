# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Paso 4 del ADR-0021, C2: ``construir()`` conecta el tope diario de observabilidad a la compuerta de inferencia."""
from __future__ import annotations

import pytest

from app_core.app_core_service import construir
from tests.app_core.test_contenedor import ENTORNO_PRUEBA


# ¤inferencia
def test_c2_construir_inyecta_la_cuota_diaria(monkeypatch: pytest.MonkeyPatch) -> None:
    for clave in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(clave, raising=False)
    entorno = {**ENTORNO_PRUEBA, "GOOGLE_CLOUD_PROJECT": "proyecto-de-prueba", "VERTEX_LOCATION": "us"}
    entorno.pop("ANTHROPIC_API_KEY", None)
    estado = construir(entorno=entorno).inferencia.estado()
    assert estado.motivo != "sin_tope_diario"
    assert estado.con_tope_diario is True
