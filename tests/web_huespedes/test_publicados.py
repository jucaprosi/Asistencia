# ¤web-huespedes
# ¤¤frontend-developer
"""Árbitro de RF-ANF-03 e INV_SOLO_PUBLICADO (T-405).

Verifica que la web pública ofrece únicamente hospedajes publicados de anfitriones activos,
que los hospedajes pausados o de anfitriones suspendidos no aparecen en catálogo, búsqueda,
comparación ni ficha directa, y que cada hospedaje visible indica quién lo ofrece.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from features.anfitriones.anfitriones_service import (
    Anfitrion,
    EstadoAnfitrion,
    EstadoHospedaje,
    Hospedaje,
)
from features.web_huespedes.tipos import Busqueda
from features.web_huespedes.web_huespedes_service import (
    ErrorWebHuespedes,
    WebHuespedesService,
    cargar_config,
)
from tests.web_huespedes.dobles import DobleAnfitriones, DobleObservabilidad, DoblePMS


# ¤web-huespedes
def _crear_entorno_prueba() -> tuple[WebHuespedesService, DobleAnfitriones, DoblePMS, DobleObservabilidad]:
    config = dict(cargar_config())
    anfitriones = DobleAnfitriones()
    pms = DoblePMS(total=Decimal("220.00"), disponible=True)
    obs = DobleObservabilidad()

    # Registrar anfitrión activo
    anfitriones.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-SAN-PABLO",
            nombre_comercial="Glamping San Pablo",
            comision_porcentaje=Decimal("15.00"),
            terminos_version="v2026.1",
            estado=EstadoAnfitrion.ACTIVO,
        )
    )

    # Hospedaje publicado
    anfitriones.publicar_hospedaje(
        propiedad_id="DOMO-LAGO",
        anfitrion_id="ANF-SAN-PABLO",
        actor_id="admin_revisor",
    )

    # Hospedaje pausado
    anfitriones.guardar_hospedaje(
        Hospedaje(
            propiedad_id="CAB-BOSQUE",
            anfitrion_id="ANF-SAN-PABLO",
            estado=EstadoHospedaje.PAUSADO,
        )
    )

    servicio = WebHuespedesService(
        config,
        pms=pms,
        observabilidad=obs,
        anfitriones=anfitriones,
    )
    return servicio, anfitriones, pms, obs


# ¤web-huespedes
def test_hospedaje_pausado_no_aparece_en_catalogo() -> None:
    """@RF-ANF-03 @INV_SOLO_PUBLICADO: Un hospedaje pausado no se ofrece en el catálogo."""
    servicio, _, _, _ = _crear_entorno_prueba()

    catalogo = servicio.catalogo()
    propiedad_ids = [f.propiedad_id for f in catalogo]

    assert "DOMO-LAGO" in propiedad_ids
    assert "CAB-BOSQUE" not in propiedad_ids

    # Cada hospedaje visible dice quién lo ofrece
    ficha_publicada = next(f for f in catalogo if f.propiedad_id == "DOMO-LAGO")
    assert ficha_publicada.anfitrion_id == "ANF-SAN-PABLO"
    assert ficha_publicada.ofrecido_por == "Glamping San Pablo"


# ¤web-huespedes
def test_hospedaje_pausado_en_ficha_retorna_error_y_404_en_web() -> None:
    """@RF-ANF-03 @INV_SOLO_PUBLICADO: Acceso directo a ficha de hospedaje pausado falla."""
    servicio, _, _, _ = _crear_entorno_prueba()
    client = TestClient(servicio.crear_app())

    # Ficha del hospedaje pausado levanta error tipado
    with pytest.raises(ErrorWebHuespedes) as exc_info:
        servicio.ficha("CAB-BOSQUE")
    assert exc_info.value.codigo == "PROPIEDAD_NO_PUBLICADA"

    # Vía HTTP retorna 404
    resp = client.get("/propiedades/CAB-BOSQUE")
    assert resp.status_code == 404

    # Hospedaje publicado retorna 200 y dice quién lo ofrece
    resp_pub = client.get("/propiedades/DOMO-LAGO")
    assert resp_pub.status_code == 200
    assert "Glamping San Pablo" in resp_pub.text
    assert "Ofrecido por" in resp_pub.text


# ¤web-huespedes
def test_hospedaje_pausado_no_aparece_en_busqueda() -> None:
    """@RF-ANF-03 @INV_SOLO_PUBLICADO: La búsqueda omite hospedajes pausados."""
    servicio, _, _, _ = _crear_entorno_prueba()
    client = TestClient(servicio.crear_app())

    manana = date.today() + timedelta(days=1)
    salida = manana + timedelta(days=2)
    busqueda = Busqueda(desde=manana, hasta=salida, huespedes=2)

    opciones = servicio.buscar(busqueda)
    pids_encontrados = [op.ficha.propiedad_id for op in opciones]

    assert "DOMO-LAGO" in pids_encontrados
    assert "CAB-BOSQUE" not in pids_encontrados

    # Vía HTTP
    resp = client.get(f"/buscar?desde={manana.isoformat()}&hasta={salida.isoformat()}&huespedes=2")
    assert resp.status_code == 200
    assert "DOMO-LAGO" in resp.text
    assert "CAB-BOSQUE" not in resp.text
    assert "Glamping San Pablo" in resp.text


# ¤web-huespedes
def test_hospedaje_pausado_omitido_en_comparar() -> None:
    """@RF-ANF-03 @INV_SOLO_PUBLICADO: Comparación ignora hospedajes sin publicar."""
    servicio, _, _, _ = _crear_entorno_prueba()
    client = TestClient(servicio.crear_app())

    manana = date.today() + timedelta(days=1)
    salida = manana + timedelta(days=2)
    busqueda = Busqueda(desde=manana, hasta=salida, huespedes=2)

    # Intentar comparar DOMO-LAGO (publicado) con CAB-BOSQUE (pausado)
    opciones = servicio.comparar(("DOMO-LAGO", "CAB-BOSQUE"), busqueda)
    pids_comparados = [op.ficha.propiedad_id for op in opciones]

    assert "DOMO-LAGO" in pids_comparados
    assert "CAB-BOSQUE" not in pids_comparados

    # Vía HTTP
    resp = client.get(f"/comparar?ids=DOMO-LAGO,CAB-BOSQUE&desde={manana.isoformat()}&hasta={salida.isoformat()}&huespedes=2")
    assert resp.status_code == 200
    assert "DOMO-LAGO" in resp.text
    assert "CAB-BOSQUE" not in resp.text


# ¤web-huespedes
def test_cada_hospedaje_visible_dice_quien_lo_ofrece_en_html() -> None:
    """@RF-ANF-03: Criterio: cada hospedaje visible dice quién lo ofrece en el HTML."""
    servicio, _, _, _ = _crear_entorno_prueba()
    client = TestClient(servicio.crear_app())

    resp = client.get("/")
    assert resp.status_code == 200
    assert "Ofrecido por:" in resp.text
    assert "Glamping San Pablo" in resp.text


# ¤web-huespedes
def test_hospedaje_de_anfitrion_suspendido_no_se_ofrece() -> None:
    """@RF-ANF-03 @INV_SOLO_PUBLICADO: visible(h) => anfitrion activo."""
    servicio, anfitriones, _, _ = _crear_entorno_prueba()

    # Suspender al anfitrión
    anfitriones.suspender_anfitrion("ANF-SAN-PABLO")

    # El catálogo ahora debe estar vacío
    catalogo = servicio.catalogo()
    assert len(catalogo) == 0

    # Ficha debe fallar
    with pytest.raises(ErrorWebHuespedes):
        servicio.ficha("DOMO-LAGO")
