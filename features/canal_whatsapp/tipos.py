# ¤canal-whatsapp
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio de la sala canal_whatsapp. Solo estos tipos cruzan la compuerta."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


# ¤canal-whatsapp
class Canal(str, Enum):
    HUESPEDES = "huespedes"
    VENDEDORES = "vendedores"


# ¤canal-whatsapp
class TipoContenido(str, Enum):
    TEXTO = "texto"
    BOTON = "boton"
    LISTA = "lista"
    IMAGEN = "imagen"
    AUDIO = "audio"
    DOCUMENTO = "documento"
    UBICACION = "ubicacion"
    DESCONOCIDO = "desconocido"


# ¤canal-whatsapp
@dataclass(frozen=True)
class MensajeEntrante:
    mensaje_id: str
    remitente: str
    canal: Canal
    tipo: TipoContenido
    texto: str | None
    medio_ref: str | None
    ubicacion: tuple[float, float] | None
    recibido_en: datetime
    contexto_respuesta_a: str | None = None
    mensajes_agrupados: tuple[MensajeEntrante, ...] = ()


# ¤canal-whatsapp
@dataclass(frozen=True)
class Boton:
    id: str
    titulo: str


# ¤canal-whatsapp
@dataclass(frozen=True)
class OpcionLista:
    id: str
    titulo: str
    descripcion: str | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class MensajeSaliente:
    destinatario: str
    texto: str
    botones: tuple[Boton, ...] = ()
    lista: tuple[OpcionLista, ...] = ()
    medio_ref: str | None = None
    en_respuesta_a: str | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class Plantilla:
    nombre: str
    idioma: str
    variables: tuple[str, ...]


# ¤canal-whatsapp
@dataclass(frozen=True)
class ResultadoEnvio:
    mensaje_id: str
    estado: Literal["sent", "delivered", "read", "failed"]
    detalle: str | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class EventoEntrante:
    evento_id: str
    mensaje_id: str
    conversacion_clave: str
    cuerpo_cifrado: bytes
    estado: Literal["pendiente", "procesando", "procesado", "muerto"]
    intentos: int
    recibido_en: datetime
    procesado_en: datetime | None = None


# ¤canal-whatsapp
@dataclass(frozen=True)
class MensajeMeta:
    mensaje_id: str
    direccion: Literal["in", "out"]
    remitente_token: str
    canal: Canal
    tipo: Literal["texto", "plantilla", "medio", "boton", "ubicacion"]
    estado: Literal["recibido", "sent", "delivered", "read", "failed"]
    plantilla: str | None
    enviado_en: datetime
    actualizado_en: datetime


# ¤canal-whatsapp
@dataclass(frozen=True)
class PlantillaMeta:
    nombre: str
    idioma: str
    categoria: Literal["utility", "authentication", "marketing"]
    variables: tuple[str, ...]
    aprobada: bool
    actualizada_en: datetime


# ¤canal-whatsapp
@dataclass(frozen=True)
class MedioMeta:
    medio_id: str
    mensaje_id: str | None
    medio_ref: str
    tipo: Literal["imagen", "audio", "documento", "ubicacion"]
    bytes: int
    expira_en: datetime


# ¤canal-whatsapp
class ErrorCanalWhatsapp(Exception):
    """Error tipado de la sala: ``codigo`` estable, ``mensaje_usuario`` apto para mostrar, detalle técnico aparte."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤canal-whatsapp
class FirmaInvalida(ErrorCanalWhatsapp):
    """Firma X-Hub-Signature-256 no coincide con el secreto de Meta (401)."""

    def __init__(self, detalle_tecnico: str | None = None) -> None:
        super().__init__("FIRMA_INVALIDA", "Firma X-Hub-Signature-256 inválida o ausente", detalle_tecnico)


# ¤canal-whatsapp
class MensajeDuplicado(ErrorCanalWhatsapp):
    """Mensaje con ID previamente registrado; se descarta de forma silenciosa e idempotente."""

    def __init__(self, mensaje_id: str) -> None:
        super().__init__("MENSAJE_DUPLICADO", "Mensaje ya procesado previamente", f"mensaje_id={mensaje_id}")


# ¤canal-whatsapp
class FueraDeVentana(ErrorCanalWhatsapp):
    """Intento de enviar mensaje de texto libre fuera de la ventana de 24 horas."""

    def __init__(self, destinatario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            "FUERA_DE_VENTANA",
            "No se puede enviar texto libre fuera de la ventana de servicio de 24 horas",
            detalle_tecnico or f"destinatario={destinatario}",
        )


# ¤canal-whatsapp
class PlantillaNoAprobada(ErrorCanalWhatsapp):
    """Intento de enviar una plantilla no aprobada por Meta."""

    def __init__(self, nombre: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            "PLANTILLA_NO_APROBADA",
            f"La plantilla '{nombre}' no está aprobada",
            detalle_tecnico or f"plantilla={nombre}",
        )


# ¤canal-whatsapp
class VariablesPlantillaInvalidas(ErrorCanalWhatsapp):
    """Número o tipo de variables incorrectas para la plantilla solicitada."""

    def __init__(self, nombre: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            "VARIABLES_PLANTILLA_INVALIDAS",
            f"Variables inválidas para la plantilla '{nombre}'",
            detalle_tecnico or f"plantilla={nombre}",
        )


# ¤canal-whatsapp
class ApiMetaNoDisponible(ErrorCanalWhatsapp):
    """Fallo en la API de Meta tras agotar los reintentos permitidos."""

    def __init__(self, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            "API_META_NO_DISPONIBLE",
            "El servicio de mensajería de Meta no respondió tras reintentos",
            detalle_tecnico,
        )


# ¤canal-whatsapp
class MedioNoPermitido(ErrorCanalWhatsapp):
    """Intento de descargar o procesar un medio de un remitente bloqueado o no permitido."""

    def __init__(self, motivo: str, detalle_tecnico: str | None = None) -> None:
        super().__init__("MEDIO_NO_PERMITIDO", f"Medio no permitido: {motivo}", detalle_tecnico)
