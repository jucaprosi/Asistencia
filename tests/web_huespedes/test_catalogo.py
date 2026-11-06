"""Árbitro de RF-WEB-01 y US-18: Catálogo público y ficha por propiedad.

Verifica que el catálogo y la ficha funcionan sin depender del PMS y sin mostrar precios ni cupos.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from features.web_huespedes.tipos import FichaPropiedad
from features.web_huespedes.web_huespedes_service import ErrorWebHuespedes, WebHuespedesService, cargar_config


def test_catalogo_sin_pms_carga_propiedades() -> None:
    # Dado el catálogo público cargado y el PMS sin responder (falla si lo llaman)
    pms_roto = MagicMock()
    pms_roto.consultar_disponibilidad.side_effect = RuntimeError("PMS caído")
    pms_roto.cotizar.side_effect = RuntimeError("PMS caído")

    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms_roto)

    # Cuando un visitante abre el catálogo
    catalogo = servicio.catalogo()

    # Entonces ve las propiedades sin llamadas al PMS y sin campos de precio ni cupo
    assert len(catalogo) >= 1
    pms_roto.consultar_disponibilidad.assert_not_called()
    pms_roto.cotizar.assert_not_called()

    for item in catalogo:
        assert isinstance(item, FichaPropiedad)
        assert item.propiedad_id
        assert item.nombre
        assert item.zona
        assert item.capacidad >= 1
        assert not hasattr(item, "precio")
        assert not hasattr(item, "cupos")


def test_ficha_propiedad_existente() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)

    ficha = servicio.ficha("EJ-01")
    assert ficha.propiedad_id == "EJ-01"
    assert ficha.nombre == "Domo de ejemplo"
    assert ficha.capacidad == 2
    assert "desayuno" in ficha.comodidades


def test_ficha_propiedad_inexistente_lanza_error_tipado() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)

    try:
        servicio.ficha("PROPIEDAD_DESCONOCIDA")
        assert False, "Debió lanzar ErrorWebHuespedes"
    except ErrorWebHuespedes as err:
        assert err.codigo == "PROPIEDAD_NO_ENCONTRADA"
        assert err.mensaje_usuario


def test_ruta_inicio_renderiza_catalogo_sin_precios() -> None:
    # Dado el PMS sin responder
    pms_roto = MagicMock()
    pms_roto.consultar_disponibilidad.side_effect = RuntimeError("PMS caído")
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms_roto)
    client = TestClient(servicio.crear_app())

    # Cuando un visitante abre la web
    resp = client.get("/")

    # Entonces ve las propiedades, sin precios ni cupos
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Domo de ejemplo" in resp.text
    assert "Nuestros Hospedajes" in resp.text
    # Sin indicadores de precios ni cupos
    assert "USD" not in resp.text
    assert "$" not in resp.text
    assert "cupo" not in resp.text.lower()
    pms_roto.consultar_disponibilidad.assert_not_called()


def test_ruta_ficha_renderiza_propiedad_y_404_en_inexistente() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    resp = client.get("/propiedades/EJ-01")
    assert resp.status_code == 200
    assert "Domo de ejemplo" in resp.text
    assert "Zona de ejemplo" in resp.text
    assert "desayuno" in resp.text
    assert "USD" not in resp.text

    resp_404 = client.get("/propiedades/NO_EXISTE")
    assert resp_404.status_code == 404
    assert "Aviso del Sistema" in resp_404.text
