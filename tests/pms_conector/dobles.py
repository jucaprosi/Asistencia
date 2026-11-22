# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Dobles de prueba para la sala pms_conector (RF-PMS-01, RF-PMS-03)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import time
from typing import Any, Iterator, Mapping

from features.pms_conector.base_internal import PMSConnector
from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.tipos import (
    Cotizacion,
    Disponibilidad,
    Incidencia,
    InstruccionesCheckin,
    PMSNoDisponible,
    Propiedad,
    Reserva,
)


# ¤pms-conector
class DobleObservabilidad:
    """Doble de observabilidad para pruebas de integración del PMS."""

    def __init__(self) -> None:
        self.logs: list[tuple[str, str, Mapping[str, Any]]] = []
        self.trazas: list[str] = []

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str:
        tid = f"traza_pms_{len(self.trazas) + 1}"
        self.trazas.append(tid)
        return tid

    @contextmanager
    def span(self, traza_id: str, sala: str, nombre: str) -> Iterator[None]:
        yield None

    def cerrar_traza(self, traza_id: str, resultado: str) -> None:
        pass

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append((nivel, evento, campos))


# ¤pms-conector
class DoblePMSConFallo(FakePMS):
    """Simula desconexión o latencia excesiva para probar reintentos y timeouts."""

    def __init__(self, fallar_lecturas: int = 0, superar_timeout: bool = False) -> None:
        super().__init__()
        self.fallar_lecturas = fallar_lecturas
        self.superar_timeout = superar_timeout
        self.intentos_lectura = 0

    def listar_propiedades(self) -> tuple[Propiedad, ...]:
        self.intentos_lectura += 1
        if self.superar_timeout:
            raise TimeoutError("Simulación de timeout superior a 8 segundos en el PMS")
        if self.intentos_lectura <= self.fallar_lecturas:
            raise PMSNoDisponible(f"Fallo transitorio en intento {self.intentos_lectura}")
        return super().listar_propiedades()
