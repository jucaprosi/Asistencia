# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Decisión del propietario (2026-11-25, ADR-0021): el día de la cuota es el de Google Cloud.

Las cuotas diarias de Google Cloud se reinician a medianoche, hora del Pacífico (America/Los_Angeles).
La cuota de inferencia y la alerta de costo diario usan ese mismo día, con su horario de verano.
"""
from __future__ import annotations

import re
import tomllib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from features.observabilidad.alertas_internal import costo_del_dia
from features.observabilidad.cuota_internal import dia_de_cuota
from features.observabilidad.tipos import Span, Traza

RAIZ = Path(__file__).resolve().parents[2]


# ¤inferencia
def _utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)


# ¤inferencia
@pytest.mark.parametrize(
    ("instante", "dia"),
    [
        ("2026-11-25T07:59:59", "2026-11-24"),  # PST (UTC-8): aún es el 24 en California
        ("2026-11-25T08:00:00", "2026-11-25"),
        ("2026-07-01T06:59:59", "2026-06-30"),  # PDT (UTC-7)
        ("2026-07-01T07:00:00", "2026-07-01"),
        # r7: días del cambio de hora de 2026 (23 h el 8 de marzo, 25 h el 1 de noviembre)
        ("2026-03-08T07:59:59", "2026-03-07"),
        ("2026-03-08T08:00:00", "2026-03-08"),  # empieza en PST
        ("2026-03-09T06:59:59", "2026-03-08"),
        ("2026-03-09T07:00:00", "2026-03-09"),  # ya en PDT
        ("2026-11-01T06:59:59", "2026-10-31"),
        ("2026-11-01T07:00:00", "2026-11-01"),  # empieza en PDT
        ("2026-11-02T07:59:59", "2026-11-01"),
        ("2026-11-02T08:00:00", "2026-11-02"),  # ya en PST
    ],
)
def test_el_dia_de_la_cuota_es_el_del_pacifico(instante: str, dia: str) -> None:
    assert dia_de_cuota(_utc(instante)) == dia


# ¤inferencia
def test_el_dia_exige_un_instante_con_zona() -> None:
    with pytest.raises(ValueError):
        dia_de_cuota(datetime(2026, 11, 25, 12, 0))


# ¤inferencia
def _traza(inicio: str, costo: str) -> Traza:
    span = Span("s", "t", "inferencia", "llamada_modelo", _utc(inicio), 1, costo_usd=Decimal(costo))
    return Traza("t", None, None, "huespedes", _utc(inicio), spans=(span,))


# ¤inferencia
def test_el_costo_diario_de_las_alertas_usa_el_mismo_dia() -> None:
    trazas = [
        _traza("2026-11-25T07:30:00", "1.50"),  # 24 en el Pacífico
        _traza("2026-11-25T08:30:00", "2.25"),  # 25 en el Pacífico
        _traza("2026-11-26T07:00:00", "4.00"),  # 25 en el Pacífico
    ]
    assert costo_del_dia(trazas, _utc("2026-11-25T23:00:00")) == pytest.approx(6.25)


# ¤inferencia
def test_una_traza_antigua_sin_zona_no_tumba_la_alerta() -> None:
    antigua = _traza("2026-11-25T09:00:00", "1.00")
    antigua = Traza("t", None, None, "huespedes", antigua.inicio.replace(tzinfo=None), spans=antigua.spans)
    assert costo_del_dia([antigua], _utc("2026-11-25T23:00:00")) == pytest.approx(1.0)


# ¤inferencia
def test_r5_la_base_de_zonas_viaja_con_la_app_y_en_el_candado() -> None:
    # r5: sin depender de que la imagen base traiga zoneinfo; si falta, la app no arranca.
    dependencias = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    tz = [d for d in dependencias if d.replace(" ", "").startswith("tzdata")]
    assert tz and ";" not in tz[0], "tzdata en dependencies y sin marcador de plataforma"
    assert re.search(r"^tzdata==\S+ \\\n\s+--hash=sha256:", (RAIZ / "requirements.lock").read_text(encoding="utf-8"), re.M)
