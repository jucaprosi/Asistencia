# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Dobles de prueba para la sala seguridad (RF-SEC-05, RF-OBS-01)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Mapping


# ¤seguridad-canal
class DobleObservabilidad:
    """Doble de observabilidad para pruebas de seguridad."""

    def __init__(self) -> None:
        self.logs: list[tuple[str, str, Mapping[str, Any]]] = []
        self.trazas_iniciadas: list[str] = []
        self.spans: list[tuple[str, str, str]] = []

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str:
        tid = f"traza_{len(self.trazas_iniciadas) + 1}"
        self.trazas_iniciadas.append(tid)
        return tid

    @contextmanager
    def span(self, traza_id: str, sala: str, nombre: str) -> Iterator[None]:
        self.spans.append((traza_id, sala, nombre))
        yield None

    def cerrar_traza(self, traza_id: str, resultado: str) -> None:
        pass

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append((nivel, evento, campos))


# ¤seguridad-canal
class DobleModeloHTTP:
    """Simula un cliente HTTP que envía peticiones al modelo LLM y captura el payload en tránsito."""

    def __init__(self, respuesta_modelo: str = "Respuesta simulada del modelo") -> None:
        self.respuesta_modelo = respuesta_modelo
        self.payloads_capturados: list[Mapping[str, Any]] = []

    def post_messages(self, payload: Mapping[str, Any]) -> str:
        """Captura el payload completo y devuelve la respuesta simulada."""
        self.payloads_capturados.append(dict(payload))
        return self.respuesta_modelo
