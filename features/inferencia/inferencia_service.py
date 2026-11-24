# ¤inferencia
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta de la sala inferencia (ADR-0021). Esqueleto del paso 2 del Orden: aún sin implementar.

Contrato:
- ``InferenciaService(entorno, cliente=None, cuota=None, config=None)``: ``entorno`` trae
  ``GOOGLE_CLOUD_PROJECT`` y ``VERTEX_LOCATION`` sin valores por defecto. En producción ``app_core`` inyecta
  ``os.environ``; el valor vacío por defecto es solo para pruebas. Aunque el entorno inyectado venga limpio,
  ``GOOGLE_API_KEY`` o ``GEMINI_API_KEY`` presentes en ``os.environ`` (que ``google-genai`` lee por su
  cuenta) hacen fallar cerrado. ``config`` sustituye a ``config_inferencia.yaml`` en pruebas;
  ``cliente`` sustituye al de ``google-genai`` en pruebas;
  ``cuota.reservar(costo_estimado) -> bool`` es el tope diario atómico que lleva observabilidad.
- ``generar(peticion) -> RespuestaInferencia``; falla cerrada con ``InferenciaNoDisponible``.
- ``estado() -> EstadoInferencia``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from features.inferencia.tipos import EstadoInferencia, PeticionInferencia, RespuestaInferencia

__all__ = ["InferenciaService", "cargar_config"]

RUTA_CONFIG = Path(__file__).with_name("config_inferencia.yaml")


# ¤inferencia
def cargar_config(ruta: Path = RUTA_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


# ¤inferencia
class InferenciaService:
    def __init__(
        self,
        entorno: Mapping[str, str] | None = None,
        cliente: Any = None,
        cuota: Any = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self._entorno = dict(entorno or {})
        self._cliente = cliente
        self._cuota = cuota
        self._config = dict(config) if config is not None else cargar_config()

    # ¤inferencia
    def inyectar_cliente_de_prueba(self, cliente: Any) -> None:
        self._cliente = cliente

    # ¤inferencia
    def estado(self) -> EstadoInferencia:
        raise NotImplementedError("ADR-0021 paso 3")

    # ¤inferencia
    def generar(self, peticion: PeticionInferencia) -> RespuestaInferencia:
        raise NotImplementedError("ADR-0021 paso 3")
