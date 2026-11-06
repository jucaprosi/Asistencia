# ¤web-huespedes
# ¤¤frontend-developer
"""Árbitro de RF-WEB-02, RF-WEB-03, INV_WEB_PRECIO_EN_VIVO, INV_WEB_LIMITE_POR_IP, INV_WEB_SOLO_LECTURA y US-18.

Verifica la búsqueda por fechas, huéspedes, tipo y zona con precios en vivo del PMS,
la degradación elegante ofreciendo WhatsApp si el PMS falla, la comparación de hasta
3 hospedajes lado a lado, y los invariantes de seguridad y cuota por IP.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from features.web_huespedes.tipos import Busqueda, OpcionDisponible
from features.web_huespedes.web_huespedes_service import (
    ErrorWebHuespedes,
    WebHuespedesService,
    cargar_config,
)


@dataclass(frozen=True)
class DobleUnidad:
    unidad_id: str
    capacidad: int = 4
    nombre: str = "Unidad Principal"


@dataclass(frozen=True)
class DobleDisponibilidad:
    disponible: bool
    unidades: tuple[DobleUnidad, ...] = ()


@dataclass(frozen=True)
class DobleCotizacion:
    total: Decimal
    moneda: str = "USD"


def _crear_doble_pms(total: Decimal = Decimal("150.00"), disponible: bool = True) -> MagicMock:
    pms = MagicMock()
    if disponible:
        pms.consultar_disponibilidad.return_value = DobleDisponibilidad(
            disponible=True,
            unidades=(DobleUnidad(unidad_id="U-01", capacidad=4),),
        )
        pms.cotizar.return_value = DobleCotizacion(total=total, moneda="USD")
    else:
        pms.consultar_disponibilidad.return_value = DobleDisponibilidad(disponible=False)
    return pms


def test_buscar_exitoso_obtiene_precios_y_disponibilidad_en_vivo() -> None:
    # Dado el PMS respondiendo cotización en vivo
    pms = _crear_doble_pms(total=Decimal("210.00"))
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms)

    busqueda = Busqueda(desde=date(2026, 12, 1), hasta=date(2026, 12, 4), huespedes=2)

    # Cuando se busca disponibilidad
    opciones = servicio.buscar(busqueda)

    # Entonces el precio y disponibilidad salen del PMS (INV_WEB_PRECIO_EN_VIVO)
    assert len(opciones) >= 1
    assert all(isinstance(op, OpcionDisponible) for op in opciones)
    assert any(op.total == Decimal("210.00") for op in opciones)
    pms.consultar_disponibilidad.assert_called()
    pms.cotizar.assert_called()

    # Y vía HTTP la respuesta tiene Cache-Control: no-store y muestra el total
    client = TestClient(servicio.crear_app())
    resp = client.get("/buscar?desde=2026-12-01&hasta=2026-12-04&huespedes=2")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert "210.00" in resp.text
    assert "Reservar por WhatsApp" in resp.text


def test_buscar_pms_falla_no_muestra_precios_y_ofrece_whatsapp() -> None:
    # Dado el PMS sin responder o con timeout
    pms_roto = MagicMock()
    pms_roto.consultar_disponibilidad.side_effect = TimeoutError("Tiempo de espera agotado con PMS")

    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms_roto)
    client = TestClient(servicio.crear_app())

    # Cuando el visitante busca
    resp = client.get("/buscar?desde=2026-12-01&hasta=2026-12-04&huespedes=2")

    # Entonces no se muestran precios y se ofrece WhatsApp (RF-WEB-02 b)
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert "Consulta de tarifas temporalmente no disponible" in resp.text
    assert "Consultar por WhatsApp" in resp.text
    # Ausencia de precios en vivo al estar el PMS caído
    assert "USD" not in resp.text
    assert "$" not in resp.text


def test_buscar_filtros_tipo_y_zona() -> None:
    pms = _crear_doble_pms(total=Decimal("120.00"))
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms)

    busqueda = Busqueda(
        desde=date(2026, 12, 10),
        hasta=date(2026, 12, 12),
        huespedes=2,
        tipo="glamping",
        zona="San Pablo",
    )
    opciones = servicio.buscar(busqueda)

    for op in opciones:
        assert op.ficha.tipo.lower() == "glamping"
        assert "san pablo" in op.ficha.zona.lower()


def test_comparar_hasta_tres_hospedajes_lado_a_lado() -> None:
    # Dado hasta 3 propiedades seleccionadas y cotización en vivo
    pms = _crear_doble_pms(total=Decimal("175.00"))
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms)

    busqueda = Busqueda(desde=date(2026, 12, 15), hasta=date(2026, 12, 18), huespedes=2)
    propiedades = ("EJ-01", "DOMO-LAGO")

    # Cuando se solicita comparación
    opciones = servicio.comparar(propiedades, busqueda)

    # Entonces muestra capacidad, zona, comodidades y total (RF-WEB-03 a)
    assert len(opciones) == 2
    for op in opciones:
        assert op.ficha.capacidad >= 2
        assert op.ficha.zona
        assert len(op.ficha.comodidades) >= 1
        assert op.total == Decimal("175.00")

    # Vía HTTP
    client = TestClient(servicio.crear_app())
    resp = client.get("/comparar?ids=EJ-01,DOMO-LAGO&desde=2026-12-15&hasta=2026-12-18&huespedes=2")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-store"
    assert "Comparación de Hospedajes" in resp.text
    assert "175.00" in resp.text
    assert "Capacidad" in resp.text
    assert "Zona" in resp.text
    assert "Comodidades" in resp.text
    assert "Continuar a WhatsApp" in resp.text


def test_comparar_rechaza_mas_de_tres_hospedajes() -> None:
    pms = _crear_doble_pms()
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms)

    busqueda = Busqueda(desde=date(2026, 12, 15), hasta=date(2026, 12, 18), huespedes=2)
    cuatro_props = ("EJ-01", "DOMO-LAGO", "CAB-BOSQUE", "SUITE-IMBABURA")

    try:
        servicio.comparar(cuatro_props, busqueda)
        assert False, "Debió rechazar más de 3 propiedades"
    except ErrorWebHuespedes as err:
        assert err.codigo == "LIMITE_COMPARACION_EXCEDIDO"

    client = TestClient(servicio.crear_app())
    resp = client.get(f"/comparar?ids={','.join(cuatro_props)}&desde=2026-12-15&hasta=2026-12-18&huespedes=2")
    assert resp.status_code == 400
    assert resp.headers["Cache-Control"] == "no-store"


def test_comparar_no_incluye_hospedajes_sin_publicar() -> None:
    pms = _crear_doble_pms(total=Decimal("190.00"))
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms)

    busqueda = Busqueda(desde=date(2026, 12, 20), hasta=date(2026, 12, 22), huespedes=2)
    # Incluye un ID inexistente / no publicado
    propiedades = ("EJ-01", "PROPIEDAD_FANTASMA_NO_PUBLICADA")

    opciones = servicio.comparar(propiedades, busqueda)

    # Criterio (b): no incluye hospedajes sin publicar
    assert len(opciones) == 1
    assert opciones[0].ficha.propiedad_id == "EJ-01"


def test_invariante_web_limite_por_ip_cero_llamadas_pms_al_exceder() -> None:
    pms = _crear_doble_pms()
    config = dict(cargar_config())
    config["limites"] = {"por_ip_minuto": 2}
    servicio = WebHuespedesService(config, pms=pms)
    client = TestClient(servicio.crear_app())

    # 1ª y 2ª llamada permitidas
    resp1 = client.get("/buscar?desde=2026-12-01&hasta=2026-12-02&huespedes=1", headers={"X-Forwarded-For": "198.51.100.42"})
    assert resp1.status_code == 200

    resp2 = client.get("/buscar?desde=2026-12-01&hasta=2026-12-02&huespedes=1", headers={"X-Forwarded-For": "198.51.100.42"})
    assert resp2.status_code == 200

    llamadas_antes = pms.consultar_disponibilidad.call_count

    # 3ª llamada excede la cuota de 2 por minuto
    resp3 = client.get("/buscar?desde=2026-12-01&hasta=2026-12-02&huespedes=1", headers={"X-Forwarded-For": "198.51.100.42"})
    assert resp3.status_code == 429
    assert resp3.headers["Cache-Control"] == "no-store"

    # Invariante INV_WEB_LIMITE_POR_IP: conteo > limite => |llamadas_pms| = 0
    llamadas_despues = pms.consultar_disponibilidad.call_count
    assert llamadas_despues == llamadas_antes, "El PMS no debió ser invocado tras exceder el límite de IP"


def test_invariante_web_solo_lectura_sin_efectos_mutadores_en_pms() -> None:
    pms = _crear_doble_pms()
    config = dict(cargar_config())
    servicio = WebHuespedesService(config, pms=pms)
    client = TestClient(servicio.crear_app())

    client.get("/buscar?desde=2026-12-01&hasta=2026-12-03&huespedes=2")
    client.get("/comparar?ids=EJ-01&desde=2026-12-01&hasta=2026-12-03&huespedes=2")

    # Invariante INV_WEB_SOLO_LECTURA: ninguna compuerta mutadora invocada
    assert not hasattr(pms, "crear_reserva_preliminar") or not pms.crear_reserva_preliminar.called
    assert not hasattr(pms, "confirmar_reserva") or not pms.confirmar_reserva.called
    assert not hasattr(pms, "cancelar_reserva") or not pms.cancelar_reserva.called
    assert not hasattr(pms, "actualizar_calendario") or not pms.actualizar_calendario.called
