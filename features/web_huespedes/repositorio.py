# ¤web-huespedes
# ¤¤frontend-developer
"""Persistencia local para la sala web_huespedes (tablas web.enlaces_contacto y web.limites_ip)."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from features.web_huespedes.tipos import EnlaceContacto


# ¤web-huespedes
class RepositorioWeb:
    """Acceso a datos para enlaces de contacto y límites por IP según esquema.sql."""

    def __init__(self, origen: str | sqlite3.Connection = ":memory:") -> None:
        if isinstance(origen, sqlite3.Connection):
            self._con = origen
        else:
            self._con = sqlite3.connect(origen, check_same_thread=False)
        self._inicializar_tablas()

    def _inicializar_tablas(self) -> None:
        with self._con:
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS enlaces_contacto (
                    codigo TEXT PRIMARY KEY,
                    propiedad_id TEXT NOT NULL,
                    desde TEXT,
                    hasta TEXT,
                    huespedes INTEGER,
                    creado_en TEXT NOT NULL,
                    expira_en TEXT NOT NULL
                )
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS limites_ip (
                    ip_hash TEXT NOT NULL,
                    ventana TEXT NOT NULL,
                    conteo INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (ip_hash, ventana)
                )
                """
            )

    def guardar_enlace(
        self,
        enlace: EnlaceContacto,
        creado_en: datetime,
        expira_en: datetime,
    ) -> None:
        """Registra un enlace de contexto. Valida invariantes de fecha y huéspedes."""
        if enlace.desde and enlace.hasta and enlace.hasta <= enlace.desde:
            raise ValueError("hasta debe ser mayor que desde si ambos están definidos")
        if enlace.huespedes is not None and enlace.huespedes < 1:
            raise ValueError("huespedes debe ser mayor o igual a 1")

        desde_str = enlace.desde.isoformat() if enlace.desde else None
        hasta_str = enlace.hasta.isoformat() if enlace.hasta else None
        creado_str = creado_en.astimezone(timezone.utc).isoformat()
        expira_str = expira_en.astimezone(timezone.utc).isoformat()

        with self._con:
            self._con.execute(
                """
                INSERT INTO enlaces_contacto (codigo, propiedad_id, desde, hasta, huespedes, creado_en, expira_en)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (enlace.codigo, enlace.propiedad_id, desde_str, hasta_str, enlace.huespedes, creado_str, expira_str),
            )

    def obtener_enlace(self, codigo: str, ahora: datetime | None = None) -> EnlaceContacto | None:
        """Recupera un enlace si existe y aún no ha expirado."""
        cursor = self._con.execute(
            """
            SELECT codigo, propiedad_id, desde, hasta, huespedes, expira_en
            FROM enlaces_contacto
            WHERE codigo = ?
            """,
            (codigo,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None

        cod, prop_id, d_str, h_str, huespedes, expira_str = fila
        momento_actual = ahora or datetime.now(timezone.utc)
        expira_dt = datetime.fromisoformat(expira_str)
        if momento_actual > expira_dt:
            return None

        d_val = date.fromisoformat(d_str) if d_str else None
        h_val = date.fromisoformat(h_str) if h_str else None

        return EnlaceContacto(
            codigo=cod,
            propiedad_id=prop_id,
            desde=d_val,
            hasta=h_val,
            huespedes=huespedes,
        )

    def registrar_solicitud_ip(self, ip_hash: str, ventana_iso: str) -> int:
        """Registra una consulta en la ventana actual e incrementa el contador atómicamente."""
        with self._con:
            cursor = self._con.execute(
                """
                INSERT INTO limites_ip (ip_hash, ventana, conteo)
                VALUES (?, ?, 1)
                ON CONFLICT(ip_hash, ventana) DO UPDATE SET conteo = conteo + 1
                RETURNING conteo
                """,
                (ip_hash, ventana_iso),
            )
            fila = cursor.fetchone()
            return int(fila[0]) if fila else 1

    def conteo_ip(self, ip_hash: str, ventana_iso: str) -> int:
        """Devuelve el conteo de solicitudes para la ventana dada."""
        cursor = self._con.execute(
            """
            SELECT conteo FROM limites_ip WHERE ip_hash = ? AND ventana = ?
            """,
            (ip_hash, ventana_iso),
        )
        fila = cursor.fetchone()
        return int(fila[0]) if fila else 0

    def cerrar(self) -> None:
        self._con.close()
