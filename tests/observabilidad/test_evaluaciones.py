# ¤observabilidad
# ¤¤devops-engineer
"""Pruebas del despacho de evaluaciones y verificación de umbrales (RF-OBS-03)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.observabilidad.tipos import SuiteNoEncontrada
from scripts.run_evals import RAIZ, evaluar_suite, main


# ¤observabilidad
def test_evaluacion_bajo_umbral_retorna_codigo_distinto_de_cero() -> None:
    """Escenario: Evaluación bajo umbral (@RF-RAG-06 @RF-OBS-03).

    Dado una suite con resultado bajo su umbral
    Cuando corre scripts/run_evals.py
    Entonces termina con Exit Code distinto de 0
    """
    # Simulamos que el evaluador del enrutador obtiene una precisión de 80% (bajo el umbral de 100%)
    mock_metricas = {"aciertos": 0.80, "total": 20}
    with patch("features.agente.agente_service.AgenteService.evaluar", return_value=mock_metricas):
        estado, codigo = evaluar_suite("enrutador")
        assert codigo != 0
        assert "FALLO_UMBRAL" in estado


# ¤observabilidad
def test_evaluacion_suite_omitida_no_declara_verde_falso() -> None:
    """Una suite sin casos o sin evaluador implementado se reporta OMITIDA con exit 0."""
    with patch.dict("scripts.run_evals.SUITES", {"suite_omitida": RAIZ / "evals" / "inexistente.jsonl"}):
        estado, codigo = evaluar_suite("suite_omitida")
        assert codigo == 0
        assert "OMITIDA" in estado
        assert "APROBADA" not in estado


# ¤observabilidad
def test_servicio_evaluar_suite_desconocida_lanza_error() -> None:
    """ObservabilidadService.evaluar lanza SuiteNoEncontrada ante una suite inválida."""
    servicio = ObservabilidadService(cargar_config())
    with pytest.raises(SuiteNoEncontrada):
        servicio.evaluar(suites=("suite_inexistente_xyz",))


# ¤observabilidad
def test_servicio_evaluar_despacha_suites_existentes() -> None:
    """ObservabilidadService.evaluar despacha correctamente y devuelve métricas."""
    servicio = ObservabilidadService(cargar_config())
    resultados = servicio.evaluar(suites=("enrutador",))
    assert "enrutador" in resultados
    assert "aciertos" in resultados["enrutador"]
