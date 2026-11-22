# ¤pasillo-central
# ¤¤qa-engineer
"""Prueba de fail-fast en montaje de panel operativo y CRM en pasillo central (T-901, C1)."""
from __future__ import annotations

from unittest.mock import patch
import pytest

from app_core.app_core_service import construir
from app_core.main import crear_app

ENTORNO_PRUEBA = {
    "APLICACION_ENTORNO": "prueba",
    "BD_URL": "sqlite:///:memory:",
    "PMS_PROVEEDOR": "doble",
    "CRM_PROVEEDOR": "doble",
    "SECRETO_HMAC": "secreto-test-32-caracteres-minimo!!",
    "LLM_PROVEEDOR": "doble",
}


def test_crear_app_monta_panel_exitosamente_sin_error() -> None:
    """Verifica que el montaje normal de crear_app levante la app con el contenedor."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    app = crear_app(contenedor)
    assert app is not None
    assert app.state.contenedor is contenedor


def test_fallo_en_montar_panel_hace_fallar_crear_app_fail_fast() -> None:
    """Verifica (C1) que un fallo al montar el panel no sea silenciado por try/except."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    with patch("app_core.panel_crm_router.montar_panel_y_crm", side_effect=RuntimeError("Fallo simulado en montaje de panel y CRM")):
        with pytest.raises(RuntimeError, match="Fallo simulado en montaje de panel y CRM"):
            crear_app(contenedor)
