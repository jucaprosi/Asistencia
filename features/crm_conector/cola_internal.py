# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Cola persistente de publicaciones con backoff exponencial y ventana de 24 horas (RF-CRM-04, INV_VENTA_NO_SE_PIERDE)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from features.crm_conector.http_internal import AdaptadorHttpCRM
from features.crm_conector.tipos import PublicacionVenta

__all__ = [
    "calcular_proximo_intento",
    "obtener_publicacion",
    "procesar_cola_reintentos",
    "registrar_o_recuperar_publicacion",
    "reintentar_publicacion_manual",
]

BACKOFF_DEFECTO = [30, 120, 600, 3600]


# ¤crm-conector
def calcular_proximo_intento(
    intentos: int,
    backoff_s: list[int] | None = None,
    ahora: datetime | None = None,
) -> datetime:
    """Calcula la próxima fecha de reintento según el esquema de backoff exponencial."""
    lista_backoff = backoff_s or BACKOFF_DEFECTO
    indice = min(max(0, intentos - 1), len(lista_backoff) - 1)
    segundos = lista_backoff[indice]
    base = ahora or datetime.now(timezone.utc)
    return base + timedelta(seconds=segundos)


# ¤crm-conector
def registrar_o_recuperar_publicacion(
    conexion: sqlite3.Connection,
    venta_id: str,
    evento: str,
    payload: Mapping[str, Any],
) -> tuple[PublicacionVenta, bool]:
    """Registra de forma idempotente (INV_VENTA_FIRMADA_IDEMPOTENTE) la publicación en crm.publicaciones.

    Retorna (PublicacionVenta, es_nueva).
    """
    ahora_iso = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(dict(payload), ensure_ascii=False)

    # Intentar inserción idempotente
    with conexion:
        cursor = conexion.execute(
            """
            INSERT INTO crm.publicaciones (
                venta_id, evento, payload_json, estado, intentos, ultima_respuesta, proximo_intento, creado_en
            ) VALUES (?, ?, ?, 'pendiente', 0, NULL, NULL, ?)
            ON CONFLICT DO NOTHING
            """,
            (venta_id, evento, payload_json, ahora_iso),
        )
        es_nueva = cursor.rowcount > 0

    pub = obtener_publicacion(conexion, venta_id, evento)
    if not pub:
        raise RuntimeError(f"No se pudo recuperar la publicación {venta_id}:{evento}")
    return pub, es_nueva


# ¤crm-conector
def obtener_publicacion(
    conexion: sqlite3.Connection,
    venta_id: str,
    evento: str,
) -> PublicacionVenta | None:
    """Recupera una publicación por su clave primaria (venta_id, evento)."""
    cursor = conexion.execute(
        """
        SELECT venta_id, estado, intentos, ultima_respuesta, proximo_intento
        FROM crm.publicaciones
        WHERE venta_id = ? AND evento = ?
        """,
        (venta_id, evento),
    )
    fila = cursor.fetchone()
    if not fila:
        return None

    prox = datetime.fromisoformat(fila["proximo_intento"]) if fila["proximo_intento"] else None
    return PublicacionVenta(
        venta_id=fila["venta_id"],
        estado=fila["estado"],
        intentos=fila["intentos"],
        ultima_respuesta=fila["ultima_respuesta"],
        proximo_intento=prox,
    )


# ¤crm-conector
def reintentar_publicacion_manual(
    conexion: sqlite3.Connection,
    venta_id: str,
    evento: str,
    adaptador: AdaptadorHttpCRM,
) -> PublicacionVenta:
    """Fuerza un reintento manual inmediato de una publicación en estado de error o pendiente."""
    cursor = conexion.execute(
        "SELECT payload_json, intentos FROM crm.publicaciones WHERE venta_id = ? AND evento = ?",
        (venta_id, evento),
    )
    fila = cursor.fetchone()
    if not fila:
        raise RuntimeError(f"Publicación {venta_id}:{evento} no encontrada para reintento manual.")

    payload = json.loads(fila["payload_json"])
    intentos = fila["intentos"] + 1

    try:
        codigo, respuesta = adaptador.enviar_publicacion(payload)
        with conexion:
            conexion.execute(
                """
                UPDATE crm.publicaciones
                SET estado = 'ok', intentos = ?, ultima_respuesta = ?, proximo_intento = NULL
                WHERE venta_id = ? AND evento = ?
                """,
                (intentos, f"{codigo} OK: {respuesta}", venta_id, evento),
            )
    except Exception as exc:
        with conexion:
            conexion.execute(
                """
                UPDATE crm.publicaciones
                SET estado = 'error', intentos = ?, ultima_respuesta = ?
                WHERE venta_id = ? AND evento = ?
                """,
                (intentos, f"Error manual: {exc}", venta_id, evento),
            )

    pub = obtener_publicacion(conexion, venta_id, evento)
    if not pub:
        raise RuntimeError("No se pudo obtener la publicación tras el reintento manual.")
    return pub


# ¤crm-conector
def procesar_cola_reintentos(
    conexion: sqlite3.Connection,
    adaptador: AdaptadorHttpCRM,
    observabilidad: Any = None,
    config: Mapping[str, Any] | None = None,
    ahora: datetime | None = None,
) -> int:
    """Procesa publicaciones pendientes respetando el backoff y la ventana de 24 horas (RF-CRM-04)."""
    ahora_dt = ahora or datetime.now(timezone.utc)
    ahora_iso = ahora_dt.isoformat()

    cola_cfg = (config or {}).get("cola", {})
    backoff_s = cola_cfg.get("backoff_s", BACKOFF_DEFECTO)
    max_horas = float(cola_cfg.get("max_horas", 24))

    cursor = conexion.execute(
        """
        SELECT venta_id, evento, payload_json, estado, intentos, creado_en
        FROM crm.publicaciones
        WHERE estado = 'pendiente'
          AND (proximo_intento IS NULL OR proximo_intento <= ?)
        ORDER BY creado_en ASC
        """,
        (ahora_iso,),
    )
    filas = cursor.fetchall()
    procesadas_con_exito = 0

    for fila in filas:
        venta_id = fila["venta_id"]
        evento = fila["evento"]
        payload = json.loads(fila["payload_json"])
        intentos = fila["intentos"] + 1
        creado_en = datetime.fromisoformat(fila["creado_en"])

        tiempo_transcurrido = (ahora_dt - creado_en).total_seconds()
        if tiempo_transcurrido >= max_horas * 3600.0:
            # Ventana de 24 horas agotada: queda como 'error' (no_publicada) y dispara alerta crítica
            # INV_VENTA_NO_SE_PIERDE: nunca se borra de la tabla
            with conexion:
                conexion.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'error', intentos = ?, ultima_respuesta = 'Ventana de 24h agotada', proximo_intento = NULL
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, venta_id, evento),
                )
            if observabilidad:
                if hasattr(observabilidad, "disparar_alerta"):
                    observabilidad.disparar_alerta(
                        "VENTA_NO_PUBLICADA",
                        "critica",
                        f"Venta {venta_id} ({evento}) no pudo ser aceptada por el CRM tras 24 horas.",
                    )
                if hasattr(observabilidad, "log"):
                    observabilidad.log(
                        "ERROR",
                        "VENTA_NO_PUBLICADA",
                        venta_id=venta_id,
                        evento_crm=evento,
                        mensaje=f"Venta {venta_id} ({evento}) no pudo ser aceptada por el CRM tras 24 horas.",
                    )
            continue

        try:
            codigo, respuesta = adaptador.enviar_publicacion(payload)
            with conexion:
                conexion.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'ok', intentos = ?, ultima_respuesta = ?, proximo_intento = NULL
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, f"{codigo} OK: {respuesta}", venta_id, evento),
                )
            procesadas_con_exito += 1
        except Exception as exc:
            prox_intento = calcular_proximo_intento(intentos, backoff_s, ahora=ahora_dt)
            with conexion:
                conexion.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'pendiente', intentos = ?, ultima_respuesta = ?, proximo_intento = ?
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, str(exc), prox_intento.isoformat(), venta_id, evento),
                )

    return procesadas_con_exito
