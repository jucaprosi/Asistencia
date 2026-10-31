# ¤web-huespedes
# ¤¤frontend-developer
"""Compuerta pública de la sala web_huespedes (RF-WEB-01..06). Solo lectura: la reserva termina en WhatsApp."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.web_huespedes.tipos import Busqueda, EnlaceContacto, FichaPropiedad, OpcionDisponible

__all__ = [
    "Busqueda", "EnlaceContacto", "FichaPropiedad", "OpcionDisponible", "ErrorWebHuespedes", "WebHuespedesService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_web_huespedes.yaml")


# ¤web-huespedes
class ErrorWebHuespedes(Exception):
    """Error tipado: el visitante ve solo mensaje_usuario."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(detalle_tecnico or mensaje_usuario)
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤web-huespedes
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


# ¤web-huespedes
class WebHuespedesService:
    """Catálogo, búsqueda, comparación y paso a WhatsApp."""

    def __init__(self, config: Mapping[str, Any], *, pms: Any, observabilidad: Any) -> None:
        self._config = config
        self._pms = pms
        self._observabilidad = observabilidad

    def catalogo(self) -> tuple[FichaPropiedad, ...]:
        raise NotImplementedError("T-105 RF-WEB-01")

    def ficha(self, propiedad_id: str) -> FichaPropiedad:
        raise NotImplementedError("T-105 RF-WEB-01")

    def buscar(self, busqueda: Busqueda) -> tuple[OpcionDisponible, ...]:
        raise NotImplementedError("T-205 RF-WEB-02")

    def comparar(self, propiedades: tuple[str, ...], busqueda: Busqueda) -> tuple[OpcionDisponible, ...]:
        raise NotImplementedError("T-205 RF-WEB-03")

    def crear_enlace_contacto(self, propiedad_id: str, busqueda: Busqueda | None) -> str:
        raise NotImplementedError("T-105 RF-WEB-04")

    def resolver_contacto(self, codigo: str) -> EnlaceContacto | None:
        raise NotImplementedError("T-205 RF-WEB-04")
