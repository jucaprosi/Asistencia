# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tipos del dominio y errores de la sala agente."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Mapping


# ¤agente-enrutador
class ModoAgente(str, Enum):
    ACTIVO = "activo"
    SILENCIO = "silencio"


# ¤agente-enrutador
@dataclass(frozen=True)
class ContextoConversacion:
    conversacion_id: str
    identidad_token: str
    rol: str
    propiedad_id: str | None
    modo: ModoAgente
    ventana_24h_hasta: datetime | None


# ¤agente-enrutador
@dataclass(frozen=True)
class Respuesta:
    texto: str
    botones: tuple[tuple[str, str], ...] = ()
    lista: tuple[tuple[str, str], ...] = ()
    herramientas_usadas: tuple[str, ...] = ()
    chunks_citados: tuple[str, ...] = ()
    modelo: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: Decimal = Decimal("0")
    degradada: bool = False
    acuse_emitido: bool = False


# ¤agente-enrutador
@dataclass(frozen=True)
class EstadoAsistente:
    """Estado del asistente para el equipo (RF-AG-05). `motivo` es un código estable, nunca texto de cara al usuario."""

    disponible: bool
    motivo: str
    desde: datetime | None
    derivadas: int


# ¤agente-enrutador
@dataclass(frozen=True)
class ResolucionPropiedad:
    propiedad_id: str | None
    metodo: Literal["codigo_reserva", "nombre", "direccion", "contexto", "pregunta"]
    candidatas: tuple[str, ...] = ()


# ¤agente-enrutador
@dataclass(frozen=True)
class DefinicionHerramienta:
    nombre: str
    descripcion: str
    esquema_entrada: Mapping[str, Any]
    esquema_salida: Mapping[str, Any] = field(default_factory=dict)
    roles: tuple[str, ...] = ()
    sala_destino: str = ""


# ¤agente-enrutador
@dataclass(frozen=True)
class ResultadoHerramienta:
    nombre: str
    salida: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    duracion_ms: int = 0


# ¤agente-enrutador
@dataclass(frozen=True)
class LlamadaHerramienta:
    id: str
    nombre: str
    argumentos: Mapping[str, Any] = field(default_factory=dict)


# ¤agente-enrutador
@dataclass(frozen=True)
class RespuestaModelo:
    texto: str
    llamadas_herramientas: tuple[LlamadaHerramienta, ...] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    costo_usd: Decimal = Decimal("0")
    modelo: str = ""
    contexto_turno: Mapping[str, Any] = field(default_factory=dict)


# ¤agente-enrutador
@dataclass(frozen=True)
class MensajeMemoria:
    mensaje_id: str
    conversacion_id: str
    direccion: Literal["in", "out"]
    tipo: str
    contenido_token: str
    traza_id: str | None
    instante: datetime


# ¤agente-enrutador
class ErrorAgente(Exception):
    """Error base tipado de la sala agente."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤agente-enrutador
class TopeIteraciones(ErrorAgente):
    """Límite de iteraciones del bucle alcanzado sin respuesta final."""

    def __init__(self, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="limite_iteraciones",
            mensaje_usuario="Se ha alcanzado el límite de iteraciones del agente.",
            detalle_tecnico=detalle_tecnico,
        )


# ¤agente-enrutador
class HerramientaFallida(ErrorAgente):
    """Una herramienta invocada falló o retornó un error."""

    def __init__(self, herramienta: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="herramienta_fallida",
            mensaje_usuario=f"La herramienta {herramienta} falló durante su ejecución.",
            detalle_tecnico=detalle_tecnico,
        )
        self.herramienta = herramienta


# ¤agente-enrutador
class ModeloNoDisponible(ErrorAgente):
    """El modelo LLM no está disponible o falló la comunicación."""

    def __init__(self, detalle_tecnico: str | None = None) -> None:
        super().__init__(
            codigo="modelo_no_disponible",
            mensaje_usuario="El modelo de lenguaje no está disponible.",
            detalle_tecnico=detalle_tecnico,
        )


# ¤agente-enrutador
class TimeoutModelo(ModeloNoDisponible):
    """El modelo LLM excedió el tiempo máximo de espera."""

    def __init__(self, timeout_s: float, detalle_tecnico: str | None = None) -> None:
        self.timeout_s = timeout_s
        super().__init__(detalle_tecnico=detalle_tecnico or f"Timeout tras {timeout_s}s")
        self.codigo = "timeout_modelo"
        self.mensaje_usuario = f"El modelo no respondió dentro del límite de {timeout_s}s."
        # Actualizar representación en cadena
        Exception.__init__(self, f"{self.codigo}: {self.mensaje_usuario}")


# ¤agente-enrutador
class PropiedadRequeridaNoResuelta(ErrorAgente):
    """La herramienta requiere propiedad_id pero la propiedad no está resuelta."""

    def __init__(self, herramienta: str) -> None:
        super().__init__(
            codigo="propiedad_requerida_no_resuelta",
            mensaje_usuario=f"La herramienta {herramienta} requiere propiedad resuelta.",
            detalle_tecnico=f"INV_PROPIEDAD_RESUELTA violada para {herramienta}",
        )
        self.herramienta = herramienta


# ¤agente-enrutador
class ConversacionEnSilencio(ErrorAgente):
    """La conversación está en modo silencio debido a handoff activo."""

    def __init__(self, conversacion_id: str) -> None:
        super().__init__(
            codigo="conversacion_en_silencio",
            mensaje_usuario="La conversación se encuentra en silencio por transferencia a humano.",
            detalle_tecnico=f"Conversación {conversacion_id} en modo silencio",
        )
        self.conversacion_id = conversacion_id


# ¤agente-enrutador
class PropiedadAmbigua(ErrorAgente):
    """Hay múltiples propiedades candidatas y se requiere clarificación."""

    def __init__(self, candidatas: tuple[str, ...]) -> None:
        super().__init__(
            codigo="propiedad_ambigua",
            mensaje_usuario="Propiedad ambigua entre varias opciones.",
            detalle_tecnico=f"Candidatas: {candidatas}",
        )
        self.candidatas = candidatas
