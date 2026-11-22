# ¤panel-operativo
# ¤¤frontend-developer
"""Persistencia interna para la sala panel_operativo (tablas del esquema panel).

Gestiona codigos_acceso, dispositivos, acciones_idempotentes y sesiones.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from features.persistencia_sql.persistencia_sql_service import envolver


# ¤panel-operativo
class PersistenciaPanel:
    """Acceso a datos para el esquema panel según docs/spec/esquema.sql."""

    def __init__(self, origen: Any = None) -> None:
        # None: DATABASE_URL (PostgreSQL, esquema panel) o SQLite en memoria; también URL, ruta o conexión.
        self._con = envolver(origen, ruta_busqueda="panel")
        if not self._con.es_postgres:
            self._inicializar_tablas()  # en PostgreSQL el esquema lo aplica scripts/migrar_db.py

    def _inicializar_tablas(self) -> None:
        with self._con:
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS codigos_acceso (
                    codigo_id TEXT PRIMARY KEY,
                    usuario_id TEXT NOT NULL,
                    codigo_hash TEXT NOT NULL,
                    intentos INTEGER NOT NULL DEFAULT 0,
                    expira_en TEXT NOT NULL,
                    usado_en TEXT
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS dispositivos (
                    dispositivo_id TEXT PRIMARY KEY,
                    usuario_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL UNIQUE,
                    clave_p256dh TEXT NOT NULL,
                    clave_auth TEXT NOT NULL,
                    creado_en TEXT NOT NULL,
                    revocado_en TEXT
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS acciones_idempotentes (
                    usuario_id TEXT NOT NULL,
                    clave TEXT NOT NULL,
                    accion TEXT NOT NULL,
                    respuesta TEXT,
                    creada_en TEXT NOT NULL,
                    PRIMARY KEY (usuario_id, clave)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS sesiones (
                    sesion_id_hash TEXT PRIMARY KEY,
                    usuario_id TEXT NOT NULL,
                    csrf TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    zonas TEXT NOT NULL,
                    creada_en TEXT NOT NULL,
                    expira_en TEXT NOT NULL,
                    cerrada_en TEXT
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS conversaciones_etiquetas (
                    conversacion_id TEXT NOT NULL,
                    etiqueta TEXT NOT NULL,
                    creada_en TEXT NOT NULL,
                    PRIMARY KEY (conversacion_id, etiqueta)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS conversaciones_notas (
                    nota_id TEXT PRIMARY KEY,
                    conversacion_id TEXT NOT NULL,
                    autor_id TEXT NOT NULL,
                    autor_nombre TEXT NOT NULL,
                    texto TEXT NOT NULL,
                    creada_en TEXT NOT NULL
                );
                """
            )

    # Códigos de acceso
    def guardar_codigo(
        self,
        codigo_id: str,
        usuario_id: str,
        codigo_hash: str,
        expira_en: datetime,
    ) -> None:
        expira_str = expira_en.astimezone(timezone.utc).isoformat()
        with self._con:
            self._con.execute(
                """
                INSERT INTO codigos_acceso (codigo_id, usuario_id, codigo_hash, intentos, expira_en, usado_en)
                VALUES (?, ?, ?, 0, ?, NULL);
                """,
                (codigo_id, usuario_id, codigo_hash, expira_str),
            )

    def obtener_codigo_activo(self, usuario_id: str) -> dict[str, Any] | None:
        cursor = self._con.execute(
            """
            SELECT codigo_id, usuario_id, codigo_hash, intentos, expira_en, usado_en
            FROM codigos_acceso
            WHERE usuario_id = ? AND usado_en IS NULL
            ORDER BY expira_en DESC
            LIMIT 1;
            """,
            (usuario_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return {
            "codigo_id": fila[0],
            "usuario_id": fila[1],
            "codigo_hash": fila[2],
            "intentos": int(fila[3]),
            "expira_en": datetime.fromisoformat(fila[4]),
            "usado_en": datetime.fromisoformat(fila[5]) if fila[5] else None,
        }

    def incrementar_intentos(self, codigo_id: str) -> int:
        with self._con:
            cursor = self._con.execute(
                """
                UPDATE codigos_acceso
                SET intentos = intentos + 1
                WHERE codigo_id = ?
                RETURNING intentos;
                """,
                (codigo_id,),
            )
            fila = cursor.fetchone()
            return int(fila[0]) if fila else 0

    def marcar_codigo_usado(self, codigo_id: str, usado_en: datetime) -> None:
        usado_str = usado_en.astimezone(timezone.utc).isoformat()
        with self._con:
            self._con.execute(
                """
                UPDATE codigos_acceso
                SET usado_en = ?
                WHERE codigo_id = ?;
                """,
                (usado_str, codigo_id),
            )

    # Sesiones
    def guardar_sesion(
        self,
        sesion_id_hash: str,
        usuario_id: str,
        csrf: str,
        rol: str,
        zonas: tuple[str, ...],
        creada_en: datetime,
        expira_en: datetime,
    ) -> None:
        creada_str = creada_en.astimezone(timezone.utc).isoformat()
        expira_str = expira_en.astimezone(timezone.utc).isoformat()
        zonas_json = json.dumps(list(zonas))
        with self._con:
            self._con.execute(
                """
                INSERT INTO sesiones (sesion_id_hash, usuario_id, csrf, rol, zonas, creada_en, expira_en, cerrada_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL);
                """,
                (sesion_id_hash, usuario_id, csrf, rol, zonas_json, creada_str, expira_str),
            )

    def obtener_sesion(self, sesion_id_hash: str) -> dict[str, Any] | None:
        cursor = self._con.execute(
            """
            SELECT sesion_id_hash, usuario_id, csrf, rol, zonas, creada_en, expira_en, cerrada_en
            FROM sesiones
            WHERE sesion_id_hash = ? AND cerrada_en IS NULL;
            """,
            (sesion_id_hash,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return {
            "sesion_id_hash": fila[0],
            "usuario_id": fila[1],
            "csrf": fila[2],
            "rol": fila[3],
            "zonas": tuple(json.loads(fila[4])),
            "creada_en": datetime.fromisoformat(fila[5]),
            "expira_en": datetime.fromisoformat(fila[6]),
            "cerrada_en": datetime.fromisoformat(fila[7]) if fila[7] else None,
        }

    def cerrar_sesion(self, sesion_id_hash: str, cerrada_en: datetime) -> None:
        cerrada_str = cerrada_en.astimezone(timezone.utc).isoformat()
        with self._con:
            self._con.execute(
                """
                UPDATE sesiones
                SET cerrada_en = ?
                WHERE sesion_id_hash = ?;
                """,
                (cerrada_str, sesion_id_hash),
            )

    # Dispositivos Web Push (RF-PAN-11, RF-PAN-12)
    def guardar_dispositivo(
        self,
        dispositivo_id: str,
        usuario_id: str,
        endpoint: str,
        clave_p256dh: str,
        clave_auth: str,
        creado_en: datetime,
    ) -> None:
        creado_str = creado_en.astimezone(timezone.utc).isoformat()
        with self._con:
            self._con.execute(
                """
                INSERT INTO dispositivos (dispositivo_id, usuario_id, endpoint, clave_p256dh, clave_auth, creado_en, revocado_en)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                ON CONFLICT(endpoint) DO UPDATE SET
                    dispositivo_id = excluded.dispositivo_id,
                    usuario_id = excluded.usuario_id,
                    clave_p256dh = excluded.clave_p256dh,
                    clave_auth = excluded.clave_auth,
                    creado_en = excluded.creado_en,
                    revocado_en = NULL;
                """,
                (dispositivo_id, usuario_id, endpoint, clave_p256dh, clave_auth, creado_str),
            )

    def obtener_dispositivos_activos_de_usuario(self, usuario_id: str) -> list[dict[str, Any]]:
        cursor = self._con.execute(
            """
            SELECT dispositivo_id, usuario_id, endpoint, clave_p256dh, clave_auth, creado_en
            FROM dispositivos
            WHERE usuario_id = ? AND revocado_en IS NULL;
            """,
            (usuario_id,),
        )
        return [
            {
                "dispositivo_id": fila[0],
                "usuario_id": fila[1],
                "endpoint": fila[2],
                "clave_p256dh": fila[3],
                "clave_auth": fila[4],
                "creado_en": datetime.fromisoformat(fila[5]),
            }
            for fila in cursor.fetchall()
        ]

    def obtener_dispositivos_activos_por_usuarios(self, usuario_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not usuario_ids:
            return []
        placeholders = ",".join("?" for _ in usuario_ids)
        cursor = self._con.execute(
            f"""
            SELECT dispositivo_id, usuario_id, endpoint, clave_p256dh, clave_auth, creado_en
            FROM dispositivos
            WHERE usuario_id IN ({placeholders}) AND revocado_en IS NULL;
            """,
            tuple(usuario_ids),
        )
        return [
            {
                "dispositivo_id": fila[0],
                "usuario_id": fila[1],
                "endpoint": fila[2],
                "clave_p256dh": fila[3],
                "clave_auth": fila[4],
                "creado_en": datetime.fromisoformat(fila[5]),
            }
            for fila in cursor.fetchall()
        ]

    def revocar_dispositivos_de_usuario(self, usuario_id: str, revocado_en: datetime) -> int:
        revocado_str = revocado_en.astimezone(timezone.utc).isoformat()
        with self._con:
            cursor = self._con.execute(
                """
                UPDATE dispositivos
                SET revocado_en = ?
                WHERE usuario_id = ? AND revocado_en IS NULL;
                """,
                (revocado_str, usuario_id),
            )
            return cursor.rowcount

    def revocar_dispositivo_por_endpoint(self, endpoint: str, revocado_en: datetime) -> int:
        revocado_str = revocado_en.astimezone(timezone.utc).isoformat()
        with self._con:
            cursor = self._con.execute(
                """
                UPDATE dispositivos
                SET revocado_en = ?
                WHERE endpoint = ? AND revocado_en IS NULL;
                """,
                (revocado_str, endpoint),
            )
            return cursor.rowcount

    def obtener_todos_dispositivos(self) -> list[dict[str, Any]]:
        cursor = self._con.execute(
            """
            SELECT dispositivo_id, usuario_id, endpoint, clave_p256dh, clave_auth, creado_en, revocado_en
            FROM dispositivos;
            """
        )
        return [
            {
                "dispositivo_id": fila[0],
                "usuario_id": fila[1],
                "endpoint": fila[2],
                "clave_p256dh": fila[3],
                "clave_auth": fila[4],
                "creado_en": datetime.fromisoformat(fila[5]),
                "revocado_en": datetime.fromisoformat(fila[6]) if fila[6] else None,
            }
            for fila in cursor.fetchall()
        ]

    # Idempotencia
    def obtener_accion_idempotente(self, usuario_id: str, clave: str) -> Mapping[str, Any] | None:
        cursor = self._con.execute(
            """
            SELECT accion, respuesta FROM acciones_idempotentes
            WHERE usuario_id = ? AND clave = ?;
            """,
            (usuario_id, clave),
        )
        fila = cursor.fetchone()
        if fila is None or fila[1] is None:
            return None
        return json.loads(fila[1])

    def registrar_accion_idempotente(
        self,
        usuario_id: str,
        clave: str,
        accion: str,
        respuesta: Mapping[str, Any],
        creada_en: datetime,
    ) -> bool:
        creada_str = creada_en.astimezone(timezone.utc).isoformat()
        resp_json = json.dumps(respuesta)
        with self._con:
            cursor = self._con.execute(
                """
                INSERT INTO acciones_idempotentes (usuario_id, clave, accion, respuesta, creada_en)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(usuario_id, clave) DO NOTHING;
                """,
                (usuario_id, clave, accion, resp_json, creada_str),
            )
            return cursor.rowcount > 0

    # ¤panel-operativo
    # Etiquetas y notas de conversaciones (TASK-008 / T-701)
    def asignar_etiqueta(self, conversacion_id: str, etiqueta: str, creada_en: datetime) -> None:
        creada_str = creada_en.astimezone(timezone.utc).isoformat()
        with self._con:
            self._con.execute(
                """
                INSERT INTO conversaciones_etiquetas (conversacion_id, etiqueta, creada_en)
                VALUES (?, ?, ?)
                ON CONFLICT DO NOTHING;
                """,
                (conversacion_id, etiqueta.strip(), creada_str),
            )

    # ¤panel-operativo
    def remover_etiqueta(self, conversacion_id: str, etiqueta: str) -> None:
        with self._con:
            self._con.execute(
                """
                DELETE FROM conversaciones_etiquetas
                WHERE conversacion_id = ? AND etiqueta = ?;
                """,
                (conversacion_id, etiqueta.strip()),
            )

    # ¤panel-operativo
    def obtener_etiquetas(self, conversacion_id: str) -> list[str]:
        cursor = self._con.execute(
            """
            SELECT etiqueta FROM conversaciones_etiquetas
            WHERE conversacion_id = ?
            ORDER BY creada_en ASC;
            """,
            (conversacion_id,),
        )
        return [fila[0] for fila in cursor.fetchall()]

    # ¤panel-operativo
    def agregar_nota(
        self,
        nota_id: str,
        conversacion_id: str,
        autor_id: str,
        autor_nombre: str,
        texto: str,
        creada_en: datetime,
    ) -> None:
        creada_str = creada_en.astimezone(timezone.utc).isoformat()
        with self._con:
            self._con.execute(
                """
                INSERT INTO conversaciones_notas (nota_id, conversacion_id, autor_id, autor_nombre, texto, creada_en)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (nota_id, conversacion_id, autor_id, autor_nombre, texto, creada_str),
            )

    # ¤panel-operativo
    def obtener_notas(self, conversacion_id: str) -> list[dict[str, Any]]:
        cursor = self._con.execute(
            """
            SELECT nota_id, conversacion_id, autor_id, autor_nombre, texto, creada_en
            FROM conversaciones_notas
            WHERE conversacion_id = ?
            ORDER BY creada_en ASC;
            """,
            (conversacion_id,),
        )
        return [
            {
                "nota_id": fila[0],
                "conversacion_id": fila[1],
                "autor_id": fila[2],
                "autor_nombre": fila[3],
                "texto": fila[4],
                "creada_en": fila[5],
            }
            for fila in cursor.fetchall()
        ]

    # ¤panel-operativo
    def cerrar(self) -> None:
        self._con.close()
