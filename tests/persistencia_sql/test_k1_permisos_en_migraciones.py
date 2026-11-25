# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""K1 (ADR-0021) contra el árbitro del ADR-0023: seguridad puede dar permisos sobre la tabla de otra sala.

El ADR-0023 reserva GRANT/REVOKE a seguridad y persistencia_sql; el árbitro contaba el ``ON schema.tabla``
del GRANT como escritura en un schema ajeno, así que ninguna tabla nueva podía recibir permisos.
"""
from __future__ import annotations

import pytest

from scripts.verificar_migraciones import _violaciones_de_contenido

_GRANT = "GRANT SELECT, INSERT, UPDATE ON observabilidad.cuota_inferencia TO app_glamping;"


# ¤inferencia
def test_k1_seguridad_puede_dar_permisos_sobre_otro_schema() -> None:
    assert _violaciones_de_contenido("x_seguridad_p.sql", "seguridad", _GRANT) == []
    assert _violaciones_de_contenido("x_persistencia_sql_p.sql", "persistencia_sql", "REVOKE DELETE ON arm.t FROM app_glamping;") == []


# ¤inferencia
def test_k1_seguridad_sigue_sin_poder_escribir_en_otro_schema() -> None:
    sql = _GRANT + "\nINSERT INTO observabilidad.cuota_inferencia (dia) VALUES ('2026-11-25');"
    assert any("observabilidad" in v for v in _violaciones_de_contenido("x_seguridad_p.sql", "seguridad", sql))


# ¤inferencia
def test_k1_otra_sala_sigue_sin_poder_dar_permisos() -> None:
    assert any("GRANT" in v for v in _violaciones_de_contenido("x_observabilidad_p.sql", "observabilidad", _GRANT))


# ¤inferencia
@pytest.mark.parametrize(
    "sql",
    [
        "GRANT SELECT ON nadie.t TO app_glamping;",  # A1: schema desconocido
        "GRANT SELECT ON t TO app_glamping;",  # A1: sin schema
        "REVOKE SELECT ON nadie.t FROM app_glamping;",  # A1 también en REVOKE
    ],
)
def test_a1_el_on_de_un_permiso_es_un_schema_conocido(sql: str) -> None:
    assert _violaciones_de_contenido("x_seguridad_p.sql", "seguridad", sql)


# ¤inferencia
@pytest.mark.parametrize(
    "sql",
    [
        "GRANT SELECT ON observabilidad.cuota_inferencia TO PUBLIC;",
        "GRANT SELECT ON observabilidad.cuota_inferencia TO app_glamping WITH GRANT OPTION;",
        "GRANT ALL PRIVILEGES ON observabilidad.cuota_inferencia TO app_glamping;",
        "GRANT ALL ON observabilidad.cuota_inferencia TO app_glamping;",
        "GRANT SELECT ON ALL TABLES IN SCHEMA observabilidad TO app_glamping;",
        "GRANT USAGE ON SCHEMA observabilidad TO app_glamping;",
        "GRANT app_glamping TO otro_rol;",
        "GRANT SELECT ON observabilidad.cuota_inferencia TO app_glamping, public;",
    ],
)
def test_a2_un_grant_amplio_exige_un_adr(sql: str) -> None:
    violaciones = _violaciones_de_contenido("x_seguridad_p.sql", "seguridad", sql)
    assert any("ADR" in v for v in violaciones), violaciones


# ¤inferencia
@pytest.mark.parametrize(
    "sql",
    [
        _GRANT + "\nCREATE TABLE observabilidad.otra (id int);",
        "REVOKE DELETE ON arm.t FROM app_glamping;\nUPDATE observabilidad.cuota_inferencia SET gastado_micro = 0;",
    ],
)
def test_a1_un_permiso_no_tapa_una_escritura_ajena(sql: str) -> None:
    assert any("escribe en el schema" in v for v in _violaciones_de_contenido("x_seguridad_p.sql", "seguridad", sql))
