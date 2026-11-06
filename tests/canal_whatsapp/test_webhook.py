"""Pruebas de RF-GW-01 e INV_FIRMA_WEBHOOK_META (desafío, firma HMAC, persistencia previa y dedup)."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import FirmaInvalida, TipoContenido
from tests.canal_whatsapp.dobles import DobleObservabilidadService, DobleSeguridadService


def calcular_firma(cuerpo: bytes, secreto: str) -> str:
    digest = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def payload_meta_mensaje(mensaje_id: str, remitente: str, texto: str) -> bytes:
    datos = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "59399999999", "phone_number_id": "phone_123"},
                            "messages": [
                                {
                                    "from": remitente,
                                    "id": mensaje_id,
                                    "timestamp": str(int(time.time())),
                                    "text": {"body": texto},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    return json.dumps(datos).encode("utf-8")


@pytest.fixture
def servicio() -> CanalWhatsappService:
    config = dict(cargar_config())
    config["verify_token"] = "token_de_prueba_123"
    config["secreto_app"] = "secreto_meta_app_456"
    return CanalWhatsappService(
        config,
        seguridad=DobleSeguridadService(),
        observabilidad=DobleObservabilidadService(),
    )


def test_verificacion_webhook_get_exitoso(servicio: CanalWhatsappService) -> None:
    """RF-GW-01 (a): Responde con el desafío hub.challenge si el token coincide."""
    resultado = servicio.verificar_webhook(
        modo="subscribe",
        token="token_de_prueba_123",
        desafio="desafio_meta_9876",
    )
    assert resultado == "desafio_meta_9876"


def test_verificacion_webhook_get_token_invalido(servicio: CanalWhatsappService) -> None:
    """RF-GW-01 (a): Rechaza el desafío si el token no coincide."""
    resultado = servicio.verificar_webhook(
        modo="subscribe",
        token="token_incorrecto",
        desafio="desafio_meta_9876",
    )
    assert resultado is None


def test_post_con_firma_valida_persiste_evento_en_pendiente_antes_de_2s(
    servicio: CanalWhatsappService,
) -> None:
    """RF-GW-01 (b, c), RF-GW-07 e INV_FIRMA_WEBHOOK_META.

    Un mensaje válido queda en canal.eventos_entrantes con estado 'pendiente' y responde en < 2 s.
    """
    msg_id = f"wamid.{uuid4().hex}"
    remitente = "593991112233"
    cuerpo = payload_meta_mensaje(msg_id, remitente, "Hola glamping")
    firma = calcular_firma(cuerpo, "secreto_meta_app_456")

    inicio = time.time()
    mensajes = servicio.recibir(cuerpo, firma)
    duracion = time.time() - inicio

    assert duracion < 2.0, "La recepción por webhook debe completarse en menos de 2 segundos"
    assert len(mensajes) == 1
    assert mensajes[0].mensaje_id == msg_id
    assert mensajes[0].remitente == remitente
    assert mensajes[0].texto == "Hola glamping"
    assert mensajes[0].tipo == TipoContenido.TEXTO

    evento = servicio.repositorio.obtener_evento(msg_id)
    assert evento is not None
    assert evento.estado == "pendiente"
    assert evento.conversacion_clave == remitente
    assert evento.cuerpo_cifrado == cuerpo


def test_post_con_firma_invalida_se_rechaza_con_401_y_no_persiste(
    servicio: CanalWhatsappService,
) -> None:
    """RF-GW-01 (b) e INV_FIRMA_WEBHOOK_META: Una firma inválida se rechaza con FirmaInvalida (401)."""
    msg_id = f"wamid.{uuid4().hex}"
    cuerpo = payload_meta_mensaje(msg_id, "593991112233", "Ataque o firma falsa")
    firma_falsa = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(FirmaInvalida) as exc_info:
        servicio.recibir(cuerpo, firma_falsa)

    assert exc_info.value.codigo == "FIRMA_INVALIDA"
    assert servicio.repositorio.obtener_evento(msg_id) is None


def test_reintento_de_meta_no_duplica_el_mensaje(servicio: CanalWhatsappService) -> None:
    """RF-GW-01 (d) y RF-GW-07: Un reintento con mensaje_id ya existente no se duplica ni se re-procesa."""
    msg_id = f"wamid.{uuid4().hex}"
    cuerpo = payload_meta_mensaje(msg_id, "593991112233", "Primer intento")
    firma = calcular_firma(cuerpo, "secreto_meta_app_456")

    primer_resultado = servicio.recibir(cuerpo, firma)
    assert len(primer_resultado) == 1

    segundo_resultado = servicio.recibir(cuerpo, firma)
    assert len(segundo_resultado) == 0

    pendientes = [e for e in servicio.repositorio.obtener_eventos_pendientes() if e.mensaje_id == msg_id]
    assert len(pendientes) == 1


def test_inv_firma_webhook_meta_falla_si_se_omite_o_altera_cuerpo(
    servicio: CanalWhatsappService,
) -> None:
    """INV_FIRMA_WEBHOOK_META: Prueba explícita que falla si la validación es vulnerada o alterada."""
    cuerpo_original = payload_meta_mensaje("wamid.123", "593991112233", "Mensaje genuino")
    firma_original = calcular_firma(cuerpo_original, "secreto_meta_app_456")

    cuerpo_alterado = payload_meta_mensaje("wamid.123", "593991112233", "Mensaje manipulado")

    with pytest.raises(FirmaInvalida):
        servicio.recibir(cuerpo_alterado, firma_original)
