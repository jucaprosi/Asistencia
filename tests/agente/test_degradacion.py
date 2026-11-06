# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Árbitro de RF-AG-05: Manejo de errores, caídas de herramientas (PMS/RAG), timeout y degradación."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.tipos import (
    DefinicionHerramienta,
    LlamadaHerramienta,
    ModeloNoDisponible,
    RespuestaModelo,
    ResultadoHerramienta,
    TimeoutModelo,
)
from features.seguridad.seguridad_service import Identidad, MensajeLimpio, Rol


# ¤agente-enrutador
class DobleObservabilidad:
    def __init__(self) -> None:
        self.trazas_iniciadas: list[dict[str, Any]] = []
        self.trazas_cerradas: list[dict[str, Any]] = []
        self.logs: list[dict[str, Any]] = []

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str:
        tid = f"traza-{len(self.trazas_iniciadas) + 1}"
        self.trazas_iniciadas.append({"traza_id": tid, "mensaje_id": mensaje_id, "conversacion_id": conversacion_id, "canal": canal})
        return tid

    @contextmanager
    def span(self, traza_id: str, sala: str, nombre: str) -> Iterator[dict[str, Any]]:
        yield {"traza_id": traza_id, "sala": sala, "nombre": nombre}

    def cerrar_traza(self, traza_id: str, resultado: str) -> None:
        self.trazas_cerradas.append({"traza_id": traza_id, "resultado": resultado})

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **campos})


# ¤agente-enrutador
class DobleSeguridad:
    def tokenizar(self, texto: str, conversacion_id: str) -> str:
        return texto

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        return texto

    def filtrar_salida(self, texto: str, conversacion_id: str) -> str:
        return texto


# ¤agente-enrutador
class DobleHerramientas:
    def __init__(self) -> None:
        self.error_programado: str | None = None

    def listar(self, rol: str, propiedad_id: str | None) -> tuple[DefinicionHerramienta, ...]:
        return (
            DefinicionHerramienta(
                nombre="consultar_disponibilidad",
                descripcion="Consulta disponibilidad de fechas",
                esquema_entrada={"type": "object", "required": ["propiedad_id", "desde", "hasta"]},
                esquema_salida={"type": "object"},
                roles=("huesped_potencial", "huesped_activo"),
                sala_destino="pms_conector",
            ),
        )

    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> ResultadoHerramienta:
        if self.error_programado:
            return ResultadoHerramienta(nombre=nombre, salida={}, error=self.error_programado)
        return ResultadoHerramienta(nombre=nombre, salida={"disponible": True})


# ¤agente-enrutador
def test_el_pms_no_responde_no_inventa_disponibilidad_y_ofrece_humano() -> None:
    """Escenario: El PMS no responde (@US-01 @RF-AG-05).

    Dado que el PMS está caído
    Cuando el huésped pregunta por disponibilidad
    Entonces el agente lo declara, no inventa disponibilidad y ofrece pasar con una persona
    """
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientas()
    herramientas.error_programado = "PMSConectorTimeout: Conexión con PMS rechazada o caída"

    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="Revisando el PMS...",
            llamadas_herramientas=(
                LlamadaHerramienta(id="call_pms", nombre="consultar_disponibilidad", argumentos={"desde": "2026-11-15", "hasta": "2026-11-18"}),
            ),
        )
    ])

    servicio = AgenteService(
        config=config,
        seguridad=DobleSeguridad(),
        herramientas=herramientas,
        conocimiento=None,
        canal=None,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_huesped", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="¿Hay disponibilidad para este fin de semana?",
        marcas=(),
        conversacion_id="conv_pms_caido",
    )

    respuesta = servicio.atender(mensaje)

    # El agente debe estar en modo degradado y no inventar disponibilidad
    assert respuesta.degradada
    assert "intermitencia" in respuesta.texto or "no puedo consultar" in respuesta.texto
    assert "no quiero entregarte datos incorrectos" in respuesta.texto.lower() or "no disponible" in respuesta.texto.lower()

    # Ofrece pasar con una persona y entrega el contacto
    assert "Carlos Alvear" in respuesta.texto or "+593991234567" in respuesta.texto

    # Se registró la causa en la traza
    logs_error = [log for log in obs.logs if log.get("evento") == "herramienta_fallida"]
    assert len(logs_error) >= 1
    assert "PMSConectorTimeout" in logs_error[0]["motivo"]


# ¤agente-enrutador
def test_escalamiento_antes_de_la_fase_4() -> None:
    """Escenario: Escalamiento antes de la fase 4 (@RF-AG-05 @RF-MCP-06).

    Dado una instalación sin bandeja de handoff activa
    Cuando el agente debe escalar
    Entonces entrega el contacto humano configurado y registra el motivo en la traza
    """
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientas()
    herramientas.error_programado = "Servicio caído antes de fase 4"

    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="Intentando acción",
            llamadas_herramientas=(
                LlamadaHerramienta(id="call_esc", nombre="consultar_disponibilidad", argumentos={"desde": "2026-11-20"}),
            ),
        )
    ])

    servicio = AgenteService(
        config=config,
        seguridad=DobleSeguridad(),
        herramientas=herramientas,
        conocimiento=None,
        canal=None,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_esc", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="Quiero reservar",
        marcas=(),
        conversacion_id="conv_escalamiento",
    )

    respuesta = servicio.atender(mensaje)
    assert respuesta.degradada

    # Entrega contacto humano configurado
    assert "Carlos Alvear" in respuesta.texto
    assert "+593991234567" in respuesta.texto

    # Registra motivo en la traza
    logs_traza = [log for log in obs.logs if "motivo" in log]
    assert len(logs_traza) >= 1
    assert any("Servicio caído" in str(l.get("motivo")) for l in logs_traza)


# ¤agente-enrutador
def test_timeout_del_modelo_degrada_y_ofrece_contacto() -> None:
    """Verifica el timeout de modelo (30 s) con degradación limpia (RF-AG-05)."""
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientas()

    # Simular TimeoutModelo
    modelo = DobleClienteModelo([TimeoutModelo(timeout_s=30.0)])

    servicio = AgenteService(
        config=config,
        seguridad=DobleSeguridad(),
        herramientas=herramientas,
        conocimiento=None,
        canal=None,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_to", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="Pregunta lenta",
        marcas=(),
        conversacion_id="conv_timeout",
    )

    respuesta = servicio.atender(mensaje)
    assert respuesta.degradada
    assert "Carlos Alvear" in respuesta.texto or "+593991234567" in respuesta.texto

    # Se registró el evento en la traza
    logs_to = [log for log in obs.logs if log.get("evento") == "modelo_timeout"]
    assert len(logs_to) >= 1
    assert "30" in logs_to[0]["motivo"]
