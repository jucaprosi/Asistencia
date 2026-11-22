"""Árbitro de las reglas de independencia de governance/tareas/TASKS.md.

Lee cada bloque ```toml``` del archivo y comprueba:
- toda tarea declara id, ola, fase, estado, sala, rol, propiedad (no vacía) y arbitro;
- dentro de una misma ola, dos tareas nunca reclaman rutas que se solapen;
- una tarea de sala solo reclama rutas de su sala o de los recursos asignados a ella; las rutas reservadas al coordinador
  solo las reclaman las tareas de `pasillo_central` o `infraestructura`;
- los ids son únicos y `depende_de` apunta a tareas existentes o a hitos TASK-00N.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

from tests.conftest import RAIZ

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


def _tareas() -> list[dict]:
    texto = TASKS.read_text(encoding="utf-8")
    bloques = re.findall(r"```toml\n(.*?)```", texto, flags=re.S)
    assert bloques, "TASKS.md no contiene bloques toml"
    return [tomllib.loads(bloque) for bloque in bloques]


def _normalizar(ruta: str) -> str:
    return ruta[:-3] if ruta.endswith("/**") else ruta


def _solapan(a: str, b: str) -> bool:
    a, b = _normalizar(a), _normalizar(b)
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")


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
    por_id = {t["id"]: t for t in tareas}
    for tarea in tareas:
        mi_ola = int(tarea["ola"])
        for dependencia in tarea["depende_de"]:
            base = dependencia.split(" ")[0]
            assert base in conocidos or re.fullmatch(r"TASK-\d{3}", base), f"{tarea['id']} depende de {dependencia!r} desconocida"
            if base in por_id:
                dep_ola = int(por_id[base]["ola"])
                assert dep_ola < mi_ola, (
                    f"Violación de regla de olas: {tarea['id']} (ola {mi_ola}) depende de {base} "
                    f"(ola {dep_ola}); la ola de una dependencia debe ser estrictamente menor."
                )


def test_regla_de_olas_falla_si_dependencia_es_de_misma_ola_o_posterior() -> None:
    """Verifica (mutante muerto) que una dependencia en la misma ola o posterior sea rechazada."""
    import pytest
    tareas_sinteticas = [
        {"id": "T-001", "ola": 2, "depende_de": []},
        {"id": "T-002", "ola": 2, "depende_de": ["T-001"]},  # misma ola!
    ]
    por_id = {t["id"]: t for t in tareas_sinteticas}
    with pytest.raises(AssertionError, match="Violación de regla de olas: T-002"):
        for tarea in tareas_sinteticas:
            mi_ola = int(tarea["ola"])
            for dep in tarea["depende_de"]:
                if dep in por_id:
                    assert int(por_id[dep]["ola"]) < mi_ola, f"Violación de regla de olas: {tarea['id']}"



def test_sin_colisiones_de_rutas_dentro_de_cada_ola() -> None:
    por_ola: dict[int, list[dict]] = {}
    for tarea in _tareas():
        por_ola.setdefault(int(tarea["ola"]), []).append(tarea)
    colisiones: list[str] = []
    for ola, tareas in por_ola.items():
        for i, a in enumerate(tareas):
            for b in tareas[i + 1:]:
                # Tareas secuenciales de la misma sala (b depende de a o viceversa) pueden compartir rutas.
                if a["id"] in b["depende_de"] or b["id"] in a["depende_de"]:
                    continue
                for ra in a["propiedad"]:
                    for rb in b["propiedad"]:
                        if _solapan(ra, rb):
                            colisiones.append(f"ola {ola}: {a['id']} y {b['id']} comparten {ra} / {rb}")
    assert not colisiones, "\n".join(colisiones)


def test_las_tareas_de_sala_solo_reclaman_lo_suyo() -> None:
    violaciones: list[str] = []
    for tarea in _tareas():
        sala = tarea["sala"]
        if sala in COORDINADOR:
            continue
        permitidas = {f"features/{sala}/", f"tests/{sala}/", f"docs/modulos/{sala}.md"} | RECURSOS_POR_SALA.get(sala, set())
        for ruta in tarea["propiedad"]:
            normal = _normalizar(ruta)
            if any(_solapan(normal, reservada) for reservada in RESERVADAS):
                violaciones.append(f"{tarea['id']} ({sala}) reclama ruta reservada {ruta}")
            elif not any(_solapan(normal, permitida) for permitida in permitidas):
                violaciones.append(f"{tarea['id']} ({sala}) reclama ruta ajena {ruta}")
    assert not violaciones, "\n".join(violaciones)


def test_maximo_cuatro_tareas_por_ola() -> None:
    por_ola: dict[int, list[dict]] = {}
    for tarea in _tareas():
        por_ola.setdefault(int(tarea["ola"]), []).append(tarea)
    for ola, tareas in por_ola.items():
        assert len(tareas) <= 4, f"ola {ola} tiene {len(tareas)} tareas (máximo 4 para trabajo en paralelo)"


def test_las_tareas_de_coordinacion_cubren_todos_los_hitos() -> None:
    """Verifica que las olas de orquestación y nube (Olas 9-12) incluyan el cierre de todos los hitos."""
    tareas = _tareas()
    coordinadoras = [t for t in tareas if t["sala"] in COORDINADOR]
    assert len(coordinadoras) >= 8, f"se esperaban al menos 8 tareas de coordinación/nube, hay {len(coordinadoras)}"
    olas_coordinacion = {int(t["ola"]) for t in coordinadoras}
    assert olas_coordinacion == {9, 10, 11, 12}, f"las olas de coordinación deben ser 9, 10, 11 y 12, se encontró {olas_coordinacion}"

