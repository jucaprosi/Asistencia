# ¤observabilidad
# ¤¤devops-engineer
"""Pruebas de cálculo de métricas operativas del PRD (OP-01..OP-10)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from features.observabilidad.metricas_internal import (
    calcular_metricas_prd,
    calcular_op_01,
    calcular_op_02,
    calcular_op_03,
    calcular_op_04,
    calcular_op_05,
    calcular_op_06,
    calcular_op_07,
    calcular_op_08,
    calcular_op_09,
    calcular_op_10,
)
from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.observabilidad.tipos import Span, Traza


# ¤observabilidad
def _crear_traza(
    traza_id: str,
    canal: str = "huespedes",
    duracion_segundos: float = 1.0,
    resultado: str = "resuelta",
    spans: tuple[Span, ...] = (),
    conversacion_id: str = "conv_1",
) -> Traza:
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    fin = inicio + timedelta(seconds=duracion_segundos)
    return Traza(
        traza_id=traza_id,
        mensaje_id=f"msg_{traza_id}",
        conversacion_id=conversacion_id,
        canal=canal,
        inicio=inicio,
        fin=fin,
        resultado=resultado,
        spans=spans,
    )


# ¤observabilidad
def test_op_01_latencia_sin_herramientas() -> None:
    """OP-01: Latencia P95 canal huéspedes sin herramientas (meta ≤ 5 s)."""
    trazas = [
        _crear_traza("t1", canal="huespedes", duracion_segundos=1.0),
        _crear_traza("t2", canal="huespedes", duracion_segundos=2.0),
        _crear_traza("t3", canal="huespedes", duracion_segundos=3.0),
        _crear_traza("t4", canal="huespedes", duracion_segundos=4.0),
    ]
    p95 = calcular_op_01(trazas)
    assert 3.0 <= p95 <= 4.0


# ¤observabilidad
def test_op_02_latencia_con_herramienta_pms() -> None:
    """OP-02: Latencia P95 canal huéspedes con PMS (meta ≤ 10 s)."""
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    span_pms = Span(
        span_id="s_pms",
        traza_id="t_pms",
        sala="pms_conector",
        nombre="consultar_disponibilidad",
        inicio=inicio,
        duracion_ms=5000,
    )
    trazas = [
        _crear_traza("t_sin", canal="huespedes", duracion_segundos=1.0),
        _crear_traza("t_pms", canal="huespedes", duracion_segundos=6.5, spans=(span_pms,)),
    ]
    p95 = calcular_op_02(trazas)
    assert p95 == 6.5


# ¤observabilidad
def test_op_03_tasa_sin_handoff() -> None:
    """OP-03: Tasa de conversaciones de huésped resueltas sin handoff (meta ≥ 60 %)."""
    trazas = [
        _crear_traza("t1", resultado="resuelta"),
        _crear_traza("t2", resultado="resuelta"),
        _crear_traza("t3", resultado="resuelta"),
        _crear_traza("t4", resultado="handoff"),
    ]
    tasa = calcular_op_03(trazas)
    assert tasa == 0.75  # 3 de 4


# ¤observabilidad
def test_op_04_fidelidad_rag() -> None:
    """OP-04: Fidelidad del RAG en spans de conocimiento (meta ≥ 95 %)."""
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    s1 = Span("s1", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"fiel": True})
    s2 = Span("s2", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"fiel": True})
    s3 = Span("s3", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"alucinacion": True})
    s4 = Span("s4", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"fiel": True})

    traza = _crear_traza("t1", spans=(s1, s2, s3, s4))
    fidelidad = calcular_op_04([traza])
    assert fidelidad == 0.75  # 3 de 4


# ¤observabilidad
def test_op_05_abstencion_preguntas_fuera_de_corpus() -> None:
    """OP-05: Tasa de abstención correcta ante preguntas trampa (meta ≥ 90 %)."""
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    s1 = Span("s1", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"pregunta_trampa": True, "se_abstuvo": True})
    s2 = Span("s2", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"pregunta_trampa": True, "se_abstuvo": True})
    s3 = Span("s3", "t1", "conocimiento", "recuperar", inicio, 50, atributos={"fuera_de_corpus": True, "se_abstuvo": False})

    traza = _crear_traza("t1", spans=(s1, s2, s3))
    abstencion = calcular_op_05([traza])
    assert round(abstencion, 2) == 0.67  # 2 de 3


# ¤observabilidad
def test_op_06_adopcion_arm() -> None:
    """OP-06: Vendedores activos reportando por canal ARM (meta ≥ 90 %)."""
    t1 = _crear_traza("t1", canal="vendedores", conversacion_id="vend_1")
    t2 = _crear_traza("t2", canal="vendedores", conversacion_id="vend_2")
    t3 = _crear_traza("t3", canal="vendedores", conversacion_id="vend_3")
    adopcion = calcular_op_06([t1, t2, t3])
    assert adopcion == 1.0


# ¤observabilidad
def test_op_07_parsing_fiable_ventas() -> None:
    """OP-07: Ventas extraídas sin corrección manual (meta ≥ 95 %)."""
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    s1 = Span("s1", "t1", "arm_jarvis", "extraer_venta", inicio, 100, atributos={"correccion_manual": False})
    s2 = Span("s2", "t1", "arm_jarvis", "extraer_venta", inicio, 100, atributos={"correccion_manual": True})
    s3 = Span("s3", "t1", "arm_jarvis", "extraer_venta", inicio, 100, atributos={"correccion_manual": False})
    s4 = Span("s4", "t1", "arm_jarvis", "extraer_venta", inicio, 100, atributos={"correccion_manual": False})

    traza = _crear_traza("t1", canal="vendedores", spans=(s1, s2, s3, s4))
    tasa = calcular_op_07([traza])
    assert tasa == 0.75  # 3 de 4


# ¤observabilidad
def test_op_08_latencia_vendedores_arm() -> None:
    """OP-08: Latencia P95 canal vendedores / ARM (meta ≤ 10 s)."""
    t1 = _crear_traza("t1", canal="vendedores", duracion_segundos=2.0)
    t2 = _crear_traza("t2", canal="vendedores", duracion_segundos=4.0)
    t3 = _crear_traza("t3", canal="vendedores", duracion_segundos=8.0)
    p95 = calcular_op_08([t1, t2, t3])
    assert p95 == 8.0


# ¤observabilidad
def test_op_09_costo_por_conversacion_resuelta() -> None:
    """OP-09: Costo promedio en USD por conversación de huésped resuelta (meta ≤ 0.10 USD)."""
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    s1 = Span("s1", "t1", "agente", "llm", inicio, 200, costo_usd=Decimal("0.040000"))
    s2 = Span("s2", "t2", "agente", "llm", inicio, 200, costo_usd=Decimal("0.060000"))

    t1 = _crear_traza("t1", resultado="resuelta", spans=(s1,))
    t2 = _crear_traza("t2", resultado="resuelta", spans=(s2,))
    t3 = _crear_traza("t3", resultado="error", spans=(s1,))  # no debe incluirse en resueltas

    costo_promedio = calcular_op_09([t1, t2, t3])
    assert costo_promedio == 0.05  # (0.04 + 0.06) / 2


# ¤observabilidad
def test_op_10_inyecciones_exitosas() -> None:
    """OP-10: Inyecciones que logran acción no autorizada (meta = 0)."""
    inicio = datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc)
    s_bloqueado = Span("s1", "t1", "seguridad", "filtrar", inicio, 10, atributos={"ataque_exitoso": False})
    t1 = _crear_traza("t1", resultado="resuelta", spans=(s_bloqueado,))
    assert calcular_op_10([t1]) == 0.0

    t2 = _crear_traza("t2", resultado="inyeccion_exitosa")
    assert calcular_op_10([t1, t2]) == 1.0


# ¤observabilidad
def test_conjunto_completo_op_01_a_10_desde_servicio() -> None:
    """Verifica que ObservabilidadService.metricas(...) calcula todas las OP-01..OP-10."""
    config = dict(cargar_config())
    servicio = ObservabilidadService(config)

    t1 = servicio.iniciar_traza("m1", "c1", canal="huespedes")
    with servicio.span(t1, "seguridad", "filtrar_entrada"):
        pass
    with servicio.span(t1, "agente", "respuesta", modelo="claude-haiku-5-5", tokens_in=500, tokens_out=100):
        pass
    servicio.cerrar_traza(t1, resultado="resuelta")

    metricas = servicio.metricas("7d")
    assert len(metricas) == 10
    mapa = {m.nombre: m for m in metricas}

    for i in range(1, 11):
        codigo = f"OP-{i:02d}"
        assert codigo in mapa, f"Falta métrica {codigo}"
        assert mapa[codigo].valor >= 0.0
