# ¤spec-glamping
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""G-2: árbitro de forma de las especificaciones de tarea (docs/spec/tareas/G-2.md, casos A1 a A11).

Cada mutante arma fichas y textos falsos (o un árbol en ``tmp_path``) y llama a la función real del
script (R5). E7 vive aquí: la lista original se escribe literal y ``SIN_SPEC`` solo se achica.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from scripts.verificar_especificaciones import (
    SECCIONES,
    SIN_SPEC,
    fichas,
    main,
    violaciones_de_especificacion,
    violaciones_del_repositorio,
)
from tests.conftest import RAIZ

E7_ORIGINAL = frozenset({
    "T-111", "T-211", "T-311", "T-410", "T-411", "T-511", "T-610", "T-810", "T-611", "T-701", "T-406-b",
})
PENDIENTE_FUERA_DE_TASKS = frozenset({"T-406-b"})

FICHA = {"id": "X-1", "estado": "pendiente", "propiedad": ["tests/x/test_a.py"], "crea": ["tests/x/test_a.py"]}
# A10: la ficha de G-2 se arma con los datos de su sección Datos, nunca desde TASKS.md.
FICHA_G2 = {
    "id": "G-2",
    "estado": "pendiente",
    "sala": "pasillo_central",
    "rol": "¤¤qa-engineer",
    "propiedad": ["scripts/verificar_especificaciones.py", "tests/test_verificar_especificaciones.py"],
    "crea": ["scripts/verificar_especificaciones.py", "tests/test_verificar_especificaciones.py"],
    "arbitro": "tests/test_verificar_especificaciones.py",
}
CABECERA = "| Caso | Dado/entonces | Prueba | Mutación |\n| :--- | :--- | :--- | :--- |"
FILA = "| A1 | dado X, entonces Y | tests/x/test_a.py::test_y | m1: quitar la guarda |"
VALIDAS = {
    "Datos": "Medido sobre `origin/main 077ab65`.",
    "API": "`def y() -> int`",
    "Reglas": "Y vale si X.",
    "Interfaz": "No aplica: sin texto de cara al usuario.",
    "Aceptación": f"{CABECERA}\n{FILA}",
    "Trazabilidad": "- `¤spec-glamping`",
}


def _texto(orden: tuple[str, ...] = SECCIONES, **cuerpos: str) -> str:
    """Especificación de X-1: las secciones en ``orden``, con los cuerpos válidos salvo los que se reemplazan."""
    secciones = {**VALIDAS, **cuerpos}
    return "# X-1\n\n" + "\n\n".join(f"## {titulo}\n\n{secciones[titulo]}" for titulo in orden) + "\n"


def _nunca(_ruta: str) -> None:
    return None


def _define_test_y(_ruta: str) -> str:
    return "def test_y():\n    assert True\n"


def _reglas(violaciones: list[str], id_: str = "X-1") -> list[str]:
    return [re.match(rf"{re.escape(id_)}: (E\d)", v).group(1) for v in violaciones]


def _toml(ficha: dict) -> str:
    def valor(v: object) -> str:
        return "[" + ", ".join(f'"{x}"' for x in v) + "]" if isinstance(v, list) else f'"{v}"'

    return "```toml\n" + "".join(f"{clave} = {valor(v)}\n" for clave, v in ficha.items()) + "```\n"


def test_e1_ficha_sin_especificacion():
    assert violaciones_de_especificacion(FICHA, _texto(), _nunca) == []
    # m1: texto None devuelve [].
    violaciones = violaciones_de_especificacion(FICHA, None, _nunca)
    assert _reglas(violaciones) == ["E1"], violaciones


def test_e2_secciones_en_orden_y_unicas():
    sin_interfaz = tuple(s for s in SECCIONES if s != "Interfaz")
    assert "E2" in _reglas(violaciones_de_especificacion(FICHA, _texto(sin_interfaz), _nunca))
    # m2: solo se comprueba que existan.
    desordenadas = ("Datos", "Reglas", "API", "Interfaz", "Aceptación", "Trazabilidad")
    assert _reglas(violaciones_de_especificacion(FICHA, _texto(desordenadas), _nunca)) == ["E2"]
    repetida = ("Datos", *SECCIONES)
    assert _reglas(violaciones_de_especificacion(FICHA, _texto(repetida), _nunca)) == ["E2"]
    # Un título dentro de un bloque de código no cuenta: ni suple una sección ni la repite.
    interfaz_en_codigo = _texto(sin_interfaz).replace("## Aceptación", "```\n## Interfaz\n```\n\n## Aceptación")
    assert "E2" in _reglas(violaciones_de_especificacion(FICHA, interfaz_en_codigo, _nunca))
    datos_en_codigo = _texto(Reglas="```markdown\n## Datos\n## API\n```")
    assert violaciones_de_especificacion(FICHA, datos_en_codigo, _nunca) == []
    # Otros títulos de nivel 2 entre las seis, y los de nivel 3, son libres.
    extra = _texto().replace("## Interfaz", "## Notas\n\nlibre\n\n### Detalle\n\n## Interfaz")
    assert violaciones_de_especificacion(FICHA, extra, _nunca) == []


def test_e3_seccion_vacia():
    # m3: solo se mira la sección final; Interfaz está en medio.
    violaciones = violaciones_de_especificacion(FICHA, _texto(Interfaz=""), _nunca)
    assert _reglas(violaciones) == ["E3"], violaciones
    assert violaciones_de_especificacion(FICHA, _texto(Interfaz="No aplica."), _nunca) == []
    # Las secciones adicionales no se miden.
    notas_vacias = _texto().replace("## Interfaz", "## Notas\n\n## Interfaz")
    assert violaciones_de_especificacion(FICHA, notas_vacias, _nunca) == []


def test_e4_datos_sin_sha():
    assert _reglas(violaciones_de_especificacion(FICHA, _texto(Datos="Medido sobre main."), _nunca)) == ["E4"]
    # m4: origin/main sin SHA.
    sin_sha = _texto(Datos="Medido sobre `origin/main`, el de hoy.")
    assert _reglas(violaciones_de_especificacion(FICHA, sin_sha, _nunca)) == ["E4"]
    largo = _texto(Datos="Medido sobre origin/main (077ab65cde9ef53e377c440df926da03e3045656).")
    assert violaciones_de_especificacion(FICHA, largo, _nunca) == []


def test_e5_tabla_de_aceptacion():
    assert violaciones_de_especificacion(FICHA, _texto(), _define_test_y) == []
    # m5: la ruta de la prueba no está en propiedad ni en crea.
    ajena = _texto(Aceptación=f"{CABECERA}\n{FILA.replace('tests/x/test_a.py', 'tests/otra/test_b.py')}")
    violaciones = violaciones_de_especificacion(FICHA, ajena, _define_test_y)
    assert _reglas(violaciones) == ["E5"] and "tests/otra/test_b.py" in violaciones[0], violaciones
    # El archivo existe y no define la función.
    otra_funcion = violaciones_de_especificacion(FICHA, _texto(), lambda _ruta: "def test_z():\n    pass\n")
    assert _reglas(otra_funcion) == ["E5"], otra_funcion
    sin_marca = _texto(Aceptación=f"{CABECERA}\n{FILA.replace('m1: ', '')}")
    assert _reglas(violaciones_de_especificacion(FICHA, sin_marca, _nunca)) == ["E5"]
    m1_dos_veces = _texto(Aceptación=f"{CABECERA}\n{FILA}\n{FILA.replace('A1', 'A2')}")
    assert _reglas(violaciones_de_especificacion(FICHA, m1_dos_veces, _nunca)) == ["E5"]
    a1_dos_veces = _texto(Aceptación=f"{CABECERA}\n{FILA}\n{FILA.replace('m1', 'm2')}")
    assert _reglas(violaciones_de_especificacion(FICHA, a1_dos_veces, _nunca)) == ["E5"]
    sin_tabla = _texto(Aceptación="A1: dado X, entonces Y.")
    assert _reglas(violaciones_de_especificacion(FICHA, sin_tabla, _nunca)) == ["E5"]
    sin_filas = _texto(Aceptación=CABECERA)
    assert _reglas(violaciones_de_especificacion(FICHA, sin_filas, _nunca)) == ["E5"]


def test_e5_prueba_aun_no_creada_es_valida():
    # m6: exigir def <función>( aunque leer devuelva None.
    assert violaciones_de_especificacion(FICHA, _texto(), _nunca) == []


def test_e6_trazabilidad_sin_rastro():
    # m7: cualquier texto no vacío.
    sin_rastro = _texto(Trazabilidad="Origen: el playbook del CTO.")
    assert _reglas(violaciones_de_especificacion(FICHA, sin_rastro, _nunca)) == ["E6"]
    mayusculas = _texto(Trazabilidad="¤ suelto y ¤Mayúsculas")
    assert _reglas(violaciones_de_especificacion(FICHA, mayusculas, _nunca)) == ["E6"]


def test_e5_celdas_con_codigo_y_barra_escapada():
    fila = r"| A1 | dado `a \| b`, entonces Y | `tests/x/test_a.py::test_y` | m1: partir por `\|` |"
    texto = _texto(Aceptación=f"{CABECERA}\n{fila}")
    assert violaciones_de_especificacion(FICHA, texto, _define_test_y) == []
    # m11: partir por cada barra desplaza las columnas y se pierde la prueba de la fila.
    ajena = r"| A1 | dado a \| b | tests/otra/test_b.py::test_y | m1: x |"
    violaciones = violaciones_de_especificacion(FICHA, _texto(Aceptación=f"{CABECERA}\n{ajena}"), _nunca)
    assert len(violaciones) == 1 and "tests/otra/test_b.py" in violaciones[0], violaciones


def _violaciones_e7(sin_spec: frozenset[str], raiz: Path) -> list[str]:
    por_id = {ficha["id"]: ficha for ficha in fichas(raiz)}
    violaciones = [f"{id_}: E7 no está en la lista original" for id_ in sorted(sin_spec - E7_ORIGINAL)]
    for id_ in sorted(sin_spec & E7_ORIGINAL):
        ficha = por_id.get(id_)
        if ficha is None:
            if id_ not in PENDIENTE_FUERA_DE_TASKS:
                violaciones.append(f"{id_}: E7 ya no está en TASKS.md; sácala de SIN_SPEC")
        elif ficha.get("estado") == "sellada":
            violaciones.append(f"{id_}: E7 ya está sellada; sácala de SIN_SPEC")
        elif (raiz / "docs/spec/tareas" / f"{id_}.md").is_file():
            violaciones.append(f"{id_}: E7 ya tiene especificación; sácala de SIN_SPEC")
    return violaciones


def test_e7_sin_spec_solo_se_achica():
    assert _violaciones_e7(SIN_SPEC, RAIZ) == []
    # m8: agregar un id que no esté en la lista original.
    assert _violaciones_e7(SIN_SPEC | {"T-408"}, RAIZ) == ["T-408: E7 no está en la lista original"]
    # Sacar un miembro siempre es válido.
    assert _violaciones_e7(SIN_SPEC - {"T-111"}, RAIZ) == []


def test_repositorio_real_sin_violaciones(tmp_path, capsys):
    assert violaciones_del_repositorio(RAIZ) == []
    assert main([]) == 0
    # m9: en una copia con la ficha de G-2, borrar su especificación hace fallar a main.
    copia = tmp_path / "repo"
    shutil.copytree(RAIZ / "docs/spec/tareas", copia / "docs/spec/tareas")
    tasks = copia / "governance/tareas/TASKS.md"
    tasks.parent.mkdir(parents=True)
    texto = (RAIZ / "governance/tareas/TASKS.md").read_text(encoding="utf-8")
    if "G-2" not in {ficha["id"] for ficha in fichas(RAIZ)}:
        texto += "\n" + _toml(FICHA_G2)
    tasks.write_text(texto, encoding="utf-8")
    assert main([str(copia)]) == 0
    (copia / "docs/spec/tareas/G-2.md").unlink()
    assert main([str(copia)]) == 1
    assert "G-2: E1" in capsys.readouterr().out


def test_la_especificacion_de_g2_cumple():
    especificacion = RAIZ / "docs/spec/tareas/G-2.md"
    assert especificacion.is_file(), "falta docs/spec/tareas/G-2.md: entra por el PR de especificación"
    texto = especificacion.read_text(encoding="utf-8")

    def leer(ruta: str) -> str | None:
        archivo = RAIZ / ruta
        return archivo.read_text(encoding="utf-8") if archivo.is_file() else None

    assert violaciones_de_especificacion(FICHA_G2, texto, leer) == []
    # m10: sin el título de Trazabilidad aparece E2.
    sin_trazabilidad = texto.replace("\n## Trazabilidad\n", "\n")
    assert sin_trazabilidad != texto
    assert "E2" in _reglas(violaciones_de_especificacion(FICHA_G2, sin_trazabilidad, leer), "G-2")
