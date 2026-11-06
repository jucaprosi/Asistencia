# ¤pms-conector
# ¤¤integration-engineer
"""Pruebas de validación local del titular contra pms.reservas_ref (RF-PMS-06)."""
from __future__ import annotations

from datetime import date
import pytest

from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.pms_conector_service import (
    PMSConectorService,
)
from tests.pms_conector.dobles import DobleObservabilidad


def test_validar_titular_local_sin_llamar_al_pms() -> None:
    """Escenario: Validar al titular sin llamar al PMS (@RF-PMS-06).
    
    Dado una reserva guardada en la referencia local
    Cuando se valida al titular de la conversación
    Entonces la decisión usa esa referencia y el PMS no recibe ninguna llamada
    """
    pms_fake = FakePMS()
    servicio = PMSConectorService(
        config={"escrituras_habilitadas": {"crear_reserva_preliminar": True}},
        observabilidad=DobleObservabilidad(),
        conector=pms_fake,
    )

    huesped_token = "tok_huesped_referencia_001"

    # 1. Crear reserva que se almacena en la tabla local pms.reservas_ref
    reserva = servicio.crear_reserva_preliminar(
        propiedad_id="glamping_imbabura",
        unidad_id="domo_lago",
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 3),
        huespedes=2,
        huesped_token=huesped_token,
        clave_idempotencia="uuid_ref_001",
    )

    # Resetear contador de llamadas al PMS
    pms_fake.llamadas_realizadas = 0

    # 2. Validar titular legítimo usando la referencia local
    es_valido = servicio.validar_titular_local(reserva.codigo, huesped_token)
    assert es_valido is True

    # 3. Comprobar que el PMS no recibió NINGUNA llamada
    assert pms_fake.llamadas_realizadas == 0

    # 4. Validar token incorrecto sin llamar al PMS
    es_invalido = servicio.validar_titular_local(reserva.codigo, "tok_impostor")
    assert es_invalido is False
    assert pms_fake.llamadas_realizadas == 0


def test_obtener_referencia_local_recupera_datos_exactos_sin_llamar_al_pms() -> None:
    """obtener_referencia_local retorna los datos de la reserva desde sqlite sin tocar el PMS."""
    pms_fake = FakePMS()
    servicio = PMSConectorService(
        config={"escrituras_habilitadas": {"crear_reserva_preliminar": True}},
        observabilidad=DobleObservabilidad(),
        conector=pms_fake,
    )

    res = servicio.crear_reserva_preliminar(
        propiedad_id="dep_ibarra_centro",
        unidad_id="suite_101",
        desde=date(2026, 12, 5),
        hasta=date(2026, 12, 7),
        huespedes=2,
        huesped_token="tok_huesped_dep",
        clave_idempotencia="uuid_ref_002",
    )

    pms_fake.llamadas_realizadas = 0

    local = servicio.obtener_referencia_local(res.codigo)
    assert local is not None
    assert local.codigo == res.codigo
    assert local.propiedad_id == "dep_ibarra_centro"
    assert local.total == res.total
    assert pms_fake.llamadas_realizadas == 0
