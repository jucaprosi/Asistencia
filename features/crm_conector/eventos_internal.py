# ¤crm-conector
# ¤¤integration-engineer
"""Procesamiento y verificación de eventos entrantes firmados desde el CRM (RF-CRM-03)."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from features.crm_conector.firma_internal import generar_cuerpo_canonico, verificar_firma
from features.crm_conector.tipos import EventoCRM, FirmaEventoInvalida

__all__ = ["procesar_evento_entrante", "verificar_firma_evento"]


# ¤crm-conector
def verificar_firma_evento(cuerpo: bytes, firma: str | None, secreto: str, fecha_iso: str | None = None) -> bool:
    """Verifica la firma HMAC-SHA256 del evento entrante con o sin cabecera de fecha."""
    if not firma or not secreto:
        return False

    firma_limpia = firma.removeprefix("sha256=").strip()

    # Opción A: HMAC sobre fecha_iso + '.' + cuerpo_canonico
    if fecha_iso and verificar_firma(secreto, fecha_iso, cuerpo, firma_limpia):
        return True

    # Opción B: HMAC directo sobre el cuerpo canónico
    cuerpo_canonico = generar_cuerpo_canonico(cuerpo).encode("utf-8")
    esperada_canonico = hmac.new(secreto.encode("utf-8"), cuerpo_canonico, hashlib.sha256).hexdigest()
    if hmac.compare_digest(esperada_canonico, firma_limpia):
        return True

    # Opción C: HMAC directo sobre los bytes crudos (webhooks externos)
    esperada_directa = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada_directa, firma_limpia)


# ¤crm-conector
def procesar_evento_entrante(
    cuerpo: bytes,
    firma: str | None,
    secreto: str,
    conexion: sqlite3.Connection,
    fecha_iso: str | None = None,
    observabilidad: Any = None,
) -> EventoCRM:
    """Valida la firma HMAC del evento entrante y lo persiste en crm.eventos."""
    if not verificar_firma_evento(cuerpo, firma, secreto, fecha_iso):
        raise FirmaEventoInvalida("Firma HMAC-SHA256 del evento CRM inválida o ausente.")

    try:
        payload = json.loads(cuerpo.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Payload de evento JSON inválido: {exc}") from exc

    evento_id = str(payload.get("evento_id") or uuid4())
    tipo = str(payload.get("tipo", "mensaje_gestor"))
    referencia = str(payload.get("referencia", payload.get("id", "")))
    actor = str(payload.get("actor", "crm"))
    datos = payload.get("datos", payload)
    ahora_dt = datetime.now(timezone.utc)
    ahora_iso = ahora_dt.isoformat()

    datos_json = json.dumps(datos, ensure_ascii=False)

    with conexion:
        conexion.execute(
            """
            INSERT OR REPLACE INTO crm.eventos (
                evento_id, tipo, referencia, datos_json, recibido_en, procesado_en
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (evento_id, tipo, referencia, datos_json, ahora_iso, ahora_iso),
        )

    if observabilidad and hasattr(observabilidad, "log"):
        observabilidad.log(
            "INFO",
            "EVENTO_CRM_RECIBIDO",
            evento_id=evento_id,
            tipo=tipo,
            referencia=referencia,
        )

    return EventoCRM(
        tipo=tipo,  # type: ignore[arg-type]
        referencia=referencia,
        actor=actor,
        datos=datos,
        recibido_en=ahora_dt,
    )
