# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Firma y verificación criptográfica HMAC-SHA256 de webhooks y eventos CRM (RF-CRM-03, RNF-09)."""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping

from features.crm_conector.tipos import FirmaEventoInvalida

__all__ = [
    "calcular_firma",
    "generar_cuerpo_canonico",
    "validar_firma",
    "verificar_firma",
]


# ¤crm-conector
def generar_cuerpo_canonico(payload: Mapping[str, Any] | str | bytes) -> str:
    """Produce la representación JSON canónica: ordenado por clave, sin espacios superfluos, UTF-8."""
    if isinstance(payload, (str, bytes)):
        if isinstance(payload, bytes):
            texto = payload.decode("utf-8")
        else:
            texto = payload
        try:
            datos = json.loads(texto)
            return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            return texto
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ¤crm-conector
def calcular_firma(secreto: str, fecha_iso: str, payload: Mapping[str, Any] | str | bytes) -> str:
    """Calcula la firma HMAC-SHA256 sobre X-Glamping-Date + '.' + cuerpo_canonico."""
    cuerpo_canonico = generar_cuerpo_canonico(payload)
    mensaje = f"{fecha_iso}.{cuerpo_canonico}".encode("utf-8")
    return hmac.new(secreto.encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


# ¤crm-conector
def verificar_firma(secreto: str, fecha_iso: str, cuerpo: str | bytes, firma: str | None) -> bool:
    """Verifica en tiempo constante si la firma coincide con el HMAC-SHA256 esperado."""
    if not firma or not secreto:
        return False
    firma_limpia = firma.removeprefix("sha256=").strip()
    firma_esperada = calcular_firma(secreto, fecha_iso, cuerpo)
    return hmac.compare_digest(firma_esperada, firma_limpia)


# ¤crm-conector
def validar_firma(secreto: str, fecha_iso: str, cuerpo: str | bytes, firma: str | None) -> None:
    """Lanza FirmaEventoInvalida si la firma no coincide o es inválida."""
    if not verificar_firma(secreto, fecha_iso, cuerpo, firma):
        raise FirmaEventoInvalida("La firma HMAC-SHA256 no coincide o la cabecera de firma está ausente.")
