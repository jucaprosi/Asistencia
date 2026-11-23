# ¤anfitriones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de INV_AISLAMIENTO_ANFITRION y RF-ANF-05.

Verifica que nadie pueda responder, reportar o ver solicitudes de otro anfitrión,
y que todo intento no autorizado se rechace y quede asentado en el audit log de seguridad.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import pytest

from features.anfitriones.anfitriones_service import (
    Anfitrion,
    AnfitrionesService,
    ErrorAnfitriones,
    EstadoHospedaje,
    EstadoSolicitud,
    Hospedaje,
    cargar_config,
)
from tests.anfitriones.dobles import (
    DobleCanalWhatsApp,
    DobleObservabilidad,
    DoblePMS,
    DobleSeguridad,
    ReservaDoble,
)


def _preparar_dos_anfitriones() -> tuple[AnfitrionesService, DobleSeguridad, str, str, str]:
    seg = DobleSeguridad()
    canal = DobleCanalWhatsApp()
    pms = DoblePMS()
    obs = DobleObservabilidad()
    config = dict(cargar_config())
    srv = AnfitrionesService(config, seguridad=seg, canal=canal, pms=pms, observabilidad=obs)

    # Anfitrión A
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-A",
            nombre_comercial="Cabañas Bosque A",
            comision_porcentaje=Decimal("12.00"),
            terminos_version="v2026.1",
        ),
        "+593991111111",
        actor_id="admin_01",
    )
    srv.guardar_hospedaje(
        Hospedaje(propiedad_id="PROP-A", anfitrion_id="ANF-A", estado=EstadoHospedaje.PUBLICADO),
        actor_id="admin_revisor",
    )

    # Anfitrión B
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-B",
            nombre_comercial="Domos Lago B",
            comision_porcentaje=Decimal("14.00"),
            terminos_version="v2026.1",
        ),
        "+593992222222",
        actor_id="admin_01",
    )
    srv.guardar_hospedaje(
        Hospedaje(propiedad_id="PROP-B", anfitrion_id="ANF-B", estado=EstadoHospedaje.PUBLICADO),
        actor_id="admin_revisor",
    )

    # Reserva en propiedad del anfitrión A
    pms.agregar_reserva(
        ReservaDoble(
            codigo="R-AISL-01",
            propiedad_id="PROP-A",
            unidad_id="U-A1",
            huesped_token="[[TOKEN:huesped_x]]",
            desde=date(2026, 12, 10),
            hasta=date(2026, 12, 12),
            huespedes=2,
            total=Decimal("250.00"),
        )
    )

    solicitud_a = srv.solicitar_reserva("R-AISL-01")
    return srv, seg, "ANF-A", "ANF-B", solicitud_a.solicitud


def test_otro_anfitrion_intenta_responder_solicitud_ajena_rechazado_y_auditado() -> None:
    # Dado una solicitud del anfitrión A
    srv, seg, _, anf_b, sol_cod = _preparar_dos_anfitriones()
    eventos_antes = len(seg.eventos)

    # Cuando el anfitrión B intenta responderla
    with pytest.raises(ErrorAnfitriones) as exc:
        srv.responder_solicitud(sol_cod, anfitrion_id=anf_b, acepta=True)

    # Entonces la operación se rechaza por acceso denegado
    assert exc.value.codigo == "ACCESO_DENEGADO"

    # Y queda asentado en el audit log (INV_AISLAMIENTO_ANFITRION)
    eventos_despues = len(seg.eventos)
    assert eventos_despues > eventos_antes
    ultimo_evento = seg.eventos[-1]
    assert ultimo_evento.actor_token == anf_b
    assert ultimo_evento.accion == "responder_solicitud"
    assert "denegado" in ultimo_evento.resultado


def test_otro_anfitrion_intenta_reportar_resultado_ajeno_rechazado_y_auditado() -> None:
    # Dado una solicitud confirmada del anfitrión A
    srv, seg, anf_a, anf_b, sol_cod = _preparar_dos_anfitriones()
    srv.responder_solicitud(sol_cod, anfitrion_id=anf_a, acepta=True)

    eventos_antes = len(seg.eventos)

    # Cuando el anfitrión B intenta reportar resultado sobre la solicitud del anfitrión A
    with pytest.raises(ErrorAnfitriones) as exc:
        srv.reportar_resultado(sol_cod, anfitrion_id=anf_b, resultado=EstadoSolicitud.NO_SHOW)

    # Entonces la operación se rechaza
    assert exc.value.codigo == "ACCESO_DENEGADO"

    # Y se audita la violación de aislamiento
    eventos_despues = len(seg.eventos)
    assert eventos_despues > eventos_antes
    ultimo_evento = seg.eventos[-1]
    assert ultimo_evento.actor_token == anf_b
    assert ultimo_evento.accion == "reportar_resultado"
    assert "denegado" in ultimo_evento.resultado


def test_aislamiento_de_listas_por_anfitrion() -> None:
    # Cada anfitrión solo puede listar sus propias solicitudes
    srv, _, anf_a, anf_b, sol_cod = _preparar_dos_anfitriones()

    solicitudes_a = srv._persistencia.listar_solicitudes_por_anfitrion(anf_a)
    assert len(solicitudes_a) == 1
    assert solicitudes_a[0].solicitud == sol_cod

    solicitudes_b = srv._persistencia.listar_solicitudes_por_anfitrion(anf_b)
    assert len(solicitudes_b) == 0
