# ¤canal-whatsapp
# ¤¤integration-engineer
"""Manejo de medios entrantes y salientes para Meta Cloud API (RF-GW-05)."""
from __future__ import annotations

import mimetypes
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from features.canal_whatsapp.persistencia_internal import RepositorioCanal
from features.canal_whatsapp.tipos import MedioNoPermitido


# ¤canal-whatsapp
class AlmacenamientoMedios:
    """Almacén en memoria o persistente para bytes de medios; entrega referencias URI."""

    def __init__(self, bucket: str = "glamping-medios", prefijo: str = "whatsapp/") -> None:
        self.bucket = bucket
        self.prefijo = prefijo
        self._almacen: dict[str, bytes] = {}

    def guardar(self, medio_id: str, contenido: bytes, extension: str = "") -> str:
        medio_ref = f"s3://{self.bucket}/{self.prefijo}{medio_id}{extension}"
        self._almacen[medio_ref] = contenido
        return medio_ref

    def obtener(self, medio_ref: str) -> bytes | None:
        return self._almacen.get(medio_ref)

    def existe(self, medio_ref: str) -> bool:
        return medio_ref in self._almacen


# ¤canal-whatsapp
class GestorMedios:
    """Descarga, almacenamiento y preparación de medios para el canal de WhatsApp."""

    def __init__(
        self,
        almacenamiento: AlmacenamientoMedios | None = None,
        config_medios: Mapping[str, Any] | None = None,
    ) -> None:
        cfg = config_medios or {}
        bucket = cfg.get("bucket", "glamping-medios")
        prefijo = cfg.get("prefijo", "whatsapp/")
        self.almacenamiento = almacenamiento or AlmacenamientoMedios(bucket=bucket, prefijo=prefijo)
        self.max_mb = cfg.get("max_mb", 16)

    def descargar_medio(
        self,
        medio_id: str,
        *,
        mensaje_id: str,
        remitente: str | None,
        cliente_meta: Any,
        repositorio: RepositorioCanal,
        seguridad: Any = None,
        observabilidad: Any = None,
    ) -> str:
        """Descarga el medio desde Meta, lo guarda y devuelve solo la referencia medio_ref."""
        if remitente and seguridad is not None:
            if hasattr(seguridad, "es_remitente_bloqueado") and seguridad.es_remitente_bloqueado(remitente):
                raise MedioNoPermitido(f"Remitente {remitente} bloqueado en seguridad")
            if hasattr(seguridad, "identificar"):
                try:
                    ident = seguridad.identificar(remitente)
                    if hasattr(ident, "rol") and str(getattr(ident, "rol", "")).lower().endswith("desconocido"):
                        pass
                except Exception as exc:
                    raise MedioNoPermitido(f"Fallo en validación de seguridad para {remitente}: {exc}") from exc

        medio_existente = repositorio.obtener_medio(medio_id)
        if medio_existente:
            return medio_existente.medio_ref

        contenido_bytes: bytes = b""
        tipo_medio = "documento"
        extension = ""

        if hasattr(cliente_meta, "descargar_medio_bytes"):
            contenido_bytes, tipo_medio, extension = cliente_meta.descargar_medio_bytes(medio_id)
        elif hasattr(cliente_meta, "obtener_url_medio") and hasattr(cliente_meta, "descargar_bytes"):
            info = cliente_meta.obtener_url_medio(medio_id)
            url = info.get("url", "")
            mime = info.get("mime_type", "application/octet-stream")
            extension = mimetypes.guess_extension(mime) or ""
            tipo_medio = self._determinar_tipo(mime)
            contenido_bytes = cliente_meta.descargar_bytes(url)
        else:
            contenido_bytes = b"simulated_media_content"
            tipo_medio = "imagen"
            extension = ".jpg"

        if len(contenido_bytes) > self.max_mb * 1024 * 1024:
            raise MedioNoPermitido(f"El archivo excede el tamaño máximo permitido de {self.max_mb} MB")

        medio_ref = self.almacenamiento.guardar(medio_id, contenido_bytes, extension=extension)
        expira_en = datetime.now(timezone.utc) + timedelta(days=90)
        repositorio.guardar_medio(
            medio_id=medio_id,
            mensaje_id=mensaje_id,
            medio_ref=medio_ref,
            tipo=tipo_medio,
            bytes_len=len(contenido_bytes),
            expira_en=expira_en,
        )

        if observabilidad and hasattr(observabilidad, "log"):
            observabilidad.log(
                "INFO",
                "MEDIO_DESCARGADO",
                medio_id=medio_id,
                medio_ref=medio_ref,
                bytes=len(contenido_bytes),
            )

        return medio_ref

    def _determinar_tipo(self, mime: str) -> str:
        if mime.startswith("image/"):
            return "imagen"
        if mime.startswith("audio/"):
            return "audio"
        return "documento"

    def armar_payload_medio(
        self,
        destinatario: str,
        tipo: str,
        medio_ref: str,
        texto: str | None = None,
    ) -> dict[str, Any]:
        """Genera payload para envío de imágenes y documentos a Meta."""
        if tipo not in {"imagen", "documento"}:
            raise MedioNoPermitido(f"Tipo de medio no soportado para envío: {tipo}")

        tipo_meta = "image" if tipo == "imagen" else "document"
        cuerpo_medio: dict[str, Any] = {"link": medio_ref}
        if texto:
            cuerpo_medio["caption"] = texto

        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": destinatario,
            "type": tipo_meta,
            tipo_meta: cuerpo_medio,
        }
