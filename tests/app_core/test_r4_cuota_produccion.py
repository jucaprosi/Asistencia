# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""r4 (dictamen del Arquitecto sobre el ADR-0021): en producción sin PostgreSQL no hay tope diario.

Sin una ``DATABASE_URL`` de PostgreSQL, observabilidad cae a SQLite en memoria: la cuota sería por instancia de
Cloud Run y el tope dejaría de ser tope. ``construir()`` debe pasar ``cuota=None`` y la sala falla cerrada.
``AlmacenTrazas`` lee ``DATABASE_URL`` de ``os.environ``, por eso se ajusta también con ``monkeypatch``.
"""
from __future__ import annotations

import pytest

from app_core.app_core_service import construir
from tests.app_core.test_contenedor import ENTORNO_PRUEBA


# ¤inferencia
def _entorno(monkeypatch: pytest.MonkeyPatch, app_env: str, database_url: str | None) -> dict[str, str]:
    for clave in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL"):
        monkeypatch.delenv(clave, raising=False)
    entorno = {**ENTORNO_PRUEBA, "APP_ENV": app_env, "GOOGLE_CLOUD_PROJECT": "proyecto-de-prueba", "VERTEX_LOCATION": "us"}
    entorno.pop("ANTHROPIC_API_KEY", None)
    entorno.pop("DATABASE_URL", None)
    if database_url is not None:
        entorno["DATABASE_URL"] = database_url
        monkeypatch.setenv("DATABASE_URL", database_url)
    return entorno


# ¤inferencia
def test_r4_produccion_sin_database_url_no_tiene_tope(monkeypatch: pytest.MonkeyPatch) -> None:
    estado = construir(entorno=_entorno(monkeypatch, "produccion", None)).inferencia.estado()
    assert estado.motivo == "sin_tope_diario"
    assert estado.con_tope_diario is False


# ¤inferencia
def test_r4_produccion_con_sqlite_no_tiene_tope(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'r4.db').as_posix()}"
    estado = construir(entorno=_entorno(monkeypatch, "produccion", url)).inferencia.estado()
    assert estado.motivo == "sin_tope_diario"
    assert estado.con_tope_diario is False


# ¤inferencia
def test_r4_beta_sin_database_url_mantiene_la_cuota(monkeypatch: pytest.MonkeyPatch) -> None:
    estado = construir(entorno=_entorno(monkeypatch, "beta", None)).inferencia.estado()
    assert estado.motivo != "sin_tope_diario"
    assert estado.con_tope_diario is True
