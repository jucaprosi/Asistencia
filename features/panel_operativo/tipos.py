# ¤panel-operativo
# ¤¤frontend-developer
"""Tipos del dominio de la sala panel_operativo (vistas que consume la UI)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping


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


# ¤panel-operativo
@dataclass(frozen=True)
class VistaUsuario:
    usuario_id: str
    correo_enmascarado: str
    numero_enmascarado: str
    rol: str
    activo: bool
    creado_en: datetime


# ¤panel-operativo
@dataclass(frozen=True)
class VistaReglaComision:
    regla_id: str
    version: int
    nombre: str
    tipo: str
    parametros: Mapping[str, Any]
    vigencia_desde: str
    activa: bool = True


# ¤panel-operativo
@dataclass(frozen=True)
class VistaAnfitrion:
    anfitrion_id: str
    nombre: str
    telefono_token: str
    porcentaje_comision: Decimal
    version_terminos: str
    estado: str
    creado_en: datetime


# ¤panel-operativo
@dataclass(frozen=True)
class VistaHospedaje:
    hospedaje_id: str
    anfitrion_id: str
    titulo: str
    estado: str
    publicado_por: str | None = None
    publicado_en: datetime | None = None


# ¤panel-operativo
@dataclass(frozen=True)
class SolicitudPrivacidad:
    solicitud_id: str
    tipo: str
    titular_hash: str
    estado: str
    creada_en: datetime
