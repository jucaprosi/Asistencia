# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""K1 del dictamen del paso 4 (ADR-0021): la cuota diaria existe y es atómica en PostgreSQL real.

Las pruebas contra PostgreSQL corren solo si ``TEST_DATABASE_URL`` apunta a una base con las migraciones
aplicadas (``python scripts/migrar_db.py``); en CI lo hace un paso propio después de migrar.
"""
from __future__ import annotations

import os
import re
import threading
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

import pytest

from features.observabilidad.cuota_internal import CuotaDiaria
from features.persistencia_sql.persistencia_sql_service import envolver, es_postgres

RAIZ = Path(__file__).resolve().parents[2]
URL_PG = os.environ.get("TEST_DATABASE_URL", "")
requiere_pg = pytest.mark.skipif(not es_postgres(URL_PG), reason="TEST_DATABASE_URL no apunta a PostgreSQL")


# ¤inferencia
def _migracion_cuota() -> str:
    candidatas = sorted((RAIZ / "docs" / "spec" / "migraciones").glob("*_observabilidad_*.sql"))
    textos = [p.read_text(encoding="utf-8") for p in candidatas]
    return next((t for t in textos if re.search(r"create table[^;]*observabilidad\.cuota_inferencia", t, re.I)), "")


# ¤inferencia
def test_k1_una_migracion_de_observabilidad_crea_la_cuota() -> None:
    sql = _migracion_cuota().lower()
    assert sql, "falta la migración de observabilidad.cuota_inferencia"
    assert "gastado_micro" in sql and "primary key" in sql
    assert re.search(r"check\s*\(\s*gastado_micro\s*>=\s*0\s*\)", sql), "el gasto no puede ser negativo"
    permisos = "\n".join(p.read_text(encoding="utf-8") for p in (RAIZ / "docs" / "spec" / "migraciones").glob("*_seguridad_*.sql"))
    assert re.search(r"grant[^;]*on[^;]*observabilidad\.cuota_inferencia[^;]*to\s+app_glamping", permisos, re.I)


# ¤inferencia
def test_k1_el_runbook_explica_la_cuota_en_postgresql() -> None:
    runbook = (RAIZ / "docs" / "modulos" / "observabilidad.md").read_text(encoding="utf-8")
    assert "cuota_inferencia" in runbook and "migrar_db.py" in runbook


# ¤inferencia
def _fabrica() -> Any:
    conexion = envolver(URL_PG, ruta_busqueda="observabilidad")

    @contextmanager
    def obtener() -> Iterator[Any]:
        with conexion:
            yield conexion

    return conexion, obtener


# P1: un día ficticio, para no tocar el gasto real si TEST_DATABASE_URL apunta a una base con datos.
_DIA = "2000-01-01"


# ¤inferencia
@pytest.fixture
def dia_ficticio(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(CuotaDiaria, "_dia", staticmethod(lambda: _DIA))
    return _DIA


# ¤inferencia
@requiere_pg
def test_k1_reserva_concurrente_entre_conexiones_no_pasa_el_tope(dia_ficticio: str) -> None:
    limpieza, obtener_limpieza = _fabrica()
    with obtener_limpieza() as con:
        con.execute("DELETE FROM cuota_inferencia WHERE dia = ?", (dia_ficticio,))
    # Cada hilo con su propia conexión: la exclusión la da PostgreSQL, no el candado del proceso.
    cuotas = [CuotaDiaria(_fabrica()[1], Decimal("1.00")) for _ in range(40)]
    aceptadas: list[bool] = []
    barrera = threading.Barrier(len(cuotas))

    def reservar(cuota: CuotaDiaria) -> None:
        barrera.wait()
        aceptadas.append(cuota.reservar(Decimal("0.03")))

    hilos = [threading.Thread(target=reservar, args=(c,)) for c in cuotas]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    with obtener_limpieza() as con:
        gastado = con.execute("SELECT gastado_micro FROM cuota_inferencia WHERE dia = ?", (dia_ficticio,)).fetchone()[0]
    assert sum(aceptadas) == 33
    assert gastado == 33 * 30_000


# ¤inferencia
@requiere_pg
def test_k1_conciliar_en_postgresql_devuelve_lo_no_gastado(dia_ficticio: str) -> None:
    _, obtener = _fabrica()
    with obtener() as con:
        con.execute("DELETE FROM cuota_inferencia WHERE dia = ?", (dia_ficticio,))
    cuota = CuotaDiaria(obtener, Decimal("1.00"))
    assert cuota.reservar(Decimal("0.50"))
    cuota.conciliar(Decimal("0.50"), Decimal("0.10"))
    assert cuota.conciliaciones_fallidas == 0
    with obtener() as con:
        assert con.execute("SELECT gastado_micro FROM cuota_inferencia WHERE dia = ?", (dia_ficticio,)).fetchone()[0] == 100_000


# ¤inferencia
def test_p1_las_pruebas_en_postgresql_no_tocan_el_dia_real() -> None:
    fuente = Path(__file__).read_text(encoding="utf-8")
    assert fuente.count("CuotaDiaria._dia()") == 1  # solo esta línea; las pruebas usan el día ficticio
