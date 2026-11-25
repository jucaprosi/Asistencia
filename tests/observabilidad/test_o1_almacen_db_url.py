# ¤observabilidad
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-414 (docs/spec/tareas/T-414.md; O-1, T1-b): el almacén de observabilidad abre la base de ``config["db_url"]``.

``app_core`` ya resuelve ``config_observabilidad.yaml`` con el ``env`` inyectado (``db_url: ${DATABASE_URL:-}``),
pero ``AlmacenTrazas`` ignoraba ``db_url`` y abría con ``envolver(None)``, que lee ``os.environ``. Si divergen, la
guarda de la cuota cree que hay PostgreSQL y el almacén usa SQLite en memoria (cuota por instancia). La sala lee
solo su config (ADPA §2.4): nunca ``os.environ``. R2: un ``db_url`` vacío o sin resolver es SQLite en memoria.
R4: ninguna prueba declara un PostgreSQL falso en ``DATABASE_URL``.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import pytest

from features.observabilidad import trazas_internal
from features.observabilidad.cuota_internal import dia_de_cuota
from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.persistencia_sql.persistencia_sql_service import es_postgres

URL_PG = os.environ.get("TEST_DATABASE_URL", "")
requiere_pg = pytest.mark.skipif(not es_postgres(URL_PG), reason="TEST_DATABASE_URL no apunta a PostgreSQL")
# Puerto 1 de loopback: PostgreSQL inalcanzable sin salir de la máquina (cero red externa).
URL_PG_INALCANZABLE = "postgresql://qa@127.0.0.1:1/qa?connect_timeout=2"
TOPE_AMPLIO = Decimal("1000")
COSTO = Decimal("0.000123")
MICRO = 123
RAIZ = Path(__file__).resolve().parents[2]
PLACEHOLDER = "${DATABASE_URL:-}"
# R4: un literal postgres:// o postgresql:// asignado a la clave DATABASE_URL en el código de una prueba.
RX_POSTGRES_FALSO = re.compile(r"""["']DATABASE_URL["']\s*:\s*["']postgres(ql)?://""")


# ¤observabilidad
def _config(db_url: str) -> Mapping[str, Any]:
    return {**cargar_config(), "db_url": db_url}


# ¤observabilidad
def _gastado_en_pg() -> int:
    import psycopg

    with psycopg.connect(URL_PG) as con:
        fila = con.execute(
            "SELECT gastado_micro FROM observabilidad.cuota_inferencia WHERE dia = %s",
            (dia_de_cuota(datetime.now(timezone.utc)),),
        ).fetchone()
        return int(fila[0]) if fila else 0


# ¤observabilidad
def test_o1_db_url_postgres_inalcanzable_no_cae_a_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """``db_url`` pide PostgreSQL y no está: la cuota no puede reservar en SQLite en memoria (falla cerrada)."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        cuota = ObservabilidadService(_config(URL_PG_INALCANZABLE)).cuota_inferencia(TOPE_AMPLIO)
        reservado = cuota.reservar(COSTO)
    except Exception:
        return  # negarse a construir o a reservar también es falla cerrada
    assert reservado is False, "la cuota reservó en SQLite aunque db_url pedía PostgreSQL"


# ¤observabilidad
@requiere_pg
def test_o1_db_url_postgres_reserva_en_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con la URL solo en ``db_url`` (``os.environ`` vacío), la reserva llega a PostgreSQL."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    cuota = ObservabilidadService(_config(URL_PG)).cuota_inferencia(TOPE_AMPLIO)
    antes = _gastado_en_pg()
    assert cuota.reservar(COSTO) is True
    try:
        assert _gastado_en_pg() - antes == MICRO, "la reserva no llegó a PostgreSQL: el almacén ignoró db_url"
    finally:
        cuota.conciliar(COSTO, Decimal("0"))  # P1: deshace solo su propio gasto


# ¤observabilidad
@requiere_pg
def test_o1_la_sala_no_lee_database_url_de_os_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    """``db_url`` vacío y ``DATABASE_URL`` en el proceso: la sala no debe tomarla del entorno (ADPA §2.4)."""
    monkeypatch.setenv("DATABASE_URL", URL_PG)
    cuota = ObservabilidadService(_config("")).cuota_inferencia(TOPE_AMPLIO)
    antes = _gastado_en_pg()
    assert cuota.reservar(COSTO) is True
    try:
        assert _gastado_en_pg() == antes, "la sala abrió la base de os.environ en lugar de su config"
    finally:
        cuota.conciliar(COSTO, Decimal("0"))


# ¤observabilidad
def _espiar_envolver(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Registra el origen que ``AlmacenTrazas`` le pasa a ``envolver`` y delega en la función real."""
    recibidos: list[Any] = []
    real = trazas_internal.envolver

    def espia(origen: Any = None, **opciones: Any) -> Any:
        recibidos.append(origen)
        return real(origen, **opciones)

    monkeypatch.setattr(trazas_internal, "envolver", espia)
    return recibidos


# ¤observabilidad
def test_r1_almacen_pasa_db_url_y_nunca_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sin servidor: ``envolver`` recibe la URL de ``db_url`` o ``:memory:``; nunca ``None`` (que lee ``os.environ``)."""
    url = f"sqlite:///{(tmp_path / 'trazas.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'del_proceso.db').as_posix()}")
    recibidos = _espiar_envolver(monkeypatch)
    ObservabilidadService(_config(url))
    ObservabilidadService(_config(""))
    assert recibidos == [url, ":memory:"]
    assert not (tmp_path / "del_proceso.db").exists(), "la sala abrió la base de os.environ"


# ¤observabilidad
def test_r2_placeholder_sin_resolver_es_memoria(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Una sala construida sin el pasillo recibe el placeholder literal: es memoria, no un archivo con ese nombre."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    recibidos = _espiar_envolver(monkeypatch)
    cuota = ObservabilidadService(_config(PLACEHOLDER)).cuota_inferencia(TOPE_AMPLIO)
    assert recibidos == [":memory:"]
    assert cuota.reservar(COSTO) is True
    assert list(tmp_path.iterdir()) == [], "se creó un archivo en el directorio de trabajo"


# ¤observabilidad
def _declaraciones_de_postgres_falso(carpeta: Path) -> list[str]:
    hallazgos: list[str] = []
    for archivo in sorted(carpeta.rglob("*.py")):
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), start=1):
            if RX_POSTGRES_FALSO.search(linea):
                hallazgos.append(f"{archivo.relative_to(carpeta).as_posix()}:{numero}")
    return hallazgos


# ¤observabilidad
def test_r4_ninguna_prueba_declara_un_postgres_falso(tmp_path: Path) -> None:
    """Las pruebas que necesitan PostgreSQL lo toman de ``TEST_DATABASE_URL``; un literal haría conectar al almacén."""
    clave = "DATABASE_URL"  # el nombre va aparte para que esta prueba no se detecte a sí misma
    malo = ["ENTORNO = {", f'    "{clave}": "postgresql://prueba",', "}"]
    (tmp_path / "test_malo.py").write_text("\n".join(malo), encoding="utf-8")
    (tmp_path / "test_malo_simple.py").write_text(f"ENTORNO = {{'{clave}' : 'postgres://x'}}", encoding="utf-8")
    bueno = ['URL = os.environ.get("TEST_DATABASE_URL", "")', f'ENTORNO = {{"{clave}": URL}}']
    (tmp_path / "test_bueno.py").write_text("\n".join(bueno), encoding="utf-8")
    assert _declaraciones_de_postgres_falso(tmp_path) == ["test_malo.py:2", "test_malo_simple.py:1"]
    assert _declaraciones_de_postgres_falso(RAIZ / "tests") == []
