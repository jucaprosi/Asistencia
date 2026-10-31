# ¤spec-glamping
# ¤¤qa-engineer
"""Árbitro de la especificación ejecutable (INV_ESPECIFICACION_VIVA, INV_CORPUS_FUERA_DEL_REPO).

Lee los tipos como texto para no acoplar esta prueba a las salas: compara lo que declaran con los contratos.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from itertools import permutations
from pathlib import Path
from typing import Any, Iterator

import pytest
import yaml
from jsonschema import Draft202012Validator

from tests.conftest import RAIZ

SPEC = RAIZ / "docs" / "spec"
DOMINIO = yaml.safe_load((SPEC / "contratos" / "dominio.yaml").read_text(encoding="utf-8"))
HERRAMIENTAS = yaml.safe_load((SPEC / "contratos" / "herramientas.yaml").read_text(encoding="utf-8"))
ESQUEMA = (SPEC / "esquema.sql").read_text(encoding="utf-8")
ETIQUETAS_VALIDAS = re.compile(r"^(RF-[A-Z]+-\d{2}|US-\d{2}|CU-\d{2}|INV_[A-Z0-9_]+)$")

_modulo = importlib.util.spec_from_file_location("generar_trazabilidad", RAIZ / "scripts" / "generar_trazabilidad.py")
assert _modulo and _modulo.loader
trazabilidad = importlib.util.module_from_spec(_modulo)
_modulo.loader.exec_module(trazabilidad)


# ¤spec-glamping
def _config(sala: str) -> dict[str, Any]:
    return yaml.safe_load((RAIZ / "features" / sala / f"config_{sala}.yaml").read_text(encoding="utf-8"))


# ¤spec-glamping
def _valores_enum(sala: str, clase: str) -> set[str]:
    texto = (RAIZ / "features" / sala / "tipos.py").read_text(encoding="utf-8")
    bloque = re.search(rf"class {clase}\(str, Enum\):\n((?:    .+\n)+)", texto)
    assert bloque, clase
    return set(re.findall(r'= "(\w+)"', bloque.group(1)))


# ¤spec-glamping
def _referencias(nodo: Any) -> Iterator[str]:
    if isinstance(nodo, dict):
        for clave, valor in nodo.items():
            if clave == "$ref":
                yield valor
            else:
                yield from _referencias(valor)
    elif isinstance(nodo, list):
        for valor in nodo:
            yield from _referencias(valor)


# ¤spec-glamping
def test_toda_historia_tiene_escenario() -> None:
    etiquetas = {e for _, _, grupo in trazabilidad.escenarios() for e in grupo}
    historias = [i for i in trazabilidad.ids_del_prd() if i.startswith("US-")]
    assert len(historias) == 17
    assert not [h for h in historias if h not in etiquetas]


# ¤spec-glamping
def test_las_etiquetas_de_los_escenarios_existen() -> None:
    ids = set(trazabilidad.ids_del_prd())
    prd = trazabilidad.PRD.read_text(encoding="utf-8")
    invariantes = (RAIZ / "governance" / "artefactos" / "INVARIANTS.md").read_text(encoding="utf-8")
    for archivo, titulo, etiquetas in trazabilidad.escenarios():
        assert etiquetas, f"{archivo}: {titulo} sin etiquetas"
        for etiqueta in etiquetas:
            assert ETIQUETAS_VALIDAS.match(etiqueta), etiqueta
            if etiqueta.startswith("INV_"):
                assert f"`{etiqueta}`" in invariantes, etiqueta
            elif etiqueta.startswith("CU-"):
                assert f"| {etiqueta} |" in prd, etiqueta
            else:
                assert etiqueta in ids, etiqueta


# ¤spec-glamping
def test_cada_requisito_funcional_tiene_escenario() -> None:
    etiquetas = {e for _, _, grupo in trazabilidad.escenarios() for e in grupo}
    assert not [i for i in trazabilidad.ids_del_prd() if i.startswith("RF-") and i not in etiquetas]


# ¤spec-glamping
def test_cada_invariante_activa_tiene_predicado_y_mecanismo() -> None:
    texto = (RAIZ / "governance" / "artefactos" / "INVARIANTS.md").read_text(encoding="utf-8")
    catalogo, resto = texto.split("## 2. Predicados", 1)
    predicados, _ = resto.split("## 3.", 1)
    activas = set(re.findall(r"^\| `(INV_\w+)` \|", catalogo, flags=re.M))
    filas = re.findall(r"^\| `(INV_\w+)` \| (.+?) \| (.+?) \|$", predicados, flags=re.M)
    assert activas == {codigo for codigo, _, _ in filas}
    assert all(predicado.strip() and mecanismo.strip() for _, predicado, mecanismo in filas)


# ¤spec-glamping
def test_cada_tarea_tiene_prompt_al_dia_y_completo() -> None:
    ruta = RAIZ / "scripts" / "generar_prompts.py"
    resultado = subprocess.run([sys.executable, str(ruta), "--check"], capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 0, resultado.stdout
    tareas = re.findall(r'^id = "(T-\d+)"', trazabilidad.TASKS.read_text(encoding="utf-8"), flags=re.M)
    prompts = {p.stem: p.read_text(encoding="utf-8") for p in (SPEC / "prompts").glob("T-*.md")}
    assert set(prompts) == set(tareas)
    for tarea, texto in prompts.items():
        assert "## Rutas que puedes escribir" in texto and "## Árbitro" in texto, tarea


# ¤spec-glamping
def test_las_entidades_del_prd_tienen_tabla() -> None:
    for tabla in ("seguridad.huespedes", "pms.reservas_ref", "pms.incidencias", "arm.ventas", "comisiones.reglas", "crm.handoffs", "agente.envios_programados"):
        assert f"CREATE TABLE {tabla} (" in ESQUEMA, tabla


# ¤spec-glamping
def test_el_escalon_marginal_no_depende_del_orden() -> None:
    ejemplo = yaml.safe_load((SPEC / "contratos" / "dominio.yaml").read_text(encoding="utf-8"))["comision"]["ejemplo_escalon"]
    tramos = [(Decimal(e["desde"]), Decimal(e["porcentaje"]) / 100) for e in ejemplo["escalones"]]

    def acumulada(volumen: Decimal, modo: str) -> Decimal:
        if modo == "volumen":
            tasa = [t for desde, t in tramos if volumen >= desde][-1]
            return (volumen * tasa).quantize(Decimal("0.01"), ROUND_HALF_UP)
        total = Decimal(0)
        for (desde, tasa), (hasta, _) in zip(tramos, [*tramos[1:], (volumen, 0)]):
            total += max(min(volumen, hasta) - desde, Decimal(0)) * tasa
        return total.quantize(Decimal("0.01"), ROUND_HALF_UP)

    ventas = [Decimal(v) for v in ejemplo["ventas"]]
    for modo in DOMINIO["comision"]["modos_escalon"]:
        for orden in permutations(ventas):
            base, total = Decimal(0), Decimal(0)
            for monto in orden:
                total += acumulada(base + monto, modo) - acumulada(base, modo)
                base += monto
            assert total == Decimal(ejemplo["total_mes"][modo])
        assert acumulada(sum(ventas) - ventas[1], modo) == Decimal(ejemplo["total_tras_anular_segunda"][modo])


# ¤spec-glamping
def test_cada_requisito_tiene_tarea() -> None:
    tareas = trazabilidad.tareas_por_id()
    assert not [i for i in trazabilidad.ids_del_prd() if i not in tareas]


# ¤spec-glamping
def test_sin_identificadores_fantasma() -> None:
    conocidos = set(trazabilidad.ids_del_prd())
    fuentes = [
        trazabilidad.PRD, trazabilidad.TASKS, RAIZ / "docs" / "ARQUITECTURA.md", RAIZ / "docs" / "FRONTEND.md",
        *(RAIZ / "docs" / "modulos").glob("*.md"), *(RAIZ / "governance" / "tareas").glob("TASK-*.md"),
    ]
    fantasmas = {
        f"{ruta.name}: {identificador}"
        for ruta in fuentes
        for identificador in trazabilidad.PATRON_ID.findall(ruta.read_text(encoding="utf-8"))
        if identificador not in conocidos
    }
    assert not fantasmas, sorted(fantasmas)


# ¤spec-glamping
def test_tipos_de_las_salas_coinciden_con_el_dominio() -> None:
    assert _valores_enum("seguridad", "Rol") == set(DOMINIO["roles"])
    assert _valores_enum("arm_jarvis", "EstadoVenta") == set(DOMINIO["venta"]["estados"])
    assert _valores_enum("comisiones", "EstadoComision") == set(DOMINIO["comision"]["estados"])
    assert _valores_enum("comisiones", "TipoRegla") == set(DOMINIO["comision"]["tipos_regla"])
    assert _valores_enum("comisiones", "ModoEscalon") == set(DOMINIO["comision"]["modos_escalon"])


# ¤spec-glamping
def test_allowlist_identica_al_dominio() -> None:
    assert _config("seguridad")["allowlist"] == DOMINIO["allowlist"]
    assert set(DOMINIO["allowlist"]) == set(DOMINIO["roles"])


# ¤spec-glamping
def test_plantillas_identicas_al_dominio() -> None:
    config = {p["nombre"]: (p["categoria"], p["variables"]) for p in _config("canal_whatsapp")["plantillas"]}
    assert config == {p["nombre"]: (p["categoria"], p["variables"]) for p in DOMINIO["plantillas"]}


# ¤spec-glamping
def test_catalogo_de_herramientas_coincide_con_el_contrato() -> None:
    contrato = HERRAMIENTAS["herramientas"]
    catalogo = {h["nombre"]: h for h in _config("herramientas_glamping")["herramientas"]}
    assert set(catalogo) == set(contrato)
    for nombre, definicion in contrato.items():
        assert set(catalogo[nombre]["roles"]) == set(definicion["roles"]), nombre
        assert catalogo[nombre]["sala_destino"] == definicion["sala_destino"], nombre
        for rol in definicion["roles"]:
            assert nombre in DOMINIO["allowlist"][rol], f"{rol} sin {nombre}"
    for rol, acciones in DOMINIO["allowlist"].items():
        for accion in set(acciones) & set(contrato):
            assert rol in contrato[accion]["roles"], f"{accion} sin {rol}"


# ¤spec-glamping
def test_esquemas_json_validos_y_referencias_resueltas() -> None:
    for definicion in HERRAMIENTAS["herramientas"].values():
        Draft202012Validator.check_schema(definicion["entrada"])
        Draft202012Validator.check_schema(definicion["salida"])
    for modelo in HERRAMIENTAS["modelos"].values():
        Draft202012Validator.check_schema(modelo)
    for referencia in _referencias(HERRAMIENTAS):
        nodo: Any = HERRAMIENTAS
        for parte in referencia.removeprefix("#/").split("/"):
            nodo = nodo[parte]


# ¤spec-glamping
def test_el_modelo_no_envia_identidad() -> None:
    prohibidos = {"telefono_token", "vendedor_id", "conversacion_id", "huesped_id", "prioridad"}
    for nombre, definicion in HERRAMIENTAS["herramientas"].items():
        if nombre == "buscar_contacto_crm":
            continue
        assert not prohibidos & set(definicion["entrada"].get("properties", {})), nombre


# ¤spec-glamping
def test_transiciones_del_ddl_coinciden_con_el_dominio() -> None:
    cuerpo = ESQUEMA[ESQUEMA.index("arm.validar_transicion()"):ESQUEMA.index("CREATE TRIGGER ventas_transicion")]
    ddl: dict[str, set[str]] = {}
    for de, lista, unico in re.findall(r"OLD\.estado = '(\w+)'\s+AND NEW\.estado (?:IN \(([^)]*)\)|= ('\w+'))", cuerpo):
        ddl[de] = set(re.findall(r"'(\w+)'", lista or unico))
    esperado = {de: set(a) for de, a in DOMINIO["venta"]["transiciones"].items() if a}
    assert ddl == esperado


# ¤spec-glamping
def test_cada_sala_con_datos_tiene_esquema_y_el_audit_es_append_only() -> None:
    for esquema in ("canal", "seguridad", "agente", "conocimiento", "pms", "crm", "arm", "comisiones", "observabilidad", "panel"):
        assert f"CREATE SCHEMA {esquema};" in ESQUEMA, esquema
    assert "REVOKE UPDATE, DELETE, TRUNCATE ON seguridad.audit_log" in ESQUEMA
    assert "vector(1024)" in ESQUEMA
    assert _config("conocimiento")["embeddings"]["dimension"] == 1024


# ¤spec-glamping
def test_el_esquema_no_cruza_salas_con_claves_foraneas() -> None:
    bloques = re.findall(r"CREATE TABLE (\w+)\.\w+ \((.*?)\n\);", ESQUEMA, flags=re.S)
    assert bloques
    for esquema, cuerpo in bloques:
        for destino in re.findall(r"REFERENCES (\w+)\.", cuerpo):
            assert destino == esquema, f"{esquema} referencia a {destino}"


# ¤spec-glamping
def test_umbrales_identicos_al_dominio() -> None:
    umbrales = _config("observabilidad")["umbrales"]
    evaluaciones = DOMINIO["evaluaciones"]
    assert umbrales["rag"]["fidelidad"] == evaluaciones["rag"]["fidelidad"]
    assert umbrales["rag"]["abstencion"] == evaluaciones["rag"]["abstencion"]
    assert umbrales["ventas"]["exactitud"] == evaluaciones["ventas"]["exactitud"]
    assert umbrales["inyecciones"]["exitos"] == evaluaciones["inyecciones"]["exitos"]
    assert umbrales["enrutador"]["aciertos"] == evaluaciones["enrutador"]["aciertos"]
    assert umbrales["pii"]["deterministica"] == evaluaciones["pii"]["deterministica"]


# ¤spec-glamping
def test_el_repositorio_publico_no_contiene_corpus() -> None:
    assert [p.name for p in (RAIZ / "docs" / "negocio").iterdir()] == ["README.md"]
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    assert "datos_privados/" in ignorados and "evals/privado/" in ignorados


# ¤spec-glamping
@pytest.mark.parametrize("archivo", ["README.md", "esquema.sql", "verificacion_esquema.sql", "contratos/dominio.yaml", "contratos/herramientas.yaml"])
def test_los_artefactos_existen(archivo: str) -> None:
    assert (SPEC / archivo).is_file()


# ¤spec-glamping
def test_la_matriz_esta_al_dia() -> None:
    ruta: Path = RAIZ / "scripts" / "generar_trazabilidad.py"
    resultado = subprocess.run([sys.executable, str(ruta), "--check"], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stdout
