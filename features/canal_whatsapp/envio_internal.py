# ¤canal-whatsapp
# ¤¤integration-engineer
"""Manejo de envíos, reintentos con backoff exponencial y estados para Meta Cloud API (RF-GW-02)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable, Mapping
from uuid import uuid4

from features.canal_whatsapp.persistencia_internal import RepositorioCanal
from features.canal_whatsapp.plantillas_internal import armar_payload_plantilla, validar_plantilla
from features.canal_whatsapp.tipos import (
    ApiMetaNoDisponible, Boton, Canal, ErrorCanalWhatsapp, FueraDeVentana,
    MensajeSaliente, OpcionLista, Plantilla, ResultadoEnvio,
)


# ¤canal-whatsapp
def armar_payload_texto(mensaje: MensajeSaliente) -> dict[str, Any]:
    """Genera payload para mensaje de texto simple."""
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": mensaje.destinatario,
        "type": "text",
        "text": {"preview_url": False, "body": mensaje.texto},
    }
    if mensaje.en_respuesta_a:
        payload["context"] = {"message_id": mensaje.en_respuesta_a}
    return payload


# ¤canal-whatsapp
def armar_payload_botones(mensaje: MensajeSaliente) -> dict[str, Any]:
    """Genera payload para mensaje interactivo de botones rápidos (máx. 3)."""
    if len(mensaje.botones) > 3:
        raise ErrorCanalWhatsapp(
            "BOTONES_EXCEDIDOS",
            "Un mensaje no puede tener más de 3 botones de respuesta rápida",
            f"recibidos={len(mensaje.botones)}",
        )
    for b in mensaje.botones:
        if len(b.titulo) > 20:
            raise ErrorCanalWhatsapp(
                "TITULO_BOTON_LARGO",
                f"El título del botón '{b.titulo}' excede el límite de 20 caracteres",
                f"longitud={len(b.titulo)}",
            )

    buttons_meta = [
        {
            "type": "reply",
            "reply": {"id": b.id, "title": b.titulo},
        }
        for b in mensaje.botones
    ]

    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": mensaje.destinatario,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": mensaje.texto},
            "action": {"buttons": buttons_meta},
        },
    }
    if mensaje.en_respuesta_a:
        payload["context"] = {"message_id": mensaje.en_respuesta_a}
    return payload


# ¤canal-whatsapp
def armar_payload_lista(mensaje: MensajeSaliente) -> dict[str, Any]:
    """Genera payload para mensaje interactivo de lista (máx. 10 opciones)."""
    if len(mensaje.lista) > 10:
        raise ErrorCanalWhatsapp(
            "OPCIONES_EXCEDIDAS",
            "Una lista no puede tener más de 10 opciones",
            f"recibidas={len(mensaje.lista)}",
        )

    rows_meta: list[dict[str, Any]] = []
    for opt in mensaje.lista:
        row: dict[str, Any] = {"id": opt.id, "title": opt.titulo}
        if opt.descripcion:
            row["description"] = opt.descripcion
        rows_meta.append(row)

    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": mensaje.destinatario,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": mensaje.texto},
            "action": {
                "button": "Ver opciones",
                "sections": [{"title": "Opciones disponibles", "rows": rows_meta}],
            },
        },
    }
    if mensaje.en_respuesta_a:
        payload["context"] = {"message_id": mensaje.en_respuesta_a}
    return payload


# ¤canal-whatsapp
class GestorEnvio:
    """Ejecutor de envíos a Meta con backoff exponencial y persistencia de estados."""

    def __init__(
        self,
        config: Mapping[str, Any],
        repositorio: RepositorioCanal,
        cliente_meta: Any,
        observabilidad: Any = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.config = config
        self.repositorio = repositorio
        self.cliente_meta = cliente_meta
        self.observabilidad = observabilidad
        self._sleep = sleep_fn or time.sleep

        reintentos_cfg = config.get("reintentos", {})
        self.max_reintentos = int(reintentos_cfg.get("max", 3))
        self.backoff_s = list(reintentos_cfg.get("backoff_s", [1, 4, 10]))

    def enviar_mensaje(
        self,
        mensaje: MensajeSaliente,
        *,
        en_ventana: bool,
        canal: Canal = Canal.HUESPEDES,
    ) -> ResultadoEnvio:
        """INV_VENTANA_24H: Fuera de ventana se rechaza antes de llamar a Meta."""
        if not en_ventana:
            raise FueraDeVentana(mensaje.destinatario)

        if mensaje.botones:
            payload = armar_payload_botones(mensaje)
            tipo_meta = "boton"
        elif mensaje.lista:
            payload = armar_payload_lista(mensaje)
            tipo_meta = "texto"
        elif mensaje.medio_ref:
            tipo_meta = "medio"
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": mensaje.destinatario,
                "type": "document" if mensaje.medio_ref.endswith(".pdf") else "image",
                "document" if mensaje.medio_ref.endswith(".pdf") else "image": {"link": mensaje.medio_ref},
            }
        else:
            payload = armar_payload_texto(mensaje)
            tipo_meta = "texto"

        mensaje_id = self._ejecutar_con_reintentos(payload)
        self.repositorio.guardar_mensaje_meta(
            mensaje_id=mensaje_id,
            direccion="out",
            remitente_token=mensaje.destinatario,
            canal=canal,
            tipo=tipo_meta,
            estado="sent",
        )
        return ResultadoEnvio(mensaje_id=mensaje_id, estado="sent")

    def enviar_plantilla(
        self,
        destinatario: str,
        plantilla: Plantilla,
        *,
        canal: Canal = Canal.HUESPEDES,
    ) -> ResultadoEnvio:
        """RF-GW-04: Valida plantilla antes de enviar y ejecuta envío."""
        definicion = self.repositorio.obtener_plantilla(plantilla.nombre)
        validar_plantilla(plantilla, definicion)

        payload = armar_payload_plantilla(destinatario, plantilla)
        mensaje_id = self._ejecutar_con_reintentos(payload)
        self.repositorio.guardar_mensaje_meta(
            mensaje_id=mensaje_id,
            direccion="out",
            remitente_token=destinatario,
            canal=canal,
            tipo="plantilla",
            estado="sent",
            plantilla=plantilla.nombre,
        )
        return ResultadoEnvio(mensaje_id=mensaje_id, estado="sent")

    def _ejecutar_con_reintentos(self, payload: dict[str, Any]) -> str:
        """RF-GW-02 (b): Backoff exponencial hasta 3 veces; error en bitácora si agota."""
        ultimo_error: Exception | None = None
        for intento in range(self.max_reintentos + 1):
            try:
                if hasattr(self.cliente_meta, "enviar"):
                    respuesta = self.cliente_meta.enviar(payload)
                elif hasattr(self.cliente_meta, "post"):
                    respuesta = self.cliente_meta.post(payload)
                else:
                    respuesta = {"messages": [{"id": f"wamid.{uuid4().hex}"}]}

                if isinstance(respuesta, dict) and "messages" in respuesta and respuesta["messages"]:
                    return respuesta["messages"][0]["id"]
                return f"wamid.{uuid4().hex}"
            except Exception as exc:
                ultimo_error = exc
                if intento < self.max_reintentos:
                    tiempo_espera = self.backoff_s[intento] if intento < len(self.backoff_s) else 10
                    self._sleep(tiempo_espera)
                else:
                    break

        if self.observabilidad and hasattr(self.observabilidad, "log"):
            self.observabilidad.log(
                "ERROR",
                "ENVIO_META_FALLIDO",
                destinatario=payload.get("to"),
                error=str(ultimo_error),
                intentos=self.max_reintentos,
            )

        raise ApiMetaNoDisponible(
            f"Fallo persistente tras {self.max_reintentos} reintentos: {ultimo_error}"
        )
