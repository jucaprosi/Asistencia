# ¤pms-conector
# ¤¤integration-engineer
"""Pruebas de selección de proveedor y control de escrituras (RF-PMS-02, INV_ESCRITURA_PMS_EXPLICITA)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import pytest

from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.plataforma_internal import PlataformaPMS
from features.pms_conector.pms_conector_service import (
    EscrituraDeshabilitada,
    PMSConectorService,
)
from features.pms_conector.tipos import Incidencia
from tests.pms_conector.dobles import DobleObservabilidad


def test_proveedor_activo_por_defecto_es_fake() -> None:
    """Verifica que sin configuración especial el proveedor seleccionado es 'fake'."""
    servicio = PMSConectorService({}, observabilidad=DobleObservabilidad())
    assert servicio.proveedor() == "fake"
    assert isinstance(servicio.conector, FakePMS)


def test_proveedor_plataforma_seleccionable_por_config() -> None:
    """Verifica que con config proveedor='plataforma' se selecciona PlataformaPMS (RF-PMS-02)."""
    servicio = PMSConectorService({"proveedor": "plataforma"}, observabilidad=DobleObservabilidad())
    assert servicio.proveedor() == "plataforma"
    assert isinstance(servicio.conector, PlataformaPMS)



def test_escrituras_deshabilitadas_por_defecto_rechazan_operaciones() -> None:
    """Escenario: Escritura deshabilitada (@RF-PMS-02 @INV_ESCRITURA_PMS_EXPLICITA).
    
    Dado una operación de escritura no habilitada en la configuración
    Cuando se invoca
    Entonces falla con EscrituraDeshabilitada y el PMS no recibe nada
    """
    pms_fake = FakePMS()
    # Configuración por defecto: escrituras_habilitadas todo false
    servicio = PMSConectorService(
        config={
            "proveedor": "fake",
            "escrituras_habilitadas": {
                "crear_reserva_preliminar": False,
                "confirmar_reserva": False,
                "cancelar_reserva": False,
                "registrar_incidencia": False,
                "housekeeping": False,
            },
        },
        observabilidad=DobleObservabilidad(),
        conector=pms_fake,
    )

    llamadas_antes = pms_fake.llamadas_realizadas

    # 1. Intento de crear reserva preliminar
    with pytest.raises(EscrituraDeshabilitada) as exc_crear:
        servicio.crear_reserva_preliminar(
            propiedad_id="glamping_imbabura",
            unidad_id="domo_lago",
            desde=date(2026, 12, 1),
            hasta=date(2026, 12, 3),
            huespedes=2,
            huesped_token="tok_123",
            clave_idempotencia="uuid_escritura_001",
        )
    assert "crear_reserva_preliminar" in str(exc_crear.value)

    # 2. Intento de confirmar reserva
    with pytest.raises(EscrituraDeshabilitada):
        servicio.confirmar_reserva("RES-2026-0001", clave_idempotencia="uuid_conf_001")

    # 3. Intento de cancelar reserva
    with pytest.raises(EscrituraDeshabilitada):
        servicio.cancelar_reserva("RES-2026-0001", motivo="Cancelación", clave_idempotencia="uuid_canc_001")

    # 4. Intento de registrar incidencia
    inc = Incidencia(
        incidencia_id="",
        propiedad_id="glamping_imbabura",
        unidad_id="domo_lago",
        reserva_codigo=None,
        categoria="agua",
        prioridad="alta",
        descripcion_token="Falta de agua",
        estado="abierta",
        gestor_id=None,
    )
    with pytest.raises(EscrituraDeshabilitada):
        servicio.registrar_incidencia(inc, clave_idempotencia="uuid_inc_001")

    # 5. Intento de registrar housekeeping
    with pytest.raises(EscrituraDeshabilitada):
        servicio.registrar_tarea_housekeeping(
            "glamping_imbabura", "domo_lago", date(2026, 12, 1), "Nota", clave_idempotencia="uuid_hk_001"
        )

    # Garantía INV_ESCRITURA_PMS_EXPLICITA: El PMS subyacente no recibió ninguna llamada
    assert pms_fake.llamadas_realizadas == llamadas_antes


def test_escrituras_habilitadas_explicitamente_se_ejecutan_con_exito() -> None:
    """Cuando una operación de escritura se habilita en config, se ejecuta en el PMS."""
    pms_fake = FakePMS()
    servicio = PMSConectorService(
        config={
            "proveedor": "fake",
            "escrituras_habilitadas": {
                "crear_reserva_preliminar": True,
                "confirmar_reserva": True,
            },
        },
        observabilidad=DobleObservabilidad(),
        conector=pms_fake,
    )

    reserva = servicio.crear_reserva_preliminar(
        propiedad_id="glamping_imbabura",
        unidad_id="domo_lago",
        desde=date(2026, 12, 10),
        hasta=date(2026, 12, 12),
        huespedes=2,
        huesped_token="tok_habilitado",
        clave_idempotencia="uuid_hab_001",
    )
    assert reserva.codigo.startswith("RES-")

    confirmada = servicio.confirmar_reserva(reserva.codigo, clave_idempotencia="uuid_hab_conf_001")
    assert confirmada.codigo == reserva.codigo
