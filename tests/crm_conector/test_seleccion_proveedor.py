# ¤crm-conector
# ¤¤integration-engineer
"""Tests de selección de proveedor de CRM por configuración (RF-CRM-02)."""
from __future__ import annotations

import pytest

from features.crm_conector.crm_conector_service import CRMConectorService, cargar_config
from features.crm_conector.fake_internal import FakeCRM
from features.crm_conector.tipos import CRMNoDisponible
from tests.crm_conector.dobles import DobleCRMAlternativo, DobleObservabilidadService


# ¤crm-conector
def test_proveedor_activo_por_defecto_es_fake() -> None:
    obs = DobleObservabilidadService()
    servicio = CRMConectorService(observabilidad=obs)
    assert isinstance(servicio._conector, FakeCRM)


# ¤crm-conector
def test_seleccion_proveedor_fake_explicito() -> None:
    obs = DobleObservabilidadService()
    config = {"proveedor": "fake", "bandeja_handoff_activa": True}
    servicio = CRMConectorService(config, observabilidad=obs)
    assert isinstance(servicio._conector, FakeCRM)


# ¤crm-conector
def test_seleccion_proveedor_desconocido_falla() -> None:
    obs = DobleObservabilidadService()
    config = {"proveedor": "proveedor_inexistente"}
    with pytest.raises(CRMNoDisponible):
        CRMConectorService(config, observabilidad=obs)


# ¤crm-conector
def test_inyeccion_conector_personalizado() -> None:
    obs = DobleObservabilidadService()
    doble = DobleCRMAlternativo()
    servicio = CRMConectorService(observabilidad=obs, conector=doble)
    assert servicio._conector is doble


# ¤crm-conector
def test_cargar_config_resuelve_valores_por_defecto() -> None:
    cfg = cargar_config()
    assert isinstance(cfg, dict)
    assert cfg.get("proveedor") in {"fake", "ghl", "chatwoot_attio"}
    assert "bandeja_handoff_activa" in cfg
