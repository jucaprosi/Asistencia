# ¤observabilidad
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-OBS-02: Trazas por mensaje, persistencia de spans, cálculo de tokens/costo y métricas operativas."""
from __future__ import annotations

import tempfile
import time
from decimal import Decimal
from pathlib import Path

import pytest

from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.observabilidad.tipos import TrazaDesconocida
from features.observabilidad.trazas_internal import AlmacenTrazas, GestorTrazas


# ¤observabilidad
def test_traza_por_mensaje_con_spans_tokens_y_costo() -> None:
    """Escenario: Traza por mensaje (@RF-OBS-02 @INV_TRAZA_POR_MENSAJE).

    Dado un mensaje entrante
    Cuando termina su procesamiento
    Entonces existe una traza con spans por sala, tokens y costo
    """
    config = dict(cargar_config())
    servicio = ObservabilidadService(config)

    # 1. Mensaje entrante inicia su traza única (INV_TRAZA_POR_MENSAJE)
    mensaje_id = "msg_in_001"
    conversacion_id = "conv_traza_001"
    traza_id = servicio.iniciar_traza(mensaje_id=mensaje_id, conversacion_id=conversacion_id, canal="huespedes")
    assert traza_id

    # 2. Spans por sala
    with servicio.span(traza_id, "seguridad", "filtrar_entrada"):
        time.sleep(0.005)

    with servicio.span(
        traza_id,
        "agente",
        "llamada_modelo",
        modelo="gemini-3.8-flash",
        tokens_in=1200,
        tokens_out=350,
        costo_usd=Decimal("0.004425"),  # lo calcula inferencia (ADR-0021, C5); aquí solo se guarda
    ):
        time.sleep(0.010)

    # 3. Termina procesamiento y se cierra la traza
    traza_cerrada = servicio.cerrar_traza(traza_id, resultado="resuelta")

    assert traza_cerrada.traza_id == traza_id
    assert traza_cerrada.mensaje_id == mensaje_id
    assert traza_cerrada.conversacion_id == conversacion_id
    assert traza_cerrada.resultado == "resuelta"
    assert traza_cerrada.fin is not None
    assert len(traza_cerrada.spans) == 2

    # Verificar span de agente con cálculo de tokens y costo
    span_agente = [s for s in traza_cerrada.spans if s.sala == "agente"][0]
    assert span_agente.modelo == "gemini-3.8-flash"
    assert span_agente.tokens_in == 1200
    assert span_agente.tokens_out == 350
    assert span_agente.costo_usd is not None
    assert span_agente.costo_usd == Decimal("0.004425")
    assert span_agente.duracion_ms >= 5


# ¤observabilidad
def test_traza_sintetica_con_tres_spans_se_persiste_y_se_recupera() -> None:
    """Criterio de aceptación T-103: 'una traza sintética con tres spans se persiste y se recupera'."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = Path(temp_dir) / "trazas_test.db"
        almacen = AlmacenTrazas(db_path=db_file)
        config = dict(cargar_config())
        gestor = GestorTrazas(config=config, almacen=almacen)

        # Iniciar traza sintética
        tid = gestor.iniciar_traza(mensaje_id="msg_sintetico", conversacion_id="conv_sintetica", canal="huespedes")

        # Span 1: sala seguridad
        with gestor.span(tid, "seguridad", "autorizar_herramienta"):
            time.sleep(0.002)

        # Span 2: sala agente con llamada al modelo
        with gestor.span(
            tid,
            "agente",
            "bucle_tool_use",
            modelo="gemini-3.5-flash-lite",
            tokens_in=500,
            tokens_out=150,
            costo_usd=Decimal("0.000525"),
        ):
            time.sleep(0.002)

        # Span 3: sala herramientas_glamping (PMS)
        with gestor.span(tid, "herramientas_glamping", "consultar_disponibilidad"):
            time.sleep(0.002)

        gestor.cerrar_traza(tid, resultado="resuelta")

        # Simular reinicio y recuperación desde la base de datos persistida
        almacen.cerrar()
        almacen_recuperado = AlmacenTrazas(db_path=db_file)
        gestor_recuperado = GestorTrazas(config=config, almacen=almacen_recuperado)

        traza_recuperada = gestor_recuperado.obtener_traza(tid)
        assert traza_recuperada.traza_id == tid
        assert traza_recuperada.mensaje_id == "msg_sintetico"
        assert traza_recuperada.resultado == "resuelta"
        assert len(traza_recuperada.spans) == 3

        salas_spans = [s.sala for s in traza_recuperada.spans]
        assert salas_spans == ["seguridad", "agente", "herramientas_glamping"]

        span_modelo = [s for s in traza_recuperada.spans if s.sala == "agente"][0]
        assert span_modelo.modelo == "gemini-3.5-flash-lite"
        assert span_modelo.tokens_in == 500
        assert span_modelo.tokens_out == 150
        assert span_modelo.costo_usd == Decimal("0.000525")

        almacen_recuperado.cerrar()


# ¤observabilidad
def test_metricas_op_calculables_directamente_de_trazas() -> None:
    """Criterio RF-OBS-02 (b): OP-01, OP-02, OP-08 y OP-09 se calculan a partir de las trazas sin instrumentación extra."""
    config = dict(cargar_config())
    servicio = ObservabilidadService(config)

    # 1. Traza sin herramientas (para OP-01)
    t1 = servicio.iniciar_traza("m1", "c1", canal="huespedes")
    with servicio.span(t1, "agente", "respuesta_directa", modelo="gemini-3.5-flash-lite", tokens_in=200, tokens_out=100):
        time.sleep(0.005)
    servicio.cerrar_traza(t1, resultado="resuelta")

    # 2. Traza con PMS (para OP-02)
    t2 = servicio.iniciar_traza("m2", "c2", canal="huespedes")
    with servicio.span(t2, "pms_conector", "consultar_disponibilidad"):
        time.sleep(0.010)
    servicio.cerrar_traza(t2, resultado="resuelta")

    # 3. Traza de vendedor / ARM (para OP-08)
    t3 = servicio.iniciar_traza("m3", "c3", canal="vendedores")
    with servicio.span(t3, "arm_jarvis", "procesar_ticket"):
        time.sleep(0.008)
    servicio.cerrar_traza(t3, resultado="resuelta")

    metricas = servicio.metricas("7d")
    nombres = {m.nombre: m.valor for m in metricas}

    assert "OP-01" in nombres
    assert "OP-02" in nombres
    assert "OP-08" in nombres
    assert "OP-09" in nombres
    assert nombres["OP-01"] >= 0.0
    assert nombres["OP-02"] >= 0.0
    assert nombres["OP-08"] >= 0.0
    assert nombres["OP-09"] >= 0.0


# ¤observabilidad
def test_span_con_traza_desconocida_lanza_error() -> None:
    """Verifica que intentar agregar un span a una traza inexistente lanza TrazaDesconocida."""
    config = dict(cargar_config())
    servicio = ObservabilidadService(config)

    with pytest.raises(TrazaDesconocida):
        with servicio.span("traza_inexistente_123", "seguridad", "accion"):
            pass
