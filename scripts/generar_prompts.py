# ¤spec-glamping
# ¤¤qa-engineer
"""Traduce cada tarea de TASKS.md en un prompt atómico en docs/spec/prompts/. Con --check falla si alguno está desactualizado.

No inventa contenido: copia requisitos, escenarios, contratos, tablas e invariantes de la especificación.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "docs" / "spec"
PRD = RAIZ / "docs" / "PRD.md"
TASKS = RAIZ / "governance" / "tareas" / "TASKS.md"
INVARIANTS = RAIZ / "governance" / "artefactos" / "INVARIANTS.md"
SALIDA = SPEC / "prompts"
ESQUEMA_POR_SALA = {
    "canal_whatsapp": "canal", "seguridad": "seguridad", "agente": "agente", "conocimiento": "conocimiento",
    "pms_conector": "pms", "operaciones": "pms", "crm_conector": "crm", "arm_jarvis": "arm", "comisiones": "comisiones",
    "observabilidad": "observabilidad", "panel_operativo": "panel",
}
REGLAS = """1. Esta especificación es tu única fuente. No consultes cómo se implementaron otras salas.
2. Escribe solo en las rutas de "Rutas que puedes escribir".
3. Usa nombres, campos, estados y tablas exactamente como aparecen aquí.
4. Otra sala solo se usa por su compuerta `_service.py`, nunca por sus archivos privados.
5. Si algo falta o se contradice, detente, anótalo como `contrato_pendiente` y pide corregir la especificación. No lo decidas.
6. Cada escenario de esta tarea debe quedar como prueba automática.
7. No escribas secretos en el repositorio ni datos reales de clientes.
8. La tarea termina con `ejecutar_arnes_glamping` en Exit Code 0 sobre todo el repositorio."""


# ¤spec-glamping
def tareas() -> list[dict]:
    """Devuelve cada tarea con su título y sus entregables."""
    texto = TASKS.read_text(encoding="utf-8")
    resultado: list[dict] = []
    for titulo, bloque, resto in re.findall(r"^### (T-\d+ — .+?)\n.*?```toml\n(.*?)```\n(.*?)(?=^### |^## |\Z)", texto, flags=re.S | re.M):
        tarea = tomllib.loads(bloque)
        tarea["titulo"] = titulo.split(" — ", 1)[1]
        tarea["entregables"] = resto.strip().replace("---", "").strip()
        resultado.append(tarea)
    return resultado


# ¤spec-glamping
def lineas_del_prd() -> dict[str, str]:
    resultado: dict[str, str] = {}
    for linea in PRD.read_text(encoding="utf-8").splitlines():
        coincidencia = re.match(r"(?:- \*\*|\| \*\*|\| )(RF-[A-Z]+-\d{2}|RNF-\d{2}|US-\d{2})\b", linea)
        if coincidencia:
            relativa = re.sub(r"\]\((?!https?:)(#?)", lambda m: "](../../PRD.md#" if m.group(1) else "](../../", linea)
            resultado.setdefault(coincidencia.group(1), relativa.removeprefix("- "))
    return resultado


# ¤spec-glamping
def bloques_gherkin() -> list[tuple[set[str], str]]:
    resultado: list[tuple[set[str], str]] = []
    for archivo in sorted((SPEC / "features").glob("*.feature")):
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lineas):
            if lineas[i].strip().startswith("@"):
                inicio = i
                i += 1
                while i < len(lineas) and lineas[i].strip():
                    i += 1
                etiquetas = {e.lstrip("@") for e in lineas[inicio].split()}
                resultado.append((etiquetas, "\n".join(l.strip() for l in lineas[inicio:i])))
            i += 1
    return resultado


# ¤spec-glamping
def predicados() -> dict[str, str]:
    seccion = INVARIANTS.read_text(encoding="utf-8").split("## 2. Predicados", 1)[1].split("## 3.", 1)[0]
    return {m.group(1): m.group(0) for m in re.finditer(r"^\| `(INV_\w+)` \|.*$", seccion, flags=re.M)}


# ¤spec-glamping
def invariantes_de_sala(sala: str) -> set[str]:
    catalogo = INVARIANTS.read_text(encoding="utf-8").split("## 2. Predicados", 1)[0]
    return {m.group(1) for m in re.finditer(r"^\| `(INV_\w+)` \|(.*)$", catalogo, flags=re.M) if f"`{sala}`" in m.group(2)}


# ¤spec-glamping
def tablas(sala: str) -> str:
    esquema = ESQUEMA_POR_SALA.get(sala)
    if not esquema:
        return ""
    ddl = (SPEC / "esquema.sql").read_text(encoding="utf-8")
    return "\n\n".join(m.group(0) for m in re.finditer(rf"^CREATE TABLE {esquema}\.\w+ \(.*?^\);", ddl, flags=re.S | re.M))


# ¤spec-glamping
def herramientas_de_sala(sala: str) -> list[str]:
    contrato = yaml.safe_load((SPEC / "contratos" / "herramientas.yaml").read_text(encoding="utf-8"))
    return [n for n, d in contrato["herramientas"].items() if d["sala_destino"] == sala]


# ¤spec-glamping
def construir(tarea: dict, prd: dict[str, str], gherkin: list[tuple[set[str], str]], leyes: dict[str, str]) -> str:
    sala = tarea["sala"]
    ids = [i for r in tarea["requisitos"] for i in re.findall(r"RF-[A-Z]+-\d{2}|RNF-\d{2}|US-\d{2}|INV_\w+", r)]
    escenarios = [texto for etiquetas, texto in gherkin if etiquetas & set(ids)]
    inv = sorted(({i for i in ids if i.startswith("INV_")} | invariantes_de_sala(sala) | {e for t, _ in gherkin if t & set(ids) for e in t if e.startswith("INV_")}) & set(leyes))
    partes = [
        f"# {tarea['id']} — {tarea['titulo']}", "",
        f"Actúa como `{tarea['rol']}` en el proyecto Asistencia. Implementa solo esta tarea.", "",
        f"- Sala: `{sala}` · Ola {tarea['ola']} · Fase {tarea['fase']}",
        f"- Depende de: {', '.join(tarea['depende_de']) or 'nada'}",
        f"- Bloqueada por: {', '.join(tarea['bloqueada_por']) or 'nada'}", "",
        "## Reglas", REGLAS, "",
        "## Rutas que puedes escribir", *[f"- `{r}`" for r in tarea["propiedad"]], "",
        "## Compuertas que consumes", *([f"- `{c}`" for c in tarea.get("consume", [])] or ["- Ninguna"]), "",
        "Sus firmas están en `docs/modulos/<sala>.md`.", "",
        "## Entregables", tarea["entregables"], "",
        "## Requisitos", *[prd[i] if i in prd else f"- {i}" for i in dict.fromkeys(ids) if not i.startswith("INV_")], "",
    ]
    if herramientas_de_sala(sala):
        partes += ["## Herramientas MCP que atiende esta sala", "Entrada y salida exactas en `docs/spec/contratos/herramientas.yaml`:", *[f"- `{h}`" for h in herramientas_de_sala(sala)], ""]
    if tablas(sala):
        partes += ["## Tablas de esta sala", "```sql", tablas(sala), "```", ""]
    if inv:
        partes += ["## Invariantes", "| Código | Predicado | Mecanismo obligatorio |", "| :--- | :--- | :--- |", *[leyes[i] for i in inv], ""]
    if escenarios:
        partes += ["## Escenarios que deben pasar", "```gherkin", "\n\n".join(escenarios), "```", ""]
    partes += ["## Árbitro", tarea["arbitro"], ""]
    return "\n".join(partes)


# ¤spec-glamping
def generar() -> dict[str, str]:
    prd, gherkin, leyes = lineas_del_prd(), bloques_gherkin(), predicados()
    return {f"{t['id']}.md": construir(t, prd, gherkin, leyes) for t in tareas()}


# ¤spec-glamping
def main() -> int:
    contenido = generar()
    if "--check" in sys.argv:
        actuales = {p.name: p.read_bytes().decode("utf-8").replace("\r\n", "\n") for p in SALIDA.glob("*.md")}
        if actuales != contenido:
            print("docs/spec/prompts está desactualizado: ejecuta python scripts/generar_prompts.py")
            return 1
        return 0
    SALIDA.mkdir(exist_ok=True)
    for antiguo in SALIDA.glob("*.md"):
        if antiguo.name not in contenido:
            antiguo.unlink()
    for nombre, texto in contenido.items():
        (SALIDA / nombre).write_bytes(texto.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
