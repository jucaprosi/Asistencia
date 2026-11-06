# ¤web-huespedes
# ¤¤frontend-developer
"""Rutas web públicas para huéspedes (FastAPI + Jinja2).

Rutas de Ola 1:
- GET /: catálogo público sin datos de PMS.
- GET /propiedades/{id}: ficha por propiedad con fotos, zona, capacidad y comodidades.
- POST /contacto (y GET /contacto): paso a WhatsApp con código de contexto sin PII.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, FastAPI, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape

from features.web_huespedes.tipos import Busqueda, FichaPropiedad
from features.web_huespedes.web_huespedes_service import ErrorWebHuespedes, WebHuespedesService

RUTA_TEMPLATES = Path(__file__).resolve().parent / "templates"


# ¤web-huespedes
def _crear_entorno_jinja() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(RUTA_TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
    )


# ¤web-huespedes
def _extraer_ip_cliente(request: Request) -> str:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# ¤web-huespedes
def _quiere_json(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "application/json" in accept and "text/html" not in accept


# ¤web-huespedes
def crear_router(servicio: WebHuespedesService) -> APIRouter:
    """Crea el router FastAPI con las rutas públicas de la sala web_huespedes."""
    router = APIRouter()
    env = _crear_entorno_jinja()

    plantilla_catalogo = env.get_template("catalogo.html")
    plantilla_ficha = env.get_template("ficha.html")
    plantilla_error = env.get_template("error.html")
    plantilla_buscar = env.get_template("buscar.html")
    plantilla_comparar = env.get_template("comparar.html")

    def _aplicar_limite_ip(request: Request) -> None:
        ip = _extraer_ip_cliente(request)
        permitido, conteo, _ = servicio.verificar_limite_ip(ip)
        if not permitido:
            mensaje = "Has superado el límite de consultas por minuto. Por favor, espera un momento antes de continuar."
            cabeceras = {"Cache-Control": "no-store"}
            if _quiere_json(request):
                raise HTTPException(status_code=429, detail=mensaje, headers=cabeceras)
            contenido = plantilla_error.render(mensaje_usuario=mensaje)
            raise HTTPException(status_code=429, detail=contenido, headers=cabeceras)

    @router.get("/", response_class=HTMLResponse)
    async def ver_catalogo(request: Request) -> Response:
        try:
            _aplicar_limite_ip(request)
        except HTTPException as exc:
            if exc.status_code == 429 and not _quiere_json(request):
                return HTMLResponse(content=exc.detail, status_code=429)
            raise

        propiedades = servicio.catalogo()
        contenido = plantilla_catalogo.render(propiedades=propiedades)
        return HTMLResponse(content=contenido)

    @router.get("/propiedades/{propiedad_id}", response_class=HTMLResponse)
    async def ver_ficha(request: Request, propiedad_id: str) -> Response:
        try:
            _aplicar_limite_ip(request)
        except HTTPException as exc:
            if exc.status_code == 429 and not _quiere_json(request):
                return HTMLResponse(content=exc.detail, status_code=429)
            raise

        try:
            ficha = servicio.ficha(propiedad_id)
        except ErrorWebHuespedes as err:
            contenido_err = plantilla_error.render(mensaje_usuario=err.mensaje_usuario)
            return HTMLResponse(content=contenido_err, status_code=404)

        contenido = plantilla_ficha.render(ficha=ficha)
        return HTMLResponse(content=contenido)

    @router.post("/contacto")
    async def iniciar_contacto_post(
        request: Request,
        propiedad_id: str = Form(None),
        desde: str | None = Form(None),
        hasta: str | None = Form(None),
        huespedes: int | None = Form(None),
    ) -> Response:
        try:
            _aplicar_limite_ip(request)
        except HTTPException as exc:
            if exc.status_code == 429 and not _quiere_json(request):
                return HTMLResponse(content=exc.detail, status_code=429)
            raise

        # Soporte para cuerpo JSON si no viene de formulario
        if not propiedad_id and request.headers.get("content-type", "").startswith("application/json"):
            datos = await request.json()
            propiedad_id = datos.get("propiedad_id")
            desde = datos.get("desde")
            hasta = datos.get("hasta")
            huespedes = datos.get("huespedes")

        if not propiedad_id:
            mensaje = "Debe indicar el identificador de la propiedad a consultar."
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje})
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje))

        busqueda: Busqueda | None = None
        d_val = date.fromisoformat(desde) if desde else None
        h_val = date.fromisoformat(hasta) if hasta else None
        if d_val and h_val and huespedes:
            busqueda = Busqueda(desde=d_val, hasta=h_val, huespedes=int(huespedes))

        try:
            enlace = servicio.crear_enlace_contacto(propiedad_id, busqueda)
        except (ErrorWebHuespedes, ValueError) as exc:
            mensaje_usuario = getattr(exc, "mensaje_usuario", str(exc))
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje_usuario})
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje_usuario))

        if _quiere_json(request):
            return JSONResponse(status_code=200, content={"url": enlace})

        return RedirectResponse(url=enlace, status_code=303)

    @router.get("/contacto")
    async def iniciar_contacto_get(
        request: Request,
        propiedad_id: str = Query(...),
        desde: str | None = Query(None),
        hasta: str | None = Query(None),
        huespedes: int | None = Query(None),
    ) -> Response:
        try:
            _aplicar_limite_ip(request)
        except HTTPException as exc:
            if exc.status_code == 429 and not _quiere_json(request):
                return HTMLResponse(content=exc.detail, status_code=429)
            raise

        busqueda: Busqueda | None = None
        d_val = date.fromisoformat(desde) if desde else None
        h_val = date.fromisoformat(hasta) if hasta else None
        if d_val and h_val and huespedes:
            busqueda = Busqueda(desde=d_val, hasta=h_val, huespedes=int(huespedes))

        try:
            enlace = servicio.crear_enlace_contacto(propiedad_id, busqueda)
        except (ErrorWebHuespedes, ValueError) as exc:
            mensaje_usuario = getattr(exc, "mensaje_usuario", str(exc))
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje_usuario})
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje_usuario))

        if _quiere_json(request):
            return JSONResponse(status_code=200, content={"url": enlace})

        return RedirectResponse(url=enlace, status_code=303)

    @router.get("/buscar")
    async def buscar_alojamientos(
        request: Request,
        desde: str | None = Query(None),
        hasta: str | None = Query(None),
        huespedes: int | None = Query(None),
        tipo: str | None = Query(None),
        zona: str | None = Query(None),
    ) -> Response:
        try:
            _aplicar_limite_ip(request)
        except HTTPException as exc:
            if exc.status_code == 429 and not _quiere_json(request):
                return HTMLResponse(content=exc.detail, status_code=429, headers={"Cache-Control": "no-store"})
            raise

        cabeceras = {"Cache-Control": "no-store"}

        if not desde or not hasta or not huespedes:
            if _quiere_json(request):
                return JSONResponse(
                    status_code=400,
                    content={"error": "Debe especificar 'desde', 'hasta' y 'huespedes'."},
                    headers=cabeceras,
                )
            contenido = plantilla_buscar.render(
                busqueda=None,
                opciones=(),
                propiedades_sin_precio=(),
                pms_disponible=True,
                error_busqueda=None,
            )
            return HTMLResponse(content=contenido, headers=cabeceras)

        try:
            d_val = date.fromisoformat(desde)
            h_val = date.fromisoformat(hasta)
            h_num = int(huespedes)
            busqueda = Busqueda(desde=d_val, hasta=h_val, huespedes=h_num, tipo=tipo, zona=zona)
        except (ValueError, TypeError):
            mensaje = "Las fechas o el número de huéspedes ingresados no son válidos."
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje}, headers=cabeceras)
            contenido = plantilla_buscar.render(
                busqueda=None,
                opciones=(),
                propiedades_sin_precio=(),
                pms_disponible=True,
                error_busqueda=mensaje,
            )
            return HTMLResponse(content=contenido, status_code=400, headers=cabeceras)

        try:
            opciones = servicio.buscar(busqueda)
            pms_ok = True
            candidatas_sin_precio: tuple[FichaPropiedad, ...] = ()
        except ErrorWebHuespedes as err:
            if err.codigo in ("PMS_NO_DISPONIBLE", "PMS_ERROR"):
                pms_ok = False
                opciones = ()
                candidatas_sin_precio = servicio.filtrar_catalogo(busqueda)
            else:
                if _quiere_json(request):
                    return JSONResponse(status_code=400, content={"error": err.mensaje_usuario}, headers=cabeceras)
                contenido = plantilla_buscar.render(
                    busqueda=busqueda,
                    opciones=(),
                    propiedades_sin_precio=(),
                    pms_disponible=True,
                    error_busqueda=err.mensaje_usuario,
                )
                return HTMLResponse(content=contenido, status_code=400, headers=cabeceras)

        if _quiere_json(request):
            datos_opciones = [
                {
                    "propiedad_id": op.ficha.propiedad_id,
                    "nombre": op.ficha.nombre,
                    "zona": op.ficha.zona,
                    "capacidad": op.ficha.capacidad,
                    "unidad_id": op.unidad_id,
                    "total": float(op.total),
                    "moneda": op.moneda,
                }
                for op in opciones
            ]
            return JSONResponse(
                content={
                    "pms_disponible": pms_ok,
                    "opciones": datos_opciones,
                    "propiedades_sin_precio": [
                        {
                            "propiedad_id": f.propiedad_id,
                            "nombre": f.nombre,
                            "zona": f.zona,
                            "capacidad": f.capacidad,
                        }
                        for f in candidatas_sin_precio
                    ],
                },
                headers=cabeceras,
            )

        contenido = plantilla_buscar.render(
            busqueda=busqueda,
            opciones=opciones,
            propiedades_sin_precio=candidatas_sin_precio,
            pms_disponible=pms_ok,
            error_busqueda=None,
        )
        return HTMLResponse(content=contenido, headers=cabeceras)

    @router.get("/comparar")
    async def comparar_alojamientos(
        request: Request,
        ids: str | None = Query(None),
        desde: str | None = Query(None),
        hasta: str | None = Query(None),
        huespedes: int | None = Query(None),
    ) -> Response:
        try:
            _aplicar_limite_ip(request)
        except HTTPException as exc:
            if exc.status_code == 429 and not _quiere_json(request):
                return HTMLResponse(content=exc.detail, status_code=429, headers={"Cache-Control": "no-store"})
            raise

        cabeceras = {"Cache-Control": "no-store"}
        lista_ids = tuple(i.strip() for i in (ids.split(",") if ids else ()) if i.strip())

        if not lista_ids:
            mensaje = "Debe indicar al menos una propiedad para comparar."
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje}, headers=cabeceras)
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje), headers=cabeceras)

        if len(lista_ids) > 3:
            mensaje = "No es posible comparar más de 3 propiedades simultáneamente."
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje}, headers=cabeceras)
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje), headers=cabeceras)

        if not desde or not hasta or not huespedes:
            mensaje = "Debe especificar 'desde', 'hasta' y 'huespedes' para la comparación."
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje}, headers=cabeceras)
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje), headers=cabeceras)

        try:
            d_val = date.fromisoformat(desde)
            h_val = date.fromisoformat(hasta)
            h_num = int(huespedes)
            busqueda = Busqueda(desde=d_val, hasta=h_val, huespedes=h_num)
        except (ValueError, TypeError):
            mensaje = "Las fechas o el número de huéspedes ingresados no son válidos."
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje}, headers=cabeceras)
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje), headers=cabeceras)

        try:
            opciones = servicio.comparar(lista_ids, busqueda)
        except ErrorWebHuespedes as err:
            mensaje = err.mensaje_usuario
            if _quiere_json(request):
                return JSONResponse(status_code=400, content={"error": mensaje}, headers=cabeceras)
            return HTMLResponse(status_code=400, content=plantilla_error.render(mensaje_usuario=mensaje), headers=cabeceras)

        if _quiere_json(request):
            datos_opciones = [
                {
                    "propiedad_id": op.ficha.propiedad_id,
                    "nombre": op.ficha.nombre,
                    "zona": op.ficha.zona,
                    "capacidad": op.ficha.capacidad,
                    "comodidades": list(op.ficha.comodidades),
                    "unidad_id": op.unidad_id,
                    "total": float(op.total),
                    "moneda": op.moneda,
                }
                for op in opciones
            ]
            return JSONResponse(content={"opciones": datos_opciones}, headers=cabeceras)

        contenido = plantilla_comparar.render(
            busqueda=busqueda,
            opciones=opciones,
        )
        return HTMLResponse(content=contenido, headers=cabeceras)

    return router


# ¤web-huespedes
def crear_app_web(servicio: WebHuespedesService) -> FastAPI:
    """Crea la aplicación web FastAPI para pruebas y montaje independiente."""
    app = FastAPI(title="Web Pública Glamping Imbabura", docs_url=None, redoc_url=None)
    router = crear_router(servicio)
    app.include_router(router)
    return app
