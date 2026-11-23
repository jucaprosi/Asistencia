# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Memoria y persistencia de conversaciones de la sala agente (RF-AG-06, esquema agente)."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from features.agente.tipos import ContextoConversacion, MensajeMemoria, ModoAgente
from features.persistencia_sql.persistencia_sql_service import envolver

__all__ = ["MemoriaConversacion"]


# ¤agente-enrutador
def _formatear_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ¤agente-enrutador
def _parsear_dt(cadena: str | None) -> datetime | None:
    if not cadena:
        return None
    try:
        return datetime.fromisoformat(cadena)
    except ValueError:
        return None


# ¤agente-enrutador
class MemoriaConversacion:
    """Gestiona el estado y los mensajes redactados de PII según el esquema agente (INV_PII_FUERA_DEL_MODELO)."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None or str(db_path) == ":memory:":
            # None: DATABASE_URL (PostgreSQL, esquema agente) o SQLite en memoria; ":memory:" fuerza SQLite.
            self._ruta_db = ":memory:"
            self._con_memoria: Any = envolver(None if db_path is None else ":memory:", ruta_busqueda="agente")
        else:
            self._ruta_db = str(db_path)
            self._con_memoria = None
            Path(self._ruta_db).parent.mkdir(parents=True, exist_ok=True)
        if not getattr(self._con_memoria, "es_postgres", False):
            self._inicializar_tablas()  # en PostgreSQL el esquema lo aplica scripts/migrar_db.py

    # ¤agente-enrutador
    @contextmanager
    def _obtener_conexion(self) -> Iterator[sqlite3.Connection]:
        if self._con_memoria is not None:
            with self._con_memoria:
                yield self._con_memoria
        else:
            con = sqlite3.connect(self._ruta_db)
            con.execute("PRAGMA foreign_keys = ON;")
            try:
                with con:
                    yield con
            finally:
                con.close()

    # ¤agente-enrutador
    def cerrar(self) -> None:
        if self._con_memoria is not None:
            self._con_memoria.close()
            self._con_memoria = None

    def _inicializar_tablas(self) -> None:
        with self._obtener_conexion() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversaciones (
                  conversacion_id  TEXT PRIMARY KEY,
                  identidad_token  TEXT NOT NULL,
                  rol              TEXT NOT NULL DEFAULT 'huesped_potencial',
                  canal            TEXT NOT NULL CHECK (canal IN ('huespedes','vendedores')),
                  propiedad_id     TEXT,
                  estado           TEXT NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa','handoff','cerrada')),
                  modo             TEXT NOT NULL DEFAULT 'activo' CHECK (modo IN ('activo','silencio')),
                  resultado        TEXT CHECK (resultado IN ('resuelta','handoff','abandonada')),
                  abstenciones_seguidas INTEGER NOT NULL DEFAULT 0 CHECK (abstenciones_seguidas >= 0),
                  ventana_24h_hasta TEXT,
                  creada           TEXT NOT NULL,
                  actualizada      TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mensajes (
                  mensaje_id       TEXT PRIMARY KEY,
                  conversacion_id  TEXT NOT NULL REFERENCES conversaciones(conversacion_id),
                  direccion        TEXT NOT NULL CHECK (direccion IN ('in','out')),
                  tipo             TEXT NOT NULL,
                  contenido_token  TEXT NOT NULL,
                  traza_id         TEXT,
                  instante         TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cache_semantico (
                  hash_consulta    TEXT PRIMARY KEY,
                  embedding        TEXT NOT NULL,
                  respuesta        TEXT NOT NULL,
                  creado_en        TEXT NOT NULL,
                  expira_en        TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS envios_programados (
                  codigo_reserva   TEXT NOT NULL,
                  plantilla        TEXT NOT NULL,
                  fecha            TEXT NOT NULL,
                  mensaje_id       TEXT,
                  creado_en        TEXT NOT NULL,
                  PRIMARY KEY (codigo_reserva, plantilla, fecha)
                );
                """
            )

    # ¤agente-enrutador
    def guardar_conversacion(
        self,
        contexto: ContextoConversacion,
        canal: str = "huespedes",
        estado: str = "activa",
        resultado: str | None = None,
    ) -> None:
        ahora = datetime.now(timezone.utc).isoformat()
        v24 = _formatear_dt(contexto.ventana_24h_hasta)
        with self._obtener_conexion() as con:
            con.execute(
                """
                INSERT INTO conversaciones (
                    conversacion_id, identidad_token, rol, canal, propiedad_id, estado, modo, resultado,
                    abstenciones_seguidas, ventana_24h_hasta, creada, actualizada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                ON CONFLICT(conversacion_id) DO UPDATE SET
                    propiedad_id = excluded.propiedad_id,
                    estado = excluded.estado,
                    modo = excluded.modo,
                    resultado = excluded.resultado,
                    actualizada = excluded.actualizada;
                """,
                (
                    contexto.conversacion_id,
                    contexto.identidad_token,
                    contexto.rol,
                    canal,
                    contexto.propiedad_id,
                    estado,
                    contexto.modo.value if isinstance(contexto.modo, ModoAgente) else str(contexto.modo),
                    resultado,
                    v24,
                    ahora,
                    ahora,
                ),
            )

    # ¤agente-enrutador
    def obtener_conversacion(self, conversacion_id: str) -> ContextoConversacion | None:
        with self._obtener_conexion() as con:
            cur = con.execute(
                """
                SELECT conversacion_id, identidad_token, rol, propiedad_id, modo, ventana_24h_hasta
                FROM conversaciones
                WHERE conversacion_id = ?;
                """,
                (conversacion_id,),
            )
            fila = cur.fetchone()
            if not fila:
                return None
            cid, itoken, rol, prop_id, modo_str, v24_str = fila
            return ContextoConversacion(
                conversacion_id=cid,
                identidad_token=itoken,
                rol=rol,
                propiedad_id=prop_id,
                modo=ModoAgente(modo_str) if modo_str in ModoAgente._value2member_map_ else ModoAgente.ACTIVO,
                ventana_24h_hasta=_parsear_dt(v24_str),
            )

    # ¤agente-enrutador
    def actualizar_modo(self, conversacion_id: str, modo: ModoAgente) -> None:
        ahora = datetime.now(timezone.utc).isoformat()
        with self._obtener_conexion() as con:
            con.execute(
                "UPDATE conversaciones SET modo = ?, actualizada = ? WHERE conversacion_id = ?;",
                (modo.value if isinstance(modo, ModoAgente) else str(modo), ahora, conversacion_id),
            )

    # ¤agente-enrutador
    def actualizar_propiedad(self, conversacion_id: str, propiedad_id: str) -> None:
        ahora = datetime.now(timezone.utc).isoformat()
        with self._obtener_conexion() as con:
            con.execute(
                "UPDATE conversaciones SET propiedad_id = ?, actualizada = ? WHERE conversacion_id = ?;",
                (propiedad_id, ahora, conversacion_id),
            )

    # ¤agente-enrutador
    def guardar_mensaje(
        self,
        mensaje_id: str,
        conversacion_id: str,
        direccion: Literal["in", "out"],
        tipo: str,
        contenido_token: str,
        traza_id: str | None = None,
        instante: datetime | None = None,
    ) -> None:
        """Persiste un mensaje en agente.mensajes redactado de PII (INV_PII_FUERA_DEL_MODELO)."""
        dt = instante or datetime.now(timezone.utc)
        dt_str = _formatear_dt(dt)
        with self._obtener_conexion() as con:
            con.execute(
                """
                INSERT INTO mensajes (
                    mensaje_id, conversacion_id, direccion, tipo, contenido_token, traza_id, instante
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (mensaje_id, conversacion_id, direccion, tipo, contenido_token, traza_id, dt_str),
            )

    # ¤agente-enrutador
    def obtener_historial(
        self,
        conversacion_id: str,
        limite: int = 30,
        horas: int = 24,
    ) -> list[MensajeMemoria]:
        """Recupera los últimos N mensajes (máx 30) dentro de la ventana de horas (máx 24h)."""
        limite_tiempo = datetime.now(timezone.utc) - timedelta(hours=horas)
        limite_str = _formatear_dt(limite_tiempo)

        with self._obtener_conexion() as con:
            cur = con.execute(
                """
                SELECT mensaje_id, conversacion_id, direccion, tipo, contenido_token, traza_id, instante
                FROM mensajes
                WHERE conversacion_id = ? AND instante >= ?
                ORDER BY instante DESC
                LIMIT ?;
                """,
                (conversacion_id, limite_str, limite),
            )
            filas = cur.fetchall()

        # Invertir para orden cronológico ascendente
        resultado: list[MensajeMemoria] = []
        for mid, cid, direccion, tipo, ctoken, traza, inst_str in reversed(filas):
            resultado.append(
                MensajeMemoria(
                    mensaje_id=mid,
                    conversacion_id=cid,
                    direccion=direccion,
                    tipo=tipo,
                    contenido_token=ctoken,
                    traza_id=traza,
                    instante=_parsear_dt(inst_str) or datetime.now(timezone.utc),
                )
            )
        return resultado

    # ¤agente-enrutador
    def registrar_envio_programado(
        self,
        codigo_reserva: str,
        plantilla: str,
        fecha: str,
        mensaje_id: str | None = None,
    ) -> bool:
        """Intenta registrar el envío programado. Retorna True si se insertó, False si ya existía (INV_ENVIO_UNICO)."""
        ahora = datetime.now(timezone.utc).isoformat()
        with self._obtener_conexion() as con:
            cur = con.execute(
                """
                INSERT INTO envios_programados (codigo_reserva, plantilla, fecha, mensaje_id, creado_en)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(codigo_reserva, plantilla, fecha) DO NOTHING;
                """,
                (codigo_reserva, plantilla, fecha, mensaje_id, ahora),
            )
            return cur.rowcount > 0

    # ¤agente-enrutador
    def ya_enviado(self, codigo_reserva: str, plantilla: str, fecha: str) -> bool:
        """Verifica si ya fue enviado."""
        with self._obtener_conexion() as con:
            cur = con.execute(
                "SELECT 1 FROM envios_programados WHERE codigo_reserva = ? AND plantilla = ? AND fecha = ?;",
                (codigo_reserva, plantilla, fecha),
            )
            return cur.fetchone() is not None

    # ¤agente-enrutador
    def obtener_historial_para_modelo(
        self,
        conversacion_id: str,
        limite: int = 30,
        horas: int = 24,
    ) -> list[dict[str, str]]:
        mensajes = self.obtener_historial(conversacion_id, limite=limite, horas=horas)
        return [
            {
                "role": "user" if m.direccion == "in" else "assistant",
                "content": m.contenido_token,
            }
            for m in mensajes
        ]
