# ¤canal-whatsapp
# ¤¤integration-engineer
"""Persistencia del esquema canal (eventos_entrantes, mensajes_meta, plantillas, medios)."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import uuid4

from features.persistencia_sql.persistencia_sql_service import Conexion, abrir_conexion
from features.canal_whatsapp.tipos import (
    Canal, EventoEntrante, MedioMeta, MensajeMeta, PlantillaMeta,
)

DDL_CANAL = """
CREATE TABLE IF NOT EXISTS canal.eventos_entrantes (
  evento_id          TEXT PRIMARY KEY,
  mensaje_id         TEXT NOT NULL UNIQUE,
  conversacion_clave TEXT NOT NULL,
  cuerpo_cifrado     BLOB NOT NULL,
  estado             TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','procesando','procesado','muerto')),
  intentos           INTEGER NOT NULL DEFAULT 0 CHECK (intentos >= 0),
  recibido_en        TEXT NOT NULL,
  procesado_en       TEXT
);

CREATE TABLE IF NOT EXISTS canal.mensajes_meta (
  mensaje_id         TEXT PRIMARY KEY,
  direccion          TEXT NOT NULL CHECK (direccion IN ('in','out')),
  remitente_token    TEXT NOT NULL,
  canal              TEXT NOT NULL CHECK (canal IN ('huespedes','vendedores')),
  tipo               TEXT NOT NULL CHECK (tipo IN ('texto','plantilla','medio','boton','ubicacion')),
  estado             TEXT NOT NULL CHECK (estado IN ('recibido','sent','delivered','read','failed')),
  plantilla          TEXT,
  enviado_en         TEXT NOT NULL,
  actualizado_en     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canal.plantillas (
  nombre             TEXT PRIMARY KEY,
  idioma             TEXT NOT NULL DEFAULT 'es',
  categoria          TEXT NOT NULL CHECK (categoria IN ('utility','authentication','marketing')),
  variables_csv      TEXT NOT NULL DEFAULT '',
  aprobada           INTEGER NOT NULL DEFAULT 0,
  actualizada_en     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canal.medios (
  medio_id           TEXT PRIMARY KEY,
  mensaje_id         TEXT,
  medio_ref          TEXT NOT NULL,
  tipo               TEXT NOT NULL CHECK (tipo IN ('imagen','audio','documento','ubicacion')),
  bytes              INTEGER NOT NULL CHECK (bytes >= 0),
  expira_en          TEXT NOT NULL,
  FOREIGN KEY (mensaje_id) REFERENCES mensajes_meta(mensaje_id)
);
"""


# ¤canal-whatsapp
def parsear_iso(cadena: str | None) -> datetime | None:
    """Convierte cadena ISO a datetime con timezone UTC si no la tiene."""
    if not cadena:
        return None
    dt = datetime.fromisoformat(cadena)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ¤canal-whatsapp
def formatear_iso(dt: datetime | None) -> str | None:
    """Serializa datetime a ISO-8601 UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ¤canal-whatsapp
class RepositorioCanal:
    """Repositorio thread-safe para las tablas del esquema canal."""

    def __init__(self, conexion: Conexion | sqlite3.Connection | str | None = None) -> None:
        self._lock = threading.RLock()
        if conexion is None or isinstance(conexion, str):
            # None: DATABASE_URL (PostgreSQL) o SQLite en memoria; str: URL o ruta SQLite explícita.
            self._conexion: Any = abrir_conexion(conexion, esquemas=("canal",))
        elif isinstance(conexion, sqlite3.Connection):
            self._conexion = Conexion.desde_sqlite(conexion, esquemas=("canal",))
        else:
            self._conexion = conexion
        self._inicializar_esquema()

    def _inicializar_esquema(self) -> None:
        with self._lock:
            self._conexion.asegurar_esquema(DDL_CANAL)

    def guardar_evento(
        self,
        mensaje_id: str,
        conversacion_clave: str,
        cuerpo_cifrado: bytes,
        *,
        evento_id: str | None = None,
        estado: str = "pendiente",
        intentos: int = 0,
        recibido_en: datetime | None = None,
    ) -> bool:
        """INV_INGESTA_DURABLE: INSERT ... ON CONFLICT (mensaje_id) DO NOTHING."""
        evento_id = evento_id or str(uuid4())
        recibido_en_iso = formatear_iso(recibido_en or datetime.now(timezone.utc))
        consulta = """
        INSERT INTO canal.eventos_entrantes
          (evento_id, mensaje_id, conversacion_clave, cuerpo_cifrado, estado, intentos, recibido_en, procesado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT (mensaje_id) DO NOTHING;
        """
        with self._lock:
            cursor = self._conexion.execute(
                consulta,
                (evento_id, mensaje_id, conversacion_clave, cuerpo_cifrado, estado, intentos, recibido_en_iso),
            )
            self._conexion.commit()
            return cursor.rowcount > 0

    def obtener_evento(self, mensaje_id: str) -> EventoEntrante | None:
        consulta = "SELECT * FROM canal.eventos_entrantes WHERE mensaje_id = ?;"
        with self._lock:
            fila = self._conexion.execute(consulta, (mensaje_id,)).fetchone()
            if not fila:
                return None
            return self._fila_a_evento(fila)

    def obtener_evento_por_id(self, evento_id: str) -> EventoEntrante | None:
        consulta = "SELECT * FROM canal.eventos_entrantes WHERE evento_id = ?;"
        with self._lock:
            fila = self._conexion.execute(consulta, (evento_id,)).fetchone()
            if not fila:
                return None
            return self._fila_a_evento(fila)

    def actualizar_estado_evento(
        self,
        evento_id: str,
        estado: str,
        *,
        intentos: int | None = None,
        procesado_en: datetime | None = None,
    ) -> None:
        campos = ["estado = ?"]
        valores: list[Any] = [estado]
        if intentos is not None:
            campos.append("intentos = ?")
            valores.append(intentos)
        if procesado_en is not None:
            campos.append("procesado_en = ?")
            valores.append(formatear_iso(procesado_en))
        valores.append(evento_id)
        consulta = f"UPDATE canal.eventos_entrantes SET {', '.join(campos)} WHERE evento_id = ?;"
        with self._lock:
            self._conexion.execute(consulta, tuple(valores))
            self._conexion.commit()

    def obtener_eventos_pendientes(self) -> list[EventoEntrante]:
        consulta = "SELECT * FROM canal.eventos_entrantes WHERE estado = 'pendiente' ORDER BY recibido_en ASC;"
        with self._lock:
            filas = self._conexion.execute(consulta).fetchall()
            return [self._fila_a_evento(f) for f in filas]

    def obtener_eventos_procesando(self) -> list[EventoEntrante]:
        consulta = "SELECT * FROM canal.eventos_entrantes WHERE estado = 'procesando' ORDER BY recibido_en ASC;"
        with self._lock:
            filas = self._conexion.execute(consulta).fetchall()
            return [self._fila_a_evento(f) for f in filas]

    def guardar_mensaje_meta(
        self,
        mensaje_id: str,
        direccion: str,
        remitente_token: str,
        canal: Canal | str,
        tipo: str,
        estado: str,
        *,
        plantilla: str | None = None,
        enviado_en: datetime | None = None,
        actualizado_en: datetime | None = None,
    ) -> None:
        canal_val = canal.value if isinstance(canal, Canal) else canal
        ahora_iso = formatear_iso(datetime.now(timezone.utc))
        enviado_iso = formatear_iso(enviado_en) if enviado_en else ahora_iso
        actualizado_iso = formatear_iso(actualizado_en) if actualizado_en else ahora_iso
        consulta = """
        INSERT INTO canal.mensajes_meta
          (mensaje_id, direccion, remitente_token, canal, tipo, estado, plantilla, enviado_en, actualizado_en)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (mensaje_id) DO UPDATE SET
          estado = excluded.estado,
          actualizado_en = excluded.actualizado_en;
        """
        with self._lock:
            self._conexion.execute(
                consulta,
                (mensaje_id, direccion, remitente_token, canal_val, tipo, estado, plantilla, enviado_iso, actualizado_iso),
            )
            self._conexion.commit()

    def actualizar_estado_mensaje(self, mensaje_id: str, estado: str, actualizado_en: datetime | None = None) -> None:
        actualizado_iso = formatear_iso(actualizado_en or datetime.now(timezone.utc))
        consulta = "UPDATE canal.mensajes_meta SET estado = ?, actualizado_en = ? WHERE mensaje_id = ?;"
        with self._lock:
            self._conexion.execute(consulta, (estado, actualizado_iso, mensaje_id))
            self._conexion.commit()

    def obtener_mensaje_meta(self, mensaje_id: str) -> MensajeMeta | None:
        consulta = "SELECT * FROM canal.mensajes_meta WHERE mensaje_id = ?;"
        with self._lock:
            fila = self._conexion.execute(consulta, (mensaje_id,)).fetchone()
            if not fila:
                return None
            return MensajeMeta(
                mensaje_id=fila["mensaje_id"],
                direccion=fila["direccion"],
                remitente_token=fila["remitente_token"],
                canal=Canal(fila["canal"]),
                tipo=fila["tipo"],
                estado=fila["estado"],
                plantilla=fila["plantilla"],
                enviado_en=parsear_iso(fila["enviado_en"]),  # type: ignore[arg-type]
                actualizado_en=parsear_iso(fila["actualizado_en"]),  # type: ignore[arg-type]
            )

    def ultimo_mensaje_entrante(self, remitente_token: str) -> datetime | None:
        consulta = """
        SELECT max(enviado_en) as ultimo FROM canal.mensajes_meta
        WHERE remitente_token = ? AND direccion = 'in';
        """
        with self._lock:
            fila = self._conexion.execute(consulta, (remitente_token,)).fetchone()
            if fila and fila["ultimo"]:
                return parsear_iso(fila["ultimo"])
        return None

    def guardar_plantilla(
        self,
        nombre: str,
        categoria: str,
        variables: Sequence[str] = (),
        *,
        idioma: str = "es",
        aprobada: bool = False,
        actualizada_en: datetime | None = None,
    ) -> None:
        vars_csv = ",".join(variables)
        actualizada_iso = formatear_iso(actualizada_en or datetime.now(timezone.utc))
        consulta = """
        INSERT INTO canal.plantillas
          (nombre, idioma, categoria, variables_csv, aprobada, actualizada_en)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (nombre) DO UPDATE SET
          idioma = excluded.idioma,
          categoria = excluded.categoria,
          variables_csv = excluded.variables_csv,
          aprobada = excluded.aprobada,
          actualizada_en = excluded.actualizada_en;
        """
        with self._lock:
            self._conexion.execute(
                consulta,
                (nombre, idioma, categoria, vars_csv, bool(aprobada), actualizada_iso),
            )
            self._conexion.commit()

    def aprobar_plantilla(self, nombre: str, aprobada: bool = True) -> None:
        actualizada_iso = formatear_iso(datetime.now(timezone.utc))
        consulta = "UPDATE canal.plantillas SET aprobada = ?, actualizada_en = ? WHERE nombre = ?;"
        with self._lock:
            self._conexion.execute(consulta, (bool(aprobada), actualizada_iso, nombre))
            self._conexion.commit()

    def obtener_plantilla(self, nombre: str) -> PlantillaMeta | None:
        consulta = "SELECT * FROM canal.plantillas WHERE nombre = ?;"
        with self._lock:
            fila = self._conexion.execute(consulta, (nombre,)).fetchone()
            if not fila:
                return None
            vars_list = tuple(fila["variables_csv"].split(",")) if fila["variables_csv"] else ()
            return PlantillaMeta(
                nombre=fila["nombre"],
                idioma=fila["idioma"],
                categoria=fila["categoria"],
                variables=vars_list,
                aprobada=bool(fila["aprobada"]),
                actualizada_en=parsear_iso(fila["actualizada_en"]),  # type: ignore[arg-type]
            )

    def listar_plantillas(self) -> list[PlantillaMeta]:
        consulta = "SELECT * FROM canal.plantillas ORDER BY nombre ASC;"
        with self._lock:
            filas = self._conexion.execute(consulta).fetchall()
            resultado: list[PlantillaMeta] = []
            for fila in filas:
                vars_list = tuple(fila["variables_csv"].split(",")) if fila["variables_csv"] else ()
                resultado.append(
                    PlantillaMeta(
                        nombre=fila["nombre"],
                        idioma=fila["idioma"],
                        categoria=fila["categoria"],
                        variables=vars_list,
                        aprobada=bool(fila["aprobada"]),
                        actualizada_en=parsear_iso(fila["actualizada_en"]),  # type: ignore[arg-type]
                    )
                )
            return resultado

    def guardar_medio(
        self,
        medio_id: str,
        mensaje_id: str | None,
        medio_ref: str,
        tipo: str,
        bytes_len: int,
        expira_en: datetime,
    ) -> None:
        expira_iso = formatear_iso(expira_en)
        consulta = """
        INSERT INTO canal.medios (medio_id, mensaje_id, medio_ref, tipo, bytes, expira_en)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (medio_id) DO NOTHING;
        """
        with self._lock:
            self._conexion.execute(consulta, (medio_id, mensaje_id, medio_ref, tipo, bytes_len, expira_iso))
            self._conexion.commit()

    def obtener_medio(self, medio_id: str) -> MedioMeta | None:
        consulta = "SELECT * FROM canal.medios WHERE medio_id = ?;"
        with self._lock:
            fila = self._conexion.execute(consulta, (medio_id,)).fetchone()
            if not fila:
                return None
            return MedioMeta(
                medio_id=fila["medio_id"],
                mensaje_id=fila["mensaje_id"],
                medio_ref=fila["medio_ref"],
                tipo=fila["tipo"],
                bytes=int(fila["bytes"]),
                expira_en=parsear_iso(fila["expira_en"]),  # type: ignore[arg-type]
            )

    def _fila_a_evento(self, fila: sqlite3.Row) -> EventoEntrante:
        return EventoEntrante(
            evento_id=fila["evento_id"],
            mensaje_id=fila["mensaje_id"],
            conversacion_clave=fila["conversacion_clave"],
            cuerpo_cifrado=bytes(fila["cuerpo_cifrado"]),
            estado=fila["estado"],
            intentos=int(fila["intentos"]),
            recibido_en=parsear_iso(fila["recibido_en"]),  # type: ignore[arg-type]
            procesado_en=parsear_iso(fila["procesado_en"]),
        )
