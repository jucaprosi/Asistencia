# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de las reglas de independencia de governance/tareas/TASKS.md.

Lee cada bloque ```toml``` del archivo y comprueba:
- toda tarea declara id, ola, fase, estado, sala, rol, propiedad (no vacía) y arbitro;
- los ids son únicos y `depende_de` apunta a tareas existentes o a hitos TASK-00N, siempre de una ola anterior (R4);
- una tarea de sala solo reclama rutas de su sala o de los recursos asignados a ella; las rutas reservadas al coordinador
  solo las reclaman las tareas de `pasillo_central` o `infraestructura`. Una ficha de sala puede tomar pruebas de otra
  sala si declara su límite en `limites` (R2); nunca código reservado.

Reglas de ortogonalidad (dictamen del Arquitecto ADPA G.I., 2026-11-25). **Regla de oro:** solo las fichas no selladas
compiten por un archivo; al sellarse, sus archivos quedan libres.
- R1: una ficha no sellada declara archivos exactos (sin `*`, `**` ni `/` final); cada uno existe en HEAD o está en
  `crea`, y `crea` está incluida en `propiedad`. `crea` declara intención y no se vuelve a comprobar después de crear:
  en el PR de la tarea, y en main entre el merge y el sellado, HEAD ya trae el archivo y la ficha sigue pendiente.
- R2: cada archivo ajeno que una ficha de sala toma lleva su límite en `limites`.
- R3: ninguna ficha no sellada reclama los archivos de gobernanza comunes.
- R4: dentro de una ola, dos fichas no selladas nunca comparten ruta, sin exenciones; a lo sumo una toca `app_core/`.
- R5: cada regla es una función del árbitro y su mutante muerto llama a esa misma función.
- R6: la sala de cada ficha está en el catálogo del PRD vivo (`salas_en_catalogo`) o es de coordinación.
"""
from __future__ import annotations

import re
import subprocess
import tomllib
from functools import lru_cache
from pathlib import Path

from tests.conftest import RAIZ, salas_en_catalogo

TASKS = RAIZ / "governance" / "tareas" / "TASKS.md"
COORDINADOR = {"pasillo_central", "infraestructura"}
RESERVADAS = (
    "app_core/", "compose.yaml", "compose.production.yaml", "Dockerfile", "infra/", ".env.example", "pyproject.toml",
    ".github/", "scripts/arnes_glamping.py", "scripts/verificar_secretos.py", "tests/conftest.py", "tests/integracion/",
    "tests/app_core/", "governance/", "docs/PRD.md", "docs/spec/", "docs/ARQUITECTURA.md", "docs/FRONTEND.md", "docs/adr/",
    "README.md", "CLAUDE.md",
)
RECURSOS_POR_SALA = {
    "seguridad": {"evals/inyecciones.jsonl", "evals/pii.jsonl", "docs/privacidad/"},
    "agente": {"docs/prompts/", "evals/enrutador.jsonl"},
    "conocimiento": {"scripts/seed_knowledge.py", "evals/set_dorado.jsonl", "docs/negocio/README.md"},
    "arm_jarvis": {"evals/ventas.jsonl"},
    "observabilidad": {"scripts/run_evals.py"},
    "panel_operativo": {"tests/e2e/"},
}
CAMPOS = ("id", "ola", "fase", "estado", "sala", "rol", "propiedad", "arbitro", "depende_de", "bloqueada_por")
GOBERNANZA_COMUN = frozenset({"governance/tareas/TASKS.md", "docs/adr/README.md", "governance/artefactos/VPA_INDEX.md"})
# R2: los conftest.py son compartidos (fixtures de toda una carpeta): ninguna ficha de sala los toma, ni con límite.
def _es_conftest(ruta: str) -> bool:
    return ruta == "conftest.py" or ruta.endswith("/conftest.py")
# Deuda de R1 medida en origin/main 077ab65: fichas pendientes escritas con comodines antes de la regla. Solo puede
# achicarse; el commit de gobernanza (R3) que las reescribe con rutas exactas vacía esta lista.
DEUDA_R1: frozenset[str] = frozenset()


def _tareas() -> list[dict]:
    texto = TASKS.read_text(encoding="utf-8")
    bloques = re.findall(r"```toml\n(.*?)```", texto, flags=re.S)
    assert bloques, "TASKS.md no contiene bloques toml"
    return [tomllib.loads(bloque) for bloque in bloques]


@lru_cache(maxsize=1)
def _archivos_en_head() -> frozenset[str]:
    salida = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "HEAD"], cwd=RAIZ, capture_output=True, text=True, check=True
    ).stdout
    return frozenset(salida.split("\n")) - {""}


def _normalizar(ruta: str) -> str:
    return ruta[:-3] if ruta.endswith("/**") else ruta


def _solapan(a: str, b: str) -> bool:
    a, b = _normalizar(a), _normalizar(b)
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")


def _no_selladas(tareas: list[dict]) -> list[dict]:
    return [t for t in tareas if t.get("estado") != "sellada"]


def _por_ola(tareas: list[dict]) -> dict[int, list[dict]]:
    por_ola: dict[int, list[dict]] = {}
    for tarea in tareas:
        por_ola.setdefault(int(tarea["ola"]), []).append(tarea)
    return por_ola


# --- R4: dependencias -------------------------------------------------------------------------------------------------
def _violaciones_de_olas(tareas: list[dict]) -> list[str]:
    """La ola de una dependencia conocida es estrictamente menor que la de quien depende."""
    por_id = {t["id"]: t for t in tareas}
    violaciones: list[str] = []
    for tarea in tareas:
        for dependencia in tarea["depende_de"]:
            base = dependencia.split(" ")[0]
            if base in por_id and int(por_id[base]["ola"]) >= int(tarea["ola"]):
                violaciones.append(
                    f"Violación de regla de olas: {tarea['id']} (ola {tarea['ola']}) depende de {base} "
                    f"(ola {por_id[base]['ola']}); la ola de una dependencia debe ser estrictamente menor."
                )
    return violaciones


# --- R4: colisiones (regla de oro, sin exención por dependencia) -----------------------------------------------------
def _colisiones(tareas: list[dict]) -> list[str]:
    colisiones: list[str] = []
    for ola, del_ola in _por_ola(_no_selladas(tareas)).items():
        for i, a in enumerate(del_ola):
            for b in del_ola[i + 1:]:
                for ra in a["propiedad"]:
                    for rb in b["propiedad"]:
                        if _solapan(ra, rb):
                            colisiones.append(f"ola {ola}: {a['id']} y {b['id']} comparten {ra} / {rb}")
    return colisiones


def _olas_con_varias_tareas_en_app_core(tareas: list[dict]) -> dict[int, list[str]]:
    """ADPA §3: en cada ola, a lo sumo una ficha no sellada toca ``app_core/`` (regla de oro, sin excepciones)."""
    por_ola: dict[int, list[str]] = {}
    for tarea in _no_selladas(tareas):
        if any(_solapan(ruta, "app_core/") for ruta in tarea["propiedad"]):
            por_ola.setdefault(int(tarea["ola"]), []).append(tarea["id"])
    return {ola: ids for ola, ids in por_ola.items() if len(ids) > 1}


# --- Salas y R2 ------------------------------------------------------------------------------------------------------
def _violaciones_de_sala(tareas: list[dict]) -> list[str]:
    """Una ficha de sala reclama lo suyo; una prueba ajena solo con su límite (R2); nunca código reservado."""
    violaciones: list[str] = []
    for tarea in tareas:
        sala = tarea["sala"]
        if sala in COORDINADOR:
            continue
        permitidas = {f"features/{sala}/", f"tests/{sala}/", f"docs/modulos/{sala}.md"} | RECURSOS_POR_SALA.get(sala, set())
        limites = tarea.get("limites", {})
        for ruta in tarea["propiedad"]:
            normal = _normalizar(ruta)
            if any(_solapan(normal, permitida) for permitida in permitidas):
                continue
            if normal.startswith("tests/") and not _es_conftest(normal) and ruta in limites:
                continue  # R2: prueba ajena tomada con su límite escrito
            if any(_solapan(normal, reservada) for reservada in RESERVADAS):
                violaciones.append(f"{tarea['id']} ({sala}) reclama ruta reservada {ruta}")
            else:
                violaciones.append(f"{tarea['id']} ({sala}) reclama ruta ajena {ruta}")
    return violaciones


def _violaciones_r2(tareas: list[dict]) -> list[str]:
    """``limites`` solo describe archivos de la propia ``propiedad``, con un texto no vacío por archivo."""
    violaciones: list[str] = []
    for tarea in _no_selladas(tareas):
        limites = tarea.get("limites", {})
        if not isinstance(limites, dict):
            violaciones.append(f"{tarea['id']}: limites debe ser una tabla archivo = límite")
            continue
        for ruta, limite in limites.items():
            if ruta not in tarea["propiedad"]:
                violaciones.append(f"{tarea['id']}: limites describe {ruta}, que no está en su propiedad")
            if not isinstance(limite, str) or not limite.strip():
                violaciones.append(f"{tarea['id']}: el límite de {ruta} está vacío")
    return violaciones


# --- R1: archivos exactos y crea -------------------------------------------------------------------------------------
def _violaciones_r1(tareas: list[dict], en_head: frozenset[str]) -> list[str]:
    violaciones: list[str] = []
    for tarea in _no_selladas(tareas):
        crea = list(tarea.get("crea", []))
        for ruta in tarea["propiedad"]:
            if "*" in ruta or ruta.endswith("/"):
                violaciones.append(f"{tarea['id']}: {ruta} no es un archivo exacto (sin *, ** ni / final)")
            elif ruta not in en_head and ruta not in crea:
                violaciones.append(f"{tarea['id']}: {ruta} no existe en HEAD y no está en crea")
        for ruta in crea:  # crea declara intención: no se exige que siga sin existir (ver docstring del módulo)
            if ruta not in tarea["propiedad"]:
                violaciones.append(f"{tarea['id']}: {ruta} está en crea pero no en su propiedad")
    return violaciones


# --- R3: gobernanza común --------------------------------------------------------------------------------------------
def _violaciones_r3(tareas: list[dict]) -> list[str]:
    return [
        f"{tarea['id']}: una ficha no sellada no reclama {ruta}; va en un commit de gobernanza"
        for tarea in _no_selladas(tareas)
        for ruta in tarea["propiedad"]
        if any(_solapan(ruta, comun) for comun in GOBERNANZA_COMUN)
    ]


# --- R6: salas del catálogo ------------------------------------------------------------------------------------------
def _violaciones_r6(tareas: list[dict], catalogo: tuple[str, ...]) -> list[str]:
    """La sala de cada ficha está en el catálogo del PRD vivo o es de coordinación: ninguna ficha abre una sala sin ADR."""
    validas = set(catalogo) | COORDINADOR
    return [f"{t['id']}: sala {t['sala']!r} no está en el catálogo del PRD ni es de coordinación"
            for t in tareas if t["sala"] not in validas]


# === Contra TASKS.md real ============================================================================================
def test_cada_tarea_declara_los_campos_obligatorios() -> None:
    for tarea in _tareas():
        faltan = [campo for campo in CAMPOS if campo not in tarea]
        assert not faltan, f"{tarea.get('id', '?')} sin campos {faltan}"
        assert tarea["propiedad"], f"{tarea['id']} sin propiedad"
        assert tarea["estado"] in {"pendiente", "boceto", "sellada", "bloqueada"}, tarea["id"]
        assert tarea["rol"].startswith("¤¤"), tarea["id"]


def test_ids_unicos_y_dependencias_resolubles() -> None:
    tareas = _tareas()
    ids = [t["id"] for t in tareas]
    assert len(ids) == len(set(ids)), "ids duplicados en TASKS.md"
    conocidos = set(ids)
    for tarea in tareas:
        for dependencia in tarea["depende_de"]:
            base = dependencia.split(" ")[0]
            assert base in conocidos or re.fullmatch(r"TASK-\d{3}", base), f"{tarea['id']} depende de {dependencia!r} desconocida"
    violaciones = _violaciones_de_olas(tareas)
    assert not violaciones, "\n".join(violaciones)


def test_sin_colisiones_de_rutas_dentro_de_cada_ola() -> None:
    colisiones = _colisiones(_tareas())
    assert not colisiones, "\n".join(colisiones)


def test_las_tareas_de_sala_solo_reclaman_lo_suyo() -> None:
    violaciones = _violaciones_de_sala(_tareas())
    assert not violaciones, "\n".join(violaciones)


def test_a_lo_sumo_una_tarea_sobre_app_core_por_ola() -> None:
    choques = _olas_con_varias_tareas_en_app_core(_tareas())
    assert not choques, f"varias fichas no selladas tocan app_core/ en la misma ola: {choques}"


def test_r1_rutas_exactas_salvo_la_deuda_declarada() -> None:
    violaciones = _violaciones_r1(_tareas(), _archivos_en_head())
    fuera_de_deuda = [v for v in violaciones if v.split(":")[0] not in DEUDA_R1]
    assert not fuera_de_deuda, "\n".join(fuera_de_deuda)


def test_r1_la_deuda_solo_se_achica() -> None:
    """Cada ficha de DEUDA_R1 sigue incumpliendo; si ya cumple, hay que sacarla de la lista."""
    con_violacion = {v.split(":")[0] for v in _violaciones_r1(_tareas(), _archivos_en_head())}
    saldadas = sorted(DEUDA_R1 - con_violacion)
    assert not saldadas, f"ya cumplen R1, sáquelas de DEUDA_R1: {saldadas}"


def test_r2_limites_bien_formados() -> None:
    violaciones = _violaciones_r2(_tareas())
    assert not violaciones, "\n".join(violaciones)


def test_r3_ninguna_ficha_pendiente_es_duena_de_la_gobernanza_comun() -> None:
    violaciones = _violaciones_r3(_tareas())
    assert not violaciones, "\n".join(violaciones)


def test_r6_cada_sala_de_ficha_esta_en_el_catalogo() -> None:
    violaciones = _violaciones_r6(_tareas(), salas_en_catalogo())
    assert not violaciones, "\n".join(violaciones)


def test_maximo_cuatro_tareas_por_ola() -> None:
    for ola, tareas in _por_ola(_tareas()).items():
        assert len(tareas) <= 4, f"ola {ola} tiene {len(tareas)} tareas (máximo 4 para trabajo en paralelo)"


def test_las_tareas_de_coordinacion_cubren_todos_los_hitos() -> None:
    """Verifica que las olas de orquestación y nube (Olas 9-12) incluyan el cierre de todos los hitos."""
    tareas = _tareas()
    coordinadoras = [t for t in tareas if t["sala"] in COORDINADOR]
    assert len(coordinadoras) >= 8, f"se esperaban al menos 8 tareas de coordinación/nube, hay {len(coordinadoras)}"
    olas_coordinacion = {int(t["ola"]) for t in coordinadoras}
    assert {9, 10, 11, 12}.issubset(olas_coordinacion), f"las olas de coordinación deben cubrir al menos 9, 10, 11 y 12, se encontró {olas_coordinacion}"


# === R5: mutantes muertos, cada uno llama a la función real ==========================================================
def _ficha(id_: str, ola: int, propiedad: list[str], *, estado: str = "pendiente", sala: str = "pasillo_central",
           depende_de: tuple[str, ...] = (), **extra: object) -> dict:
    return {"id": id_, "ola": ola, "estado": estado, "sala": sala, "propiedad": propiedad,
            "depende_de": list(depende_de), **extra}


HEAD_FALSO = frozenset({"features/agente/agente_service.py", "tests/agente/test_bucle.py", "tests/app_core/test_contenedor.py"})


def test_mutante_olas_rechaza_dependencia_de_la_misma_ola() -> None:
    fichas = [_ficha("T-001", 2, ["a.py"]), _ficha("T-002", 2, ["b.py"], depende_de=("T-001",))]
    assert [v for v in _violaciones_de_olas(fichas) if "T-002" in v]
    assert not _violaciones_de_olas([_ficha("T-001", 1, ["a.py"]), _ficha("T-002", 2, ["b.py"], depende_de=("T-001",))])


def test_mutante_r4_sin_exencion_por_dependencia() -> None:
    """Dos fichas de la misma ola que comparten archivo chocan aunque una dependa de la otra."""
    fichas = [_ficha("T-001", 3, ["features/agente/agente_service.py"], sala="agente"),
              _ficha("T-002", 3, ["features/agente/agente_service.py"], sala="agente", depende_de=("T-001",))]
    assert _colisiones(fichas)


def test_mutante_regla_de_oro_las_selladas_no_compiten() -> None:
    fichas = [_ficha("T-001", 3, ["features/agente/agente_service.py"], estado="sellada"),
              _ficha("T-002", 3, ["features/agente/agente_service.py"])]
    assert _colisiones(fichas) == []
    con_app_core = [_ficha("T-110", 9, ["app_core/main.py"], estado="sellada"),
                    _ficha("T-510", 9, ["app_core/contenedor.py"], estado="sellada"),
                    _ficha("P-1", 9, ["app_core/worker.py"])]
    assert _olas_con_varias_tareas_en_app_core(con_app_core) == {}


def test_mutante_app_core_dos_fichas_disjuntas_en_la_misma_ola() -> None:
    fichas = [_ficha("P-1", 20, ["app_core/contenedor.py"]), _ficha("TL-2", 20, ["app_core/main.py"]),
              _ficha("S-1", 20, ["features/seguridad/pii_internal.py"], sala="seguridad")]
    assert _olas_con_varias_tareas_en_app_core(fichas) == {20: ["P-1", "TL-2"]}


def test_mutante_r1_rechaza_comodines_y_barra_final() -> None:
    for ruta in ("features/agente/**", "features/agente/*.py", "features/agente/"):
        assert _violaciones_r1([_ficha("T-001", 1, [ruta], sala="agente")], HEAD_FALSO), ruta


def test_mutante_r1_archivo_inexistente_sin_crea() -> None:
    nuevo = "tests/agente/test_nuevo.py"
    assert _violaciones_r1([_ficha("T-001", 1, [nuevo], sala="agente")], HEAD_FALSO)
    assert not _violaciones_r1([_ficha("T-001", 1, [nuevo], sala="agente", crea=[nuevo])], HEAD_FALSO)


def test_mutante_r1_crea_ajeno_a_la_propiedad() -> None:
    existente = "tests/agente/test_bucle.py"
    assert _violaciones_r1([_ficha("T-001", 1, [existente], sala="agente", crea=["tests/agente/otro.py"])], HEAD_FALSO)


def test_mutante_r1_crea_ya_presente_en_head_no_es_violacion() -> None:
    """En el PR de la tarea (y en main antes de sellar) HEAD ya trae lo que la ficha pendiente declaró en crea."""
    creado = "tests/agente/test_bucle.py"
    assert not _violaciones_r1([_ficha("T-001", 1, [creado], sala="agente", crea=[creado])], HEAD_FALSO)


def test_mutante_r1_no_aplica_a_selladas() -> None:
    assert not _violaciones_r1([_ficha("T-001", 1, ["features/agente/**"], estado="sellada")], HEAD_FALSO)


def test_mutante_r2_prueba_ajena_exige_limite() -> None:
    ajena = "tests/app_core/test_contenedor.py"
    sin_limite = _ficha("O-1", 4, ["features/agente/agente_service.py", ajena], sala="agente")
    assert any(ajena in v for v in _violaciones_de_sala([sin_limite]))
    con_limite = _ficha("O-1", 4, ["features/agente/agente_service.py", ajena], sala="agente",
                        limites={ajena: "solo la constante ENTORNO_PRUEBA"})
    assert _violaciones_de_sala([con_limite]) == []


def test_mutante_r2_nunca_codigo_reservado_ni_conftest() -> None:
    for ruta in ("app_core/contenedor.py", "tests/conftest.py", "tests/app_core/conftest.py"):
        ficha = _ficha("O-1", 4, [ruta], sala="agente", limites={ruta: "solo una línea"})
        assert _violaciones_de_sala([ficha]), ruta


def test_mutante_r2_limites_mal_formados() -> None:
    ajena = "tests/app_core/test_contenedor.py"
    vacio = _ficha("O-1", 4, [ajena], sala="agente", limites={ajena: "  "})
    fuera = _ficha("O-1", 4, ["features/agente/agente_service.py"], sala="agente", limites={ajena: "solo la constante"})
    assert _violaciones_r2([vacio])
    assert _violaciones_r2([fuera])


def test_mutante_r3_rechaza_la_gobernanza_comun() -> None:
    for ruta in sorted(GOBERNANZA_COMUN):
        assert _violaciones_r3([_ficha("G-9", 1, [ruta])]), ruta
    assert not _violaciones_r3([_ficha("G-9", 1, ["governance/tareas/TASKS.md"], estado="sellada")])


def test_mutante_r6_sala_inexistente_no_abre_sala_sin_adr() -> None:
    """Una errata de sala con su crea pasaría R1 y abriría features/segurida/ sin ADR."""
    ficha = _ficha("S-9", 1, ["features/segurida/x.py"], sala="segurida", crea=["features/segurida/x.py"])
    assert not _violaciones_r1([ficha], HEAD_FALSO)  # R1 sola no la ve
    assert _violaciones_r6([ficha], ("seguridad", "agente"))
    assert not _violaciones_r6([_ficha("T-1", 1, ["x.py"], sala="infraestructura")], ("seguridad",))
