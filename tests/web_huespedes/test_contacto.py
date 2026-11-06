"""Árbitro de RF-WEB-04, INV_WEB_SIN_PII, INV_WEB_SOLO_LECTURA y US-18.

Verifica el paso a WhatsApp con código de contexto sin PII, la resolución del contexto para el asistente
y que ninguna ruta efectúe reservas en el PMS.
"""
from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from features.web_huespedes.tipos import Busqueda, EnlaceContacto
from features.web_huespedes.web_huespedes_service import WebHuespedesService, cargar_config


def test_crear_enlace_contacto_formato_codigo_y_sin_pii() -> None:
    # Dado una opción elegida
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)

    busqueda = Busqueda(desde=date(2026, 11, 15), hasta=date(2026, 11, 18), huespedes=2)

    # Cuando el visitante solicita enlace de contacto
    enlace = servicio.crear_enlace_contacto("EJ-01", busqueda)

    # Entonces se abre el chat con un código W-XXXXXXXX, sin nombre ni teléfono en el enlace
    assert enlace.startswith("https://wa.me/")

    parsed = urllib.parse.urlparse(enlace)
    qs = urllib.parse.parse_qs(parsed.query)
    assert "text" in qs
    mensaje = qs["text"][0]

    match = re.search(r"W-[A-Z0-9]{8}", mensaje)
    assert match is not None, f"El mensaje '{mensaje}' no contiene un código W-XXXXXXXX válido"
    codigo = match.group(0)

    # Invariante INV_WEB_SIN_PII: ningún dato personal en el enlace
    assert "nombre" not in enlace.lower()
    assert "email" not in enlace.lower()
    assert "@" not in enlace

    # Y el asistente recibe propiedad, fechas y huéspedes al resolverlo
    contexto = servicio.resolver_contacto(codigo)
    assert isinstance(contexto, EnlaceContacto)
    assert contexto.codigo == codigo
    assert contexto.propiedad_id == "EJ-01"
    assert contexto.desde == date(2026, 11, 15)
    assert contexto.hasta == date(2026, 11, 18)
    assert contexto.huespedes == 2


def test_resolver_contacto_inexistente_o_expirado() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)

    assert servicio.resolver_contacto("W-00000000") is None

    # Simular enlace expirado
    codigo = "W-EXPIRADO"
    ahora = datetime.now(timezone.utc)
    enlace = EnlaceContacto(codigo=codigo, propiedad_id="EJ-01")
    servicio._repositorio.guardar_enlace(
        enlace,
        creado_en=ahora - timedelta(hours=100),
        expira_en=ahora - timedelta(hours=1),
    )
    assert servicio.resolver_contacto(codigo) is None


def test_post_contacto_redirige_a_whatsapp_con_contexto() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    resp = client.post(
        "/contacto",
        data={
            "propiedad_id": "EJ-01",
            "desde": "2026-12-01",
            "hasta": "2026-12-05",
            "huespedes": "3",
        },
        follow_redirects=False,
    )

    assert resp.status_code == 303
    url_destino = resp.headers["location"]
    assert url_destino.startswith("https://wa.me/")

    # Extraer código y validar resolución
    match = re.search(r"W-[A-Z0-9]{8}", urllib.parse.unquote(url_destino))
    assert match is not None
    codigo = match.group(0)

    resuelto = servicio.resolver_contacto(codigo)
    assert resuelto is not None
    assert resuelto.propiedad_id == "EJ-01"
    assert resuelto.desde == date(2026, 12, 1)
    assert resuelto.hasta == date(2026, 12, 5)
    assert resuelto.huespedes == 3


def test_inv_web_solo_lectura_la_web_no_reserva() -> None:
    # Dado cualquier visitante y un PMS con métodos de reserva vigilados
    pms_mock = MagicMock()
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms_mock)
    client = TestClient(servicio.crear_app())

    # Cuando usa la web (catálogo, ficha, contacto)
    client.get("/")
    client.get("/propiedades/EJ-01")
    client.post("/contacto", data={"propiedad_id": "EJ-01"})
    client.get("/contacto?propiedad_id=EJ-01")

    # Entonces ninguna ruta crea, cambia o cancela reservas en el PMS
    assert not hasattr(pms_mock, "crear_reserva") or pms_mock.crear_reserva.call_count == 0
    assert not hasattr(pms_mock, "modificar_reserva") or pms_mock.modificar_reserva.call_count == 0
    assert not hasattr(pms_mock, "cancelar_reserva") or pms_mock.cancelar_reserva.call_count == 0
    pms_mock.assert_not_called()
