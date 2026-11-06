"""Pruebas de RF-GW-02: Envío de texto, botones, listas, estados y reintentos con backoff."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import (
    ApiMetaNoDisponible, Boton, ErrorCanalWhatsapp, MensajeSaliente, OpcionLista,
)
from tests.canal_whatsapp.dobles import (
    ApiMetaSimulada, DobleObservabilidadService, DobleSeguridadService,
)


@pytest.fixture
def api_simulada() -> ApiMetaSimulada:
    return ApiMetaSimulada(fallos_iniciales=0)


@pytest.fixture
def obs_doble() -> DobleObservabilidadService:
    return DobleObservabilidadService()


@pytest.fixture
def servicio(api_simulada: ApiMetaSimulada, obs_doble: DobleObservabilidadService) -> CanalWhatsappService:
    config = dict(cargar_config())
    s = CanalWhatsappService(
        config,
        seguridad=DobleSeguridadService(),
        observabilidad=obs_doble,
        cliente_http=api_simulada,
        sleep_fn=lambda _: None,
    )
    s.repositorio.guardar_mensaje_meta(
        mensaje_id="in_previo_123",
        direccion="in",
        remitente_token="593991234567",
        canal="huespedes",
        tipo="texto",
        estado="recibido",
        enviado_en=datetime.now(timezone.utc),
    )
    return s


def test_envio_texto_registra_sent(servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada) -> None:
    """RF-GW-02: Envía texto simple y registra estado inicial sent."""
    mensaje = MensajeSaliente(destinatario="593991234567", texto="Bienvenido al Glamping")
    res = servicio.enviar(mensaje)

    assert res.estado == "sent"
    assert res.mensaje_id.startswith("wamid.")
    assert len(api_simulada.mensajes_enviados) == 1
    assert api_simulada.mensajes_enviados[0]["payload"]["text"]["body"] == "Bienvenido al Glamping"

    meta = servicio.repositorio.obtener_mensaje_meta(res.mensaje_id)
    assert meta is not None
    assert meta.estado == "sent"
    assert meta.direccion == "out"


def test_envio_botones_rapidos(servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada) -> None:
    """RF-GW-02: Envía texto con botones de respuesta rápida (hasta 3)."""
    botones = (
        Boton(id="b1", titulo="Ver cabañas"),
        Boton(id="b2", titulo="Ubicación"),
        Boton(id="b3", titulo="Hablar con humano"),
    )
    mensaje = MensajeSaliente(destinatario="593991234567", texto="¿En qué te ayudo?", botones=botones)
    res = servicio.enviar(mensaje)

    assert res.estado == "sent"
    enviado = api_simulada.mensajes_enviados[0]["payload"]
    assert enviado["type"] == "interactive"
    assert len(enviado["interactive"]["action"]["buttons"]) == 3


def test_envio_botones_exceso_falla(servicio: CanalWhatsappService) -> None:
    """RF-GW-02: Rechaza mensajes con más de 3 botones."""
    botones = tuple(Boton(id=f"b{i}", titulo=f"Boton {i}") for i in range(4))
    mensaje = MensajeSaliente(destinatario="593991234567", texto="Muchos botones", botones=botones)

    with pytest.raises(ErrorCanalWhatsapp) as exc:
        servicio.enviar(mensaje)
    assert exc.value.codigo == "BOTONES_EXCEDIDOS"


def test_envio_lista_interactiva(servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada) -> None:
    """RF-GW-02: Envía mensaje interactivo de lista (hasta 10 opciones)."""
    opciones = tuple(
        OpcionLista(id=f"op_{i}", titulo=f"Cabaña {i}", descripcion=f"Descripción {i}")
        for i in range(10)
    )
    mensaje = MensajeSaliente(destinatario="593991234567", texto="Elige tu cabaña", lista=opciones)
    res = servicio.enviar(mensaje)

    assert res.estado == "sent"
    enviado = api_simulada.mensajes_enviados[0]["payload"]
    assert enviado["type"] == "interactive"
    assert len(enviado["interactive"]["action"]["sections"][0]["rows"]) == 10


def test_envio_lista_excede_diez_falla(servicio: CanalWhatsappService) -> None:
    """RF-GW-02: Rechaza listas con más de 10 opciones."""
    opciones = tuple(OpcionLista(id=f"op_{i}", titulo=f"Opcion {i}") for i in range(11))
    mensaje = MensajeSaliente(destinatario="593991234567", texto="Demasiadas opciones", lista=opciones)

    with pytest.raises(ErrorCanalWhatsapp) as exc:
        servicio.enviar(mensaje)
    assert exc.value.codigo == "OPCIONES_EXCEDIDAS"


def test_actualizacion_de_estados_meta(servicio: CanalWhatsappService) -> None:
    """RF-GW-02 (a): Registra cada estado (sent, delivered, read, failed) vía status updates."""
    mensaje = MensajeSaliente(destinatario="593991234567", texto="Mensaje de prueba estados")
    res = servicio.enviar(mensaje)
    msg_id = res.mensaje_id

    servicio.actualizar_estado(msg_id, "delivered")
    assert servicio.repositorio.obtener_mensaje_meta(msg_id).estado == "delivered"  # type: ignore[union-attr]

    servicio.actualizar_estado(msg_id, "read")
    assert servicio.repositorio.obtener_mensaje_meta(msg_id).estado == "read"  # type: ignore[union-attr]

    servicio.actualizar_estado(msg_id, "failed")
    assert servicio.repositorio.obtener_mensaje_meta(msg_id).estado == "failed"  # type: ignore[union-attr]


def test_reintentos_exponenciales_exito_al_tercer_intento(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-02 (b): Falla dos veces y tiene éxito en el 3er intento."""
    api_simulada.fallos_restantes = 2

    mensaje = MensajeSaliente(destinatario="593991234567", texto="Mensaje con reintento")
    res = servicio.enviar(mensaje)

    assert res.estado == "sent"
    assert len(api_simulada.llamadas) == 3


def test_reintentos_agotados_registra_en_observabilidad(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada, obs_doble: DobleObservabilidadService,
) -> None:
    """RF-GW-02 (b): Tras agotar 3 reintentos, registra en bitácora de errores y lanza ApiMetaNoDisponible."""
    api_simulada.fallos_restantes = 10

    mensaje = MensajeSaliente(destinatario="593991234567", texto="Mensaje que fallará")
    with pytest.raises(ApiMetaNoDisponible):
        servicio.enviar(mensaje)

    assert len(api_simulada.llamadas) == 4
    logs_error = [log for log in obs_doble.logs if log["nivel"] == "ERROR"]
    assert len(logs_error) >= 1
    assert logs_error[0]["evento"] == "ENVIO_META_FALLIDO"
