# ¤spec-glamping
# ¤¤qa-engineer
"""Genera docs/spec/TRAZABILIDAD.md: requisito, tareas y escenarios. Con --check falla si el archivo está desactualizado."""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PRD = RAIZ / "docs" / "PRD.md"
TASKS = RAIZ / "governance" / "tareas" / "TASKS.md"
FEATURES = RAIZ / "docs" / "spec" / "features"
SALIDA = RAIZ / "docs" / "spec" / "TRAZABILIDAD.md"
PATRON_ID = re.compile(r"\b(?:RF-[A-Z]+-\d{2}|RNF-\d{2}|US-\d{2})\b")


# ¤spec-glamping
def ids_del_prd() -> list[str]:
    ids: list[str] = []
    for linea in PRD.read_text(encoding="utf-8").splitlines():
        coincidencia = re.match(r"(?:- \*\*|\| \*\*|\| )(RF-[A-Z]+-\d{2}|RNF-\d{2}|US-\d{2})\b", linea)
        if coincidencia and coincidencia.group(1) not in ids:
            ids.append(coincidencia.group(1))
    return ids


# ¤spec-glamping
def tareas_por_id() -> dict[str, list[str]]:
    texto = TASKS.read_text(encoding="utf-8")
    resultado: dict[str, list[str]] = {}
    for bloque in re.findall(r"```toml\n(.*?)```", texto, flags=re.S):
        tarea = tomllib.loads(bloque)
        for requisito in tarea.get("requisitos", []):
            for identificador in PATRON_ID.findall(requisito):
                resultado.setdefault(identificador, []).append(tarea["id"])
    return resultado


# ¤spec-glamping
def escenarios() -> list[tuple[str, str, tuple[str, ...]]]:
    """Devuelve (archivo, título, etiquetas) de cada escenario."""
    resultado: list[tuple[str, str, tuple[str, ...]]] = []
    for archivo in sorted(FEATURES.glob("*.feature")):
        etiquetas: tuple[str, ...] = ()
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            limpia = linea.strip()
            if limpia.startswith("@"):
                etiquetas = tuple(parte.lstrip("@") for parte in limpia.split())
            elif limpia.startswith("Escenario:"):
                resultado.append((archivo.name, limpia.removeprefix("Escenario:").strip(), etiquetas))
                etiquetas = ()
    return resultado


# ¤spec-glamping
def construir() -> str:
    por_tarea = tareas_por_id()
    por_escenario: dict[str, list[str]] = {}
    for archivo, titulo, etiquetas in escenarios():
        for etiqueta in etiquetas:
            por_escenario.setdefault(etiqueta, []).append(f"{archivo}: {titulo}")
    lineas = [
        "# Matriz de trazabilidad",
        "`¤spec-glamping`",
        "",
        "Archivo generado por `scripts/generar_trazabilidad.py`. No se edita a mano.",
        "",
        "| Requisito | Tareas | Escenarios |",
        "| :--- | :--- | :--- |",
    ]
    for identificador in ids_del_prd():
        tareas = ", ".join(dict.fromkeys(por_tarea.get(identificador, []))) or "sin tarea"
        filas = "<br>".join(por_escenario.get(identificador, [])) or "por árbitro de la tabla del PRD"
        lineas.append(f"| {identificador} | {tareas} | {filas} |")
    lineas += ["", "`¤spec-glamping/`", ""]
    return "\n".join(lineas)


# ¤spec-glamping
def main() -> int:
    contenido = construir()
    if "--check" in sys.argv:
        actual = SALIDA.read_bytes().decode("utf-8").replace("\r\n", "\n") if SALIDA.exists() else ""
        if actual != contenido:
            print("docs/spec/TRAZABILIDAD.md está desactualizada: ejecuta python scripts/generar_trazabilidad.py")
            return 1
        return 0
    SALIDA.write_bytes(contenido.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
