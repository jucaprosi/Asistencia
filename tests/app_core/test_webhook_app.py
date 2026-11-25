# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del árbitro para T-110: rutas HTTP /webhook (Meta) y montaje del catálogo público de web_huespedes."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.main import crear_app

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "META_ACCESS_TOKEN": "token_acceso_meta_test",
    "META_VERIFY_TOKEN": "token_prueba_meta_123",
    "META_APP_SECRET": "secreto_meta_app_456",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


# ¤pasillo-central
def calcular_firma(cuerpo: bytes, secreto: str) -> str:
    """Calcula la firma HMAC-SHA256 con el formato esperado por Meta (sha256=...)."""
    digest = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ¤pasillo-central
def payload_meta_mensaje(mensaje_id: str, remitente: str, texto: str) -> bytes:
    """Genera la estructura de evento entrante conforme a la API de WhatsApp Cloud de Meta."""
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
def contenedor() -> Contenedor:
    return construir(entorno=ENTORNO_PRUEBA)


@pytest.fixture
def cliente(contenedor: Contenedor) -> TestClient:
    app = crear_app(contenedor)
    return TestClient(app)


# ¤pasillo-central
def test_verificacion_webhook_get_exitoso(cliente: TestClient) -> None:
    """RF-GW-01 (a): Responde con el desafío hub.challenge si las credenciales coinciden."""
    respuesta = cliente.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "token_prueba_meta_123",
            "hub.challenge": "desafio_meta_challenge_777",
        },
    )
    assert respuesta.status_code == 200
    assert respuesta.text == "desafio_meta_challenge_777"


# ¤pasillo-central
def test_verificacion_webhook_get_token_invalido(cliente: TestClient) -> None:
    """RF-GW-01 (a): Rechaza con 403 si el token de verificación no coincide."""
    respuesta = cliente.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "token_falso_erroneo",
            "hub.challenge": "desafio_meta_challenge_777",
        },
    )
    assert respuesta.status_code == 403


# ¤pasillo-central
def test_post_webhook_firma_valida_persiste_evento_en_pendiente_antes_de_2s(
    cliente: TestClient,
    contenedor: Contenedor,
) -> None:
    """RF-GW-01 (b, c), RF-GW-07 e INV_FIRMA_WEBHOOK_META.

    Un POST válido queda persistido antes de responder 200 en < 2 s.
    """
    msg_id = f"wamid.{uuid4().hex}"
    remitente = "593991234567"
    cuerpo = payload_meta_mensaje(msg_id, remitente, "Hola, deseo información del glamping")
    firma = calcular_firma(cuerpo, "secreto_meta_app_456")

    inicio = time.time()
    respuesta = cliente.post(
        "/webhook",
        content=cuerpo,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": firma,
        },
    )
    duracion = time.time() - inicio

    assert respuesta.status_code == 200
    assert duracion < 2.0, f"Respuesta demoró {duracion}s (debe ser < 2 s)"

    # Verificar que el evento quedó persistido en la base de datos
    evento = contenedor.canal.repositorio.obtener_evento(msg_id)
    assert evento is not None
    assert evento.mensaje_id == msg_id
    assert evento.conversacion_clave == remitente
    assert evento.estado in ("pendiente", "procesado")


# ¤pasillo-central
def test_post_webhook_firma_invalida_rechazo_401_sin_persistencia(
    cliente: TestClient,
    contenedor: Contenedor,
) -> None:
    """RF-GW-01 (b) e INV_FIRMA_WEBHOOK_META.

    Un POST con firma inválida responde 401 y no persiste ningún evento.
    """
    msg_id = f"wamid.{uuid4().hex}"
    remitente = "593991234567"
    cuerpo = payload_meta_mensaje(msg_id, remitente, "Mensaje alterado")
    firma_invalida = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    respuesta = cliente.post(
        "/webhook",
        content=cuerpo,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": firma_invalida,
        },
    )

    assert respuesta.status_code == 401

    # Verificar que no se persistió ningún evento
    evento = contenedor.canal.repositorio.obtener_evento(msg_id)
    assert evento is None


# ¤pasillo-central
def test_post_webhook_sin_cabecera_firma_rechazo_401(cliente: TestClient) -> None:
    """Verifica que un POST sin cabecera X-Hub-Signature-256 sea rechazado con 401."""
    cuerpo = payload_meta_mensaje("wamid.sin_firma", "593991234567", "Sin cabecera")
    respuesta = cliente.post(
        "/webhook",
        content=cuerpo,
        headers={"Content-Type": "application/json"},
    )
    assert respuesta.status_code == 401


# ¤pasillo-central
def test_reintento_meta_no_duplica_mensaje(
    cliente: TestClient,
    contenedor: Contenedor,
) -> None:
    """RF-GW-01 (d) y RF-GW-07: Un reintento de Meta con el mismo message_id responde 200 sin duplicar."""
    msg_id = f"wamid.{uuid4().hex}"
    remitente = "593991234567"
    cuerpo = payload_meta_mensaje(msg_id, remitente, "Mensaje que Meta reintentará")
    firma = calcular_firma(cuerpo, "secreto_meta_app_456")

    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": firma,
    }

    # Primer envío
    resp1 = cliente.post("/webhook", content=cuerpo, headers=headers)
    assert resp1.status_code == 200

    # Segundo envío (reintento idéntico de Meta)
    resp2 = cliente.post("/webhook", content=cuerpo, headers=headers)
    assert resp2.status_code == 200

    # Verificar que el evento persiste exactamente una vez
    evento = contenedor.canal.repositorio.obtener_evento(msg_id)
    assert evento is not None


# ¤pasillo-central
def test_get_raiz_web_publica_montada(cliente: TestClient) -> None:
    """Montaje de web_huespedes: GET / sirve el catálogo público de alojamientos en HTML."""
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "text/html" in respuesta.headers.get("content-type", "")
    assert "Glamping" in respuesta.text or "Imbabura" in respuesta.text or "Catálogo" in respuesta.text


# ¤pasillo-central
def test_get_salud_sigue_activo(cliente: TestClient) -> None:
    """Verifica que /health siga respondiendo 200 OK con el estado y entorno."""
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["estado"] == "ok"
    assert datos["entorno"] == "prueba"
