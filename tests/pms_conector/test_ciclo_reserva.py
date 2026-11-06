# ¤pms-conector
# ¤¤integration-engineer
"""Pruebas del ciclo de vida y expiración de reservas (RF-PMS-05, US-02)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import pytest

from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.pms_conector_service import (
    EstadoReserva,
    PMSConectorService,
)
from tests.pms_conector.dobles import DobleObservabilidad


def test_reserva_preliminar_vencida_pasa_a_expirada_y_libera_unidad() -> None:
    """Escenario: Una reserva preliminar sin pago expira (@US-02 @RF-PMS-05).
    
    Dado una reserva "preliminar" vencida
    Cuando se consulta en el PMS
    Entonces su estado es "expirada" y la unidad vuelve a estar libre
    """
    pms_fake = FakePMS()
    servicio = PMSConectorService(
        config={"escrituras_habilitadas": {"crear_reserva_preliminar": True}},
        observabilidad=DobleObservabilidad(),
        conector=pms_fake,
    )

    desde = date(2026, 12, 10)
    hasta = date(2026, 12, 12)

    # 1. Crear reserva preliminar
    reserva = servicio.crear_reserva_preliminar(
        propiedad_id="glamping_imbabura",
        unidad_id="domo_lago",
        desde=desde,
        hasta=hasta,
        huespedes=2,
        huesped_token="tok_vencimiento_test",
        clave_idempotencia="idemp_vencimiento_001",
    )
    assert reserva.estado == EstadoReserva.PRELIMINAR

    # Verificar que la unidad ya no está libre
    disp_ocupada = servicio.consultar_disponibilidad("glamping_imbabura", desde, hasta, 2)
    unidades_libres = [u.unidad_id for u in disp_ocupada.unidades]
    assert "domo_lago" not in unidades_libres

    # 2. Simular que la reserva venció hace 1 hora modificando expira_en en memoria
    res_en_pms = pms_fake._reservas[reserva.codigo]
    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    pms_fake._reservas[reserva.codigo] = type(res_en_pms)(
        codigo=res_en_pms.codigo,
        propiedad_id=res_en_pms.propiedad_id,
        unidad_id=res_en_pms.unidad_id,
        huesped_token=res_en_pms.huesped_token,
        desde=res_en_pms.desde,
        hasta=res_en_pms.hasta,
        huespedes=res_en_pms.huespedes,
        estado=EstadoReserva.PRELIMINAR,
        total=res_en_pms.total,
        expira_en=hace_una_hora,
        pms_ref=res_en_pms.pms_ref,
    )

    # 3. Al consultar en el PMS, la reserva pasa a expirada
    res_consultada = servicio.obtener_reserva(reserva.codigo)
    assert res_consultada.estado == EstadoReserva.EXPIRADA

    # 4. Y la unidad vuelve a estar disponible
    disp_liberada = servicio.consultar_disponibilidad("glamping_imbabura", desde, hasta, 2)
    assert disp_liberada.disponible is True
    assert "domo_lago" in [u.unidad_id for u in disp_liberada.unidades]


def test_transicion_de_preliminar_a_confirmada() -> None:
    """Una reserva preliminar vigente se confirma y asegura sus fechas definitivamente."""
    servicio = PMSConectorService(
        config={
            "escrituras_habilitadas": {
                "crear_reserva_preliminar": True,
                "confirmar_reserva": True,
            }
        },
        observabilidad=DobleObservabilidad(),
    )

    desde = date(2026, 12, 15)
    hasta = date(2026, 12, 17)

    res = servicio.crear_reserva_preliminar(
        "glamping_imbabura", "domo_bosque", desde, hasta, 3, "tok_usr", "idemp_c1"
    )
    assert res.estado == EstadoReserva.PRELIMINAR
    assert res.expira_en is not None

    confirmada = servicio.confirmar_reserva(res.codigo, "idemp_c2")
    assert confirmada.estado == EstadoReserva.CONFIRMADA
    assert confirmada.expira_en is None


def test_cancelacion_de_reserva_libera_el_calendario() -> None:
    """Cancelar una reserva confirmada libera las fechas ocupadas en el PMS."""
    servicio = PMSConectorService(
        config={
            "escrituras_habilitadas": {
                "crear_reserva_preliminar": True,
                "confirmar_reserva": True,
                "cancelar_reserva": True,
            }
        },
        observabilidad=DobleObservabilidad(),
    )

    desde = date(2026, 12, 20)
    hasta = date(2026, 12, 22)

    res = servicio.crear_reserva_preliminar(
        "dep_ibarra_centro", "suite_101", desde, hasta, 2, "tok_usr", "idemp_canc_1"
    )
    servicio.confirmar_reserva(res.codigo, "idemp_canc_2")

    # Cancelar reserva
    cancelada = servicio.cancelar_reserva(res.codigo, "Fuerza mayor", "idemp_canc_3")
    assert cancelada.estado == EstadoReserva.CANCELADA

    # Fechas nuevamente disponibles
    disp = servicio.consultar_disponibilidad("dep_ibarra_centro", desde, hasta, 2)
    assert "suite_101" in [u.unidad_id for u in disp.unidades]
