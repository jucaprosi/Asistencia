# ¤crm-conector
# ¤¤integration-engineer
"""Compuerta pública de la sala crm_conector (RF-CRM-01..05). Fase 0: interfaz; FakeCRM en TASK-004, proveedor en TASK-007."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from features.crm_conector.tipos import Contacto, EventoCRM, Oportunidad, PublicacionVenta

__all__ = [
    "Contacto", "EventoCRM", "Oportunidad", "PublicacionVenta", "ErrorCRM", "CRMConectorService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_crm_conector.yaml")
ReceptorEvento = Callable[[EventoCRM], Any]


# ¤crm-conector
class ErrorCRM(Exception):
    """Error tipado de la sala crm_conector (CRMNoDisponible, WebhookRechazado, FirmaEventoInvalida...)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤crm-conector
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤crm-conector
class CRMConectorService:
    """Publica ventas firmadas e idempotentes, recibe eventos del CRM y asigna conversaciones al inbox."""

    def __init__(self, config: Mapping[str, Any], *, observabilidad: Any) -> None:
        self._config = config
        self._observabilidad = observabilidad
        self._receptores: dict[str, list[ReceptorEvento]] = {}

    def registrar_receptor(self, tipo: str, receptor: ReceptorEvento) -> None:
        """El pasillo central enlaza aquí a arm_jarvis, agente y panel_operativo para los eventos del CRM."""
        self._receptores.setdefault(tipo, []).append(receptor)

    def buscar_contacto(self, telefono_token: str | None = None, email_token: str | None = None) -> Contacto | None:
        raise NotImplementedError("TASK-004 RF-CRM-01")

    def crear_contacto(self, contacto: Contacto) -> Contacto:
        raise NotImplementedError("TASK-004 RF-CRM-01")

    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        raise NotImplementedError("TASK-004 RF-CRM-01")

    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad:
        raise NotImplementedError("TASK-004 RF-CRM-01")

    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        raise NotImplementedError("TASK-007 RF-CRM-03")

    def procesar_cola(self) -> int:
        raise NotImplementedError("TASK-007 RF-CRM-04")

    def asignar_conversacion(self, conversacion_id: str, zona_id: str, resumen: str) -> str:
        raise NotImplementedError("TASK-004 RF-MCP-06 / ADR-0010")

    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        raise NotImplementedError("TASK-007 RF-CRM-01")

    def recibir_evento(self, cuerpo: bytes, firma: str) -> EventoCRM:
        raise NotImplementedError("TASK-007 RF-CRM-05")
