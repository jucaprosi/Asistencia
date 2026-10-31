# ¤crm-conector
# ¤¤integration-engineer
"""Tipos del dominio de la sala crm_conector."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Mapping


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
