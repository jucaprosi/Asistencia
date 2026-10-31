# ¤arm-jarvis
# ¤¤backend-developer
"""Compuerta pública de la sala arm_jarvis (RF-ARM-01..09). Fase 0: interfaz; lógica en TASK-006 y TASK-007."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.arm_jarvis.tipos import (
    EstadoVenta, ResumenComision, Tablero, Transicion, Vendedor, Venta, VentaExtraida,
)

__all__ = [
    "EstadoVenta", "ResumenComision", "Tablero", "Transicion", "Vendedor", "Venta", "VentaExtraida",
    "ErrorArm", "ArmJarvisService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_arm_jarvis.yaml")


# ¤arm-jarvis
class ErrorArm(Exception):
    """Error tipado de la sala arm_jarvis (TransicionInvalida, ComisionAjena, CambioNoPermitido...)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤arm-jarvis
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤arm-jarvis
class ArmJarvisService:
    """ARM: extrae ventas de texto libre, gestiona estados con auditoría, comisión, ticket, notificaciones, tablero."""

    def __init__(
        self, config: Mapping[str, Any], *, seguridad: Any, comisiones: Any, crm: Any, canal: Any, observabilidad: Any,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._comisiones = comisiones
        self._crm = crm
        self._canal = canal
        self._observabilidad = observabilidad

    def procesar(self, mensaje: Any) -> str:
        raise NotImplementedError("TASK-006 RF-ARM-01/02/05")

    def extraer(self, texto: str) -> VentaExtraida:
        raise NotImplementedError("TASK-006 RF-ARM-02")

    def validar(self, venta_id: str, actor: Any, correcciones: Mapping[str, Any] | None = None) -> Venta:
        raise NotImplementedError("TASK-006 RF-ARM-03/04")

    def rechazar(self, venta_id: str, actor: Any, motivo: str) -> Venta:
        raise NotImplementedError("TASK-006 RF-ARM-03")

    def anular(self, venta_id: str, actor: Any, motivo: str) -> Venta:
        raise NotImplementedError("TASK-006 RF-ARM-03")

    def marcar_publicacion(self, venta_id: str, ok: bool, detalle: str | None) -> None:
        raise NotImplementedError("TASK-007 RF-CRM-04")

    def consultar_comision_propia(self, vendedor_id: str, periodo: str | None = None) -> ResumenComision:
        raise NotImplementedError("TASK-006 RF-ARM-07")

    def listar(
        self, estado: EstadoVenta | None, vendedor_id: str | None, periodo: str | None, pagina: int,
    ) -> tuple[Venta, ...]:
        raise NotImplementedError("TASK-006 RF-PAN-02")

    def detalle(self, venta_id: str) -> tuple[Venta, tuple[Transicion, ...]]:
        raise NotImplementedError("TASK-006 RF-PAN-03")

    def tablero(self, periodo: str) -> Tablero:
        raise NotImplementedError("TASK-007 RF-ARM-08")

    def preguntar_jarvis(self, actor: Any, pregunta: str, conversacion_id: str) -> str:
        raise NotImplementedError("TASK-006 RF-ARM-09")

    def aplicar_cambio_configuracion(self, actor: Any, cambio: Mapping[str, Any], confirmado: bool) -> None:
        raise NotImplementedError("TASK-006 RF-ARM-09")
