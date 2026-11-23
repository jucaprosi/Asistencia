# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Dobles de prueba para la sala canal_whatsapp (seguridad, observabilidad y API simulada de Meta)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from features.observabilidad.tipos import Alerta, Metrica, Span, Traza
from features.seguridad.tipos import Identidad, Rol


class DobleSeguridadService:
    """Doble de seguridad para canal_whatsapp (control de remitentes bloqueados y roles)."""

    def __init__(self, bloqueados: set[str] | None = None, roles: dict[str, Rol] | None = None) -> None:
        self.bloqueados = set(bloqueados or set())
        self.roles = dict(roles or {})

    def bloquear(self, remitente: str) -> None:
        self.bloqueados.add(remitente)

    def desbloquear(self, remitente: str) -> None:
        self.bloqueados.discard(remitente)

    def registrar_rol(self, remitente: str, rol: Rol) -> None:
        self.roles[remitente] = rol

    def es_remitente_bloqueado(self, remitente: str) -> bool:
        return remitente in self.bloqueados

    def identificar(self, remitente: str) -> Identidad:
        if self.es_remitente_bloqueado(remitente):
            return Identidad(remitente_token=remitente, rol=Rol.DESCONOCIDO, sujeto_id=None)
        rol = self.roles.get(remitente, Rol.HUESPED_ACTIVO)
        return Identidad(remitente_token=remitente, rol=rol, sujeto_id=f"user_{remitente}")


class DobleObservabilidadService:
    """Doble de observabilidad para registrar logs, trazas y alertas."""

    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []
        self.alertas: list[Alerta] = []
        self.trazas: dict[str, Traza] = {}

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str:
        traza_id = str(uuid4())
        return traza_id

    @contextmanager
    def span(self, traza_id: str, sala: str, nombre: str) -> Iterator[Span]:
        s = Span(
            span_id=str(uuid4()),
            traza_id=traza_id,
            sala=sala,
            nombre=nombre,
            inicio=datetime.now(timezone.utc),
            duracion_ms=10,
            atributos={},
        )
        yield s

    def cerrar_traza(self, traza_id: str, resultado: str) -> Traza:
        t = Traza(
            traza_id=traza_id,
            mensaje_id=None,
            conversacion_id=None,
            canal="huespedes",
            inicio=datetime.now(timezone.utc),
            fin=datetime.now(timezone.utc),
            resultado=resultado,
            spans=(),
        )
        self.trazas[traza_id] = t
        return t

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **campos})

    def disparar_alerta(self, nombre: str, severidad: str, mensaje: str) -> None:
        alerta = Alerta(
            nombre=nombre,
            severidad=severidad,  # type: ignore[arg-type]
            mensaje=mensaje,
            disparada_en=datetime.now(timezone.utc),
        )
        self.alertas.append(alerta)

    def alertas_activas(self) -> tuple[Alerta, ...]:
        return tuple(self.alertas)

    def metricas(self, ventana: str = "7d") -> tuple[Metrica, ...]:
        return ()


class ApiMetaSimulada:
    """Simulador de Meta Cloud API con inyección de fallos controlados para backoff y medios."""

    def __init__(self, fallos_iniciales: int = 0) -> None:
        self.fallos_restantes = fallos_iniciales
        self.mensajes_enviados: list[dict[str, Any]] = []
        self.llamadas: list[dict[str, Any]] = []
        self.medios_almacenados: dict[str, tuple[bytes, str, str]] = {
            "media_img_1": (b"JPEG_BINARY_DATA", "imagen", ".jpg"),
            "media_doc_1": (b"%PDF-1.4 DUMMY DOCUMENT", "documento", ".pdf"),
            "media_aud_1": (b"OGG_OPUS_AUDIO_DATA", "audio", ".ogg"),
        }

    def enviar(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.llamadas.append(dict(payload))
        if self.fallos_restantes > 0:
            self.fallos_restantes -= 1
            raise ConnectionError("Simulated Meta 500 Service Unavailable")

        msg_id = f"wamid.{uuid4().hex}"
        self.mensajes_enviados.append({"id": msg_id, "payload": payload})
        return {
            "messaging_product": "whatsapp",
            "contacts": [{"input": payload.get("to"), "wa_id": payload.get("to")}],
            "messages": [{"id": msg_id}],
        }

    def descargar_medio_bytes(self, medio_id: str) -> tuple[bytes, str, str]:
        if medio_id in self.medios_almacenados:
            return self.medios_almacenados[medio_id]
        return (b"RAW_GENERIC_BYTES", "documento", ".bin")
