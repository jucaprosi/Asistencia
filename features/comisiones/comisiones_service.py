# ¤comisiones
# ¤¤backend-developer
"""Compuerta pública de la sala comisiones (RF-COM-01..03). Fase 0: interfaz; lógica en TASK-006 y TASK-007."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

from features.comisiones.tipos import Comision, Escalon, EstadoComision, Periodo, ReglaComision, TipoRegla

__all__ = [
    "Comision", "Escalon", "EstadoComision", "Periodo", "ReglaComision", "TipoRegla",
    "ErrorComisiones", "ComisionesService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_comisiones.yaml")


# ¤comisiones
class ErrorComisiones(Exception):
    """Error tipado de la sala comisiones (SinReglaVigente, PeriodoCerrado, ComisionYaFijada...)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤comisiones
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤comisiones
class ComisionesService:
    """Cálculo reproducible con la regla vigente a la fecha de la venta; períodos cerrados inmutables."""

    def __init__(self, config: Mapping[str, Any], *, seguridad: Any, observabilidad: Any) -> None:
        self._config = config
        self._seguridad = seguridad
        self._observabilidad = observabilidad

    def calcular(
        self, venta_id: str, vendedor_id: str, propiedad_id: str | None, producto: str, monto: Decimal,
        fecha_venta: date,
        ticket: str,
    ) -> Comision:
        raise NotImplementedError("TASK-006 RF-COM-01")

    def fijar(self, comision_id: str) -> Comision:
        raise NotImplementedError("TASK-006 RF-COM-01")

    def resumen(self, vendedor_id: str | None, periodo_id: str) -> Mapping[str, Any]:
        raise NotImplementedError("TASK-006 RF-ARM-07")

    def reglas(self, vigentes_en: date | None = None) -> tuple[ReglaComision, ...]:
        raise NotImplementedError("TASK-006 RF-COM-01")

    def crear_regla(self, actor: Any, regla: ReglaComision) -> ReglaComision:
        raise NotImplementedError("TASK-007 RF-PAN-09")

    def cerrar_periodo(self, periodo_id: str, actor: Any) -> Periodo:
        raise NotImplementedError("TASK-006 RF-COM-02")

    def ajustar(self, comision_id: str, actor: Any, nuevo_monto: Decimal, motivo: str) -> Comision:
        raise NotImplementedError("TASK-006 RF-COM-02")

    def exportar(self, periodo_id: str, formato: Literal["csv", "json"]) -> bytes:
        raise NotImplementedError("TASK-007 RF-COM-03")
