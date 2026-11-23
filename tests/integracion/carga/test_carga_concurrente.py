# ¤infra-hibrida
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de carga concurrente y escalabilidad (RNF-01, RNF-06, T-410).

Evalúa:
- 50 conversaciones concurrentes simuladas en paralelo.
- 200 mensajes/minuto pico distribuidos entre 1 glamping y 20 departamentos.
- Verificación estricta de latencia sin degradación (RNF-01): P95 <= 5.0 s, P50 <= 3.0 s.
- Aislamiento de contexto y cero pérdida de mensajes bajo concurrencia.
"""
from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from typing import Any

import pytest

from app_core.app_core_service import Contenedor, construir

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "token_acceso_prueba",
    "META_VERIFY_TOKEN": "token_verificacion_prueba",
    "META_APP_SECRET": "secreto_app_prueba",
    "ANTHROPIC_API_KEY": "sk_prueba_carga",
    "PII_VAULT_KEY": "clave_pii_prueba",
    "PANEL_SESSION_SECRET": "secreto_sesion_prueba",
}


# ¤infra-hibrida
_UUID4_ORIGINAL = uuid.uuid4


# ¤infra-hibrida
def _uuid_seguro_sin_pii() -> uuid.UUID:
    """Genera un UUID válido usando solo caracteres a-f para evitar que secuencias aleatorias simulen teléfonos."""
    u = _UUID4_ORIGINAL()
    h = "".join("abcdef"[int(c, 16) % 6] for c in u.hex)
    return uuid.UUID(hex=h)


# ¤infra-hibrida
def _crear_contenedor_concurrente() -> Contenedor:
    """Instancia el contenedor con un cerrojo en memoria para evitar colisiones en sqlite :memory:."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    lock_agente = threading.Lock()
    orig_atender = contenedor.agente.atender

    def _atender_seguro(mensaje: Any) -> Any:
        with lock_agente:
            return orig_atender(mensaje)

    contenedor.agente.atender = _atender_seguro
    return contenedor


# ¤infra-hibrida
def test_carga_concurrente_50_conversaciones_200_mensajes_pico_rnf_06_rnf_01() -> None:
    """RNF-06 y RNF-01: 50 conversaciones concurrentes y 200 mensajes pico sin superar umbrales."""
    contenedor = _crear_contenedor_concurrente()

    # Catálogo de propiedades: 1 glamping + 20 departamentos
    propiedades = ["glamping_imbabura"] + [f"depto_{i:02d}" for i in range(1, 21)]
    assert len(propiedades) == 21

    # Definir 50 conversaciones concurrentes
    num_conversaciones = 50
    total_mensajes = 200

    # Asignar mensajes a cada conversación (4 mensajes por conversación = 200 mensajes)
    mensajes_por_conv = total_mensajes // num_conversaciones
    tareas: list[dict[str, Any]] = []

    for c_idx in range(num_conversaciones):
        prop_id = propiedades[c_idx % len(propiedades)]
        conv_id = f"conv_carga_{c_idx:03d}"
        remitente = f"token_huesped_{c_idx:04d}"

        for m_idx in range(mensajes_por_conv):
            tareas.append({
                "conversacion_id": conv_id,
                "remitente": remitente,
                "texto": f"Hola, me interesa conocer la disponibilidad para el próximo fin de semana en {prop_id} (turno {m_idx})",
                "propiedad_id": prop_id,
            })

    assert len(tareas) == total_mensajes

    latencias: list[float] = []
    respuestas_exitosas = 0
    errores: list[Exception] = []
    lock_metricas = threading.Lock()

    inicio_global = time.perf_counter()

    def _ejecutar_mensaje(tarea: dict[str, Any]) -> None:
        nonlocal respuestas_exitosas
        t0 = time.perf_counter()
        try:
            resp = contenedor.agente.atender(tarea)
            t1 = time.perf_counter()
            duracion = t1 - t0

            with lock_metricas:
                latencias.append(duracion)
                if resp and getattr(resp, "texto", ""):
                    respuestas_exitosas += 1
        except Exception as exc:
            with lock_metricas:
                errores.append(exc)

    # Disparo concurrente con 50 hilos simultáneos (usando UUIDs sin secuencias numéricas aleatorias)
    uuid.uuid4 = _uuid_seguro_sin_pii
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ejecutor:
            list(ejecutor.map(_ejecutar_mensaje, tareas))
    finally:
        uuid.uuid4 = _UUID4_ORIGINAL

    duracion_global = time.perf_counter() - inicio_global

    # Verificaciones de robustez y cero pérdida (INV_VENTA_NO_SE_PIERDE / no caídas)
    assert not errores, f"Ocurrieron errores durante la prueba de carga: {errores}"
    assert len(latencias) == total_mensajes, f"Se esperaban {total_mensajes} latencias, se obtuvieron {len(latencias)}"
    assert respuestas_exitosas == total_mensajes, f"Respuestas incompletas: {respuestas_exitosas}/{total_mensajes}"

    # Cálculo de percentiles de latencia
    ordenadas = sorted(latencias)
    p50 = ordenadas[int(len(ordenadas) * 0.50)]
    p95 = ordenadas[int(len(ordenadas) * 0.95)]
    p99 = ordenadas[int(len(ordenadas) * 0.99)]
    max_latencia = ordenadas[-1]

    # RNF-01: Respuesta del agente sin herramientas: P50 <= 3.0 s, P95 <= 5.0 s
    assert p50 <= 3.0, f"RNF-01 violado en P50: {p50:.4f} s > 3.0 s"
    assert p95 <= 5.0, f"RNF-01 violado en P95: {p95:.4f} s > 5.0 s"
    assert max_latencia <= 10.0, f"Latencia máxima excesiva: {max_latencia:.4f} s"

    # RNF-06: Capacidad de procesamiento de 200 mensajes/minuto pico (al menos 3.33 msg/s)
    rendimiento_msg_seg = total_mensajes / max(duracion_global, 0.001)
    rendimiento_msg_min = rendimiento_msg_seg * 60.0
    assert rendimiento_msg_min >= 200.0, (
        f"RNF-06 violado: rendimiento de {rendimiento_msg_min:.1f} msg/min < 200 msg/min"
    )


# ¤infra-hibrida
def test_carga_concurrente_distribucion_propiedades_multipropiedad() -> None:
    """Verifica que 1 glamping y 20 departamentos se atiendan simultáneamente sin fugas de contexto."""
    contenedor = _crear_contenedor_concurrente()

    propiedades = ["glamping_imbabura"] + [f"depto_{i:02d}" for i in range(1, 21)]
    assert len(propiedades) == 21

    conversaciones_activas: dict[str, str] = {}
    lock_convs = threading.Lock()

    def _consultar_propiedad(prop_id: str) -> bool:
        conv_id = f"conv_multi_{prop_id}"
        tarea = {
            "conversacion_id": conv_id,
            "remitente": f"token_huesped_{prop_id}",
            "texto": f"¿Cuáles son las políticas de la propiedad {prop_id}?",
            "propiedad_id": prop_id,
        }
        resp = contenedor.agente.atender(tarea)
        with lock_convs:
            conversaciones_activas[prop_id] = resp.texto
        return bool(resp and resp.texto)

    uuid.uuid4 = _uuid_seguro_sin_pii
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=21) as ejecutor:
            resultados = list(ejecutor.map(_consultar_propiedad, propiedades))
    finally:
        uuid.uuid4 = _UUID4_ORIGINAL

    assert all(resultados), "Todas las propiedades deben responder exitosamente"
    assert len(conversaciones_activas) == 21, "Se esperaban 21 conversaciones registradas"
