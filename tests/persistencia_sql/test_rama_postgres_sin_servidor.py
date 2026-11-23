# ¤persistencia-sql
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Rama PostgreSQL de la sala persistencia_sql y de los repositorios, sin servidor.

Un doble de la conexión de psycopg registra cada sentencia. Así se verifica, en la suite de siempre, que
en PostgreSQL las salas no ejecutan su DDL de SQLite (el esquema lo aplica ``scripts/migrar_db.py``), que
los datos semilla sí se aseguran y que el adaptador traduce marcadores, lecturas y errores.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Any

import pytest

from features.persistencia_sql.persistencia_sql_service import (
    Conexion,
    PersistenciaSqlService,
    cargar_config,
    cerrar_conexiones_postgres,
    envolver,
)


# ¤persistencia-sql
class _CursorDoble:
    def __init__(self, filas: list[tuple[Any, ...]], columnas: list[str]) -> None:
        self._filas = filas
        self.description = [type("Col", (), {"name": c})() for c in columnas] if columnas else None
        self.rowcount = len(filas) if columnas else 1

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._filas


# ¤persistencia-sql
class _PsycopgDoble:
    """Registra sentencias; responde filas vacías salvo que se programe una respuesta."""

    def __init__(self) -> None:
        self.sentencias: list[tuple[str, Any]] = []
        self.commits = 0
        self.rollbacks = 0
        self.respuesta: tuple[list[tuple[Any, ...]], list[str]] = ([], [])
        self.fallo: Exception | None = None

    def execute(self, sql: str, parametros: Any = None) -> _CursorDoble:
        self.sentencias.append((sql, parametros))
        if self.fallo is not None:
            fallo, self.fallo = self.fallo, None
            raise fallo
        filas, columnas = self.respuesta
        self.respuesta = ([], [])
        return _CursorDoble(filas, columnas)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        pass


# ¤persistencia-sql
def _conexion_pg() -> tuple[Conexion, _PsycopgDoble]:
    conexion = Conexion.__new__(Conexion)
    conexion.url = "postgresql://doble/db"
    conexion.dialecto = "postgresql"
    conexion._lock = threading.RLock()
    conexion._en_transaccion = False
    doble = _PsycopgDoble()
    conexion._crudo = doble
    return conexion, doble


# ¤persistencia-sql
def test_lectura_se_confirma_sola_y_devuelve_filas_por_nombre() -> None:
    conexion, doble = _conexion_pg()
    doble.respuesta = ([("a", 1)], ["id", "n"])
    fila = conexion.execute("SELECT id, n FROM t WHERE id = ?", ("a",)).fetchone()
    assert fila["id"] == "a" and fila[1] == 1 and fila.keys() == ["id", "n"] and len(fila) == 2
    assert doble.sentencias[-1] == ("SELECT id, n FROM t WHERE id = %s", ("a",))
    assert doble.commits == 1, "una lectura fuera de transacción no debe dejar la sesión 'idle in transaction'"


# ¤persistencia-sql
def test_escritura_queda_en_transaccion_hasta_commit() -> None:
    conexion, doble = _conexion_pg()
    conexion.execute("INSERT INTO t (id) VALUES (?)", ("a",))
    conexion.execute("SELECT 1")
    assert doble.commits == 0, "la lectura dentro de una transacción no debe confirmarla"
    with conexion:
        pass
    assert doble.commits == 1


# ¤persistencia-sql
def test_error_de_integridad_revierte_y_se_traduce() -> None:
    import psycopg

    conexion, doble = _conexion_pg()
    doble.fallo = psycopg.errors.UniqueViolation("duplicado")
    with pytest.raises(sqlite3.IntegrityError):
        conexion.execute("INSERT INTO t (id) VALUES (?)", ("a",))
    assert doble.rollbacks == 1
    doble.fallo = psycopg.OperationalError("caída")
    with pytest.raises(sqlite3.OperationalError):
        conexion.execute("SELECT 1")
    doble.fallo = psycopg.errors.UndefinedTable("sin tabla")
    with pytest.raises(sqlite3.DatabaseError):
        conexion.execute("SELECT 1")
    doble.fallo = RuntimeError("otro")
    with pytest.raises(RuntimeError):
        conexion.execute("SELECT 1")


# ¤persistencia-sql
def test_contexto_revierte_si_hay_excepcion_y_cursor_delega() -> None:
    conexion, doble = _conexion_pg()
    with pytest.raises(ValueError):
        with conexion:
            conexion.execute("UPDATE t SET a = ?", (1,))
            raise ValueError("falla")
    assert doble.rollbacks == 1
    cursor = conexion.cursor()
    doble.respuesta = ([(7,)], ["n"])
    assert cursor.execute("SELECT n FROM t").fetchone()["n"] == 7
    assert cursor.fetchall() == []
    cursor.close()
    assert cursor.fetchone() is None


# ¤persistencia-sql
def test_ddl_de_sqlite_no_se_ejecuta_en_postgres() -> None:
    conexion, doble = _conexion_pg()
    conexion.asegurar_esquema("CREATE TABLE canal.x (id TEXT)")
    conexion.adjuntar_esquema("canal")
    conexion.row_factory = sqlite3.Row
    assert doble.sentencias == []
    conexion.executescript("SELECT 1; SELECT 2;")
    assert doble.sentencias == [("SELECT 1; SELECT 2;", None)] and doble.commits == 1
    conexion.rollback()
    conexion.close()


# ¤persistencia-sql
def test_salas_no_crean_tablas_en_postgres_pero_siembran_datos() -> None:
    from features.anfitriones.persistencia_internal import PersistenciaAnfitriones
    from features.arm_jarvis.persistencia_internal import RepositorioArm
    from features.canal_whatsapp.persistencia_internal import RepositorioCanal
    from features.comisiones.persistencia_internal import PersistenciaComisiones
    from features.conocimiento.persistencia_internal import RepositorioConocimiento
    from features.crm_conector.persistencia_internal import inicializar_base_datos as iniciar_crm
    from features.panel_operativo.persistencia_internal import PersistenciaPanel
    from features.pms_conector.persistencia_internal import inicializar_base_datos as iniciar_pms
    from features.seguridad.persistencia_internal import inicializar_base_datos as iniciar_seguridad

    for construir in (
        PersistenciaAnfitriones, RepositorioArm, RepositorioCanal, PersistenciaComisiones,
        RepositorioConocimiento, PersistenciaPanel, iniciar_pms, iniciar_seguridad,
    ):
        conexion, doble = _conexion_pg()
        construir(conexion)
        assert not [s for s, _ in doble.sentencias if "CREATE" in s.upper()], construir

    conexion, doble = _conexion_pg()
    iniciar_crm(conexion)
    sembradas = [p for s, p in doble.sentencias if "INSERT INTO crm.zonas" in s]
    assert {p[0] for p in sembradas} == {"imbabura_norte", "ibarra_urbano"}
    assert not [s for s, _ in doble.sentencias if "CREATE" in s.upper()]


# ¤persistencia-sql
def test_envolver_normaliza_origenes_y_rechaza_otros(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    crudo = sqlite3.connect(":memory:")
    envuelta = envolver(crudo, esquemas=("pms",))
    assert envolver(envuelta, esquemas=("crm",)) is envuelta
    assert envolver(None).dialecto == "sqlite" and envolver(":memory:").dialecto == "sqlite"
    with pytest.raises(TypeError):
        envolver(42)
    envuelta.executemany("CREATE TABLE IF NOT EXISTS pms.t (id TEXT)", [()])
    envuelta.cursor().executemany("INSERT INTO pms.t (id) VALUES (?)", [("a",), ("b",)])
    assert envuelta.execute("SELECT count(*) FROM pms.t").fetchone()[0] == 2
    envuelta.close()


# ¤persistencia-sql
def test_servicio_y_ruta_de_busqueda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    servicio = PersistenciaSqlService(cargar_config())
    assert not servicio.es_postgres and servicio.abrir().dialecto == "sqlite"
    assert PersistenciaSqlService(url="postgresql://x/y").es_postgres
    assert cerrar_conexiones_postgres() >= 0
