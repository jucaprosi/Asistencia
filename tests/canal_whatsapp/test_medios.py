"""Pruebas de RF-GW-05: Recepción, descarga protegida, referencia URI y envío de medios."""
from __future__ import annotations

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import MedioNoPermitido, MensajeSaliente
from tests.canal_whatsapp.dobles import (
    ApiMetaSimulada, DobleObservabilidadService, DobleSeguridadService,
)


@pytest.fixture
def api_simulada() -> ApiMetaSimulada:
    return ApiMetaSimulada()


@pytest.fixture
def seguridad_doble() -> DobleSeguridadService:
    return DobleSeguridadService()


@pytest.fixture
def servicio(api_simulada: ApiMetaSimulada, seguridad_doble: DobleSeguridadService) -> CanalWhatsappService:
    config = dict(cargar_config())
    return CanalWhatsappService(
        config,
        seguridad=seguridad_doble,
        observabilidad=DobleObservabilidadService(),
        cliente_http=api_simulada,
        sleep_fn=lambda _: None,
    )


def test_descarga_medio_remitente_permitido_entrega_referencia_sin_bytes(
    servicio: CanalWhatsappService,
) -> None:
    """RF-GW-05 (a): Guarda el archivo en almacenamiento y entrega medio_ref al agente, nunca los bytes."""
    remitente_permitido = "593991234567"
    medio_id = "media_img_1"

    medio_ref = servicio.descargar_medio(medio_id, remitente=remitente_permitido)

    assert isinstance(medio_ref, str)
    assert medio_ref.startswith("s3://glamping-medios/whatsapp/media_img_1")
    assert not isinstance(medio_ref, (bytes, bytearray))

    registro = servicio.repositorio.obtener_medio(medio_id)
    assert registro is not None
    assert registro.medio_ref == medio_ref
    assert registro.tipo == "imagen"
    assert registro.bytes > 0


def test_descarga_medio_remitente_bloqueado_no_se_descarga(
    servicio: CanalWhatsappService, seguridad_doble: DobleSeguridadService,
) -> None:
    """RF-GW-05 (b): Los medios de números bloqueados o descartados no se descargan."""
    numero_bloqueado = "593996666666"
    seguridad_doble.bloquear(numero_bloqueado)

    medio_id = "media_doc_1"

    with pytest.raises(MedioNoPermitido) as exc_info:
        servicio.descargar_medio(medio_id, remitente=numero_bloqueado)

    assert exc_info.value.codigo == "MEDIO_NO_PERMITIDO"
    assert servicio.repositorio.obtener_medio(medio_id) is None


def test_envio_imagen_saliente(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-05: Envía imágenes usando referencia medio_ref."""
    destinatario = "593991234567"
    hace_un_minuto = "2026-10-31T20:00:00+00:00"
    servicio.repositorio.guardar_mensaje_meta(
        mensaje_id="in_reciente",
        direccion="in",
        remitente_token=destinatario,
        canal="huespedes",
        tipo="texto",
        estado="recibido",
    )

    msg = MensajeSaliente(
        destinatario=destinatario,
        texto="Mapa de acceso al glamping",
        medio_ref="s3://glamping-medios/whatsapp/mapa.jpg",
    )
    res = servicio.enviar(msg)

    assert res.estado == "sent"
    assert len(api_simulada.mensajes_enviados) == 1
    enviado = api_simulada.mensajes_enviados[0]["payload"]
    assert enviado["type"] == "image"
    assert enviado["image"]["link"] == "s3://glamping-medios/whatsapp/mapa.jpg"


def test_envio_documento_saliente(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-05: Envía documentos usando referencia medio_ref."""
    destinatario = "593991234567"
    servicio.repositorio.guardar_mensaje_meta(
        mensaje_id="in_reciente_doc",
        direccion="in",
        remitente_token=destinatario,
        canal="huespedes",
        tipo="texto",
        estado="recibido",
    )

    msg = MensajeSaliente(
        destinatario=destinatario,
        texto="Reglamento del Glamping",
        medio_ref="s3://glamping-medios/whatsapp/reglamento.pdf",
    )
    res = servicio.enviar(msg)

    assert res.estado == "sent"
    enviado = api_simulada.mensajes_enviados[0]["payload"]
    assert enviado["type"] == "document"
    assert enviado["document"]["link"] == "s3://glamping-medios/whatsapp/reglamento.pdf"
