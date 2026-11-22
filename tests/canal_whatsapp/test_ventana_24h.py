# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de RF-GW-03 e INV_VENTANA_24H: Control de la ventana de servicio de 24 horas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import FueraDeVentana, MensajeSaliente, Plantilla
from tests.canal_whatsapp.dobles import (
    ApiMetaSimulada, DobleObservabilidadService, DobleSeguridadService,
)


@pytest.fixture
def api_simulada() -> ApiMetaSimulada:
    return ApiMetaSimulada()


@pytest.fixture
def servicio(api_simulada: ApiMetaSimulada) -> CanalWhatsappService:
    config = dict(cargar_config())
    s = CanalWhatsappService(
        config,
        seguridad=DobleSeguridadService(),
        observabilidad=DobleObservabilidadService(),
        cliente_http=api_simulada,
        sleep_fn=lambda _: None,
    )
    return s


def test_dentro_de_ventana_permite_texto_libre(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-03: Dentro de 24 horas desde el último mensaje del usuario se puede enviar texto libre."""
    huesped = "593991234567"
    hace_dos_horas = datetime.now(timezone.utc) - timedelta(hours=2)
    servicio.repositorio.guardar_mensaje_meta(
        mensaje_id="in_huesped_1",
        direccion="in",
        remitente_token=huesped,
        canal="huespedes",
        tipo="texto",
        estado="recibido",
        enviado_en=hace_dos_horas,
    )

    assert servicio.en_ventana_24h(huesped) is True

    res = servicio.enviar(MensajeSaliente(destinatario=huesped, texto="Hola, en breve te confirmamos."))
    assert res.estado == "sent"
    assert len(api_simulada.mensajes_enviados) == 1


def test_fuera_de_ventana_rechaza_texto_libre_sin_llamar_a_meta(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-03 (b) e INV_VENTANA_24H: Texto libre fuera de 24 horas se rechaza con FueraDeVentana."""
    huesped = "593998887766"
    hace_veinticinco_horas = datetime.now(timezone.utc) - timedelta(hours=25)
    servicio.repositorio.guardar_mensaje_meta(
        mensaje_id="in_huesped_viejo",
        direccion="in",
        remitente_token=huesped,
        canal="huespedes",
        tipo="texto",
        estado="recibido",
        enviado_en=hace_veinticinco_horas,
    )

    assert servicio.en_ventana_24h(huesped) is False

    with pytest.raises(FueraDeVentana) as exc_info:
        servicio.enviar(MensajeSaliente(destinatario=huesped, texto="Mensaje no permitido"))

    assert exc_info.value.codigo == "FUERA_DE_VENTANA"
    assert len(api_simulada.mensajes_enviados) == 0, "No debe llamarse a Meta para texto libre fuera de ventana"


def test_contacto_nuevo_sin_mensajes_esta_fuera_de_ventana(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-03: Un contacto sin historial de mensajes entrantes está fuera de ventana."""
    nuevo_contacto = "593990001122"
    assert servicio.en_ventana_24h(nuevo_contacto) is False

    with pytest.raises(FueraDeVentana):
        servicio.enviar(MensajeSaliente(destinatario=nuevo_contacto, texto="Hola desconocido"))
    assert len(api_simulada.mensajes_enviados) == 0


def test_fuera_de_ventana_permite_plantilla_aprobada(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-03 (a) / US-03: Fuera de ventana se pueden enviar plantillas aprobadas (ej. instrucciones_checkin)."""
    huesped = "593994445566"
    servicio.aprobar_plantilla("instrucciones_checkin", True)

    plantilla = Plantilla(
        nombre="instrucciones_checkin",
        idioma="es",
        variables=("Carlos", "Domo Estelar", "15:00"),
    )
    res = servicio.enviar_plantilla(huesped, plantilla)

    assert res.estado == "sent"
    assert len(api_simulada.mensajes_enviados) == 1
    enviado = api_simulada.mensajes_enviados[0]["payload"]
    assert enviado["type"] == "template"
    assert enviado["template"]["name"] == "instrucciones_checkin"


def test_inv_ventana_24h_falla_si_se_intenta_eludir_la_compuerta(
    servicio: CanalWhatsappService,
) -> None:
    """INV_VENTANA_24H: Verifica que el predicado (¬plantilla ⇒ ahora - ultimo < 24h) sea estricto."""
    huesped_expirado = "593999999000"
    servicio.repositorio.guardar_mensaje_meta(
        mensaje_id="in_exp",
        direccion="in",
        remitente_token=huesped_expirado,
        canal="huespedes",
        tipo="texto",
        estado="recibido",
        enviado_en=datetime.now(timezone.utc) - timedelta(hours=24, minutes=1),
    )

    assert servicio.en_ventana_24h(huesped_expirado) is False
    with pytest.raises(FueraDeVentana):
        servicio.enviar(MensajeSaliente(destinatario=huesped_expirado, texto="Intento fuera de ventana"))
