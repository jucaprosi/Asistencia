# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Fixtures compartidas: raíz del repositorio y catálogo de salas (fuente: governance/artefactos/PRD.md §2)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIOS_EXCLUIDOS = {".git", "transcriptor_tiktok", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist"}

SALAS_FASE_0 = (
    "canal_whatsapp", "seguridad", "agente", "conocimiento", "pms_conector", "crm_conector", "arm_jarvis",
    "comisiones", "observabilidad", "herramientas_glamping", "panel_operativo", "web_huespedes", "anfitriones",
)


def archivos_python(*subdirectorios: str) -> list[Path]:
    """Todos los .py bajo los subdirectorios dados, sin los excluidos."""
    resultado: list[Path] = []
    for sub in subdirectorios:
        base = RAIZ / sub
        if not base.exists():
            continue
        for ruta in base.rglob("*.py"):
            if not any(parte in DIRECTORIOS_EXCLUIDOS for parte in ruta.parts):
                resultado.append(ruta)
    return sorted(resultado)


def salas_en_catalogo() -> tuple[str, ...]:
    """Lee las salas declaradas en governance/artefactos/PRD.md (filas con `features/<sala>`)."""
    prd = (RAIZ / "governance" / "artefactos" / "PRD.md").read_text(encoding="utf-8")
    return tuple(sorted(set(re.findall(r"`features/([a-z_]+)`", prd))))


@pytest.fixture(scope="session")
def raiz() -> Path:
    return RAIZ


@pytest.fixture(scope="session")
def salas() -> tuple[str, ...]:
    return SALAS_FASE_0


# ¤persistencia-sql
# Modo PostgreSQL de toda la suite: con GLAMPING_SUITE_POSTGRES=<url> cada repositorio que no recibe una
# conexión explícita usa esa base (DATABASE_URL), y las tablas se vacían antes de cada prueba.
_URL_SUITE_PG = __import__("os").environ.get("GLAMPING_SUITE_POSTGRES", "")


@pytest.fixture(autouse=True)
def _base_postgres_limpia(monkeypatch: pytest.MonkeyPatch):
    if not _URL_SUITE_PG:
        yield
        return
    import psycopg

    from features.persistencia_sql.persistencia_sql_service import cerrar_conexiones_postgres

    monkeypatch.setenv("DATABASE_URL", _URL_SUITE_PG)
    with psycopg.connect(_URL_SUITE_PG, autocommit=True) as con:
        tablas = [
            f"{esquema}.{tabla}"
            for esquema, tabla in con.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema', 'public')"
            )
        ]
        if tablas:
            con.execute("TRUNCATE " + ", ".join(tablas) + " CASCADE")
    yield
    cerrar_conexiones_postgres()
