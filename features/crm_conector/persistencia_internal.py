# ¤crm-conector
# ¤¤integration-engineer
"""Persistencia local y gestión de tablas del esquema crm (RF-CRM-06, INV_HANDOFF_UNICO)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping

from features.crm_conector.tipos import Handoff, HandoffExistente, ReferenciaCRM, Zona
from features.persistencia_sql.persistencia_sql_service import Conexion, envolver


# ¤crm-conector
def inicializar_base_datos(conexion: Any = None) -> Conexion:
    """Inicializa el esquema crm y sus tablas protegidas."""
    conexion = envolver(conexion, esquemas=("crm",))
    if conexion.es_postgres:
        # El esquema lo aplica scripts/migrar_db.py; las zonas semilla son datos y se aseguran igual.
        _sembrar_zonas_defecto(conexion)
        conexion.commit()
        return conexion

    # Verificar si la base de datos 'crm' ya está adjunta
    bases_adjuntas = [fila[1] for fila in conexion.execute("PRAGMA database_list").fetchall()]
    if "crm" not in bases_adjuntas:
        conexion.execute("ATTACH DATABASE ':memory:' AS crm")

    # Tabla crm.zonas
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS crm.zonas (
            zona_id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            gestor_principal_id TEXT NOT NULL,
            gestor_respaldo_id TEXT NOT NULL,
            CHECK (gestor_principal_id <> gestor_respaldo_id)
        )
        """
    )

    # Tabla crm.handoffs
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS crm.handoffs (
            handoff_id TEXT PRIMARY KEY,
            conversacion_id TEXT NOT NULL,
            motivo TEXT NOT NULL CHECK (
                motivo IN (
                    'peticion_explicita',
                    'baja_confianza',
                    'fuera_alcance',
                    'incidencia_critica',
                    'inyeccion_repetida',
                    'degradacion',
                    'limite_iteraciones'
                )
            ),
            zona_id TEXT REFERENCES zonas(zona_id),
            estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'tomado', 'devuelto')),
            asignado_a TEXT,
            resumen_token TEXT NOT NULL,
            inicio TEXT NOT NULL,
            tomado_en TEXT,
            ultima_actividad TEXT NOT NULL,
            devuelto_en TEXT,
            devuelto_por TEXT CHECK (devuelto_por IN ('gestor', 'vencimiento'))
        )
        """
    )

    # Índice único parcial para INV_HANDOFF_UNICO: solo un handoff abierto por conversación
    conexion.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS crm.un_handoff_abierto
        ON handoffs (conversacion_id)
        WHERE estado <> 'devuelto'
        """
    )

    # Tabla crm.publicaciones
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS crm.publicaciones (
            venta_id TEXT NOT NULL,
            evento TEXT NOT NULL CHECK (evento IN ('venta_validada', 'venta_anulada')),
            payload_json TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'ok', 'error')),
            intentos INTEGER NOT NULL DEFAULT 0,
            ultima_respuesta TEXT,
            proximo_intento TEXT,
            creado_en TEXT NOT NULL,
            PRIMARY KEY (venta_id, evento)
        )
        """
    )

    # Tabla crm.eventos
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS crm.eventos (
            evento_id TEXT PRIMARY KEY,
            tipo TEXT NOT NULL,
            referencia TEXT NOT NULL,
            datos_json TEXT NOT NULL,
            recibido_en TEXT NOT NULL,
            procesado_en TEXT
        )
        """
    )

    # Tabla crm.referencias
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS crm.referencias (
            entidad TEXT NOT NULL,
            id_local TEXT NOT NULL,
            crm_ref TEXT NOT NULL,
            PRIMARY KEY (entidad, id_local)
        )
        """
    )

    # Insertar zonas semilla si no existen
    _sembrar_zonas_defecto(conexion)
    conexion.commit()
    return conexion


# ¤crm-conector
def _sembrar_zonas_defecto(conexion: sqlite3.Connection) -> None:
    zonas_semilla = [
        ("imbabura_norte", "Imbabura Norte", "00000000-0000-0000-0000-000000000010", "00000000-0000-0000-0000-000000000011"),
        ("ibarra_urbano", "Ibarra Urbano", "00000000-0000-0000-0000-000000000020", "00000000-0000-0000-0000-000000000021"),
    ]
    for zid, nom, g_p, g_r in zonas_semilla:
        conexion.execute(
            """
            INSERT INTO crm.zonas (zona_id, nombre, gestor_principal_id, gestor_respaldo_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (zona_id) DO NOTHING
            """,
            (zid, nom, g_p, g_r),
        )


# ¤crm-conector
def insertar_zona(conexion: sqlite3.Connection, zona: Zona) -> None:
    conexion.execute(
        """
        INSERT INTO crm.zonas (zona_id, nombre, gestor_principal_id, gestor_respaldo_id)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (zona_id) DO UPDATE SET
            nombre = excluded.nombre, gestor_principal_id = excluded.gestor_principal_id,
            gestor_respaldo_id = excluded.gestor_respaldo_id
        """,
        (zona.zona_id, zona.nombre, zona.gestor_principal_id, zona.gestor_respaldo_id),
    )
    conexion.commit()


# ¤crm-conector
def obtener_zona(conexion: sqlite3.Connection, zona_id: str) -> Zona | None:
    cursor = conexion.execute(
        "SELECT zona_id, nombre, gestor_principal_id, gestor_respaldo_id FROM crm.zonas WHERE zona_id = ?",
        (zona_id,),
    )
    fila = cursor.fetchone()
    if not fila:
        return None
    return Zona(
        zona_id=fila["zona_id"],
        nombre=fila["nombre"],
        gestor_principal_id=fila["gestor_principal_id"],
        gestor_respaldo_id=fila["gestor_respaldo_id"],
    )


# ¤crm-conector
def listar_zonas(conexion: sqlite3.Connection) -> list[Zona]:
    cursor = conexion.execute("SELECT zona_id, nombre, gestor_principal_id, gestor_respaldo_id FROM crm.zonas")
    return [
        Zona(
            zona_id=f["zona_id"],
            nombre=f["nombre"],
            gestor_principal_id=f["gestor_principal_id"],
            gestor_respaldo_id=f["gestor_respaldo_id"],
        )
        for f in cursor.fetchall()
    ]


# ¤crm-conector
def _parse_iso(fecha_iso: str | None) -> datetime | None:
    if not fecha_iso:
        return None
    try:
        return datetime.fromisoformat(fecha_iso)
    except ValueError:
        return None


# ¤crm-conector
def _fila_a_handoff(f: sqlite3.Row) -> Handoff:
    return Handoff(
        handoff_id=f["handoff_id"],
        conversacion_id=f["conversacion_id"],
        motivo=f["motivo"],
        zona_id=f["zona_id"],
        estado=f["estado"],
        asignado_a=f["asignado_a"],
        resumen_token=f["resumen_token"],
        inicio=datetime.fromisoformat(f["inicio"]),
        tomado_en=_parse_iso(f["tomado_en"]),
        ultima_actividad=_parse_iso(f["ultima_actividad"]),
        devuelto_en=_parse_iso(f["devuelto_en"]),
        devuelto_por=f["devuelto_por"],
    )


# ¤crm-conector
def crear_handoff(conexion: sqlite3.Connection, handoff: Handoff) -> Handoff:
    """Inserta un nuevo handoff asegurando INV_HANDOFF_UNICO."""
    # Verificar si ya existe handoff abierto para la conversación
    existente = obtener_handoff_abierto_por_conversacion(conexion, handoff.conversacion_id)
    if existente:
        raise HandoffExistente(
            f"La conversación {handoff.conversacion_id} ya tiene un handoff abierto con id {existente.handoff_id}."
        )

    try:
        conexion.execute(
            """
            INSERT INTO crm.handoffs (
                handoff_id, conversacion_id, motivo, zona_id, estado, asignado_a,
                resumen_token, inicio, tomado_en, ultima_actividad, devuelto_en, devuelto_por
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handoff.handoff_id,
                handoff.conversacion_id,
                handoff.motivo,
                handoff.zona_id,
                handoff.estado,
                handoff.asignado_a,
                handoff.resumen_token,
                handoff.inicio.isoformat(),
                handoff.tomado_en.isoformat() if handoff.tomado_en else None,
                handoff.ultima_actividad.isoformat() if handoff.ultima_actividad else handoff.inicio.isoformat(),
                handoff.devuelto_en.isoformat() if handoff.devuelto_en else None,
                handoff.devuelto_por,
            ),
        )
        conexion.commit()
    except sqlite3.IntegrityError as exc:
        if "un_handoff_abierto" in str(exc) or "UNIQUE" in str(exc):
            raise HandoffExistente(f"Violación de INV_HANDOFF_UNICO: {exc}") from exc
        raise
    return handoff


# ¤crm-conector
def obtener_handoff(conexion: sqlite3.Connection, handoff_id: str) -> Handoff | None:
    cursor = conexion.execute("SELECT * FROM crm.handoffs WHERE handoff_id = ?", (handoff_id,))
    f = cursor.fetchone()
    if not f:
        return None
    return _fila_a_handoff(f)


# ¤crm-conector
def obtener_handoff_abierto_por_conversacion(
    conexion: sqlite3.Connection, conversacion_id: str
) -> Handoff | None:
    cursor = conexion.execute(
        "SELECT * FROM crm.handoffs WHERE conversacion_id = ? AND estado <> 'devuelto'",
        (conversacion_id,),
    )
    f = cursor.fetchone()
    if not f:
        return None
    return _fila_a_handoff(f)


# ¤crm-conector
def actualizar_handoff(conexion: sqlite3.Connection, handoff: Handoff) -> None:
    conexion.execute(
        """
        UPDATE crm.handoffs
        SET estado = ?, asignado_a = ?, tomado_en = ?, ultima_actividad = ?, devuelto_en = ?, devuelto_por = ?
        WHERE handoff_id = ?
        """,
        (
            handoff.estado,
            handoff.asignado_a,
            handoff.tomado_en.isoformat() if handoff.tomado_en else None,
            handoff.ultima_actividad.isoformat() if handoff.ultima_actividad else datetime.now(timezone.utc).isoformat(),
            handoff.devuelto_en.isoformat() if handoff.devuelto_en else None,
            handoff.devuelto_por,
            handoff.handoff_id,
        ),
    )
    conexion.commit()


# ¤crm-conector
def listar_handoffs(
    conexion: sqlite3.Connection,
    zona_id: str | None = None,
    estado: str | None = None,
) -> list[Handoff]:
    query = "SELECT * FROM crm.handoffs WHERE 1=1"
    params: list[Any] = []
    if zona_id is not None:
        query += " AND zona_id = ?"
        params.append(zona_id)
    if estado is not None:
        query += " AND estado = ?"
        params.append(estado)
    query += " ORDER BY inicio ASC"
    cursor = conexion.execute(query, params)
    return [_fila_a_handoff(f) for f in cursor.fetchall()]


# ¤crm-conector
def guardar_referencia(conexion: sqlite3.Connection, ref: ReferenciaCRM) -> None:
    conexion.execute(
        "INSERT INTO crm.referencias (entidad, id_local, crm_ref) VALUES (?, ?, ?) "
        "ON CONFLICT (entidad, id_local) DO UPDATE SET crm_ref = excluded.crm_ref",
        (ref.entidad, ref.id_local, ref.crm_ref),
    )
    conexion.commit()


# ¤crm-conector
def obtener_referencia(conexion: sqlite3.Connection, entidad: str, id_local: str) -> str | None:
    cursor = conexion.execute(
        "SELECT crm_ref FROM crm.referencias WHERE entidad = ? AND id_local = ?",
        (entidad, id_local),
    )
    f = cursor.fetchone()
    return f["crm_ref"] if f else None
