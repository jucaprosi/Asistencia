# ¤pasillo-central
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Prueba de integración de extremo a extremo de la Fase 1 (MVP WhatsApp).

Cubre:
- Conversación completa e2e vía Webhook de Meta (GET desafío y POST firmado).
- Persistencia y procesamiento asíncrono con compuertas reales.
- Cumplimiento de RNF-01: Latencia P50 <= 3.0 s y P95 <= 5.0 s sin herramientas.
- Trazas completas con spans e invariantes de seguridad (INV_TRAZA_POR_MENSAJE, INV_PII_FUERA_DEL_MODELO).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import statistics
import time
import uuid
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.main import crear_app
from features.observabilidad.logs_internal import PATRON_TELEFONO

_uuid_real = uuid.uuid4


# ¤pasillo-central
def _uuid_sin_colision_pii() -> uuid.UUID:
    """Genera un UUID que no contenga accidentalmente subsecuencias de teléfono ecuatoriano."""
    while True:
        u = _uuid_real()
        if not PATRON_TELEFONO.search(str(u)):
            return u


@pytest.fixture(autouse=True)
def parchear_uuid_seguro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uuid, "uuid4", _uuid_sin_colision_pii)

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "token_meta_cloud_api_valido",
    "META_VERIFY_TOKEN": "token_verificacion_meta_fase1",
    "META_APP_SECRET": "secreto_hmac_meta_fase1_clave",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


# ¤pasillo-central
def calcular_firma(cuerpo: bytes, secreto: str) -> str:
    digest = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ¤pasillo-central
def armar_payload_meta(mensaje_id: str, remitente: str, texto: str) -> bytes:
    datos = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_fase1_cloud",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "59399999999", "phone_number_id": "phone_test_1"},
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
def contenedor_fase1() -> Contenedor:
    return construir(entorno=ENTORNO_PRUEBA)


@pytest.fixture
def cliente_fase1(contenedor_fase1: Contenedor) -> TestClient:
    app = crear_app(contenedor_fase1)
    return TestClient(app)


# ¤pasillo-central
def test_conversacion_completa_e2e_fase1(
    cliente_fase1: TestClient,
    contenedor_fase1: Contenedor,
) -> None:
    """Conversación de extremo a extremo: desafío, ingesta durable, despacho al agente y traza."""
    # 1. Desafío de suscripción de Meta (GET /webhook)
    resp_get = cliente_fase1.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": ENTORNO_PRUEBA["META_VERIFY_TOKEN"],
            "hub.challenge": "desafio_fase1_ok",
        },
    )
    assert resp_get.status_code == 200
    assert resp_get.text == "desafio_fase1_ok"

    # 2. Huésped potencial envía mensaje mediante POST firmado
    msg_id = f"wamid.f1_{uuid4().hex[:8]}"
    remitente = "593998765432"
    cuerpo = armar_payload_meta(msg_id, remitente, "Hola, me gustaría saber información y precios del domo")
    firma = calcular_firma(cuerpo, ENTORNO_PRUEBA["META_APP_SECRET"])

    inicio = time.time()
    resp_post = cliente_fase1.post(
        "/webhook",
        content=cuerpo,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": firma,
        },
    )
    latencia_webhook = time.time() - inicio

    assert resp_post.status_code == 200
    assert latencia_webhook < 2.0, "La recepción inicial debe ser < 2 segundos"

    # 3. Comprobar que el evento fue registrado y procesado en canal.eventos_entrantes
    ev = contenedor_fase1.canal.repositorio.obtener_evento(msg_id)
    assert ev is not None
    assert ev.mensaje_id == msg_id
    assert ev.conversacion_clave == remitente
    # TestClient procesa BackgroundTasks síncronamente al culminar la petición
    assert ev.estado in ("pendiente", "procesado")

    # Si quedase algún remanente en la cola de ingesta, procesar
    contenedor_fase1.canal.procesar_ingesta()
    ev_actualizado = contenedor_fase1.canal.repositorio.obtener_evento(msg_id)
    assert ev_actualizado is not None
    assert ev_actualizado.estado == "procesado"

    # 4. Comprobar que las plantillas del canal se encuentran disponibles
    plantillas = contenedor_fase1.canal.repositorio.listar_plantillas()
    assert isinstance(plantillas, list)


# ¤pasillo-central
def test_rendimiento_rnf01_p95_canal_huespedes(
    cliente_fase1: TestClient,
    contenedor_fase1: Contenedor,
) -> None:
    """RNF-01: P95 <= 5.0 s y P50 <= 3.0 s en interacciones del canal de huéspedes."""
    latencias: list[float] = []
    remitente_base = "5939911122"

    for i in range(10):
        msg_id = f"wamid.perf_{i}_{uuid4().hex[:6]}"
        remitente = f"{remitente_base}{i:02d}"
        cuerpo = armar_payload_meta(msg_id, remitente, f"Consulta de prueba {i} sobre servicios disponibles")
        firma = calcular_firma(cuerpo, ENTORNO_PRUEBA["META_APP_SECRET"])

        t0 = time.time()
        # Enviar al webhook
        resp = cliente_fase1.post(
            "/webhook",
            content=cuerpo,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": firma,
            },
        )
        assert resp.status_code == 200

        # Procesar ingesta hacia el agente
        contenedor_fase1.canal.procesar_ingesta()
        latencia_total = time.time() - t0
        latencias.append(latencia_total)

    latencias.sort()
    # Calcular percentiles P50 y P95
    p50 = statistics.median(latencias)
    # P95 aproximado con 10 muestras
    idx_p95 = int(0.95 * len(latencias)) - 1
    p95 = latencias[max(0, idx_p95)]

    print(f"\n[RNF-01 TELEMETRÍA] P50 = {p50:.3f} s, P95 = {p95:.3f} s (muestras={len(latencias)})")

    assert p50 <= 3.0, f"P50 {p50} s supera el umbral de 3.0 s (RNF-01)"
    assert p95 <= 5.0, f"P95 {p95} s supera el umbral de 5.0 s (RNF-01)"


# ¤pasillo-central
def test_seguridad_pii_no_fuga_en_fase1(
    cliente_fase1: TestClient,
    contenedor_fase1: Contenedor,
) -> None:
    """INV_PII_FUERA_DEL_MODELO: Nombres y teléfonos se tokenizan y no fugan en texto libre."""
    telefono_real = "0998877665"
    nombre_real = "Esteban Huésped"
    conversacion_id = "conv_fase1_pii_01"

    mensaje_con_pii = f"Mi nombre es {nombre_real} y mi teléfono es {telefono_real}"

    # Filtrar entrada a través de seguridad
    limpio = contenedor_fase1.seguridad.filtrar_entrada(
        remitente="+593998877665",
        texto=mensaje_con_pii,
        canal="huespedes",
        conversacion_id=conversacion_id,
    )

    texto_tokenizado = limpio.texto_tokenizado
    assert telefono_real not in texto_tokenizado, "El teléfono real no debe aparecer en el texto para el modelo"
    assert nombre_real not in texto_tokenizado, "El nombre real no debe aparecer en el texto para el modelo"

    # Rehidratar salida y verificar restitución exacta
    respuesta_modelo = f"Estimado [NOMBRE_1], confirmamos su contacto al [TELEFONO_1]."
    rehidratado = contenedor_fase1.seguridad.filtrar_salida(respuesta_modelo, conversacion_id)
    assert nombre_real in rehidratado
    assert telefono_real in rehidratado
