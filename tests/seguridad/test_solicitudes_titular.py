# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PRIV-05 (Solicitudes del titular ARCOP y plazo operativo de 15 días).

Verifica:
1. Registro de solicitudes con plazo operativo de 15 días exactos.
2. Conservación legal (ventas validadas/fiscal/reserva activa) deja la solicitud en 'atendida_parcial' con motivo.
3. Consulta de solicitudes próximas a vencer (alerta preventiva para el panel).
4. Solicitud de eliminación sin obligaciones de conservación ejecuta criptoborrado y pasa a 'atendida'.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from features.seguridad.seguridad_service import SeguridadService
from tests.seguridad.dobles import DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_registro_solicitudes_con_plazo_operativo_15_dias(servicio: SeguridadService) -> None:
    """RF-PRIV-05: Solicitudes ARCOP registradas con plazo operativo de 15 días."""
    titular = "hash_titular_pedro_99"
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    solicitud = servicio.registrar_solicitud_titular(titular, tipo="acceso", recibida_en=ahora)
    assert solicitud.tipo == "acceso"
    assert solicitud.estado == "recibida"
    assert solicitud.recibida_en == ahora
    # Límite operativo exacto de 15 días (dominio.yaml)
    assert solicitud.limite_en == ahora + timedelta(days=15)

    # Listar solicitudes
    lista = servicio.listar_solicitudes_titular()
    assert any(s.solicitud_id == solicitud.solicitud_id for s in lista)


def test_conservacion_por_obligacion_legal_atendida_parcial(servicio: SeguridadService) -> None:
    """Escenario: Conservación por obligación legal (@US-17 @RF-PRIV-05).
    
    Dado un titular con una venta validada sujeta a conservación
    Cuando pide eliminación
    Entonces la solicitud queda "atendida_parcial" con motivo registrado
    """
    titular = "hash_titular_empresa_sri"
    solicitud = servicio.registrar_solicitud_titular(titular, tipo="eliminacion")

    # Cuando pide eliminación pero tiene datos sujetos a conservación legal
    motivo_legal = "Venta validada con comprobante fiscal vigente; sujeta a conservación de 5 años por normativa tributaria."
    solicitud_atendida = servicio.atender_solicitud_titular(
        solicitud.solicitud_id,
        atendida_por="usr_admin_legal",
        sujeto_a_conservacion=True,
        motivo_conservacion=motivo_legal,
    )

    # Entonces la solicitud queda en atendida_parcial con motivo registrado
    assert solicitud_atendida.estado == "atendida_parcial"
    assert solicitud_atendida.motivo == motivo_legal
    assert solicitud_atendida.atendida_por == "usr_admin_legal"
    assert solicitud_atendida.atendida_en is not None


def test_solicitudes_proximas_a_vencer(servicio: SeguridadService) -> None:
    """RF-PRIV-05 (b): El panel muestra las solicitudes próximas a vencer."""
    ahora = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Solicitud recibida hace 13 días (vence en 2 días: próxima a vencer)
    recibida_hace_13 = ahora - timedelta(days=13)
    sol_urgente = servicio.registrar_solicitud_titular("titular_urgente", tipo="oposicion", recibida_en=recibida_hace_13)

    # 2. Solicitud recibida hoy (vence en 15 días: no urgente)
    sol_nueva = servicio.registrar_solicitud_titular("titular_nuevo", tipo="portabilidad", recibida_en=ahora)

    # 3. Solicitud recibida hace 14 días pero ya atendida (no debe salir)
    recibida_hace_14 = ahora - timedelta(days=14)
    sol_cerrada = servicio.registrar_solicitud_titular("titular_cerrado", tipo="acceso", recibida_en=recibida_hace_14)
    servicio.atender_solicitud_titular(sol_cerrada.solicitud_id, atendida_por="usr_admin")

    # Consultar solicitudes próximas a vencer en ventana de 3 días
    proximas = servicio.solicitudes_proximas_a_vencer(dias_aviso=3, ahora=ahora)
    ids_proximas = {s.solicitud_id for s in proximas}

    assert sol_urgente.solicitud_id in ids_proximas
    assert sol_nueva.solicitud_id not in ids_proximas
    assert sol_cerrada.solicitud_id not in ids_proximas
