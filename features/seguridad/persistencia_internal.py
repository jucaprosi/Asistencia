# ¤seguridad-canal
# ¤¤security-engineer
"""Persistencia local y base de datos para la sala seguridad."""
from __future__ import annotations

import sqlite3
from typing import Any

from features.persistencia_sql.persistencia_sql_service import Conexion, envolver


# ¤seguridad-canal
def inicializar_base_datos(conexion: Any = None) -> Conexion:
    """Inicializa el esquema seguridad y sus tablas protegidas."""
    conexion = envolver(conexion, esquemas=("seguridad",))
    if conexion.es_postgres:
        return conexion  # el esquema lo aplica scripts/migrar_db.py (docs/spec/esquema.sql)

    # Verificar si la base de datos 'seguridad' ya está adjunta
    bases_adjuntas = [fila[1] for fila in conexion.execute("PRAGMA database_list").fetchall()]
    if "seguridad" not in bases_adjuntas:
        conexion.execute("ATTACH DATABASE ':memory:' AS seguridad")

    # Tabla usuarios
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.usuarios (
            usuario_id TEXT PRIMARY KEY,
            correo_hash TEXT NOT NULL UNIQUE,
            numero_hash TEXT NOT NULL UNIQUE,
            rol TEXT NOT NULL CHECK (rol IN ('vendedor','lider','gestor','administrador','anfitrion')),
            sujeto_id TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            alta_por TEXT,
            alta_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            baja_en TEXT
        )
        """
    )

    # Tabla huespedes
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.huespedes (
            huesped_id TEXT PRIMARY KEY,
            telefono_token TEXT NOT NULL UNIQUE,
            nombre_token TEXT,
            idioma TEXT NOT NULL DEFAULT 'es',
            crm_ref TEXT,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Tabla bloqueos
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.bloqueos (
            numero_hash TEXT PRIMARY KEY,
            motivo TEXT NOT NULL,
            bloqueado_por TEXT NOT NULL,
            bloqueado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Tabla boveda_tokens
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.boveda_tokens (
            token TEXT PRIMARY KEY,
            titular_hash TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('nombre','telefono','correo','documento','tarjeta','direccion','clave_wifi','codigo_acceso')),
            valor_cifrado BLOB NOT NULL,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ultimo_uso_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS seguridad.boveda_por_titular ON boveda_tokens (titular_hash)"
    )

    # Tabla rate_limit
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.rate_limit (
            remitente_hash TEXT NOT NULL,
            ventana TEXT NOT NULL CHECK (ventana IN ('segundo','minuto','dia')),
            inicio TEXT NOT NULL,
            contador INTEGER NOT NULL DEFAULT 0 CHECK (contador >= 0),
            aviso_enviado INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (remitente_hash, ventana, inicio)
        )
        """
    )

    # Tabla consentimientos
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.consentimientos (
            consentimiento_id TEXT PRIMARY KEY,
            titular_hash TEXT NOT NULL,
            base TEXT NOT NULL CHECK (base IN ('aviso_primer_contacto','reserva','relacion_laboral')),
            version_aviso TEXT NOT NULL,
            otorgado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            revocado_en TEXT
        )
        """
    )

    # Tabla solicitudes_titular
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.solicitudes_titular (
            solicitud_id TEXT PRIMARY KEY,
            titular_hash TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('acceso','rectificacion','eliminacion','oposicion','portabilidad')),
            estado TEXT NOT NULL DEFAULT 'recibida' CHECK (estado IN ('recibida','en_curso','atendida','atendida_parcial','rechazada')),
            recibida_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            limite_en TEXT NOT NULL,
            atendida_en TEXT,
            atendida_por TEXT,
            motivo TEXT
        )
        """
    )

    # Tabla audit_log (INSERT-only)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS seguridad.audit_log (
            audit_id TEXT PRIMARY KEY,
            instante TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            actor_token TEXT NOT NULL,
            rol TEXT NOT NULL,
            accion TEXT NOT NULL,
            herramienta TEXT,
            propiedad_id TEXT,
            resultado TEXT NOT NULL,
            hash_prompt TEXT,
            traza_id TEXT
        )
        """
    )

    # Disparadores para forzar INV_AUDIT_APPEND_ONLY
    conexion.execute(
        """
        CREATE TRIGGER IF NOT EXISTS seguridad.audit_no_upd
        BEFORE UPDATE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'REVOKE: operacion UPDATE denegada sobre seguridad.audit_log');
        END
        """
    )
    conexion.execute(
        """
        CREATE TRIGGER IF NOT EXISTS seguridad.audit_no_del
        BEFORE DELETE ON audit_log
        BEGIN
            SELECT RAISE(ABORT, 'REVOKE: operacion DELETE denegada sobre seguridad.audit_log');
        END
        """
    )

    conexion.commit()
    return conexion
