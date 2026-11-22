# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Adaptador HTTP configurable con firma HMAC-SHA256 y soporte para fixtures simulados (RF-CRM-03)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from features.crm_conector.firma_internal import calcular_firma, generar_cuerpo_canonico
from features.crm_conector.tipos import (
    ContactoDuplicado,
    CRMNoDisponible,
    LimiteDeTasa,
    WebhookRechazado,
)

__all__ = ["AdaptadorHttpCRM"]

TransporteHttp = Callable[[str, str, dict[str, str], bytes], tuple[int, str]]


# ¤crm-conector
class AdaptadorHttpCRM:
    """Cliente HTTP para publicar eventos firmados al CRM con transporte configurable."""

    def __init__(
        self,
        url: str = "",
        secreto_hmac: str = "",
        cabecera_firma: str = "X-Glamping-Signature",
        transporte: TransporteHttp | None = None,
    ) -> None:
        self.url = url
        self.secreto_hmac = secreto_hmac
        self.cabecera_firma = cabecera_firma
        self.transporte = transporte or self._transporte_defecto

    # ¤crm-conector
    def _transporte_defecto(
        self,
        metodo: str,
        url: str,
        cabeceras: dict[str, str],
        cuerpo: bytes,
    ) -> tuple[int, str]:
        """Transporte por defecto basado en urllib o respuesta simulada si no hay URL activa."""
        if not url:
            # En entorno local/offline sin URL externa configurada, responde exitoso
            return 200, json.dumps({"status": "ok", "mensaje": "Simulated local webhook acceptance"})

        import urllib.request
        import urllib.error

        req = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                codigo = resp.getcode()
                texto = resp.read().decode("utf-8", errors="replace")
                return codigo, texto
        except urllib.error.HTTPError as exc:
            codigo = exc.code
            texto = exc.read().decode("utf-8", errors="replace")
            return codigo, texto
        except Exception as exc:
            raise CRMNoDisponible(f"Fallo de conexión HTTP con CRM: {exc}") from exc

    # ¤crm-conector
    def enviar_publicacion(
        self,
        payload: Mapping[str, Any],
        url: str | None = None,
        fecha_iso: str | None = None,
    ) -> tuple[int, str]:
        """Envía un payload firmado por HMAC-SHA256 con cabeceras de fecha y firma requeridas."""
        destino = url or self.url
        fecha = fecha_iso or datetime.now(timezone.utc).isoformat()
        cuerpo_canonico = generar_cuerpo_canonico(payload)
        cuerpo_bytes = cuerpo_canonico.encode("utf-8")

        firma = calcular_firma(self.secreto_hmac, fecha, cuerpo_canonico)

        cabeceras = {
            "Content-Type": "application/json",
            "X-Glamping-Date": fecha,
            self.cabecera_firma: firma,
        }

        codigo, respuesta = self.transporte("POST", destino, cabeceras, cuerpo_bytes)

        if codigo == 429:
            raise LimiteDeTasa(f"CRM devolvió límite de tasa (HTTP 429): {respuesta}")
        if codigo in {400, 422}:
            raise WebhookRechazado(f"CRM rechazó el webhook (HTTP {codigo}): {respuesta}")
        if codigo == 409:
            raise ContactoDuplicado(f"CRM reportó duplicado (HTTP 409): {respuesta}")
        if codigo >= 500:
            raise CRMNoDisponible(f"CRM no disponible (HTTP {codigo}): {respuesta}")

        return codigo, respuesta
