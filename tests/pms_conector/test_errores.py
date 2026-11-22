# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de manejo de errores, reintentos y timeouts (RF-PMS-03, INV_ESCRITURA_PMS_EXPLICITA)."""
from __future__ import annotations

from datetime import date
import pytest

from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.pms_conector_service import (
    FechasInvalidas,
    IdempotenciaRequerida,
    PMSConectorService,
    PMSNoDisponible,
    PropiedadInexistente,
    ReservaInexistente,
    SinDisponibilidad,
)
from tests.pms_conector.dobles import DobleObservabilidad, DoblePMSConFallo


def test_propiedad_inexistente_lanza_error_tipado() -> None:
    """Consultar disponibilidad de una propiedad inexistente lanza PropiedadInexistente."""
    servicio = PMSConectorService({}, observabilidad=DobleObservabilidad())
    with pytest.raises(PropiedadInexistente):
        servicio.consultar_disponibilidad("propiedad_fantasma", date(2026, 12, 1), date(2026, 12, 3), 2)


def test_fechas_invalidas_lanza_error_tipado() -> None:
    """Rango de fechas donde hasta <= desde lanza FechasInvalidas."""
    servicio = PMSConectorService({}, observabilidad=DobleObservabilidad())
    with pytest.raises(FechasInvalidas):
        servicio.consultar_disponibilidad("glamping_imbabura", date(2026, 12, 5), date(2026, 12, 5), 2)

    with pytest.raises(FechasInvalidas):
        servicio.cotizar("glamping_imbabura", "domo_lago", date(2026, 12, 5), date(2026, 12, 4), 2)


def test_reserva_inexistente_lanza_error_tipado() -> None:
    """Consultar un código de reserva inexistente lanza ReservaInexistente."""
    servicio = PMSConectorService({}, observabilidad=DobleObservabilidad())
    with pytest.raises(ReservaInexistente):
        servicio.obtener_reserva("RES-INEXISTENTE-9999")


def test_sin_disponibilidad_al_intentar_reservar_unidad_ocupada() -> None:
    """Intentar reservar una unidad que ya está ocupada lanza SinDisponibilidad."""
    servicio = PMSConectorService(
        config={"escrituras_habilitadas": {"crear_reserva_preliminar": True}},
        observabilidad=DobleObservabilidad(),
    )
    # Primera reserva
    servicio.crear_reserva_preliminar(
        propiedad_id="glamping_imbabura",
        unidad_id="domo_lago",
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 3),
        huespedes=2,
        huesped_token="tok_1",
        clave_idempotencia="uuid_1",
    )

    # Segunda reserva para las mismas fechas y unidad
    with pytest.raises(SinDisponibilidad):
        servicio.crear_reserva_preliminar(
            propiedad_id="glamping_imbabura",
            unidad_id="domo_lago",
            desde=date(2026, 12, 1),
            hasta=date(2026, 12, 3),
            huespedes=2,
            huesped_token="tok_2",
            clave_idempotencia="uuid_2",
        )


def test_escritura_sin_clave_de_idempotencia_no_se_reintenta_y_falla() -> None:
    """Escritura sin clave de idempotencia falla inmediatamente con IdempotenciaRequerida."""
    pms_fake = FakePMS()
    servicio = PMSConectorService(
        config={"escrituras_habilitadas": {"crear_reserva_preliminar": True}},
        observabilidad=DobleObservabilidad(),
        conector=pms_fake,
    )

    llamadas_antes = pms_fake.llamadas_realizadas
    with pytest.raises(IdempotenciaRequerida):
        servicio.crear_reserva_preliminar(
            propiedad_id="glamping_imbabura",
            unidad_id="domo_lago",
            desde=date(2026, 12, 1),
            hasta=date(2026, 12, 3),
            huespedes=2,
            huesped_token="tok_1",
            clave_idempotencia="",  # Sin clave
        )

    # El PMS no recibió ninguna llamada
    assert pms_fake.llamadas_realizadas == llamadas_antes


def test_pms_lento_supera_timeout_y_lectura_se_reintenta() -> None:
    """Escenario: Errores del PMS (@RF-PMS-03 @INV_ESCRITURA_PMS_EXPLICITA).
    
    Dado un PMS que supera 8 segundos
    Cuando la operación es de lectura se reintenta
    Y cuando es de escritura sin clave de idempotencia no se reintenta
    Entonces el agente recibe un error tipado accionable
    """
    # 1. PMS que supera timeout de lectura
    pms_timeout = DoblePMSConFallo(superar_timeout=True)
    servicio = PMSConectorService(
        config={"timeout_s": 0.05, "reintentos_lectura": 2},
        observabilidad=DobleObservabilidad(),
        conector=pms_timeout,
    )

    with pytest.raises(PMSNoDisponible) as exc:
        servicio.listar_propiedades()
    assert "PMS no disponible" in str(exc.value) or "timeout" in str(exc.value).lower()
    # Se ejecutó el intento inicial + 2 reintentos = 3 llamadas
    assert pms_timeout.intentos_lectura == 3


def test_pms_recupera_tras_fallo_transitorio_en_reintento() -> None:
    """Una lectura que falla 1 vez pero se recupera en el reintento culmina con éxito."""
    pms_recuperable = DoblePMSConFallo(fallar_lecturas=1)
    servicio = PMSConectorService(
        config={"reintentos_lectura": 2},
        observabilidad=DobleObservabilidad(),
        conector=pms_recuperable,
    )

    propiedades = servicio.listar_propiedades()
    assert len(propiedades) >= 2
    assert pms_recuperable.intentos_lectura == 2
