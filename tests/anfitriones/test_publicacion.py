# ¤anfitriones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-ANF-01, RF-ANF-02 e INV_SOLO_PUBLICADO.

Verifica el alta de anfitriones con términos y porcentaje pactado, el guardado de teléfono como token,
el registro en el audit log, y la publicación revisada de hospedajes impidiendo la auto-publicación.
"""
from __future__ import annotations

from decimal import Decimal
import pytest

from features.anfitriones.anfitriones_service import (
    Anfitrion,
    AnfitrionesService,
    ErrorAnfitriones,
    EstadoAnfitrion,
    EstadoHospedaje,
    Hospedaje,
    cargar_config,
)
from tests.anfitriones.dobles import (
    DobleCanalWhatsApp,
    DobleObservabilidad,
    DoblePMS,
    DobleSeguridad,
)


def _crear_servicio(
    seguridad: DobleSeguridad | None = None,
    canal: DobleCanalWhatsApp | None = None,
    pms: DoblePMS | None = None,
    obs: DobleObservabilidad | None = None,
) -> tuple[AnfitrionesService, DobleSeguridad, DobleCanalWhatsApp, DoblePMS, DobleObservabilidad]:
    seg = seguridad or DobleSeguridad()
    can = canal or DobleCanalWhatsApp()
    p = pms or DoblePMS()
    o = obs or DobleObservabilidad()
    config = dict(cargar_config())
    srv = AnfitrionesService(config, seguridad=seg, canal=can, pms=p, observabilidad=o)
    return srv, seg, can, p, o


def test_alta_anfitrion_con_terminos_y_porcentaje_exitoso() -> None:
    # Dado un anfitrión con términos aceptados y porcentaje pactado
    srv, seg, _, _, _ = _crear_servicio()
    anf = Anfitrion(
        anfitrion_id="ANF-01",
        nombre_comercial="Glamping Vista Volcan",
        comision_porcentaje=Decimal("12.50"),
        terminos_version="v2026.1",
    )

    # Cuando el administrador lo registra
    registrado = srv.registrar_anfitrion(anf, "+593998877665", actor_id="admin_01")

    # Entonces queda activo y su teléfono se guarda como token
    assert registrado.estado == EstadoAnfitrion.ACTIVO
    assert registrado.telefono_token.startswith("[[TOKEN:")
    assert registrado.nombre_comercial == "Glamping Vista Volcan"
    assert registrado.comision_porcentaje == Decimal("12.50")

    # Y cada cambio queda en el audit log
    assert len(seg.eventos) >= 1
    evento = seg.eventos[0]
    assert evento.actor_token == "admin_01"
    assert evento.accion == "alta_anfitrion"


def test_alta_sin_terminos_rechazada() -> None:
    # Dado un anfitrión sin versión de términos
    srv, _, _, _, _ = _crear_servicio()
    anf = Anfitrion(
        anfitrion_id="ANF-02",
        nombre_comercial="Cabañas del Valle",
        comision_porcentaje=Decimal("10.00"),
        terminos_version="",  # Sin términos
    )

    # Cuando el administrador intenta registrarlo, entonces se rechaza
    with pytest.raises(ErrorAnfitriones) as exc_info:
        srv.registrar_anfitrion(anf, "+593991122334", actor_id="admin_01")

    assert exc_info.value.codigo == "TERMINOS_NO_ACEPTADOS"


def test_publicacion_revisada_por_equipo_con_actor_y_fecha() -> None:
    # Dado un anfitrión activo y un hospedaje en borrador
    srv, seg, _, _, _ = _crear_servicio()
    anf = srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-03",
            nombre_comercial="Domo Andino",
            comision_porcentaje=Decimal("15.00"),
            terminos_version="v2026.1",
        ),
        "+593990001111",
        actor_id="admin_01",
    )

    hospedaje_borrador = Hospedaje(
        propiedad_id="PROP-01",
        anfitrion_id=anf.anfitrion_id,
        estado=EstadoHospedaje.BORRADOR,
    )
    srv.guardar_hospedaje(hospedaje_borrador, actor_id="admin_01")

    # Cuando un administrador lo publica
    hospedaje_publicado = Hospedaje(
        propiedad_id="PROP-01",
        anfitrion_id=anf.anfitrion_id,
        estado=EstadoHospedaje.PUBLICADO,
    )
    publicado = srv.guardar_hospedaje(hospedaje_publicado, actor_id="admin_revisor")

    # Entonces queda publicado con el actor y la fecha
    assert publicado.estado == EstadoHospedaje.PUBLICADO
    assert publicado.publicado_por == "admin_revisor"
    assert publicado.publicado_en is not None

    # Y queda visible en la lista de publicados (INV_SOLO_PUBLICADO)
    visibles = srv.publicados()
    assert len(visibles) == 1
    assert visibles[0].propiedad_id == "PROP-01"


def test_anfitrion_no_publica_por_si_mismo() -> None:
    # Dado un hospedaje de un anfitrión
    srv, seg, _, _, _ = _crear_servicio()
    anf_id = "ANF-AUTO-PUB"
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id=anf_id,
            nombre_comercial="Auto Pub Glamping",
            comision_porcentaje=Decimal("10.00"),
            terminos_version="v2026.1",
        ),
        "+593992223334",
        actor_id="admin_01",
    )

    hospedaje = Hospedaje(
        propiedad_id="PROP-AUTO",
        anfitrion_id=anf_id,
        estado=EstadoHospedaje.PUBLICADO,
    )

    # Cuando el propio anfitrión intenta publicarlo directamente
    with pytest.raises(ErrorAnfitriones) as exc_info:
        srv.guardar_hospedaje(hospedaje, actor_id=anf_id)

    # Entonces la operación se rechaza
    assert exc_info.value.codigo == "PUBLICACION_NO_AUTORIZADA"

    # Y no aparece publicado
    assert len(srv.publicados()) == 0


def test_inv_solo_publicado_ignora_anfitrion_suspendido_o_pausado() -> None:
    srv, _, _, _, _ = _crear_servicio()

    # Anfitrión 1: Activo con hospedaje publicado
    anf1 = srv.registrar_anfitrion(
        Anfitrion(anfitrion_id="ANF-A1", nombre_comercial="A1", comision_porcentaje=Decimal("10"), terminos_version="v1"),
        "+593991", "admin",
    )
    srv.guardar_hospedaje(Hospedaje(propiedad_id="PROP-A1", anfitrion_id="ANF-A1", estado=EstadoHospedaje.PUBLICADO), actor_id="admin")

    # Anfitrión 2: Hospedaje pausado
    anf2 = srv.registrar_anfitrion(
        Anfitrion(anfitrion_id="ANF-A2", nombre_comercial="A2", comision_porcentaje=Decimal("10"), terminos_version="v1"),
        "+593992", "admin",
    )
    srv.guardar_hospedaje(Hospedaje(propiedad_id="PROP-A2", anfitrion_id="ANF-A2", estado=EstadoHospedaje.PAUSADO), actor_id="admin")

    # Anfitrión 3: Suspendido con hospedaje que estaba publicado
    anf3 = srv.registrar_anfitrion(
        Anfitrion(anfitrion_id="ANF-A3", nombre_comercial="A3", comision_porcentaje=Decimal("10"), terminos_version="v1"),
        "+593993", "admin",
    )
    srv.guardar_hospedaje(Hospedaje(propiedad_id="PROP-A3", anfitrion_id="ANF-A3", estado=EstadoHospedaje.PUBLICADO), actor_id="admin")
    # Suspender al anfitrión 3
    srv._persistencia._con.execute("UPDATE anfitriones SET estado = 'suspendido' WHERE anfitrion_id = 'ANF-A3'")

    # Solo el publicado del anfitrión activo es visible
    visibles = srv.publicados()
    assert len(visibles) == 1
    assert visibles[0].propiedad_id == "PROP-A1"
