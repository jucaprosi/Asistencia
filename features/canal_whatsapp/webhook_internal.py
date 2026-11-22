# ¤canal-whatsapp
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Manejo interno del webhook de Meta (verificación GET, firma HMAC, deserialización y parsing)."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from features.canal_whatsapp.tipos import (
    Canal, FirmaInvalida, MensajeEntrante, TipoContenido,
)


# ¤canal-whatsapp
def validar_firma_webhook(cuerpo: bytes, firma_sha256: str | None, secreto_app: str) -> None:
    """INV_FIRMA_WEBHOOK_META: Comparación en tiempo constante sobre bytes crudos."""
    if not firma_sha256 or not secreto_app:
        raise FirmaInvalida("Firma ausente o secreto de aplicación no configurado")

    firma_limpia = firma_sha256.removeprefix("sha256=").strip()
    firma_calculada = hmac.new(
        secreto_app.encode("utf-8"),
        cuerpo,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(firma_calculada, firma_limpia):
        raise FirmaInvalida("La firma calculada no coincide con X-Hub-Signature-256")


# ¤canal-whatsapp
def verificar_desafio(modo: str, token: str, desafio: str, verify_token: str) -> str | None:
    """Responde al desafío de verificación GET de Meta si el token coincide."""
    if modo == "subscribe" and token == verify_token:
        return desafio
    return None


# ¤canal-whatsapp
def parsear_payload_webhook(cuerpo: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extrae las listas de mensajes y de status updates del JSON crudo de Meta."""
    try:
        datos = json.loads(cuerpo.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Payload JSON inválido: {exc}") from exc

    mensajes: list[dict[str, Any]] = []
    estados: list[dict[str, Any]] = []

    for entry in datos.get("entry", []):
        for change in entry.get("changes", []):
            valor = change.get("value", {})
            if "messages" in valor:
                mensajes.extend(valor["messages"])
            if "statuses" in valor:
                estados.extend(valor["statuses"])

    return mensajes, estados


# ¤canal-whatsapp
def convertir_mensaje_meta(raw: dict[str, Any], canal: Canal = Canal.HUESPEDES) -> MensajeEntrante:
    """Convierte un mensaje crudo de Meta Cloud API a MensajeEntrante tipado."""
    mensaje_id = raw.get("id", "")
    remitente = raw.get("from", "")
    ts_str = raw.get("timestamp")
    if ts_str:
        try:
            recibido_en = datetime.fromtimestamp(int(ts_str), tz=timezone.utc)
        except (ValueError, TypeError):
            recibido_en = datetime.now(timezone.utc)
    else:
        recibido_en = datetime.now(timezone.utc)

    tipo_raw = raw.get("type", "desconocido")
    tipo = TipoContenido.DESCONOCIDO
    texto: str | None = None
    medio_ref: str | None = None
    ubicacion: tuple[float, float] | None = None

    if tipo_raw == "text":
        tipo = TipoContenido.TEXTO
        texto = raw.get("text", {}).get("body")
    elif tipo_raw == "interactive":
        interactive = raw.get("interactive", {})
        subtipo = interactive.get("type")
        if subtipo == "button_reply":
            tipo = TipoContenido.BOTON
            texto = interactive.get("button_reply", {}).get("title") or interactive.get("button_reply", {}).get("id")
        elif subtipo == "list_reply":
            tipo = TipoContenido.LISTA
            texto = interactive.get("list_reply", {}).get("title") or interactive.get("list_reply", {}).get("id")
    elif tipo_raw == "button":
        tipo = TipoContenido.BOTON
        texto = raw.get("button", {}).get("text")
    elif tipo_raw == "image":
        tipo = TipoContenido.IMAGEN
        medio_ref = raw.get("image", {}).get("id")
        texto = raw.get("image", {}).get("caption")
    elif tipo_raw == "audio":
        tipo = TipoContenido.AUDIO
        medio_ref = raw.get("audio", {}).get("id")
    elif tipo_raw == "document":
        tipo = TipoContenido.DOCUMENTO
        medio_ref = raw.get("document", {}).get("id")
        texto = raw.get("document", {}).get("filename")
    elif tipo_raw == "location":
        tipo = TipoContenido.UBICACION
        loc = raw.get("location", {})
        if "latitude" in loc and "longitude" in loc:
            ubicacion = (float(loc["latitude"]), float(loc["longitude"]))

    contexto = raw.get("context", {})
    contexto_respuesta_a = contexto.get("id")

    return MensajeEntrante(
        mensaje_id=mensaje_id,
        remitente=remitente,
        canal=canal,
        tipo=tipo,
        texto=texto,
        medio_ref=medio_ref,
        ubicacion=ubicacion,
        recibido_en=recibido_en,
        contexto_respuesta_a=contexto_respuesta_a,
    )
