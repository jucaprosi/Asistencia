# ¤seguridad-canal
# ¤¤security-engineer
"""Árbitro de RF-SEC-07: Row-Level Security por propiedad_id y rol NOBYPASSRLS."""
from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from features.seguridad.rls_internal import (
    ROL_APLICACION_RLS,
    TABLAS_CON_RLS,
    GuardiaContextoInquilino,
    contexto_inquilino,
    generar_ddl_migraciones_rls,
    obtener_propiedad_actual,
)
from features.seguridad.seguridad_service import SeguridadService


# ¤seguridad-canal
def test_migraciones_rls_rol_nobypassrls_y_cobertura_tablas() -> None:
    ddl = generar_ddl_migraciones_rls()

    # Rol NOBYPASSRLS
    assert "NOBYPASSRLS" in ddl
    assert f"CREATE ROLE {ROL_APLICACION_RLS} NOLOGIN NOBYPASSRLS;" in ddl

    # Cobertura de todas las tablas con propiedad_id
    for tabla in TABLAS_CON_RLS:
        assert f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;" in ddl
        assert f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY;" in ddl
        assert f"ON {tabla}" in ddl
        assert "current_setting('app.propiedad_id', true)" in ddl

    # INV_AUDIT_APPEND_ONLY: revocar borrado y modificación
    assert f"REVOKE UPDATE, DELETE, TRUNCATE ON seguridad.audit_log FROM {ROL_APLICACION_RLS};" in ddl


# ¤seguridad-canal
def test_guardia_contexto_inquilino_activacion_y_reinicio() -> None:
    assert obtener_propiedad_actual() is None

    with contexto_inquilino("propiedad_san_pablo") as prop:
        assert prop == "propiedad_san_pablo"
        assert obtener_propiedad_actual() == "propiedad_san_pablo"

        # Contexto anidado para otra propiedad
        with contexto_inquilino("propiedad_cuenca") as prop_anidada:
            assert prop_anidada == "propiedad_cuenca"
            assert obtener_propiedad_actual() == "propiedad_cuenca"

        # Al salir del anidado, recupera el contexto anterior
        assert obtener_propiedad_actual() == "propiedad_san_pablo"

    assert obtener_propiedad_actual() is None


# ¤seguridad-canal
def test_escenario_rf_sec_07_aislamiento_por_propiedad_en_chunks() -> None:
    """Escenario: Aislamiento por propiedad en la base.

    Dado el rol de aplicación con la propiedad A
    Cuando consulta chunks
    Entonces no recibe filas de la propiedad B
    """
    guardia = GuardiaContextoInquilino()

    chunks_simulados = [
        {"chunk_id": "c1", "propiedad_id": "propiedad_A", "texto": "Normas de Domo A"},
        {"chunk_id": "c2", "propiedad_id": "propiedad_A", "texto": "Tarifas de Domo A"},
        {"chunk_id": "c3", "propiedad_id": "propiedad_B", "texto": "Secretos de Propiedad B"},
        {"chunk_id": "c4", "propiedad_id": "propiedad_B", "texto": "Precios de Propiedad B"},
        {"chunk_id": "c_glob", "propiedad_id": "global", "texto": "Políticas Generales de Glamping"},
    ]

    # Con propiedad A activa
    with contexto_inquilino("propiedad_A"):
        filas_visibles = guardia.filtrar_filas(chunks_simulados)
        ids_visibles = {f["chunk_id"] for f in filas_visibles}

        assert "c1" in ids_visibles
        assert "c2" in ids_visibles
        assert "c_glob" in ids_visibles
        # Invariante INV_SIN_FUGA_ENTRE_PROPIEDADES: NUNCA filas de B
        assert "c3" not in ids_visibles
        assert "c4" not in ids_visibles
        assert guardia.verificar_aislamiento_filas(filas_visibles) is True

    # Con propiedad B activa
    with contexto_inquilino("propiedad_B"):
        filas_visibles_b = guardia.filtrar_filas(chunks_simulados)
        ids_visibles_b = {f["chunk_id"] for f in filas_visibles_b}

        assert "c3" in ids_visibles_b
        assert "c4" in ids_visibles_b
        assert "c_glob" in ids_visibles_b
        assert "c1" not in ids_visibles_b
        assert "c2" not in ids_visibles_b
        assert guardia.verificar_aislamiento_filas(filas_visibles_b) is True


# ¤seguridad-canal
def test_aislamiento_en_tablas_locales_sqlite() -> None:
    """Verifica que en SQLite el simulador respete el contexto de inquilino."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE conocimiento_chunks (
            chunk_id TEXT PRIMARY KEY,
            propiedad_id TEXT NOT NULL,
            texto TEXT NOT NULL
        )
        """
    )
    conn.execute("INSERT INTO conocimiento_chunks VALUES ('1', 'prop_A', 'Info A')")
    conn.execute("INSERT INTO conocimiento_chunks VALUES ('2', 'prop_B', 'Info B')")
    conn.execute("INSERT INTO conocimiento_chunks VALUES ('3', 'global', 'Info Global')")

    with contexto_inquilino("prop_A", conn):
        cursor = conn.execute(
            """
            SELECT * FROM conocimiento_chunks
            WHERE propiedad_id = current_propiedad_id() OR propiedad_id = 'global'
            """
        )
        filas = cursor.fetchall()
        props = {f["propiedad_id"] for f in filas}
        assert props == {"prop_A", "global"}
        assert "prop_B" not in props


# ¤seguridad-canal
def test_seguridad_service_expone_rls_y_migraciones() -> None:
    svc = SeguridadService()
    ddl = svc.generar_migraciones_rls()
    assert "app_glamping" in ddl
    assert "NOBYPASSRLS" in ddl

    with svc.contexto_inquilino("propiedad_glamping"):
        assert obtener_propiedad_actual() == "propiedad_glamping"
    assert obtener_propiedad_actual() is None
