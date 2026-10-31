# ¤panel-operativo
# ¤¤frontend-developer
"""Tipos del dominio de la sala panel_operativo (vistas que consume la UI)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


# ¤panel-operativo
@dataclass(frozen=True)
class Sesion:
    usuario_id: str
    rol: str
    zonas: tuple[str, ...]
    expira_en: datetime
    csrf: str


# ¤panel-operativo
@dataclass(frozen=True)
class VistaVentaPorValidar:
    venta_id: str
    ticket: str
    vendedor: str
    cliente: str
    producto: str
    monto: Decimal
    fecha_venta: date
    confianza: float
    campos_dudosos: tuple[str, ...]
    texto_original: str
    comision_estimada: Decimal
    creada: datetime


# ¤panel-operativo
@dataclass(frozen=True)
class VistaHandoff:
    conversacion_id: str
    propiedad: str
    zona_id: str
    motivo: str
    resumen: str
    esperando_desde: datetime
    asignado_a: str | None = None


# ¤panel-operativo
@dataclass(frozen=True)
class EstadoSistema:
    metricas: tuple = field(default_factory=tuple)
    alertas: tuple = field(default_factory=tuple)
    cola_crm: int = 0
    ultima_traza: datetime | None = None


# ¤panel-operativo
@dataclass(frozen=True)
class AvisoMovil:
    tipo: str
    cantidad: int
    ruta: str
