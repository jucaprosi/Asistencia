# ¤anfitriones
# ¤¤backend-developer
"""Árbitro de RF-ANF-06: Resultado de la estadía y liquidación de comisión.

Verifica el reporte de cancelada y no_show dentro del plazo de 3 días sin generar comisión,
el rechazo si el plazo venció, y la transición automática a completada al no existir reporte.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from features.anfitriones.anfitriones_service import (
    Anfitrion,
    AnfitrionesService,
    ErrorAnfitriones,
    EstadoHospedaje,
    EstadoSolicitud,
    Hospedaje,
    Solicitud,
    cargar_config,
)
from tests.anfitriones.dobles import (
    DobleCanalWhatsApp,
    DobleObservabilidad,
    DoblePMS,
    DobleSeguridad,
    ReservaDoble,
)


def _preparar_servicio_con_reserva_confirmada(
    desde: date, hasta: date, total: Decimal = Decimal("400.00")
) -> tuple[AnfitrionesService, Solicitud]:
    seg = DobleSeguridad()
    canal = DobleCanalWhatsApp()
    pms = DoblePMS()
    obs = DobleObservabilidad()
    config = dict(cargar_config())
    srv = AnfitrionesService(config, seguridad=seg, canal=canal, pms=pms, observabilidad=obs)

    anf_id = "ANF-RESULTADO"
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id=anf_id,
            nombre_comercial="Glamping Resultados",
            comision_porcentaje=Decimal("10.00"),
            terminos_version="v2026.1",
        ),
        "+593998887776",
        actor_id="admin_01",
    )

    srv.guardar_hospedaje(
        Hospedaje(propiedad_id="DOMO-RES", anfitrion_id=anf_id, estado=EstadoHospedaje.PUBLICADO),
        actor_id="admin_revisor",
    )

    codigo_res = f"R-{abs(hash((desde, hasta))) % 10000}"
    pms.agregar_reserva(
        ReservaDoble(
            codigo=codigo_res,
            propiedad_id="DOMO-RES",
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_res]]",
            desde=desde,
            hasta=hasta,
            huespedes=2,
            total=total,
        )
    )

    sol = srv.solicitar_reserva(codigo_res)
    srv.responder_solicitud(sol.solicitud, anf_id, acepta=True)
    sol_confirmada = srv._persistencia.obtener_solicitud(sol.solicitud)
    return srv, sol_confirmada


def test_anfitrion_reporta_no_show_dentro_del_plazo() -> None:
    # Dado una reserva confirmada cuya salida fue ayer (dentro del plazo de 3 días)
    ayer = datetime.now(timezone.utc).date() - timedelta(days=1)
    anteayer = ayer - timedelta(days=2)
    srv, sol = _preparar_servicio_con_reserva_confirmada(desde=anteayer, hasta=ayer)

    # Cuando el anfitrión reporta no_show
    actualizada = srv.reportar_resultado(
        solicitud=sol.solicitud,
        anfitrion_id="ANF-RESULTADO",
        resultado=EstadoSolicitud.NO_SHOW,
    )

    # Entonces pasa a no_show
    assert actualizada.estado == EstadoSolicitud.NO_SHOW

    # Y no genera comisión (estado no es completada)
    assert actualizada.estado != EstadoSolicitud.COMPLETADA


def test_anfitrion_reporta_cancelada_dentro_del_plazo() -> None:
    ayer = datetime.now(timezone.utc).date() - timedelta(days=2)
    desde = ayer - timedelta(days=2)
    srv, sol = _preparar_servicio_con_reserva_confirmada(desde=desde, hasta=ayer)

    actualizada = srv.reportar_resultado(
        solicitud=sol.solicitud,
        anfitrion_id="ANF-RESULTADO",
        resultado=EstadoSolicitud.CANCELADA,
    )

    assert actualizada.estado == EstadoSolicitud.CANCELADA


def test_anfitrion_intenta_reportar_tras_vencer_plazo_falla() -> None:
    # Dado una reserva confirmada cuya salida fue hace 5 días (plazo de 3 días vencido)
    hace_cinco_dias = datetime.now(timezone.utc).date() - timedelta(days=5)
    desde = hace_cinco_dias - timedelta(days=2)
    srv, sol = _preparar_servicio_con_reserva_confirmada(desde=desde, hasta=hace_cinco_dias)

    # Cuando intenta reportar no_show o cancelada
    with pytest.raises(ErrorAnfitriones) as exc:
        srv.reportar_resultado(
            solicitud=sol.solicitud,
            anfitrion_id="ANF-RESULTADO",
            resultado=EstadoSolicitud.NO_SHOW,
        )

    # Entonces la operación es rechazada por plazo vencido
    assert exc.value.codigo == "PLAZO_VENCIDO"


def test_sin_reporte_la_estadia_se_completa() -> None:
    # Dado una reserva confirmada cuyo plazo de reporte venció (salida hace 6 días)
    hace_seis_dias = datetime.now(timezone.utc).date() - timedelta(days=6)
    desde = hace_seis_dias - timedelta(days=2)
    srv, sol = _preparar_servicio_con_reserva_confirmada(desde=desde, hasta=hace_seis_dias)

    # Cuando corre el proceso diario
    completadas = srv.procesar_estadias_completadas(ahora_fecha=datetime.now(timezone.utc).date())

    # Entonces pasa a completada
    assert any(c.solicitud == sol.solicitud for c in completadas)
    recuperada = srv._persistencia.obtener_solicitud(sol.solicitud)
    assert recuperada.estado == EstadoSolicitud.COMPLETADA
