# ¤arm-jarvis
# ¤¤backend-developer
"""Tipos del dominio y excepciones de la sala arm_jarvis."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

__all__ = [
    "EstadoVenta",
    "Vendedor",
    "VentaExtraida",
    "Venta",
    "Transicion",
    "ResumenComision",
    "Tablero",
    "ErrorArm",
    "VendedorNoRegistrado",
    "TransicionInvalida",
    "CamposFaltantes",
    "NoEsVenta",
    "ComisionAjena",
    "CambioNoPermitido",
    "ConfirmacionRequerida",
    "VentaNoEncontrada",
]


# ¤arm-jarvis
class EstadoVenta(str, Enum):
    POR_VALIDAR = "por_validar"
    VALIDADA = "validada"
    RECHAZADA = "rechazada"
    PUBLICADA = "publicada"
    NO_PUBLICADA = "no_publicada"
    ANULADA = "anulada"


# ¤arm-jarvis
@dataclass(frozen=True)
class Vendedor:
    vendedor_id: str
    telefono_token: str
    nombre: str
    activo: bool
    regla_comision_default_id: str | None = None


# ¤arm-jarvis
@dataclass(frozen=True)
class VentaExtraida:
    cliente_token: str | None
    telefono_cliente_token: str | None
    producto: str | None
    propiedad_id: str | None
    monto: Decimal | None
    moneda: str
    fecha_venta: date | None
    confianza: float
    campos_faltantes: tuple[str, ...] = ()
    es_venta: bool = True
    noches: int | None = None
    fecha_llegada: date | None = None
    confianza_campos: Mapping[str, float] = field(default_factory=dict)


# ¤arm-jarvis
@dataclass(frozen=True)
class Venta:
    venta_id: str
    ticket: str
    vendedor_id: str
    extraida: VentaExtraida
    texto_original_token: str
    estado: EstadoVenta
    creada: datetime
    actualizada: datetime
    comision_estimada: Decimal | None = None
    comision_fijada: Decimal | None = None
    reserva_ref: str | None = None
    posible_duplicado: bool = False
    posible_duplicado_de: str | None = None
    mensaje_id: str = ""
    indice_en_mensaje: int = 0


# ¤arm-jarvis
@dataclass(frozen=True)
class Transicion:
    venta_id: str
    de: EstadoVenta
    a: EstadoVenta
    actor_id: str
    rol: str
    motivo: str | None
    timestamp: datetime


# ¤arm-jarvis
@dataclass(frozen=True)
class ResumenComision:
    vendedor_id: str
    periodo: str
    validada: Decimal
    pendiente: Decimal
    ventas: int


# ¤arm-jarvis
@dataclass(frozen=True)
class Tablero:
    periodo: str
    ventas_por_mes: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
    ventas_por_vendedor: tuple[tuple[str, Decimal, int], ...] = field(default_factory=tuple)
    ventas_por_propiedad: tuple[tuple[str, Decimal], ...] = field(default_factory=tuple)
    comisiones_validadas: Decimal = Decimal("0.00")
    comisiones_pendientes: Decimal = Decimal("0.00")
    por_validar: int = 0


# ¤arm-jarvis
class ErrorArm(Exception):
    """Error base tipado de la sala arm_jarvis."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤arm-jarvis
class VendedorNoRegistrado(ErrorArm):
    """El remitente no es un vendedor registrado o activo en el sistema."""

    def __init__(self, remitente: str) -> None:
        super().__init__(
            codigo="vendedor_no_registrado",
            mensaje_usuario="El remitente no cuenta con rol de vendedor activo.",
            detalle_tecnico=f"Remitente {remitente} no registrado en arm.vendedores",
        )
        self.remitente = remitente


# ¤arm-jarvis
class TransicionInvalida(ErrorArm):
    """La transición de estado solicitada viola la máquina de estados o permisos."""

    def __init__(self, estado_actual: str, estado_nuevo: str, motivo: str | None = None) -> None:
        mensaje = motivo or f"No se puede pasar del estado '{estado_actual}' a '{estado_nuevo}'."
        super().__init__(
            codigo="transicion_invalida",
            mensaje_usuario=mensaje,
            detalle_tecnico=motivo or f"Transición {estado_actual} -> {estado_nuevo} no permitida",
        )
        self.estado_actual = estado_actual
        self.estado_nuevo = estado_nuevo


# ¤arm-jarvis
class CamposFaltantes(ErrorArm):
    """La venta extraída carece de campos obligatorios requeridos (monto, producto)."""

    def __init__(self, campos: tuple[str, ...], pregunta: str) -> None:
        super().__init__(
            codigo="campos_faltantes",
            mensaje_usuario=pregunta,
            detalle_tecnico=f"Campos obligatorios faltantes: {campos}",
        )
        self.campos = campos
        self.pregunta = pregunta


# ¤arm-jarvis
class NoEsVenta(ErrorArm):
    """El mensaje procesado no corresponde a una venta comercial."""

    def __init__(self, texto: str) -> None:
        super().__init__(
            codigo="no_es_venta",
            mensaje_usuario="El mensaje recibido no contiene información de venta.",
            detalle_tecnico=f"Texto analizado no clasificado como venta: {texto[:50]}...",
        )


# ¤arm-jarvis
class ComisionAjena(ErrorArm):
    """Un vendedor intentó consultar la comisión de otro vendedor (INV_COMISION_PROPIA)."""

    def __init__(self, vendedor_actor: str, vendedor_solicitado: str) -> None:
        super().__init__(
            codigo="comision_ajena",
            mensaje_usuario="Solo puedes consultar tu propia comisión.",
            detalle_tecnico=(
                f"Intento de acceso cruzado: {vendedor_actor} consultó comisiones de {vendedor_solicitado}"
            ),
        )
        self.vendedor_actor = vendedor_actor
        self.vendedor_solicitado = vendedor_solicitado


# ¤arm-jarvis
class CambioNoPermitido(ErrorArm):
    """El cambio de configuración solicitado no está permitido al rol o es reservado."""

    def __init__(self, clave: str, rol: str) -> None:
        super().__init__(
            codigo="cambio_no_permitido",
            mensaje_usuario=f"El rol '{rol}' no tiene permisos para modificar la configuración '{clave}'.",
            detalle_tecnico=f"Clave {clave} no autorizada para rol {rol}",
        )
        self.clave = clave
        self.rol = rol


# ¤arm-jarvis
class ConfirmacionRequerida(ErrorArm):
    """La operación solicitada requiere confirmación explícita del usuario."""

    def __init__(self, cambio: Mapping[str, Any], pregunta: str) -> None:
        super().__init__(
            codigo="confirmacion_requerida",
            mensaje_usuario=pregunta,
            detalle_tecnico=f"Se requiere confirmación para aplicar cambio: {cambio}",
        )
        self.cambio = cambio
        self.pregunta = pregunta


# ¤arm-jarvis
class VentaNoEncontrada(ErrorArm):
    """La venta con el identificador solicitado no existe."""

    def __init__(self, venta_id: str) -> None:
        super().__init__(
            codigo="venta_no_encontrada",
            mensaje_usuario=f"No se encontró la venta con ID '{venta_id}'.",
            detalle_tecnico=f"ID de venta desconocido: {venta_id}",
        )
        self.venta_id = venta_id
