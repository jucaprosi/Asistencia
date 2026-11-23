# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio y excepciones de la sala crm_conector (RF-CRM-01..06, RF-MCP-06)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Mapping

MotivoHandoff = Literal[
    "peticion_explicita",
    "baja_confianza",
    "fuera_alcance",
    "incidencia_critica",
    "inyeccion_repetida",
    "degradacion",
    "limite_iteraciones",
]

EstadoHandoff = Literal["pendiente", "tomado", "devuelto"]
DevueltoPor = Literal["gestor", "vencimiento"]


# ¤crm-conector
@dataclass(frozen=True)
class Contacto:
    contacto_id: str
    nombre_token: str
    telefono_token: str
    email_token: str | None = None
    crm_ref: str | None = None


# ¤crm-conector
@dataclass(frozen=True)
class Oportunidad:
    oportunidad_id: str
    contacto_id: str
    propiedad_id: str | None
    etapa: str
    monto: Decimal | None = None
    crm_ref: str | None = None


# ¤crm-conector
@dataclass(frozen=True)
class PublicacionVenta:
    venta_id: str
    estado: Literal["pendiente", "ok", "error"]
    intentos: int
    ultima_respuesta: str | None = None
    proximo_intento: datetime | None = None


# ¤crm-conector
@dataclass(frozen=True)
class EventoCRM:
    tipo: Literal["venta_validada", "venta_rechazada", "handoff_devuelto", "incidencia_resuelta", "mensaje_gestor"]
    referencia: str
    actor: str
    datos: Mapping[str, Any]
    recibido_en: datetime


# ¤crm-conector
@dataclass(frozen=True)
class Zona:
    zona_id: str
    nombre: str
    gestor_principal_id: str
    gestor_respaldo_id: str


# ¤crm-conector
@dataclass(frozen=True)
class Handoff:
    handoff_id: str
    conversacion_id: str
    motivo: str
    zona_id: str | None
    estado: EstadoHandoff
    asignado_a: str | None
    resumen_token: str
    inicio: datetime
    tomado_en: datetime | None = None
    ultima_actividad: datetime | None = None
    devuelto_en: datetime | None = None
    devuelto_por: DevueltoPor | None = None


# ¤crm-conector
@dataclass(frozen=True)
class ResultadoHandoff:
    handoff_id: str
    asignado_a: str
    canal: Literal["panel"] = "panel"
    minutos_estimados: int = 15


# ¤crm-conector
@dataclass(frozen=True)
class ReferenciaCRM:
    entidad: str
    id_local: str
    crm_ref: str


# ¤crm-conector
class ErrorCRM(Exception):
    """Error base de la sala crm_conector."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤crm-conector
class CRMNoDisponible(ErrorCRM):
    """El proveedor de CRM no responde o no está disponible."""

    def __init__(self, mensaje: str = "El CRM no está disponible en este momento.") -> None:
        super().__init__("CRM_NO_DISPONIBLE", mensaje)


# ¤crm-conector
class ContactoDuplicado(ErrorCRM):
    """El contacto ya existe con el mismo identificador o token."""

    def __init__(self, mensaje: str = "Contacto duplicado en el CRM.") -> None:
        super().__init__("CONTACTO_DUPLICADO", mensaje)


# ¤crm-conector
class ContactoNoEncontrado(ErrorCRM):
    """No se encontró el contacto solicitado."""

    def __init__(self, mensaje: str = "Contacto no encontrado.") -> None:
        super().__init__("CONTACTO_NO_ENCONTRADO", mensaje)


# ¤crm-conector
class OportunidadInexistente(ErrorCRM):
    """La oportunidad especificada no existe en el CRM."""

    def __init__(self, mensaje: str = "Oportunidad no encontrada.") -> None:
        super().__init__("OPORTUNIDAD_INEXISTENTE", mensaje)


# ¤crm-conector
class WebhookRechazado(ErrorCRM):
    """El webhook fue rechazado por el destino y debe encolarse."""

    def __init__(self, mensaje: str = "Webhook rechazado por el CRM.") -> None:
        super().__init__("WEBHOOK_RECHAZADO", mensaje)


# ¤crm-conector
class LimiteDeTasa(ErrorCRM):
    """Se superó la tasa de llamadas al CRM."""

    def __init__(self, mensaje: str = "Límite de tasa excedido en el CRM.") -> None:
        super().__init__("LIMITE_DE_TASA", mensaje)


# ¤crm-conector
class FirmaEventoInvalida(ErrorCRM):
    """La firma criptográfica del webhook o evento recibido es inválida."""

    def __init__(self, mensaje: str = "Firma de evento inválida.") -> None:
        super().__init__("FIRMA_EVENTO_INVALIDA", mensaje)


# ¤crm-conector
class HandoffExistente(ErrorCRM):
    """Violación de INV_HANDOFF_UNICO: la conversación ya tiene un handoff abierto."""

    def __init__(self, mensaje: str = "La conversación ya tiene un handoff abierto.") -> None:
        super().__init__("HANDOFF_EXISTENTE", mensaje)


# ¤crm-conector
class HandoffInexistente(ErrorCRM):
    """El handoff especificado no existe."""

    def __init__(self, mensaje: str = "Handoff no encontrado.") -> None:
        super().__init__("HANDOFF_INEXISTENTE", mensaje)


# ¤crm-conector
class ZonaInexistente(ErrorCRM):
    """La zona especificada no existe."""

    def __init__(self, mensaje: str = "Zona no encontrada.") -> None:
        super().__init__("ZONA_INEXISTENTE", mensaje)


# ¤crm-conector
class BandejaHandoffInactiva(ErrorCRM):
    """Escalamiento antes de la fase 4 cuando la bandeja no está activa."""

    def __init__(self, contacto_humano: str, mensaje: str = "Bandeja de handoff inactiva.") -> None:
        super().__init__("BANDEJA_INACTIVA", mensaje, detalle_tecnico=contacto_humano)
        self.contacto_humano = contacto_humano
