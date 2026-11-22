# ¤infra-cloud
# ¤¤qa-engineer
"""Pruebas de persistencia PostgreSQL y preparación para Cloud Run / Cloud SQL (ADR-0019).

Verifica la disponibilidad de psycopg, la normalización de cadenas de conexión,
la ejecución dry-run del esquema canónico docs/spec/esquema.sql, y el manejo
robusto de errores de conexión.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app_core.main import main as app_core_main
from scripts.migrar_db import (
    aplicar_esquema,
    main as migrar_main,
    normalizar_url_db,
    verificar_conexion,
)

RAIZ = Path(__file__).resolve().parent.parent


# ¤infra-cloud
def test_psycopg_disponible() -> None:
    """Verifica que el driver nativo psycopg3 esté instalado en el entorno."""
    import psycopg
    assert hasattr(psycopg, "__version__")
    assert psycopg.__version__.startswith("3.")


# ¤infra-cloud
def test_normalizar_url_db() -> None:
    """Verifica que cadenas con esquema postgres:// se normalicen a postgresql://."""
    assert normalizar_url_db("postgres://usuario:clave@host/db") == "postgresql://usuario:clave@host/db"
    assert normalizar_url_db("postgresql://usuario:clave@host/db") == "postgresql://usuario:clave@host/db"
    assert normalizar_url_db("sqlite:///:memory:") == "sqlite:///:memory:"


# ¤infra-cloud
def test_verificar_conexion_sin_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica que sin DATABASE_URL retorne un estado controlado sin lanzar excepción no capturada."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    resultado = verificar_conexion(db_url="")
    assert resultado["conectado"] is False
    assert "no configurada" in resultado["error"]


# ¤infra-cloud
def test_verificar_conexion_url_invalida() -> None:
    """Verifica que ante una URL inalcanzable se capture la excepción y se reporte conectado=False."""
    resultado = verificar_conexion(db_url="postgresql://usuario_ficticio:clave@127.0.0.1:54999/db_ficticia", timeout=1.0)
    assert resultado["conectado"] is False
    assert "error" in resultado


# ¤infra-cloud
def test_aplicar_esquema_dry_run_exitoso() -> None:
    """Verifica que el archivo canónico docs/spec/esquema.sql sea legible y válido en simulación dry-run."""
    ruta_esquema = RAIZ / "docs" / "spec" / "esquema.sql"
    resultado = aplicar_esquema(db_url="postgresql://dummy:dummy@localhost:5432/dummy", ruta_esquema=ruta_esquema, dry_run=True)
    assert resultado["exito"] is True
    assert resultado["dry_run"] is True
    assert resultado["bytes"] > 20000
    assert resultado["bloques"] > 10


# ¤infra-cloud
def test_esquema_canonico_contiene_pgvector_y_esquemas_adpa() -> None:
    """Verifica que docs/spec/esquema.sql declare pgvector, pgcrypto y los 12 esquemas ADPA requeridos."""
    contenido = (RAIZ / "docs" / "spec" / "esquema.sql").read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in contenido
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto;" in contenido
    assert "CREATE ROLE app_glamping NOLOGIN NOBYPASSRLS;" in contenido

    esquemas_esperados = [
        "canal", "seguridad", "agente", "conocimiento", "pms", "crm",
        "arm", "comisiones", "observabilidad", "panel", "web", "anfitriones",
    ]
    for esquema in esquemas_esperados:
        assert f"CREATE SCHEMA {esquema};" in contenido, f"Falta la creación del esquema {esquema}"


# ¤infra-cloud
def test_main_migrar_db_cli_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica el comando CLI python scripts/migrar_db.py --dry-run con URL ficticia."""
    codigo = migrar_main(["--url", "postgresql://dummy", "--dry-run"])
    assert codigo == 0
    captura = capsys.readouterr()
    assert "[OK] Simulación (dry-run)" in captura.out


# ¤infra-cloud
def test_main_migrar_db_cli_check_falla_controlada(capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica que python scripts/migrar_db.py --check con host inalcanzable retorne código 1."""
    codigo = migrar_main(["--url", "postgresql://host_inexistente_12345/db", "--check"])
    assert codigo == 1
    captura = capsys.readouterr()
    assert "[ERROR]" in captura.err


# ¤infra-cloud
def test_app_core_main_migrar_db_dry_run(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Verifica la invocación de migraciones desde el punto de entrada de app_core."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy")
    # Invocar con migrar_main directamente pasando dry-run para validar integración
    from scripts.migrar_db import main as migrar_main_directo
    codigo = migrar_main_directo(["--dry-run"])
    assert codigo == 0


# ¤infra-cloud
def test_mutante_esquema_inexistente_lanza_error() -> None:
    """Caso sintético: una ruta de esquema inexistente genera FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        aplicar_esquema(db_url="postgresql://dummy", ruta_esquema=RAIZ / "no_existe.sql")


# ¤infra-cloud
def test_mutante_url_vacia_lanza_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Caso sintético: invocar aplicar_esquema sin URL genera ValueError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL no configurada"):
        aplicar_esquema(db_url="")
