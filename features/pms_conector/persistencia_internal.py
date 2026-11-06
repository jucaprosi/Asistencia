# ¤pms-conector
# ¤¤integration-engineer
"""Persistencia local y gestión de tablas del esquema pms (RF-PMS-06, INV_SIN_DOBLE_RESERVA)."""
from __future__ import annotations

import sqlite3


# ¤pms-conector
def inicializar_base_datos(conexion: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Inicializa el esquema pms y sus tablas protegidas."""
    if conexion is None:
        conexion = sqlite3.connect(":memory:", check_same_thread=False)

    conexion.row_factory = sqlite3.Row

    # Verificar si la base de datos 'pms' ya está adjunta
    bases_adjuntas = [fila[1] for fila in conexion.execute("PRAGMA database_list").fetchall()]
    if "pms" not in bases_adjuntas:
        conexion.execute("ATTACH DATABASE ':memory:' AS pms")

    # Tabla propiedades
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.propiedades (
            propiedad_id TEXT PRIMARY KEY,
            tipo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            zona_id TEXT NOT NULL,
            direccion TEXT NOT NULL,
            pms_ref TEXT,
            prompt_variante TEXT NOT NULL DEFAULT 'glamping',
            activa INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    # Tabla unidades
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.unidades (
            unidad_id TEXT PRIMARY KEY,
            propiedad_id TEXT NOT NULL REFERENCES propiedades(propiedad_id),
            nombre TEXT NOT NULL,
            capacidad INTEGER NOT NULL CHECK (capacidad >= 1),
            edificio TEXT,
            piso TEXT,
            acceso_ref TEXT,
            wifi_ref TEXT
        )
        """
    )

    # Tabla reservas_ref (referencia local para validación rápida del titular sin invocar al PMS)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.reservas_ref (
            codigo_reserva TEXT PRIMARY KEY,
            propiedad_id TEXT NOT NULL,
            unidad_id TEXT NOT NULL,
            huesped_token TEXT NOT NULL,
            desde TEXT NOT NULL,
            hasta TEXT NOT NULL,
            huespedes INTEGER NOT NULL DEFAULT 1,
            total TEXT NOT NULL,
            estado TEXT NOT NULL CHECK (estado IN ('preliminar','confirmada','cancelada','expirada','completada')),
            expira_en TEXT,
            pms_ref TEXT,
            actualizada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Tabla tarifas_noche
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.tarifas_noche (
            unidad_id TEXT NOT NULL,
            noche TEXT NOT NULL,
            precio TEXT NOT NULL,
            minimo_noches INTEGER NOT NULL DEFAULT 1 CHECK (minimo_noches >= 1),
            PRIMARY KEY (unidad_id, noche)
        )
        """
    )

    # Tabla noches_ocupadas (INV_SIN_DOBLE_RESERVA: PK por unidad y noche)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.noches_ocupadas (
            unidad_id TEXT NOT NULL,
            noche TEXT NOT NULL,
            origen TEXT NOT NULL CHECK (origen IN ('reserva','bloqueo')),
            codigo_reserva TEXT,
            PRIMARY KEY (unidad_id, noche)
        )
        """
    )

    # Tabla incidencias
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.incidencias (
            incidencia_id TEXT PRIMARY KEY,
            propiedad_id TEXT NOT NULL,
            unidad_id TEXT,
            codigo_reserva TEXT,
            categoria TEXT NOT NULL,
            prioridad TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'abierta',
            descripcion_token TEXT NOT NULL,
            gestor_id TEXT,
            creada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resuelta_en TEXT,
            resuelta_por TEXT,
            nota TEXT
        )
        """
    )

    # Tabla idempotencia
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.idempotencia (
            clave TEXT PRIMARY KEY,
            operacion TEXT NOT NULL,
            resultado_json TEXT NOT NULL,
            creado_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Secuencia para tickets de incidencias
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS pms.secuencia_incidencias (
            anio INTEGER PRIMARY KEY,
            ultimo INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    conexion.commit()
    return conexion
