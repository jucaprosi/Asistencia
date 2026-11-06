# ¤pms-conector
# ¤¤integration-engineer
"""Prueba de contrato abstracto del conector PMS (RF-PMS-01).

Parametrizada para verificar que cualquier implementación (FakePMS, proveedor real de plataforma)
cumple rigurosamente el contrato devolviendo tipos propios del dominio y cero objetos de SDKs.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import pytest

from features.pms_conector.base_internal import PMSConnector
from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.plataforma_internal import PlataformaPMS
from features.pms_conector.tipos import (
    Cotizacion,
    Disponibilidad,
    EstadoReserva,
    Incidencia,
    InstruccionesCheckin,
    Propiedad,
    Reserva,
    Unidad,
)


# ¤pms-conector
@pytest.fixture(params=[FakePMS, PlataformaPMS])
def conector(request: pytest.FixtureRequest) -> PMSConnector:
    """Fixture que provee instancias frescas de cada implementación bajo prueba de contrato."""
    fabrica = request.param
    return fabrica()


# ¤pms-conector
def test_contrato_pms_devuelve_tipos_puros_del_dominio(conector: PMSConnector) -> None:
    """Escenario: Contrato del conector PMS (@RF-PMS-01).
    
    Dado la implementación FakePMS y la del proveedor (PlataformaPMS)
    Cuando corre la misma prueba de contrato
    Entonces ambas devuelven tipos propios del dominio y ningún objeto del SDK
    """
    # 1. listar_propiedades
    propiedades = conector.listar_propiedades()
    assert isinstance(propiedades, tuple)
    assert len(propiedades) >= 2
    for p in propiedades:
        assert isinstance(p, Propiedad)
        assert isinstance(p.propiedad_id, str)
        assert isinstance(p.activa, bool)
        # Comprobar que no es un objeto de SDK
        assert type(p).__module__.startswith("features.pms_conector")

    prop_id = propiedades[0].propiedad_id

    # 2. consultar_disponibilidad
    desde = date(2026, 12, 1)
    hasta = date(2026, 12, 3)
    disp = conector.consultar_disponibilidad(prop_id, desde, hasta, huespedes=2)
    assert isinstance(disp, Disponibilidad)
    assert isinstance(disp.disponible, bool)
    assert isinstance(disp.unidades, tuple)
    assert len(disp.unidades) >= 1
    unidad = disp.unidades[0]
    assert isinstance(unidad, Unidad)
    assert unidad.capacidad >= 2

    # 3. cotizar
    cot = conector.cotizar(prop_id, unidad.unidad_id, desde, hasta, huespedes=2)
    assert isinstance(cot, Cotizacion)
    assert isinstance(cot.total, Decimal)
    assert cot.moneda == "USD"
    assert isinstance(cot.desglose, tuple)
    assert len(cot.desglose) == 2  # 2 noches

    # 4. crear_reserva_preliminar
    clave_idemp = "idemp_contrato_001"
    reserva = conector.crear_reserva_preliminar(
        prop_id,
        unidad.unidad_id,
        desde,
        hasta,
        huespedes=2,
        huesped_token="tok_huesped_contrato",
        clave_idempotencia=clave_idemp,
    )
    assert isinstance(reserva, Reserva)
    assert reserva.estado == EstadoReserva.PRELIMINAR
    assert reserva.codigo.startswith("RES-")
    assert reserva.expira_en is not None

    # 5. obtener_reserva
    res_obtenida = conector.obtener_reserva(reserva.codigo)
    assert isinstance(res_obtenida, Reserva)
    assert res_obtenida.codigo == reserva.codigo
    assert res_obtenida.estado == EstadoReserva.PRELIMINAR

    # 6. reservas_con_llegada
    llegadas = conector.reservas_con_llegada(desde)
    assert isinstance(llegadas, tuple)
    assert any(r.codigo == reserva.codigo for r in llegadas)

    # 7. confirmar_reserva
    confirmada = conector.confirmar_reserva(reserva.codigo, clave_idempotencia="idemp_conf_001")
    assert isinstance(confirmada, Reserva)
    assert confirmada.estado == EstadoReserva.CONFIRMADA
    assert confirmada.expira_en is None

    # 8. obtener_instrucciones_checkin
    checkin = conector.obtener_instrucciones_checkin(reserva.codigo)
    assert isinstance(checkin, InstruccionesCheckin)
    assert isinstance(checkin.propiedad, str)
    assert isinstance(checkin.hora_checkin, str)
    assert isinstance(checkin.acceso, tuple)
    assert isinstance(checkin.wifi_red, str)
    assert checkin.wifi_clave_token.startswith("[[SECRETO:")

    # 9. registrar_incidencia
    inc_in = Incidencia(
        incidencia_id="",
        propiedad_id=prop_id,
        unidad_id=unidad.unidad_id,
        reserva_codigo=reserva.codigo,
        categoria="limpieza",
        prioridad="media",
        descripcion_token="Falta toalla de mano",
        estado="abierta",
        gestor_id=None,
    )
    inc_creada = conector.registrar_incidencia(inc_in, clave_idempotencia="idemp_inc_001")
    assert isinstance(inc_creada, Incidencia)
    assert inc_creada.incidencia_id.startswith("I-")

    # 10. registrar_tarea_housekeeping
    hk_id = conector.registrar_tarea_housekeeping(
        prop_id, unidad.unidad_id, fecha=desde, nota="Limpieza profunda previa", clave_idempotencia="idemp_hk_001"
    )
    assert isinstance(hk_id, str)
    assert hk_id.startswith("HK-2026-")

    # 11. guardar_tarifas
    noches_tarifa = conector.guardar_tarifas(
        unidad.unidad_id,
        desde=date(2026, 12, 10),
        hasta=date(2026, 12, 15),
        precio=Decimal("150.00"),
        minimo_noches=2,
        actor_id="admin_01",
    )
    assert noches_tarifa == 5

    # 12. actualizar_calendario (bloquear y liberar)
    noches_bloq, omit = conector.actualizar_calendario(
        unidad.unidad_id,
        desde=date(2026, 12, 20),
        hasta=date(2026, 12, 22),
        accion="bloquear",
        actor_id="admin_01",
    )
    assert noches_bloq == 2
    assert omit == 0

    # 13. cancelar_reserva
    cancelada = conector.cancelar_reserva(reserva.codigo, motivo="Cambio de itinerario", clave_idempotencia="idemp_canc_001")
    assert isinstance(cancelada, Reserva)
    assert cancelada.estado == EstadoReserva.CANCELADA
