# ¤anfitriones
# ¤¤backend-developer
"""Árbitro de RF-ANF-04, RF-ANF-05, INV_CONTACTO_TRAS_CONFIRMAR y US-19.

Verifica la creación de solicitudes desde reservas del PMS con fechas, total y porcentaje congelados,
el envío de la plantilla con vigencia de 24 horas, la confirmación/rechazo por el anfitrión,
la entrega de contactos solo tras confirmar, y la expiración de solicitudes vencidas.
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
    cargar_config,
)
from tests.anfitriones.dobles import (
    DobleCanalWhatsApp,
    DobleObservabilidad,
    DoblePMS,
    DobleSeguridad,
    ReservaDoble,
)


def _preparar_entorno() -> tuple[AnfitrionesService, DoblePMS, DobleCanalWhatsApp, DobleSeguridad]:
    seg = DobleSeguridad()
    canal = DobleCanalWhatsApp()
    pms = DoblePMS()
    obs = DobleObservabilidad()
    config = dict(cargar_config())
    srv = AnfitrionesService(config, seguridad=seg, canal=canal, pms=pms, observabilidad=obs)

    # Registrar anfitrión con 15% de comisión
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-SAN-PABLO",
            nombre_comercial="Glamping San Pablo",
            comision_porcentaje=Decimal("15.00"),
            terminos_version="v2026.1",
        ),
        "+593991234567",
        actor_id="admin_01",
    )

    # Publicar hospedaje
    srv.guardar_hospedaje(
        Hospedaje(
            propiedad_id="DOMO-LAGO",
            anfitrion_id="ANF-SAN-PABLO",
            estado=EstadoHospedaje.PUBLICADO,
        ),
        actor_id="admin_revisor",
    )

    return srv, pms, canal, seg


def test_solicitar_reserva_datos_del_pms_y_porcentaje_congelado() -> None:
    # Dado una reserva preliminar de un hospedaje publicado en el PMS
    srv, pms, canal, _ = _preparar_entorno()
    pms.agregar_reserva(
        ReservaDoble(
            codigo="R-2026-1001",
            propiedad_id="DOMO-LAGO",
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_juan]]",
            desde=date(2026, 12, 10),
            hasta=date(2026, 12, 13),
            huespedes=2,
            total=Decimal("450.00"),
        )
    )

    # Cuando el asistente crea la solicitud
    solicitud = srv.solicitar_reserva("R-2026-1001")

    # Entonces fechas y total salen del PMS
    assert solicitud.codigo_reserva == "R-2026-1001"
    assert solicitud.solicitud.startswith("PL-")
    assert solicitud.desde == date(2026, 12, 10)
    assert solicitud.hasta == date(2026, 12, 13)
    assert solicitud.total == Decimal("450.00")

    # Y el porcentaje del anfitrión queda congelado en 15%
    assert solicitud.comision_porcentaje == Decimal("15.00")
    assert solicitud.estado == EstadoSolicitud.SOLICITADA

    # Y el anfitrión recibe la plantilla con vigencia de 24 horas
    assert len(canal.plantillas_enviadas) == 1
    dest, plantilla = canal.plantillas_enviadas[0]
    assert "San Pablo" in plantilla.variables[0]
    assert plantilla.nombre == "solicitud_reserva_anfitrion"
    assert (solicitud.vence_en - solicitud.creado_en) >= timedelta(hours=23, minutes=59)


def test_porcentaje_congelado_no_cambia_si_anfitrion_actualiza_comision() -> None:
    srv, pms, _, _ = _preparar_entorno()
    pms.agregar_reserva(
        ReservaDoble(
            codigo="R-2026-1002",
            propiedad_id="DOMO-LAGO",
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_ana]]",
            desde=date(2026, 12, 15),
            hasta=date(2026, 12, 17),
            huespedes=2,
            total=Decimal("300.00"),
        )
    )

    solicitud = srv.solicitar_reserva("R-2026-1002")
    assert solicitud.comision_porcentaje == Decimal("15.00")

    # Modificar porcentaje futuro del anfitrión a 20%
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-SAN-PABLO",
            nombre_comercial="Glamping San Pablo",
            comision_porcentaje=Decimal("20.00"),
            terminos_version="v2026.2",
        ),
        "+593991234567",
        actor_id="admin_01",
    )

    # La solicitud previamente generada conserva su porcentaje original congelado
    recuperada = srv._persistencia.obtener_solicitud(solicitud.solicitud)
    assert recuperada.comision_porcentaje == Decimal("15.00")


def test_anfitrion_confirma_y_se_entrega_contacto() -> None:
    # Dado una solicitud vigente
    srv, pms, canal, _ = _preparar_entorno()
    pms.agregar_reserva(
        ReservaDoble(
            codigo="R-2026-1003",
            propiedad_id="DOMO-LAGO",
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_carlos]]",
            desde=date(2026, 12, 20),
            hasta=date(2026, 12, 22),
            huespedes=2,
            total=Decimal("280.00"),
        )
    )
    solicitud = srv.solicitar_reserva("R-2026-1003")
    canal.plantillas_enviadas.clear()

    # Cuando su anfitrión la confirma
    sol_confirmada = srv.responder_solicitud(
        solicitud.solicitud,
        anfitrion_id="ANF-SAN-PABLO",
        acepta=True,
    )

    # Entonces el estado pasa a confirmada
    assert sol_confirmada.estado == EstadoSolicitud.CONFIRMADA
    assert sol_confirmada.respondida_en is not None

    # Y solo entonces huésped y anfitrión reciben el contacto del otro (INV_CONTACTO_TRAS_CONFIRMAR)
    assert len(canal.plantillas_enviadas) == 2
    plantillas_nombres = [p.nombre for _, p in canal.plantillas_enviadas]
    assert all(n == "reserva_confirmada" for n in plantillas_nombres)


def test_anfitrion_rechaza_y_no_se_entrega_contacto() -> None:
    # Dado una solicitud vigente
    srv, pms, canal, _ = _preparar_entorno()
    pms.agregar_reserva(
        ReservaDoble(
            codigo="R-2026-1004",
            propiedad_id="DOMO-LAGO",
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_maria]]",
            desde=date(2026, 12, 24),
            hasta=date(2026, 12, 26),
            huespedes=2,
            total=Decimal("350.00"),
        )
    )
    solicitud = srv.solicitar_reserva("R-2026-1004")
    canal.plantillas_enviadas.clear()

    # Cuando el anfitrión la rechaza
    sol_rechazada = srv.responder_solicitud(
        solicitud.solicitud,
        anfitrion_id="ANF-SAN-PABLO",
        acepta=False,
        motivo="Mantenimiento no programado",
    )

    # Entonces el estado pasa a rechazada
    assert sol_rechazada.estado == EstadoSolicitud.RECHAZADA

    # Y el contacto NO se entrega
    assert len(canal.plantillas_enviadas) == 0


def test_solicitud_sin_respuesta_expira() -> None:
    # Dado una solicitud sin respuesta al vencer
    srv, pms, _, _ = _preparar_entorno()
    pms.agregar_reserva(
        ReservaDoble(
            codigo="R-2026-1005",
            propiedad_id="DOMO-LAGO",
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_lucia]]",
            desde=date(2026, 12, 28),
            hasta=date(2026, 12, 30),
            huespedes=2,
            total=Decimal("320.00"),
        )
    )
    solicitud = srv.solicitar_reserva("R-2026-1005")

    # Simular paso del tiempo: 25 horas después
    ahora_futuro = datetime.now(timezone.utc) + timedelta(hours=25)

    # Cuando corre el proceso de vencimiento
    expiradas = srv.expirar_solicitudes_vencidas(ahora=ahora_futuro)

    # Entonces pasa a expirada
    assert any(s.solicitud == solicitud.solicitud for s in expiradas)
    recuperada = srv._persistencia.obtener_solicitud(solicitud.solicitud)
    assert recuperada.estado == EstadoSolicitud.EXPIRADA

    # E intentar responderla después arroja error
    with pytest.raises(ErrorAnfitriones) as exc:
        srv.responder_solicitud(solicitud.solicitud, "ANF-SAN-PABLO", acepta=True)
    assert exc.value.codigo == "SOLICITUD_EXPIRADA"
