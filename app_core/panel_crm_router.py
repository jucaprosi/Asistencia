# ¤pasillo-central
# ¤¤solutions-architect
"""Montaje HTTP de las rutas de panel_operativo y crm_conector en el pasillo central (T-310).

Registra:
- Montaje de /panel/* (BFF y estáticos)
- Ruta POST /crm/eventos -> crm.recibir_evento -> despacho a receptores (agente.reanudar, panel)
"""
from __future__ import annotations

import importlib
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app_core.app_core_service import Contenedor
from features.crm_conector.crm_conector_service import (
    EventoCRM,
    FirmaEventoInvalida,
    WebhookRechazado,
)


# ¤pasillo-central
def registrar_receptores_crm(contenedor: Contenedor) -> None:
    """Enlaza los receptores de eventos entrantes del CRM con las salas agente y panel."""

    def _receptor_crm(evento: EventoCRM) -> None:
        if evento.tipo == "handoff_devuelto":
            conversacion_id = str(evento.datos.get("conversacion_id") or evento.referencia)
            if hasattr(contenedor.agente, "reanudar"):
                contenedor.agente.reanudar(conversacion_id)
            if hasattr(contenedor.panel, "_handoffs"):
                handoffs = getattr(contenedor.panel, "_handoffs", {})
                if conversacion_id in handoffs:
                    handoffs[conversacion_id]["estado"] = "devuelto"
                    handoffs[conversacion_id]["asignado_a"] = None
        elif evento.tipo == "incidencia_resuelta":
            incidencia_id = str(evento.datos.get("incidencia_id") or evento.referencia)
            if hasattr(contenedor.panel, "_incidencias"):
                incidencias = getattr(contenedor.panel, "_incidencias", {})
                if incidencia_id in incidencias:
                    incidencias[incidencia_id]["estado"] = "resuelta"

    if hasattr(contenedor.crm, "registrar_receptor"):
        contenedor.crm.registrar_receptor("*", _receptor_crm)


# ¤pasillo-central
def crear_router_crm(contenedor: Contenedor) -> APIRouter:
    """Crea el router FastAPI con la ruta POST /crm/eventos."""
    router = APIRouter()

    @router.post("/crm/eventos")
    async def recibir_evento_crm(request: Request) -> Response:
        cuerpo = await request.body()
        firma = (
            request.headers.get("x-crm-signature")
            or request.headers.get("x-signature")
            or request.headers.get("x-glamping-signature")
            or request.headers.get("x-hub-signature-256")
            or ""
        )
        try:
            evento = contenedor.crm.recibir_evento(cuerpo, firma=firma)
        except FirmaEventoInvalida as exc:
            raise HTTPException(status_code=401, detail=str(exc))
        except WebhookRechazado as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Error procesando evento CRM: {exc}")

        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "evento": evento.tipo,
                "referencia": evento.referencia,
            },
        )

    return router


# ¤pasillo-central
def montar_panel(app: FastAPI, contenedor: Contenedor) -> None:
    """Monta la aplicación del panel operativo con sus rutas BFF y archivos estáticos."""
    try:
        modulo_bff = importlib.import_module("features.panel_operativo.bff_internal")
        crear_router_bff = getattr(modulo_bff, "crear_router_bff")
        router = crear_router_bff(contenedor.panel)
        app.include_router(router)

        ruta_estaticos = getattr(modulo_bff, "RUTA_ESTATICOS", None)
        if ruta_estaticos and ruta_estaticos.is_dir():
            app.mount("/panel/estaticos", StaticFiles(directory=str(ruta_estaticos)), name="panel_estaticos")

        @app.get("/panel/manifest.webmanifest")
        @app.get("/panel/manifest.json")
        async def _servir_manifest() -> Response:
            if ruta_estaticos:
                p = ruta_estaticos / "manifest.webmanifest"
                if not p.is_file():
                    p = ruta_estaticos / "manifest.json"
                if p.is_file():
                    return FileResponse(p, media_type="application/manifest+json")
            return JSONResponse(status_code=404, content={"detail": "Not found"})

        @app.get("/panel/sw.js")
        async def _servir_sw() -> Response:
            if ruta_estaticos:
                p = ruta_estaticos / "sw.js"
                if p.is_file():
                    return FileResponse(
                        p,
                        media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/panel/"},
                    )
            return Response(content="// SW", status_code=200, media_type="application/javascript")

        @app.get("/panel", response_class=HTMLResponse)
        @app.get("/panel/", response_class=HTMLResponse)
        async def _servir_panel_index() -> Response:
            if ruta_estaticos:
                p = ruta_estaticos / "index.html"
                if p.is_file():
                    return HTMLResponse(content=p.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>Panel Operativo</h1>", status_code=200)

    except Exception as exc:
        if hasattr(contenedor.observabilidad, "log"):
            contenedor.observabilidad.log("ERROR", "error_montaje_panel", error=str(exc))


# ¤pasillo-central
def montar_panel_y_crm(app: FastAPI, contenedor: Contenedor) -> None:
    """Monta en la aplicación principal el panel operativo y los webhooks del CRM."""
    registrar_receptores_crm(contenedor)
    app.include_router(crear_router_crm(contenedor))
    montar_panel(app, contenedor)
