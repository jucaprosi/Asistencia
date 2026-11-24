# ¤persistencia-sql
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de migraciones (ADR-0023): nombres por sala, orden, inmutabilidad y confinamiento de schema."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import migrar_db
from scripts.verificar_migraciones import cargar_base, verificar_migraciones

ESQUEMA = "CREATE SCHEMA canal;\n"
LEGADO = "001_alinear_esquema_con_codigo.sql"


# ¤persistencia-sql
def _repo(tmp_path: Path, archivos: dict[str, str], esquema: str = ESQUEMA) -> tuple[Path, Path]:
    carpeta = tmp_path / "migraciones"
    carpeta.mkdir()
    for nombre, sql in archivos.items():
        (carpeta / nombre).write_text(sql, encoding="utf-8")
    ruta_esquema = tmp_path / "esquema.sql"
    ruta_esquema.write_text(esquema, encoding="utf-8")
    return carpeta, ruta_esquema


# ¤persistencia-sql
def _base(archivos: dict[str, str], esquema: str = ESQUEMA) -> dict[str, str]:
    return {"esquema.sql": esquema, **archivos}


# ¤persistencia-sql
def test_formato_correcto_y_legado_pasan(tmp_path: Path) -> None:
    archivos = {
        LEGADO: "ALTER TABLE pms.reservas_ref ADD COLUMN x text;",
        "202611240900_canal_whatsapp_indice_medios.sql": "CREATE INDEX i ON canal.medios (tipo);",
    }
    carpeta, esquema = _repo(tmp_path, archivos)
    assert verificar_migraciones(carpeta, esquema, _base({LEGADO: archivos[LEGADO]})) == []


# ¤persistencia-sql
@pytest.mark.parametrize(
    "nombre",
    ["002_canal_whatsapp_x.sql", "202611240900-canal_whatsapp-x.sql", "2026112409_canal_whatsapp_x.sql"],
)
def test_nombre_fuera_de_formato_falla(tmp_path: Path, nombre: str) -> None:
    carpeta, esquema = _repo(tmp_path, {nombre: "SELECT 1;"})
    assert any("formato" in v for v in verificar_migraciones(carpeta, esquema, None))


# ¤persistencia-sql
def test_sala_inexistente_falla(tmp_path: Path) -> None:
    carpeta, esquema = _repo(tmp_path, {"202611240900_facturacion_x.sql": "SELECT 1;"})
    assert any("sala" in v for v in verificar_migraciones(carpeta, esquema, None))


# ¤persistencia-sql
def test_marca_de_tiempo_repetida_falla(tmp_path: Path) -> None:
    carpeta, esquema = _repo(tmp_path, {
        "202611240900_canal_whatsapp_a.sql": "CREATE INDEX a ON canal.medios (tipo);",
        "202611240900_arm_jarvis_b.sql": "CREATE INDEX b ON arm.ventas (estado);",
    })
    assert any("marca de tiempo" in v for v in verificar_migraciones(carpeta, esquema, None))


# ¤persistencia-sql
def test_migracion_nueva_anterior_a_la_ultima_de_main_falla(tmp_path: Path) -> None:
    en_main = {"202611241000_arm_jarvis_b.sql": "CREATE INDEX b ON arm.ventas (estado);"}
    nueva = {"202611240900_canal_whatsapp_a.sql": "CREATE INDEX a ON canal.medios (tipo);"}
    carpeta, esquema = _repo(tmp_path, {**en_main, **nueva})
    violaciones = verificar_migraciones(carpeta, esquema, _base(en_main))
    assert any("202611240900_canal_whatsapp_a.sql" in v and "antes" in v for v in violaciones)


# ¤persistencia-sql
def test_editar_migracion_o_linea_base_de_main_falla(tmp_path: Path) -> None:
    en_main = {"202611240900_canal_whatsapp_a.sql": "CREATE INDEX a ON canal.medios (tipo);"}
    carpeta, esquema = _repo(
        tmp_path,
        {"202611240900_canal_whatsapp_a.sql": "CREATE INDEX a ON canal.medios (estado);"},
        esquema="CREATE SCHEMA canal; -- editado\n",
    )
    violaciones = verificar_migraciones(carpeta, esquema, _base(en_main))
    assert any("202611240900_canal_whatsapp_a.sql" in v and "cambió" in v for v in violaciones)
    assert any("esquema.sql" in v and "cambió" in v for v in violaciones)


# ¤persistencia-sql
def test_schema_ajeno_sin_declarar_falla_y_declarado_pasa(tmp_path: Path) -> None:
    base_arm = {"202611240800_arm_jarvis_base.sql": "CREATE INDEX b ON arm.ventas (estado);"}
    ajena = {"202611240900_comisiones_x.sql": "ALTER TABLE arm.ventas ADD COLUMN c text;"}
    carpeta, esquema = _repo(tmp_path, {**base_arm, **ajena})
    assert any("arm" in v and "schema" in v for v in verificar_migraciones(carpeta, esquema, _base(base_arm)))

    (carpeta / "202611240900_comisiones_x.sql").write_text(
        "-- depende: 202611240800_arm_jarvis_base.sql\nALTER TABLE arm.ventas ADD COLUMN c text;",
        encoding="utf-8",
    )
    assert verificar_migraciones(carpeta, esquema, _base(base_arm)) == []


# ¤persistencia-sql
def test_dependencia_inexistente_o_posterior_falla(tmp_path: Path) -> None:
    carpeta, esquema = _repo(tmp_path, {
        "202611240900_comisiones_x.sql": "-- depende: 202611241000_arm_jarvis_y.sql\nSELECT 1;",
        "202611241000_arm_jarvis_y.sql": "-- depende: 209901010000_arm_jarvis_no_existe.sql\nSELECT 1;",
    })
    violaciones = verificar_migraciones(carpeta, esquema, None)
    assert any("posterior" in v for v in violaciones)
    assert any("no existe" in v for v in violaciones)


# ¤persistencia-sql
def test_migrar_db_rechaza_dependencia_que_no_se_aplica_antes() -> None:
    archivos = [
        ("000_linea_base.sql", "SELECT 1;"),
        ("202611240900_comisiones_x.sql", "-- depende: 202611241000_arm_jarvis_y.sql\nSELECT 1;"),
        ("202611241000_arm_jarvis_y.sql", "SELECT 1;"),
    ]
    with pytest.raises(RuntimeError, match="depende"):
        migrar_db.validar_dependencias(archivos)
    migrar_db.validar_dependencias([archivos[0], archivos[2]])


# ¤persistencia-sql
def test_el_repositorio_cumple_el_arbitro() -> None:
    raiz = Path(__file__).resolve().parents[2]
    violaciones = verificar_migraciones(
        raiz / "docs" / "spec" / "migraciones", raiz / "docs" / "spec" / "esquema.sql", cargar_base("origin/main")
    )
    assert violaciones == [], violaciones
