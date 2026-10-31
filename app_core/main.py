# ¤pasillo-central
# ¤¤solutions-architect
"""Arranque HTTP del submarino. Fábrica para uvicorn: ``uvicorn app_core.main:crear_app --factory``.

En la fase 0 solo existe ``GET /health``; el webhook de Meta, los eventos del CRM y el panel llegan con sus tareas.
"""
from __future__ import annotations

import argparse
from typing import Any

from app_core.app_core_service import Contenedor, cargar_config_app, construir

VERSION = "0.1.0"


# ¤pasillo-central
def salud(contenedor: Contenedor | None = None) -> dict[str, Any]:
    """Estado mínimo observable: no toca red ni base de datos."""
    entorno = "desconocido"
    if contenedor is not None:
        entorno = str(contenedor.config_app.get("aplicacion", {}).get("entorno", entorno))
    return {"estado": "ok", "version": VERSION, "entorno": entorno}


# ¤pasillo-central
def crear_app(contenedor: Contenedor | None = None) -> Any:
    """Construye la aplicación FastAPI. Importa FastAPI aquí para que las pruebas de estructura no lo exijan."""
    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError("FastAPI no está instalado: pip install -e .") from exc

    contenedor_activo = contenedor if contenedor is not None else construir()
    app = FastAPI(title="Glamping Imbabura — asistente", version=VERSION, docs_url=None, redoc_url=None)
    app.state.contenedor = contenedor_activo

    @app.get("/health")
    def _health() -> dict[str, Any]:
        return salud(contenedor_activo)

    return app


# ¤pasillo-central
def main(argumentos: list[str] | None = None) -> int:
    """Punto de entrada por línea de comandos: ``--comprobar`` valida la configuración sin levantar red."""
    analizador = argparse.ArgumentParser(description="Pasillo central de glamping-imbabura-agent")
    analizador.add_argument("--comprobar", action="store_true", help="Valida config_app.yaml y termina")
    analizador.add_argument("--worker", action="store_true", help="Modo worker de tareas programadas (TASK-004)")
    opciones = analizador.parse_args(argumentos)
    if opciones.comprobar:
        salas = cargar_config_app().get("salas", [])
        print(f"config_app.yaml válido: {len(salas)} salas declaradas")
        return 0
    if opciones.worker:
        print("worker: las tareas programadas se activan en TASK-004; nada que ejecutar")
        return 0
    analizador.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
