# ¤observabilidad
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-416: las evaluaciones construyen AgenteService con SeguridadService real (RF-OBS-03, RF-SEC-05).

La suite enrutador no se omite en silencio: una falla queda registrada sin datos.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.seguridad.seguridad_service import SeguridadService
from scripts.run_evals import evaluar_suite

_METRICAS = {"aciertos": 1.0, "total": 20}


def _espia_agente() -> MagicMock:
    espia = MagicMock(name="AgenteService")
    espia.return_value.evaluar.return_value = dict(_METRICAS)
    return espia


# ¤observabilidad
def test_r1_evaluar_pasa_seguridad_real() -> None:
    """A1: ObservabilidadService.evaluar construye AgenteService con SeguridadService real."""
    espia = _espia_agente()
    with patch("features.agente.agente_service.AgenteService", espia):
        ObservabilidadService(cargar_config()).evaluar(suites=("enrutador",))
    assert espia.call_count == 1
    assert isinstance(espia.call_args.kwargs.get("seguridad"), SeguridadService)


# ¤observabilidad
def test_r1_run_evals_pasa_seguridad_real() -> None:
    """A2: run_evals.evaluar_suite('enrutador') construye AgenteService con SeguridadService real."""
    espia = _espia_agente()
    with patch("features.agente.agente_service.AgenteService", espia):
        estado, codigo = evaluar_suite("enrutador")
    assert espia.call_count == 1
    assert isinstance(espia.call_args.kwargs.get("seguridad"), SeguridadService)
    assert codigo == 0 and "APROBADA" in estado


# ¤observabilidad
def test_r3_falla_del_enrutador_se_registra_sin_datos() -> None:
    """A3: la falla del enrutador deja evaluacion_fallida con suite y tipo, sin el mensaje."""
    servicio = ObservabilidadService(cargar_config())
    with patch(
        "features.agente.agente_service.AgenteService.evaluar",
        side_effect=RuntimeError("dato 0991234567"),
    ), patch.object(ObservabilidadService, "log") as log:
        resultados = servicio.evaluar(suites=("enrutador",))
    assert "enrutador" not in resultados
    llamadas = [c for c in log.call_args_list if "evaluacion_fallida" in c.args]
    assert len(llamadas) == 1
    assert llamadas[0].kwargs.get("suite") == "enrutador"
    assert llamadas[0].kwargs.get("tipo") == "RuntimeError"
    assert "0991234567" not in json.dumps(
        [list(c.args) + [c.kwargs] for c in log.call_args_list], default=str
    )


# ¤observabilidad
def test_r4_las_otras_suites_no_cambian() -> None:
    """A4: la falla de rag no se registra (R4)."""
    servicio = ObservabilidadService(cargar_config())
    with patch(
        "features.conocimiento.conocimiento_service.ConocimientoService.evaluar",
        side_effect=RuntimeError("falla rag"),
    ), patch.object(ObservabilidadService, "log") as log:
        resultados = servicio.evaluar(suites=("rag",))
    assert "rag" not in resultados
    assert not [c for c in log.call_args_list if "evaluacion_fallida" in c.args]


# ¤observabilidad
def test_r5_evaluacion_real_trae_aciertos() -> None:
    """A5: la evaluación real de enrutador, con seguridad real, trae aciertos."""
    resultados = ObservabilidadService(cargar_config()).evaluar(suites=("enrutador",))
    assert "aciertos" in resultados["enrutador"]
