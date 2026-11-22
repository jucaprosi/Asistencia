# ¤persistencia-sql
# ¤¤data-engineer
"""Consultas portadas a SQL común (ON CONFLICT, rangos) de crm_conector y seguridad, en SQLite."""
from __future__ import annotations

from datetime import datetime

import pytest

from features.crm_conector import persistencia_internal as crm
from features.crm_conector.tipos import ReferenciaCRM, Zona
from features.seguridad.persistencia_internal import inicializar_base_datos as iniciar_seguridad
from features.seguridad.rate_limit_internal import RateLimiter
from features.seguridad.tipos import LimiteExcedido


# ¤persistencia-sql
def test_crm_zonas_y_referencias_se_actualizan_con_on_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    conexion = crm.inicializar_base_datos()
    assert crm.obtener_zona(conexion, "no-existe") is None
    crm.insertar_zona(conexion, Zona("z1", "Uno", "g1", "g2"))
    crm.insertar_zona(conexion, Zona("z1", "Uno bis", "g3", "g4"))
    assert crm.obtener_zona(conexion, "z1") == Zona("z1", "Uno bis", "g3", "g4")
    assert "z1" in {z.zona_id for z in crm.listar_zonas(conexion)}

    assert crm.obtener_referencia(conexion, "contacto", "c1") is None
    crm.guardar_referencia(conexion, ReferenciaCRM("contacto", "c1", "r1"))
    crm.guardar_referencia(conexion, ReferenciaCRM("contacto", "c1", "r2"))
    assert crm.obtener_referencia(conexion, "contacto", "c1") == "r2"

    assert crm.obtener_handoff(conexion, "no-existe") is None
    assert crm.listar_handoffs(conexion, zona_id="z1", estado="abierto") == []
    assert crm._parse_iso(None) is None and crm._parse_iso("no-fecha") is None


# ¤persistencia-sql
def test_rate_limit_acepta_instante_sin_zona_y_exige(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    limitador = RateLimiter(iniciar_seguridad())
    instante = datetime(2026, 11, 22, 10, 0, 0)
    limitador.exigir("h1", instante=instante)
    limitador.exigir("h1", instante=instante)
    with pytest.raises(LimiteExcedido):
        limitador.exigir("h1", instante=instante)
