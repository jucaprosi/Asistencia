# ¤persistencia-sql
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Contrato de la sala persistencia_sql y de los repositorios portados, en SQLite y en PostgreSQL real.

Las pruebas de PostgreSQL se ejecutan solo si ``TEST_DATABASE_URL`` apunta a una base con el esquema de
``docs/spec/esquema.sql`` aplicado (``python scripts/migrar_db.py``), por ejemplo el servicio
``postgres-beta`` de ``compose.yaml``. Sin esa variable se omiten y el resto corre en SQLite.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from features.canal_whatsapp.canal_whatsapp_service import Canal
from features.canal_whatsapp.persistencia_internal import RepositorioCanal
from features.persistencia_sql.persistencia_sql_service import (
    Conexion,
    _a_formato_psycopg,
    abrir_conexion,
    es_postgres,
)

URL_PG = os.environ.get("TEST_DATABASE_URL", "")
requiere_pg = pytest.mark.skipif(not es_postgres(URL_PG), reason="TEST_DATABASE_URL no apunta a PostgreSQL")


# ¤persistencia-sql
def test_sin_url_abre_sqlite_en_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    conexion = abrir_conexion()
    assert conexion.dialecto == "sqlite"


# ¤persistencia-sql
def test_detecta_postgres_por_prefijo() -> None:
    assert es_postgres("postgresql://u@h/db") and es_postgres("postgres://u@h/db")
    assert not es_postgres("sqlite:///x.db") and not es_postgres("") and not es_postgres(None)


# ¤persistencia-sql
def test_marcadores_se_traducen_sin_tocar_literales() -> None:
    sql = "SELECT * FROM t WHERE a = ? AND b LIKE 'x?%' AND c = ?"
    assert _a_formato_psycopg(sql) == "SELECT * FROM t WHERE a = %s AND b LIKE 'x?%%' AND c = %s"


# ¤persistencia-sql
def test_sqlite_emula_esquemas_con_attach() -> None:
    conexion = abrir_conexion("", esquemas=("canal",))
    conexion.execute("CREATE TABLE canal.t (id TEXT PRIMARY KEY)")
    conexion.execute("INSERT INTO canal.t (id) VALUES (?)", ("a",))
    assert conexion.execute("SELECT id FROM canal.t").fetchone()["id"] == "a"


# ¤persistencia-sql
def test_envuelve_conexion_sqlite_existente() -> None:
    crudo = sqlite3.connect(":memory:")
    conexion = Conexion.desde_sqlite(crudo, esquemas=("canal",))
    repo = RepositorioCanal(conexion)
    assert repo.guardar_evento("m1", "c1", b"x")


# ¤persistencia-sql
@pytest.fixture
def repo_canal_pg() -> RepositorioCanal:
    conexion = abrir_conexion(URL_PG)
    conexion.execute(
        "TRUNCATE canal.medios, canal.mensajes_meta, canal.eventos_entrantes, canal.plantillas CASCADE"
    )
    conexion.commit()
    return RepositorioCanal(conexion)


# ¤persistencia-sql
@requiere_pg
def test_pg_evento_es_durable_e_idempotente(repo_canal_pg: RepositorioCanal) -> None:
    assert repo_canal_pg.guardar_evento("wamid.1", "conv-1", b"\x00cifrado")
    assert not repo_canal_pg.guardar_evento("wamid.1", "conv-1", b"\x00cifrado"), "reintento de Meta duplicado"

    # Una conexión nueva (otra instancia de Cloud Run) ve el evento: ya no vive en memoria.
    otro = RepositorioCanal(abrir_conexion(URL_PG))
    evento = otro.obtener_evento("wamid.1")
    assert evento is not None
    assert evento.cuerpo_cifrado == b"\x00cifrado"
    assert evento.recibido_en.tzinfo is not None
    assert [e.mensaje_id for e in otro.obtener_eventos_pendientes()] == ["wamid.1"]

    otro.actualizar_estado_evento(evento.evento_id, "procesado", intentos=1, procesado_en=datetime.now(timezone.utc))
    assert repo_canal_pg.obtener_evento_por_id(evento.evento_id).estado == "procesado"


# ¤persistencia-sql
@requiere_pg
def test_pg_mensajes_plantillas_y_medios(repo_canal_pg: RepositorioCanal) -> None:
    hace_una_hora = datetime.now(timezone.utc) - timedelta(hours=1)
    repo_canal_pg.guardar_mensaje_meta("wamid.2", "in", "tok-1", Canal.HUESPEDES, "texto", "recibido", enviado_en=hace_una_hora)
    repo_canal_pg.actualizar_estado_mensaje("wamid.2", "read")
    assert repo_canal_pg.obtener_mensaje_meta("wamid.2").estado == "read"
    ultimo = repo_canal_pg.ultimo_mensaje_entrante("tok-1")
    assert ultimo is not None and abs((ultimo - hace_una_hora).total_seconds()) < 1

    repo_canal_pg.guardar_plantilla("bienvenida", "utility", ("nombre", "fecha"), aprobada=False)
    repo_canal_pg.aprobar_plantilla("bienvenida")
    plantilla = repo_canal_pg.obtener_plantilla("bienvenida")
    assert plantilla.aprobada is True and plantilla.variables == ("nombre", "fecha")
    assert [p.nombre for p in repo_canal_pg.listar_plantillas()] == ["bienvenida"]

    expira = datetime.now(timezone.utc) + timedelta(days=90)
    repo_canal_pg.guardar_medio("med-1", "wamid.2", "s3://b/med-1", "imagen", 10, expira)
    repo_canal_pg.guardar_medio("med-2", None, "s3://b/med-2", "audio", 5, expira)
    assert repo_canal_pg.obtener_medio("med-1").mensaje_id == "wamid.2"
    assert repo_canal_pg.obtener_medio("med-2").mensaje_id is None


# ¤persistencia-sql
@requiere_pg
def test_pg_clave_foranea_se_traduce_a_integrity_error(repo_canal_pg: RepositorioCanal) -> None:
    expira = datetime.now(timezone.utc) + timedelta(days=1)
    with pytest.raises(sqlite3.IntegrityError):
        repo_canal_pg.guardar_medio("med-x", "no-existe", "s3://b/x", "imagen", 1, expira)
    # Tras el error la conexión sigue usable (se hizo rollback).
    assert repo_canal_pg.guardar_evento("wamid.3", "conv-3", b"y")
