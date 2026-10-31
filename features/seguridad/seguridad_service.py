# ¤seguridad-canal
# ¤¤security-engineer
"""Compuerta pública de la sala seguridad (RF-SEC-01..07).

Fase 0: interfaz declarada e importable; la lógica llega en TASK-001 (whitelist, rate limit, PII) y TASK-005 (resto).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.seguridad.tipos import EventoAuditoria, Identidad, MensajeLimpio, Rol, Veredicto

__all__ = [
    "EventoAuditoria", "Identidad", "MensajeLimpio", "Rol", "Veredicto",
    "ErrorSeguridad", "SeguridadService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_seguridad.yaml")


# ¤seguridad-canal
class ErrorSeguridad(Exception):
    """Error tipado de la sala seguridad."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤seguridad-canal
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤seguridad-canal
class SeguridadService:
    """Todo mensaje entra y sale por aquí. Única sala que ve PII en claro (bóveda de tokens)."""

    def __init__(self, config: Mapping[str, Any], *, observabilidad: Any) -> None:
        self._config = config
        self._observabilidad = observabilidad

    def identificar(self, remitente: str) -> Identidad:
        raise NotImplementedError("TASK-001 RF-SEC-01")

    def filtrar_entrada(self, remitente: str, texto: str, canal: str) -> MensajeLimpio | Veredicto:
        raise NotImplementedError("TASK-001 RF-SEC-01/03/05")

    def autorizar(self, rol: Rol, herramienta: str) -> Veredicto:
        raise NotImplementedError("TASK-005 RF-SEC-02")

    def tokenizar(self, texto: str, conversacion_id: str) -> str:
        raise NotImplementedError("TASK-001 RF-SEC-05")

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        raise NotImplementedError("TASK-001 RF-SEC-05")

    def filtrar_salida(self, texto: str, conversacion_id: str) -> str:
        raise NotImplementedError("TASK-001 RF-SEC-05")

    def auditar(self, evento: EventoAuditoria) -> None:
        raise NotImplementedError("TASK-005 RF-SEC-06")

    def informe_semanal(self, desde: date, hasta: date) -> bytes:
        raise NotImplementedError("TASK-005 RF-SEC-06")

    def administrar_usuarios(self, actor: Identidad, numero: str, rol: Rol, alta: bool) -> None:
        raise NotImplementedError("TASK-005 RF-SEC-01")
