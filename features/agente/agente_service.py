# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Compuerta pública de la sala agente (RF-AG-01..07).

Fase 0: interfaz declarada e importable; la lógica llega en TASK-001, TASK-004 y TASK-005.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.agente.tipos import ContextoConversacion, ModoAgente, ResolucionPropiedad, Respuesta

__all__ = [
    "ContextoConversacion", "ModoAgente", "ResolucionPropiedad", "Respuesta",
    "ErrorAgente", "AgenteService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_agente.yaml")


# ¤agente-enrutador
class ErrorAgente(Exception):
    """Error tipado de la sala agente."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤agente-enrutador
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤agente-enrutador
class AgenteService:
    """Atiende conversaciones de huéspedes. El ARM tiene su propio cliente de modelo (DPD)."""

    def __init__(
        self, config: Mapping[str, Any], *, seguridad: Any, herramientas: Any, conocimiento: Any, canal: Any,
        observabilidad: Any,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._herramientas = herramientas
        self._conocimiento = conocimiento
        self._canal = canal
        self._observabilidad = observabilidad

    def atender(self, mensaje: Any) -> Respuesta:
        raise NotImplementedError("TASK-001 RF-AG-04")

    def resolver_propiedad(self, mensaje: Any, contexto: ContextoConversacion) -> ResolucionPropiedad:
        raise NotImplementedError("TASK-004 RF-AG-01")

    def herramientas_para(self, rol: str, propiedad_id: str | None) -> tuple[str, ...]:
        raise NotImplementedError("TASK-004 RF-AG-03")

    def entrar_en_silencio(self, conversacion_id: str, motivo: str) -> None:
        raise NotImplementedError("TASK-004 CU-08")

    def reanudar(self, conversacion_id: str) -> None:
        raise NotImplementedError("TASK-004 CU-08")

    def enviar_checkins_del_dia(self, fecha: date) -> int:
        raise NotImplementedError("TASK-004 US-03")

    def contexto(self, conversacion_id: str) -> ContextoConversacion:
        raise NotImplementedError("TASK-001 RF-AG-06")
