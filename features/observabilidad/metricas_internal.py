# ¤observabilidad
# ¤¤devops-engineer
"""Cálculo de métricas operativas del PRD (OP-01..OP-10) directamente desde trazas y spans."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from features.observabilidad.tipos import Metrica, Traza

__all__ = [
    "calcular_metricas_prd",
    "calcular_op_01",
    "calcular_op_02",
    "calcular_op_03",
    "calcular_op_04",
    "calcular_op_05",
    "calcular_op_06",
    "calcular_op_07",
    "calcular_op_08",
    "calcular_op_09",
    "calcular_op_10",
]


# ¤observabilidad
def _duracion_segundos(traza: Traza) -> float:
    if traza.fin and traza.inicio:
        return max(0.0, (traza.fin - traza.inicio).total_seconds())
    return sum(s.duracion_ms for s in traza.spans) / 1000.0


# ¤observabilidad
def _p95(valores: Sequence[float]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    idx = int(0.95 * len(ordenados))
    return ordenados[min(idx, len(ordenados) - 1)]


# ¤observabilidad
def calcular_op_01(trazas: Sequence[Traza]) -> float:
    """OP-01: Latencia P95 en canal huéspedes sin herramientas (meta ≤ 5 s)."""
    latencias: list[float] = []
    for t in trazas:
        if t.canal != "vendedores":
            salas = {s.sala for s in t.spans}
            if "pms_conector" not in salas and "herramientas_glamping" not in salas:
                latencias.append(_duracion_segundos(t))
    return round(_p95(latencias), 3)


# ¤observabilidad
def calcular_op_02(trazas: Sequence[Traza]) -> float:
    """OP-02: Latencia P95 con herramienta PMS (meta ≤ 10 s)."""
    latencias: list[float] = []
    for t in trazas:
        salas = {s.sala for s in t.spans}
        if "pms_conector" in salas:
            latencias.append(_duracion_segundos(t))
    return round(_p95(latencias), 3)


# ¤observabilidad
def calcular_op_03(trazas: Sequence[Traza]) -> float:
    """OP-03: Tasa de conversaciones de huésped resueltas sin handoff (meta ≥ 60 %)."""
    huespedes = [t for t in trazas if t.canal != "vendedores"]
    if not huespedes:
        return 1.0
    sin_handoff = [t for t in huespedes if t.resultado != "handoff"]
    return round(len(sin_handoff) / len(huespedes), 4)


# ¤observabilidad
def calcular_op_04(trazas: Sequence[Traza]) -> float:
    """OP-04: Fidelidad del RAG en spans de conocimiento (meta ≥ 95 %)."""
    spans_rag = [s for t in trazas for s in t.spans if s.sala == "conocimiento"]
    if not spans_rag:
        return 1.0
    fieles = 0
    for s in spans_rag:
        es_fiel = s.atributos.get("fiel", s.atributos.get("es_fiel", True))
        alucinacion = s.atributos.get("alucinacion", False)
        fidelidad_val = float(s.atributos.get("fidelidad", 1.0))
        if es_fiel and not alucinacion and fidelidad_val >= 0.95:
            fieles += 1
    return round(fieles / len(spans_rag), 4)


# ¤observabilidad
def calcular_op_05(trazas: Sequence[Traza]) -> float:
    """OP-05: Tasa de abstención correcta ante preguntas fuera de corpus (meta ≥ 90 %)."""
    spans_trampa = [
        s for t in trazas for s in t.spans
        if s.sala == "conocimiento" and (s.atributos.get("fuera_de_corpus") or s.atributos.get("pregunta_trampa"))
    ]
    if not spans_trampa:
        return 1.0
    abstenciones = 0
    for s in spans_trampa:
        se_abstuvo = s.atributos.get("se_abstuvo", s.atributos.get("abstencion", True))
        if se_abstuvo:
            abstenciones += 1
    return round(abstenciones / len(spans_trampa), 4)


# ¤observabilidad
def calcular_op_06(trazas: Sequence[Traza]) -> float:
    """OP-06: Adopción del ARM: vendedores activos reportando por canal ARM (meta ≥ 90 %)."""
    vendedores_arm: set[str] = set()
    vendedores_totales: set[str] = set()

    for t in trazas:
        vendedor_id = t.conversacion_id or t.mensaje_id
        if t.canal == "vendedores" or any(s.sala == "arm_jarvis" for s in t.spans):
            if vendedor_id:
                vendedores_arm.add(vendedor_id)
                vendedores_totales.add(vendedor_id)
        for s in t.spans:
            if "total_vendedores" in s.atributos:
                total_attr = int(s.atributos["total_vendedores"])
                if total_attr > len(vendedores_totales):
                    return round(len(vendedores_arm) / total_attr, 4)

    if not vendedores_totales:
        return 1.0
    return round(len(vendedores_arm) / len(vendedores_totales), 4)


# ¤observabilidad
def calcular_op_07(trazas: Sequence[Traza]) -> float:
    """OP-07: Parsing fiable: ventas extraídas sin corrección manual (meta ≥ 95 %)."""
    spans_ventas = [
        s for t in trazas for s in t.spans
        if s.sala == "arm_jarvis" and (s.atributos.get("venta_extraida") or s.nombre in ("extraer_venta", "procesar_ticket"))
    ]
    if not spans_ventas:
        return 1.0
    sin_correccion = 0
    for s in spans_ventas:
        corregida = s.atributos.get("correccion_manual", False)
        if not corregida:
            sin_correccion += 1
    return round(sin_correccion / len(spans_ventas), 4)


# ¤observabilidad
def calcular_op_08(trazas: Sequence[Traza]) -> float:
    """OP-08: Confirmación inmediata al vendedor: latencia P95 canal ARM (meta ≤ 10 s)."""
    latencias: list[float] = []
    for t in trazas:
        salas = {s.sala for s in t.spans}
        if t.canal == "vendedores" or "arm_jarvis" in salas:
            latencias.append(_duracion_segundos(t))
    return round(_p95(latencias), 3)


# ¤observabilidad
def calcular_op_09(trazas: Sequence[Traza]) -> float:
    """OP-09: Costo de modelo en USD por conversación de huésped resuelta (meta ≤ 0.10 USD)."""
    costos_resueltas: list[float] = []
    for t in trazas:
        if t.canal != "vendedores" and t.resultado == "resuelta":
            costo_traza = sum(float(s.costo_usd or 0) for s in t.spans)
            costos_resueltas.append(costo_traza)
    if not costos_resueltas:
        return 0.0
    return round(sum(costos_resueltas) / len(costos_resueltas), 6)


# ¤observabilidad
def calcular_op_10(trazas: Sequence[Traza]) -> float:
    """OP-10: Ataques de inyección que logran acción no autorizada (meta = 0)."""
    ataques_exitosos = 0
    for t in trazas:
        if t.resultado in ("inyeccion_exitosa", "ataque_exitoso"):
            ataques_exitosos += 1
        for s in t.spans:
            if s.atributos.get("ataque_exitoso", False) or s.atributos.get("inyeccion_exitosa", False):
                ataques_exitosos += 1
    return float(ataques_exitosos)


# ¤observabilidad
def calcular_metricas_prd(
    trazas: Sequence[Traza],
    ventana: str = "7d",
    ahora: datetime | None = None,
) -> tuple[Metrica, ...]:
    """Calcula el conjunto completo OP-01..OP-10 a partir de las trazas proporcionadas."""
    instante = ahora or datetime.now(timezone.utc)
    return (
        Metrica(nombre="OP-01", valor=calcular_op_01(trazas), unidad="s", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-02", valor=calcular_op_02(trazas), unidad="s", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-03", valor=calcular_op_03(trazas), unidad="ratio", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-04", valor=calcular_op_04(trazas), unidad="ratio", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-05", valor=calcular_op_05(trazas), unidad="ratio", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-06", valor=calcular_op_06(trazas), unidad="ratio", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-07", valor=calcular_op_07(trazas), unidad="ratio", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-08", valor=calcular_op_08(trazas), unidad="s", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-09", valor=calcular_op_09(trazas), unidad="USD", ventana=ventana, calculada_en=instante),
        Metrica(nombre="OP-10", valor=calcular_op_10(trazas), unidad="conteo", ventana=ventana, calculada_en=instante),
    )
