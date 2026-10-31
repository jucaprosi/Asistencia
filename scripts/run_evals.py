# ¤observabilidad
# ¤¤qa-engineer
"""Ejecuta las suites de evaluación (RF-OBS-03) y falla bajo umbral.

Fase 0: declara las suites y sus archivos; una suite sin archivo se reporta OMITIDA. El evaluador real de cada
suite llega con su tarea (rag: TASK-002, enrutador: TASK-004, inyecciones: TASK-005, ventas: TASK-006).
Uso: ``python scripts/run_evals.py [--suite nombre]``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SUITES = {
    "rag": RAIZ / "evals" / "set_dorado.jsonl",
    "enrutador": RAIZ / "evals" / "enrutador.jsonl",
    "inyecciones": RAIZ / "evals" / "inyecciones.jsonl",
    "ventas": RAIZ / "evals" / "ventas.jsonl",
}


# ¤observabilidad
def evaluar_suite(nombre: str) -> tuple[str, int]:
    """Devuelve (estado, exit code). Sin archivo de casos la suite se omite sin fallar."""
    archivo = SUITES[nombre]
    if not archivo.is_file():
        return f"OMITIDA (falta {archivo.relative_to(RAIZ)})", 0
    casos = [linea for linea in archivo.read_text(encoding="utf-8").splitlines() if linea.strip()]
    return f"PENDIENTE DE EVALUADOR ({len(casos)} casos; evaluador llega con su tarea)", 1


# ¤observabilidad
def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Evaluaciones de glamping-imbabura-agent")
    analizador.add_argument("--suite", choices=sorted(SUITES), action="append", help="suite a ejecutar (repetible)")
    opciones = analizador.parse_args(argumentos)
    seleccion = opciones.suite or sorted(SUITES)
    codigo_global = 0
    for nombre in seleccion:
        estado, codigo = evaluar_suite(nombre)
        print(f"[{'OK' if codigo == 0 else 'FALLO'}] {nombre}: {estado}")
        codigo_global = codigo_global or codigo
    return codigo_global


if __name__ == "__main__":
    raise SystemExit(main())
