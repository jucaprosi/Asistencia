# ¤persistencia-sql
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de migraciones (ADR-0023): nombres por sala, orden, inmutabilidad y confinamiento de schema."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import migrar_db
from scripts.verificar_migraciones import SCHEMAS_POR_SALA, cargar_base, main, verificar_migraciones

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
def test_schema_ajeno_sin_declarar_falla_y_referencia_declarada_pasa(tmp_path: Path) -> None:
    base_arm = {"202611240800_arm_jarvis_base.sql": "CREATE INDEX b ON arm.ventas (estado);"}
    ajena = {"202611240900_comisiones_x.sql": "ALTER TABLE comisiones.c ADD COLUMN v uuid REFERENCES arm.ventas (id);"}
    carpeta, esquema = _repo(tmp_path, {**base_arm, **ajena})
    assert any("arm" in v and "schema" in v for v in verificar_migraciones(carpeta, esquema, _base(base_arm)))

    (carpeta / "202611240900_comisiones_x.sql").write_text(
        "-- depende: 202611240800_arm_jarvis_base.sql\n" + ajena["202611240900_comisiones_x.sql"], encoding="utf-8"
    )
    assert verificar_migraciones(carpeta, esquema, _base(base_arm)) == []


# ¤persistencia-sql
@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE arm.ventas ADD COLUMN c text;",
        "DROP TABLE arm.ventas;",
        "CREATE INDEX x ON arm.ventas (estado);",
        "INSERT INTO arm.ventas (id) VALUES (1);",
        "UPDATE arm.ventas SET estado = 'x';",
        "DELETE FROM arm.ventas;",
        "TRUNCATE arm.ventas;",
    ],
)
def test_depende_no_da_permiso_de_escritura_en_schema_ajeno(tmp_path: Path, sql: str) -> None:
    base_arm = {"202611240800_arm_jarvis_base.sql": "CREATE INDEX b ON arm.ventas (estado);"}
    carpeta, esquema = _repo(tmp_path, {
        **base_arm,
        "202611240900_comisiones_x.sql": f"-- depende: 202611240800_arm_jarvis_base.sql\n{sql}",
    })
    assert any("escribe" in v for v in verificar_migraciones(carpeta, esquema, None))


# ¤persistencia-sql
@pytest.mark.parametrize(
    "sql",
    [
        'ALTER TABLE "pms"."reservas_ref" DROP COLUMN total;',
        "SET search_path TO pms; ALTER TABLE reservas_ref DROP COLUMN total;",
        "SELECT set_config('search_path', 'pms', false);",
        "CREATE SCHEMA nuevo; CREATE TABLE nuevo.t (id int);",
        "CREATE TABLE t (id int);",
        "/* comentario */ ALTER TABLE pms.reservas_ref DROP COLUMN total;",
    ],
)
def test_evasiones_de_la_deteccion_fallan(tmp_path: Path, sql: str) -> None:
    carpeta, esquema = _repo(tmp_path, {"202611240900_agente_x.sql": sql})
    assert verificar_migraciones(carpeta, esquema, None) != []


# ¤persistencia-sql
@pytest.mark.parametrize(
    "sql",
    [
        "DROP SCHEMA pms CASCADE;",
        "ALTER SCHEMA pms RENAME TO pms_viejo;",
        "SELECT * INTO pms.copia FROM agente.t;",
        "COPY pms.reservas_ref FROM '/tmp/x.csv';",
        "ALTER INDEX pms.idx RENAME TO idx2;",
        "COMMENT ON TABLE pms.reservas_ref IS 'x';",
        "MERGE INTO pms.reservas_ref r USING agente.t a ON r.id = a.id WHEN MATCHED THEN DELETE;",
        "INSERT INTO agente.t VALUES ('a--b'); DROP TABLE pms.reservas_ref;",
        "INSERT INTO agente.t VALUES ('a/*b'); DROP TABLE pms.reservas_ref; -- */",
        "DO $$ BEGIN EXECUTE 'DROP TABLE ' || 'pm' || 's.reservas_ref'; END $$;",
        "GRANT ALL ON SCHEMA pms TO public;",
    ],
)
def test_huecos_del_redictamen_fallan_aun_con_depende(tmp_path: Path, sql: str) -> None:
    base_pms = {"202611240800_pms_conector_base.sql": "CREATE INDEX b ON pms.reservas_ref (id);"}
    carpeta, esquema = _repo(tmp_path, {
        **base_pms,
        "202611240900_agente_x.sql": f"-- depende: 202611240800_pms_conector_base.sql\n{sql}",
    })
    violaciones = verificar_migraciones(carpeta, esquema, None)
    assert any("202611240900_agente_x.sql" in v for v in violaciones), violaciones


# ¤persistencia-sql
def test_mencion_en_literal_pasa(tmp_path: Path) -> None:
    carpeta, esquema = _repo(tmp_path, {
        "202611240900_agente_x.sql": "COMMENT ON TABLE agente.t IS 'copia de pms.reservas_ref -- y /* nada */';"
    })
    assert verificar_migraciones(carpeta, esquema, None) == []


# ¤persistencia-sql
@pytest.mark.parametrize("nombre", ["202611240900_herramientas_glamping_x.sql", "202611240900_inferencia_x.sql"])
def test_sala_sin_schema_o_inexistente_no_tiene_migraciones(tmp_path: Path, nombre: str) -> None:
    carpeta, esquema = _repo(tmp_path, {nombre: "SELECT 1;"})
    assert verificar_migraciones(carpeta, esquema, None) != []


# ¤persistencia-sql
@pytest.mark.parametrize("marca", ["209913991299", "209901010000"])
def test_marca_invalida_o_futura_falla(tmp_path: Path, marca: str) -> None:
    carpeta, esquema = _repo(tmp_path, {f"{marca}_canal_whatsapp_x.sql": "CREATE INDEX a ON canal.medios (tipo);"})
    assert any("marca" in v for v in verificar_migraciones(carpeta, esquema, None))


# ¤persistencia-sql
def test_segundo_nombre_heredado_falla(tmp_path: Path) -> None:
    carpeta, esquema = _repo(tmp_path, {LEGADO: "SELECT 1;", "002_alinear_otra_cosa.sql": "SELECT 1;"})
    assert any("002_alinear_otra_cosa.sql" in v for v in verificar_migraciones(carpeta, esquema, None))


# ¤persistencia-sql
def test_mapa_de_schemas_coincide_con_salas_y_esquema() -> None:
    raiz = Path(__file__).resolve().parents[2]
    salas = {p.name for p in (raiz / "features").iterdir() if p.is_dir() and not p.name.startswith("_")}
    assert set(SCHEMAS_POR_SALA) == salas
    duenos: dict[str, list[str]] = {}
    for sala, schemas in SCHEMAS_POR_SALA.items():
        for schema in schemas:
            duenos.setdefault(schema, []).append(sala)
    assert all(len(d) == 1 for d in duenos.values()), duenos
    creados = re.findall(r"^CREATE SCHEMA (\w+);", (raiz / "docs/spec/esquema.sql").read_text(encoding="utf-8"), re.M)
    assert creados and all(len(duenos.get(s, [])) == 1 for s in creados), creados


# ¤persistencia-sql
def test_exigir_base_falla_sin_base() -> None:
    assert main(["--base", "rama-que-no-existe", "--exigir-base"]) == 1


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
    base = cargar_base("origin/main")
    if base is None:
        pytest.skip("origin/main no disponible: no se puede comparar contra la rama base")
    violaciones = verificar_migraciones(raiz / "docs" / "spec" / "migraciones", raiz / "docs" / "spec" / "esquema.sql", base)
    assert violaciones == [], violaciones
