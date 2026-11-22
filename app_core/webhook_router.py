# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Rutas HTTP del webhook de Meta (WhatsApp Cloud API) para verificación y recepción (RF-GW-01, RF-GW-07)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, Response

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, FirmaInvalida

__all__ = ["crear_router_webhook"]


# ¤pasillo-central
def crear_router_webhook(canal: CanalWhatsappService | None = None) -> APIRouter:
    """Crea el router FastAPI para los endpoints GET y POST de /webhook."""
    router = APIRouter()

    def _resolver_canal(request: Request) -> CanalWhatsappService:
        if canal is not None:
            return canal
        contenedor = getattr(request.app.state, "contenedor", None)
        if contenedor is not None and hasattr(contenedor, "canal"):
            return contenedor.canal
        raise RuntimeError("No se encontró CanalWhatsappService en el contenedor de la aplicación.")

    @router.get("/webhook")
    async def verificar_webhook_meta(
        request: Request,
        hub_mode: str | None = Query(None, alias="hub.mode"),
        hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(None, alias="hub.challenge"),
    ) -> Response:
        """RF-GW-01 (a): Responde con hub.challenge si las credenciales de suscripción coinciden."""
        servicio_canal = _resolver_canal(request)

        modo = hub_mode or request.query_params.get("mode") or ""
        token = hub_verify_token or request.query_params.get("verify_token") or ""
        desafio = hub_challenge or request.query_params.get("challenge") or ""

        if not modo or not token or not desafio:
            return Response(content="Parámetros de verificación incompletos", status_code=400)

        resultado = servicio_canal.verificar_webhook(modo, token, desafio)
        if resultado is not None:
            return Response(content=resultado, media_type="text/plain", status_code=200)

        return Response(content="Verificación fallida", status_code=403)

    @router.post("/webhook")
    async def recibir_webhook_meta(
        request: Request,
        background_tasks: BackgroundTasks,
        x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    ) -> Response:
        """RF-GW-01 (b-d) e INV_FIRMA_WEBHOOK_META: Valida firma HMAC, persiste evento y procesa asíncronamente."""
        if not x_hub_signature_256:
            return Response(content="Cabecera X-Hub-Signature-256 ausente", status_code=401)

        servicio_canal = _resolver_canal(request)
        cuerpo = await request.body()

        try:
            servicio_canal.recibir(cuerpo, x_hub_signature_256)
        except FirmaInvalida:
            return Response(content="Firma inválida", status_code=401)
        except Exception as exc:
            if "firma" in str(exc).lower():
                return Response(content="Firma inválida", status_code=401)
            raise

        # Procesamiento asíncrono con cola (RF-GW-01 c, RF-GW-07)
        if hasattr(servicio_canal, "procesar_ingesta"):
            background_tasks.add_task(servicio_canal.procesar_ingesta)

        return Response(content="EVENT_RECEIVED", media_type="text/plain", status_code=200)

    return router
