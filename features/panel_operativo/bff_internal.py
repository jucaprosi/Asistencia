# ¤panel-operativo
# ¤¤frontend-developer
"""BFF interno del panel operativo (/panel/api/*).

Rutas de Ola 2: sesión, handoffs por zona e incidencias.
Aplica autorización por endpoint (INV_PANEL_POR_ROL), idempotencia (INV_ACCION_IDEMPOTENTE)
y no contiene lógica de negocio (INV_PANEL_SIN_LOGICA).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from fastapi import APIRouter, Cookie, FastAPI, Header, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from features.panel_operativo.panel_operativo_service import ErrorPanel, PanelOperativoService
from features.panel_operativo.sesiones_internal import ErrorSesion
from features.panel_operativo.tipos import Sesion

RUTA_ESTATICOS = Path(__file__).resolve().parent / "estaticos"


# ¤panel-operativo
def crear_router_bff(servicio: PanelOperativoService) -> APIRouter:
    """Crea el router FastAPI con los endpoints de la API del panel operativo."""
    router = APIRouter(prefix="/panel/api")

    def _obtener_sesion_desde_request(request: Request) -> Sesion:
        token = request.cookies.get("panel_session")
        if not token:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:].strip()
        if not token:
            raise HTTPException(status_code=401, detail={"mensaje_usuario": "Se requiere iniciar sesión."})
        try:
            return servicio.validar_sesion(token)
        except ErrorSesion as exc:
            status = 401
            if exc.codigo == "sesion_expirada":
                status = 401
            raise HTTPException(status_code=status, detail={"mensaje_usuario": exc.mensaje_usuario})

    def _verificar_csrf(request: Request, sesion: Sesion) -> None:
        token_csrf = request.headers.get("x-csrf-token")
        if not token_csrf or token_csrf != sesion.csrf:
            raise HTTPException(
                status_code=403,
                detail={"mensaje_usuario": "Token CSRF inválido o faltante."},
            )

    def _obtener_idempotencia(request: Request) -> str | None:
        return request.headers.get("idempotency-key")

    def _manejar_idempotencia(request: Request, usuario_id: str) -> tuple[str | None, Response | None]:
        key = _obtener_idempotencia(request)
        if key:
            previa = servicio._persistencia.obtener_accion_idempotente(usuario_id, key)
            if previa is not None:
                return key, JSONResponse(content=previa, headers={"Cache-Control": "no-store", "Idempotency-Replay": "true"})
        return key, None

    def _guardar_idempotencia(usuario_id: str, key: str | None, accion: str, resultado: Any) -> None:
        if key:
            try:
                servicio._persistencia.registrar_accion_idempotente(
                    usuario_id, key, accion, jsonable_encoder(resultado), datetime.now(timezone.utc)
                )
            except Exception:
                pass

    # Sesión
    @router.post("/sesion/codigo")
    async def solicitar_codigo_endpoint(request: Request) -> Response:
        datos = await request.json()
        correo = datos.get("correo", "")
        if not correo:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "Debe proporcionar un correo electrónico."},
                headers={"Cache-Control": "no-store"},
            )
        resp = servicio.solicitar_codigo(correo)
        return JSONResponse(content=resp, headers={"Cache-Control": "no-store"})

    @router.post("/sesion")
    async def iniciar_sesion_endpoint(request: Request) -> Response:
        datos = await request.json()
        correo = datos.get("correo", "")
        codigo = datos.get("codigo", "")
        if not correo or not codigo:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "Correo y código son requeridos."},
                headers={"Cache-Control": "no-store"},
            )
        try:
            sesion, cookie_token = servicio.iniciar_sesion(correo, codigo)
        except ErrorSesion as exc:
            return JSONResponse(
                status_code=401,
                content={"mensaje_usuario": exc.mensaje_usuario},
                headers={"Cache-Control": "no-store"},
            )

        resp = JSONResponse(
            content={
                "usuario_id": sesion.usuario_id,
                "rol": sesion.rol,
                "zonas": list(sesion.zonas),
                "csrf": sesion.csrf,
            },
            headers={"Cache-Control": "no-store"},
        )
        es_segura = bool(servicio._config.get("sesion", {}).get("cookie_segura", True)) and (request.url.scheme == "https")
        resp.set_cookie(
            key="panel_session",
            value=cookie_token,
            max_age=12 * 3600,
            httponly=True,
            secure=es_segura,
            samesite="strict",
        )
        return resp

    @router.delete("/sesion")
    async def cerrar_sesion_endpoint(request: Request) -> Response:
        token = request.cookies.get("panel_session")
        if not token:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer "):
                token = auth[7:].strip()
        if token:
            try:
                sesion = servicio.validar_sesion(token)
                _verificar_csrf(request, sesion)
                servicio.cerrar_sesion(sesion, token)
            except (HTTPException, ErrorSesion):
                pass
        resp = JSONResponse(content={"cerrada": True}, headers={"Cache-Control": "no-store"})
        resp.delete_cookie("panel_session")
        return resp

    @router.get("/sesion")
    async def obtener_sesion_activa(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        return JSONResponse(
            content={
                "usuario_id": sesion.usuario_id,
                "rol": sesion.rol,
                "zonas": list(sesion.zonas),
                "csrf": sesion.csrf,
            },
            headers={"Cache-Control": "no-store"},
        )

    # Dispositivos y Web Push (RF-PAN-11, RF-PAN-12)
    @router.get("/dispositivos/vapid-public-key")
    async def obtener_vapid_key_endpoint() -> Response:
        return JSONResponse(
            content={"public_key": servicio.obtener_vapid_public_key()},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/dispositivos")
    async def listar_dispositivos_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        disps = servicio.dispositivos_usuario(sesion)
        return JSONResponse(
            content={"dispositivos": jsonable_encoder(list(disps))},
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/dispositivos/suscribir")
    async def suscribir_dispositivo_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa

        body = await request.json()
        endpoint = str(body.get("endpoint", "")).strip()
        keys = body.get("keys", {}) if isinstance(body.get("keys"), dict) else {}
        p256dh = str(keys.get("p256dh") or body.get("clave_p256dh", "")).strip()
        auth = str(keys.get("auth") or body.get("clave_auth", "")).strip()

        try:
            res = servicio.suscribir_dispositivo(sesion, endpoint, p256dh, auth)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "suscribir_dispositivo", res)
            return JSONResponse(content=jsonable_encoder(res), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.delete("/dispositivos")
    async def revocar_dispositivo_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa

        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        endpoint = str(body.get("endpoint", "")).strip()
        if not endpoint:
            endpoint = request.query_params.get("endpoint", "")
        revocado = servicio.revocar_dispositivo(sesion, endpoint)
        res = {"ok": True, "revocado": revocado}
        _guardar_idempotencia(sesion.usuario_id, idemp_key, "revocar_dispositivo", res)
        return JSONResponse(content=res, headers={"Cache-Control": "no-store"})

    # Inicio por rol (P-02)
    @router.get("/inicio")
    async def inicio_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        datos_inicio: dict[str, Any] = {"rol": sesion.rol, "usuario_id": sesion.usuario_id}
        if sesion.rol == "gestor":
            h_pendientes = len(servicio.handoffs(sesion))
            inc_pendientes = len(servicio.incidencias(sesion))
            datos_inicio["tarjetas"] = [
                {"titulo": "Conversaciones esperando en tu zona", "valor": h_pendientes, "accion": "/handoffs"},
                {"titulo": "Incidencias abiertas en tu zona", "valor": inc_pendientes, "accion": "/incidencias"},
            ]
        elif sesion.rol == "lider":
            datos_inicio["tarjetas"] = [
                {"titulo": "Ventas por validar", "valor": 0, "accion": "/ventas"},
                {"titulo": "Comisiones del período", "valor": "USD 0,00", "accion": "/comisiones"},
            ]
        else:
            datos_inicio["tarjetas"] = [
                {"titulo": "Salud del sistema", "valor": "Optima", "accion": "/salud"},
                {"titulo": "Usuarios activos", "valor": 3, "accion": "/usuarios"},
            ]
        return JSONResponse(content=datos_inicio, headers={"Cache-Control": "no-store"})

    # Handoffs (RF-PAN-07, US-09, US-10)
    @router.get("/handoffs")
    async def listar_handoffs(request: Request, zona: str | None = None) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            lista = servicio.handoffs(sesion, zona_filtro=zona)
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

        items = [
            {
                "conversacion_id": h.conversacion_id,
                "propiedad": h.propiedad,
                "zona_id": h.zona_id,
                "motivo": h.motivo,
                "resumen": h.resumen,
                "esperando_desde": h.esperando_desde.isoformat(),
                "asignado_a": h.asignado_a,
            }
            for h in lista
        ]
        return JSONResponse(content=items, headers={"Cache-Control": "no-store"})

    @router.get("/handoffs/{conversacion_id}")
    async def detalle_conversacion_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            detalle = servicio.detalle_conversacion(sesion, conversacion_id)
            return JSONResponse(content=dict(detalle), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "handoff_no_encontrado":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/handoffs/{conversacion_id}/tomar")
    async def tomar_handoff_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        try:
            servicio.tomar_handoff(sesion, conversacion_id)
            resultado = {"ok": True, "conversacion_id": conversacion_id, "estado": "tomado"}
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "tomar_handoff", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/handoffs/{conversacion_id}/responder")
    async def responder_handoff_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        datos = await request.json()
        texto = datos.get("texto", "").strip()
        if not texto:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "El texto del mensaje no puede estar vacío."},
                headers={"Cache-Control": "no-store"},
            )

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        try:
            servicio.responder(sesion, conversacion_id, texto)
            resultado = {"ok": True, "conversacion_id": conversacion_id, "mensaje_enviado": True}
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "responder_handoff", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "fuera_de_ventana_24h":
                return JSONResponse(
                    status_code=409,
                    content={"mensaje_usuario": exc.mensaje_usuario, "fuera_de_ventana": True},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/handoffs/{conversacion_id}/devolver")
    async def devolver_handoff_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        try:
            servicio.devolver_al_asistente(sesion, conversacion_id)
            resultado = {"ok": True, "conversacion_id": conversacion_id, "estado": "devuelto"}
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "devolver_handoff", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ¤panel-operativo
    # Inbox Completo de Huéspedes (TASK-008 / T-701 / ADR-0010)
    @router.get("/conversaciones")
    @router.get("/api/conversaciones")
    async def listar_conversaciones_inbox_endpoint(
        request: Request,
        propiedad_id: str | None = None,
        estado: str | None = None,
        busqueda: str | None = None,
        limite: int = 50,
    ) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            items = servicio.listar_inbox(
                sesion,
                propiedad_id=propiedad_id,
                estado=estado,
                busqueda=busqueda,
                limite=limite,
            )
            return JSONResponse(content=items, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ¤panel-operativo
    @router.get("/conversaciones/{conversacion_id}")
    @router.get("/api/conversaciones/{conversacion_id}")
    async def detalle_conversacion_inbox_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            detalle = servicio.detalle_inbox(sesion, conversacion_id)
            return JSONResponse(content=detalle, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "conversacion_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ¤panel-operativo
    @router.post("/conversaciones/{conversacion_id}/etiquetas")
    @router.post("/api/conversaciones/{conversacion_id}/etiquetas")
    async def asignar_etiqueta_inbox_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        try:
            cuerpo = await request.json()
            etiqueta = str(cuerpo.get("etiqueta", "")).strip()
            if not etiqueta:
                raise HTTPException(status_code=400, detail={"mensaje_usuario": "La etiqueta no puede estar vacía."})
            etiquetas = servicio.asignar_etiqueta_inbox(sesion, conversacion_id, etiqueta)
            return JSONResponse(content={"ok": True, "conversacion_id": conversacion_id, "etiquetas": etiquetas}, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "conversacion_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ¤panel-operativo
    @router.delete("/conversaciones/{conversacion_id}/etiquetas/{etiqueta}")
    @router.delete("/api/conversaciones/{conversacion_id}/etiquetas/{etiqueta}")
    async def remover_etiqueta_inbox_endpoint(request: Request, conversacion_id: str, etiqueta: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        try:
            etiquetas = servicio.remover_etiqueta_inbox(sesion, conversacion_id, etiqueta)
            return JSONResponse(content={"ok": True, "conversacion_id": conversacion_id, "etiquetas": etiquetas}, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "conversacion_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ¤panel-operativo
    @router.post("/conversaciones/{conversacion_id}/notas")
    @router.post("/api/conversaciones/{conversacion_id}/notas")
    async def agregar_nota_inbox_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        try:
            cuerpo = await request.json()
            texto = str(cuerpo.get("texto", "")).strip()
            nota = servicio.agregar_nota_inbox(sesion, conversacion_id, texto)
            return JSONResponse(content={"ok": True, "nota": nota}, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "conversacion_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ¤panel-operativo
    @router.post("/conversaciones/{conversacion_id}/responder")
    @router.post("/api/conversaciones/{conversacion_id}/responder")
    async def responder_inbox_endpoint(request: Request, conversacion_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        try:
            cuerpo = await request.json()
            texto = str(cuerpo.get("texto", "")).strip()
            res = servicio.responder_inbox(sesion, conversacion_id, texto)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "conversacion_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # Incidencias (RF-PAN-08)
    @router.get("/incidencias")
    async def listar_incidencias(request: Request, zona: str | None = None) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            lista = servicio.incidencias(sesion, filtros={"zona": zona} if zona else None)
            return JSONResponse(content=list(lista), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/incidencias/{incidencia_id}/resolver")
    async def resolver_incidencia_endpoint(request: Request, incidencia_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        datos = await request.json()
        nota = datos.get("nota", "").strip()
        if not nota:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "La nota de resolución es obligatoria."},
                headers={"Cache-Control": "no-store"},
            )

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        try:
            servicio.resolver_incidencia(sesion, incidencia_id, nota)
            resultado = {
                "ok": True,
                "incidencia_id": incidencia_id,
                "estado": "resuelta",
                "actor": sesion.usuario_id,
                "nota": nota,
            }
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "resolver_incidencia", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=resultado, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "zona_no_autorizada":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "incidencia_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # Desglose de comisión (INV_PANEL_SIN_LOGICA)
    @router.get("/comisiones/{venta_id}/desglose")
    async def desglose_comision_endpoint(request: Request, venta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "No tiene permisos para ver comisiones."})
        desglose = servicio.desglose_comision(sesion, venta_id)
        return JSONResponse(content=jsonable_encoder(dict(desglose)), headers={"Cache-Control": "no-store"})

    # Tablero de comisiones y estados de cuenta (RF-PAN-04, P-05, P-05b)
    @router.get("/comisiones/tablero")
    async def tablero_comisiones_endpoint(request: Request, periodo: str | None = None) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "No tiene permisos para ver el tablero de comisiones."})
        try:
            datos = servicio.tablero_comisiones(sesion, periodo_id=periodo or "2026-10")
            return JSONResponse(content=jsonable_encoder(datos), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/comisiones/vendedores/{vendedor_id}/estado_cuenta")
    async def estado_cuenta_vendedor_endpoint(request: Request, vendedor_id: str, periodo: str | None = None) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "No tiene permisos para ver estados de cuenta de vendedores."})
        try:
            datos = servicio.estado_cuenta_vendedor(sesion, vendedor_id, periodo_id=periodo or "2026-10")
            return JSONResponse(content=jsonable_encoder(datos), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # Cierre de período y exportación (RF-PAN-05, P-06)
    @router.get("/comisiones/periodos/{periodo_id}/resumen_cierre")
    async def resumen_cierre_endpoint(request: Request, periodo_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "No tiene permisos para cerrar períodos de comisiones."})
        try:
            resumen = servicio.resumen_cierre(sesion, periodo_id)
            return JSONResponse(content=jsonable_encoder(resumen), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/comisiones/periodos/{periodo_id}/cerrar")
    async def cerrar_periodo_endpoint(request: Request, periodo_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "No tiene permisos para cerrar períodos."})

        datos = await request.json() if request.headers.get("content-type") == "application/json" else {}
        confirmacion = str(datos.get("confirmacion_escrita", "")).strip()
        try:
            resultado = servicio.cerrar_periodo(sesion, periodo_id, confirmacion)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "cerrar_periodo", resultado)
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "confirmacion_invalida":
                return JSONResponse(
                    status_code=400,
                    content={"codigo": "confirmacion_invalida", "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            if exc.codigo == "periodo_cerrado":
                return JSONResponse(
                    status_code=409,
                    content={"codigo": "periodo_cerrado", "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/comisiones/periodos/{periodo_id}/exportar")
    async def exportar_periodo_endpoint(request: Request, periodo_id: str, formato: str = "csv") -> Response:
        sesion = _obtener_sesion_desde_request(request)
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "No tiene permisos para exportar comisiones."})
        try:
            datos_bytes = servicio.exportar_periodo(sesion, periodo_id, formato=formato)
            media_type = "application/json" if formato.lower() == "json" else "text/csv"
            filename = f"comisiones_{periodo_id}.{formato.lower()}"
            return Response(
                content=datos_bytes,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
            )
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # Ventas P-03 y P-04 (RF-PAN-02, RF-PAN-03, US-06)
    @router.get("/ventas/por_validar")
    async def listar_ventas_por_validar_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            lista = servicio.ventas_por_validar(sesion)
            return JSONResponse(content=jsonable_encoder(list(lista)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/ventas/{venta_id}/validar")
    async def validar_venta_endpoint(request: Request, venta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        correcciones = None
        try:
            body = await request.json()
            if isinstance(body, dict) and "correcciones" in body:
                correcciones = body["correcciones"]
        except Exception:
            pass

        try:
            resultado = servicio.validar_venta(sesion, venta_id, correcciones=correcciones)
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "validar_venta", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            if exc.codigo == "sin_regla_vigente":
                return JSONResponse(
                    status_code=422,
                    content={"codigo": "sin_regla_vigente", "mensaje_usuario": exc.mensaje_usuario, "venta_id": venta_id},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/ventas/{venta_id}/rechazar")
    async def rechazar_venta_endpoint(request: Request, venta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        motivo = ""
        try:
            body = await request.json()
            if isinstance(body, dict):
                motivo = str(body.get("motivo", "")).strip()
        except Exception:
            pass

        if not motivo:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "El motivo de rechazo es obligatorio."},
                headers={"Cache-Control": "no-store"},
            )

        try:
            resultado = servicio.rechazar_venta(sesion, venta_id, motivo=motivo)
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "rechazar_venta", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/ventas/{venta_id}")
    async def detalle_venta_endpoint(request: Request, venta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            detalle = servicio.detalle_venta(sesion, venta_id)
            return JSONResponse(content=jsonable_encoder(dict(detalle)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "venta_no_encontrada":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/ventas/{venta_id}/anular")
    async def anular_venta_endpoint(request: Request, venta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)

        idempotency_key = _obtener_idempotencia(request)
        if idempotency_key:
            respuesta_previa = servicio._persistencia.obtener_accion_idempotente(sesion.usuario_id, idempotency_key)
            if respuesta_previa is not None:
                return JSONResponse(content=respuesta_previa, headers={"Cache-Control": "no-store"})

        motivo = ""
        try:
            body = await request.json()
            if isinstance(body, dict):
                motivo = str(body.get("motivo", "")).strip()
        except Exception:
            pass

        if not motivo:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "El motivo de anulación es obligatorio."},
                headers={"Cache-Control": "no-store"},
            )

        try:
            resultado = servicio.anular_venta(sesion, venta_id, motivo=motivo)
            if idempotency_key:
                servicio._persistencia.registrar_accion_idempotente(
                    sesion.usuario_id, idempotency_key, "anular_venta", resultado, datetime.now(timezone.utc)
                )
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/ventas/{venta_id}/reintentar_publicacion")
    async def reintentar_publicacion_endpoint(request: Request, venta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        try:
            resultado = servicio.reintentar_publicacion_crm(sesion, venta_id)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "reintentar_publicacion", resultado)
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # Jarvis P-07 (RF-PAN-06, RF-ARM-09)
    @router.post("/jarvis/chat")
    async def jarvis_chat_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "Solo líderes y administradores pueden consultar a Jarvis."})

        datos = await request.json()
        pregunta = str(datos.get("pregunta", "")).strip()
        conversacion_id = str(datos.get("conversacion_id", ""))
        if not pregunta:
            return JSONResponse(
                status_code=400,
                content={"mensaje_usuario": "La pregunta no puede estar vacía."},
                headers={"Cache-Control": "no-store"},
            )

        try:
            resultado = servicio.preguntar_jarvis(sesion, pregunta, conversacion_id)
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/jarvis/configuracion")
    async def jarvis_configuracion_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        if sesion.rol not in {"lider", "administrador"}:
            raise HTTPException(status_code=403, detail={"mensaje_usuario": "Solo líderes y administradores pueden modificar configuración."})

        datos = await request.json()
        cambio = datos.get("cambio", {})
        confirmado = bool(datos.get("confirmado", False))
        if not confirmado:
            return JSONResponse(
                status_code=422,
                content={"codigo": "confirmacion_requerida", "mensaje_usuario": "Todo cambio de configuración exige confirmación explícita."},
                headers={"Cache-Control": "no-store"},
            )

        try:
            resultado = servicio.confirmar_cambio_jarvis(sesion, cambio, confirmado)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "jarvis_configuracion", resultado)
            return JSONResponse(content=jsonable_encoder(resultado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # ==========================================
    # Administración P-11 (RF-PAN-09, RF-ANF-01, RF-ANF-02, RF-PMS-08)
    # ==========================================

    @router.get("/admin/usuarios")
    async def listar_usuarios_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            lista = servicio.usuarios(sesion)
            return JSONResponse(content=jsonable_encoder(list(lista)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/usuarios")
    async def administrar_usuario_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json()
        numero = datos.get("numero", "")
        rol = datos.get("rol", "gestor")
        alta = bool(datos.get("alta", True))
        sujeto_id = datos.get("sujeto_id")
        correo = datos.get("correo")
        try:
            servicio.editar_usuario(sesion, numero=numero, rol=rol, alta=alta, sujeto_id=sujeto_id, correo=correo)
            res = {"ok": True, "alta": alta, "numero": numero}
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "admin_usuarios", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/bloqueos")
    async def bloquear_numero_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json()
        numero = datos.get("numero", "")
        motivo = datos.get("motivo", "Bloqueo preventivo")
        try:
            servicio.bloquear_numero(sesion, numero, motivo)
            res = {"ok": True, "bloqueado": numero}
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "admin_bloqueos", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.delete("/admin/bloqueos/{numero}")
    async def desbloquear_numero_endpoint(request: Request, numero: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        try:
            servicio.desbloquear_numero(sesion, numero)
            res = {"ok": True, "desbloqueado": numero}
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "admin_desbloqueos", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/reglas_comision")
    async def listar_reglas_comision_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            reglas = servicio.reglas_comision(sesion)
            return JSONResponse(content=jsonable_encoder(list(reglas)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/reglas_comision")
    async def crear_regla_comision_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json()
        try:
            nueva = servicio.crear_regla_comision(sesion, datos)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "crear_regla_comision", nueva)
            return JSONResponse(content=jsonable_encoder(nueva), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/anfitriones")
    async def listar_anfitriones_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            anfs = servicio.anfitriones(sesion)
            return JSONResponse(content=jsonable_encoder(list(anfs)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/anfitriones")
    async def registrar_anfitrion_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json()
        try:
            anf = servicio.registrar_anfitrion(sesion, datos)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "registrar_anfitrion", anf)
            return JSONResponse(content=jsonable_encoder(anf), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "sin_terminos":
                raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    # Cobro y pagos de anfitriones (RF-ANF-08)
    @router.get("/admin/anfitriones/estados_cuenta")
    async def listar_estados_cuenta_anfitriones_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            ecs = servicio.estados_cuenta_anfitriones(sesion)
            return JSONResponse(content=jsonable_encoder(list(ecs)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/anfitriones/estados_cuenta/{estado_cuenta_id}/pago")
    async def registrar_pago_anfitrion_endpoint(request: Request, estado_cuenta_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        try:
            res = servicio.registrar_pago_anfitrion(sesion, estado_cuenta_id)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "registrar_pago_anfitrion", res)
            return JSONResponse(content=jsonable_encoder(res), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "estado_cuenta_no_encontrado":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/anfitriones/pausar_vencidos")
    async def pausar_vencidos_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        try:
            pausados = servicio.pausar_hospedajes_por_cobro_vencido(sesion)
            res = {"ok": True, "pausados": pausados}
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "pausar_vencidos", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/hospedajes")
    async def listar_hospedajes_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            hospedajes = servicio.hospedajes(sesion)
            return JSONResponse(content=jsonable_encoder(list(hospedajes)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/hospedajes/{hospedaje_id}/publicar")
    async def publicar_hospedaje_endpoint(request: Request, hospedaje_id: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        try:
            pub = servicio.publicar_hospedaje(sesion, hospedaje_id)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "publicar_hospedaje", pub)
            return JSONResponse(content=jsonable_encoder(pub), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo == "hospedaje_no_encontrado":
                raise HTTPException(status_code=404, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/calendario/bloquear")
    async def bloquear_fechas_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json()
        unidad_id = datos.get("unidad_id", "")
        desde_str = datos.get("desde")
        hasta_str = datos.get("hasta")
        if not unidad_id or not desde_str or not hasta_str:
            raise HTTPException(status_code=400, detail={"mensaje_usuario": "unidad_id, desde y hasta son requeridos."})
        from datetime import date
        desde = date.fromisoformat(desde_str)
        hasta = date.fromisoformat(hasta_str)
        try:
            res = servicio.bloquear_fechas(sesion, unidad_id, desde, hasta)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "bloquear_fechas", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo in {"rol_no_autorizado", "unidad_ajena"}:
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/calendario/liberar")
    async def liberar_fechas_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json()
        unidad_id = datos.get("unidad_id", "")
        desde_str = datos.get("desde")
        hasta_str = datos.get("hasta")
        if not unidad_id or not desde_str or not hasta_str:
            raise HTTPException(status_code=400, detail={"mensaje_usuario": "unidad_id, desde y hasta son requeridos."})
        from datetime import date
        desde = date.fromisoformat(desde_str)
        hasta = date.fromisoformat(hasta_str)
        try:
            res = servicio.liberar_fechas(sesion, unidad_id, desde, hasta)
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "liberar_fechas", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo in {"rol_no_autorizado", "unidad_ajena"}:
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})
        except ErrorPanel as exc:
            if exc.codigo in {"rol_no_autorizado", "unidad_ajena"}:
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/auditoria")
    async def listar_auditoria_endpoint(request: Request, actor: str | None = None, accion: str | None = None) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            filtros = {}
            if actor:
                filtros["actor"] = actor
            if accion:
                filtros["accion"] = accion
            eventos = servicio.auditoria(sesion, filtros)
            return JSONResponse(content=jsonable_encoder(list(eventos)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/auditoria/exportar")
    async def exportar_auditoria_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            csv_bytes = servicio.exportar_auditoria_csv(sesion)
            return Response(
                content=csv_bytes,
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="auditoria.csv"', "Cache-Control": "no-store"},
            )
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/privacidad/solicitudes")
    async def listar_solicitudes_privacidad_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            sols = servicio.solicitudes_privacidad(sesion)
            return JSONResponse(content=jsonable_encoder(list(sols)), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/privacidad/solicitudes")
    async def registrar_solicitud_privacidad_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        datos = await request.json()
        tipo = datos.get("tipo", "acceso")
        titular_hash = datos.get("titular_hash", "")
        try:
            sol = servicio.registrar_solicitud_privacidad(sesion, tipo=tipo, titular_hash=titular_hash)
            return JSONResponse(content=jsonable_encoder(sol), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/salud")
    async def salud_sistema_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            estado = servicio.estado_sistema(sesion)
            return JSONResponse(content=jsonable_encoder(estado), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/conocimiento/reindexar")
    async def reindexar_conocimiento_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        try:
            res = servicio.reindexar(sesion)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.get("/admin/plantillas")
    async def listar_plantillas_endpoint(request: Request) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        try:
            plantillas = servicio.plantillas(sesion)
            return JSONResponse(content=list(plantillas), headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    @router.post("/admin/plantillas/{nombre}/aprobar")
    async def aprobar_plantilla_endpoint(request: Request, nombre: str) -> Response:
        sesion = _obtener_sesion_desde_request(request)
        _verificar_csrf(request, sesion)
        idemp_key, resp_previa = _manejar_idempotencia(request, sesion.usuario_id)
        if resp_previa:
            return resp_previa
        datos = await request.json() if request.headers.get("content-type") == "application/json" else {}
        aprobada = bool(datos.get("aprobada", True))
        try:
            servicio.aprobar_plantilla(sesion, nombre, aprobada=aprobada)
            res = {"ok": True, "nombre": nombre, "aprobada": aprobada}
            _guardar_idempotencia(sesion.usuario_id, idemp_key, "aprobar_plantilla", res)
            return JSONResponse(content=res, headers={"Cache-Control": "no-store"})
        except ErrorPanel as exc:
            if exc.codigo == "rol_no_autorizado":
                raise HTTPException(status_code=403, detail={"mensaje_usuario": exc.mensaje_usuario})
            if exc.codigo in {"conflicto_estado", "periodo_cerrado"}:
                return JSONResponse(
                    status_code=409,
                    content={"codigo": exc.codigo, "mensaje_usuario": exc.mensaje_usuario},
                    headers={"Cache-Control": "no-store"},
                )
            raise HTTPException(status_code=400, detail={"mensaje_usuario": exc.mensaje_usuario})

    return router


# ¤panel-operativo
def crear_app_panel(servicio: PanelOperativoService) -> FastAPI:
    """Crea la aplicación FastAPI completa del panel operativo con BFF y estáticos."""
    app = FastAPI(title="Panel Operativo Glamping Imbabura", docs_url=None, redoc_url=None)
    router = crear_router_bff(servicio)
    app.include_router(router)

    if RUTA_ESTATICOS.is_dir():
        app.mount("/panel/estaticos", StaticFiles(directory=str(RUTA_ESTATICOS)), name="estaticos")

    @app.get("/panel/manifest.webmanifest")
    @app.get("/panel/manifest.json")
    async def servir_manifest() -> Response:
        manifest_path = RUTA_ESTATICOS / "manifest.webmanifest"
        if not manifest_path.is_file():
            manifest_path = RUTA_ESTATICOS / "manifest.json"
        if manifest_path.is_file():
            return FileResponse(
                manifest_path,
                media_type="application/manifest+json",
                headers={"Cache-Control": "public, max-age=86400"},
            )
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    @app.get("/panel/sw.js")
    async def servir_service_worker() -> Response:
        sw_path = RUTA_ESTATICOS / "sw.js"
        if sw_path.is_file():
            return FileResponse(
                sw_path,
                media_type="application/javascript",
                headers={
                    "Cache-Control": "no-cache",
                    "Service-Worker-Allowed": "/panel/",
                },
            )
        return Response(content="// SW not found", status_code=404, media_type="application/javascript")

    @app.get("/panel", response_class=HTMLResponse)
    @app.get("/panel/", response_class=HTMLResponse)
    async def servir_panel_index() -> Response:
        index_html = RUTA_ESTATICOS / "index.html"
        if index_html.is_file():
            return HTMLResponse(content=index_html.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Panel Operativo</h1>", status_code=200)

    return app
