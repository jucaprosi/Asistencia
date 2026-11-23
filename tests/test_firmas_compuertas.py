# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de congelación y crecimiento monotónico de firmas públicas de compuertas ADPA.

Regla 4 de TASKS.md §1:
- Las firmas de cada `_service.py` solo crecen.
- Añadir métodos o parámetros es válido.
- Quitar o cambiar firmas existentes falla salvo que se declare explícitamente
  en 'cambios_de_contrato' con su 'motivo' técnico.
"""
from __future__ import annotations

import ast
import glob
import json
from pathlib import Path
import pytest

from tests.conftest import RAIZ

ARCHIVO_FIRMAS = RAIZ / "governance" / "artefactos" / "FIRMAS_COMPUERTAS.json"


def extraer_firmas_actuales(raiz: Path = RAIZ) -> dict[str, dict[str, list[str]]]:
    """Extrae las firmas públicas de las clases Service en features/*/*_service.py."""
    servicios = sorted(raiz.glob("features/*/*_service.py"))
    firmas: dict[str, dict[str, list[str]]] = {}
    for ruta in servicios:
        with open(ruta, "r", encoding="utf-8") as f:
            arbol = ast.parse(f.read(), filename=str(ruta))
        rel = ruta.relative_to(raiz).as_posix()
        for nodo in arbol.body:
            if isinstance(nodo, ast.ClassDef) and not nodo.name.startswith("_") and nodo.name.endswith("Service"):
                metodos: dict[str, list[str]] = {}
                for item in nodo.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith("_"):
                            args = [a.arg for a in item.args.args]
                            metodos[item.name] = args
                firmas[f"{rel}::{nodo.name}"] = metodos
    return firmas


def validar_compatibilidad_firmas(
    firmas_base: dict[str, dict[str, list[str]]],
    firmas_nuevas: dict[str, dict[str, list[str]]],
    cambios_permitidos: list[dict[str, str]] | None = None,
) -> list[str]:
    """Compara que firmas_nuevas preserve o extienda firmas_base sin regresiones."""
    errores: list[str] = []
    permitidos = {
        (c["servicio"], c["metodo"]): c["motivo"]
        for c in (cambios_permitidos or [])
        if "servicio" in c and "metodo" in c and c.get("motivo")
    }

    for servicio, metodos_base in firmas_base.items():
        if servicio not in firmas_nuevas:
            if (servicio, "*") not in permitidos:
                errores.append(f"Compuerta eliminada sin justificación: {servicio}")
            continue

        metodos_nuevos = firmas_nuevas[servicio]
        for metodo, args_base in metodos_base.items():
            if metodo not in metodos_nuevos:
                if (servicio, metodo) not in permitidos:
                    errores.append(
                        f"Método eliminado sin justificación en {servicio}: {metodo}() "
                        f"(requiere registrar entrada en 'cambios_de_contrato' con motivo)"
                    )
                continue

            args_nuevos = metodos_nuevos[metodo]
            # Los argumentos base deben preservarse en el mismo orden inicial
            if args_nuevos[:len(args_base)] != args_base:
                if (servicio, metodo) not in permitidos:
                    errores.append(
                        f"Firma alterada en {servicio}::{metodo}(): esperaba argumentos iniciales "
                        f"{args_base}, obtenidos {args_nuevos[:len(args_base)]}"
                    )

    return errores


def test_firmas_publicas_de_compuertas_solo_crecen() -> None:
    """Verifica que ninguna compuerta haya eliminado métodos públicos de la línea base."""
    assert ARCHIVO_FIRMAS.exists(), f"Línea base no encontrada en {ARCHIVO_FIRMAS}"
    with open(ARCHIVO_FIRMAS, "r", encoding="utf-8") as f:
        linea_base = json.load(f)

    firmas_base = linea_base.get("firmas", {})
    cambios_permitidos = linea_base.get("cambios_de_contrato", [])
    firmas_actuales = extraer_firmas_actuales(RAIZ)

    errores = validar_compatibilidad_firmas(firmas_base, firmas_actuales, cambios_permitidos)
    assert not errores, "\n".join(errores)


def test_quitar_funcion_de_compuerta_sin_justificacion_falla_mutante() -> None:
    """Verifica (mutante muerto) que remover una función sin justificación haga fallar el árbitro."""
    firmas_base = {
        "features/agente/agente_service.py::AgenteService": {
            "procesar_mensaje": ["self", "mensaje"],
            "metodo_critico": ["self", "param"],
        }
    }
    # Mutante: el código nuevo no tiene metodo_critico
    firmas_mutadas = {
        "features/agente/agente_service.py::AgenteService": {
            "procesar_mensaje": ["self", "mensaje"],
        }
    }

    errores = validar_compatibilidad_firmas(firmas_base, firmas_mutadas, cambios_permitidos=[])
    assert len(errores) == 1
    assert "Método eliminado sin justificación" in errores[0]
    assert "metodo_critico" in errores[0]


def test_quitar_funcion_con_justificacion_pasa() -> None:
    """Verifica que con entrada válida en cambios_de_contrato se permita el cambio de contrato."""
    firmas_base = {
        "features/agente/agente_service.py::AgenteService": {
            "metodo_obsoleto": ["self"],
        }
    }
    firmas_mutadas = {
        "features/agente/agente_service.py::AgenteService": {}
    }
    cambios = [
        {
            "servicio": "features/agente/agente_service.py::AgenteService",
            "metodo": "metodo_obsoleto",
            "motivo": "Deprecado tras migración a compuerta asíncrona (ADR-0019)",
        }
    ]

    errores = validar_compatibilidad_firmas(firmas_base, firmas_mutadas, cambios_permitidos=cambios)
    assert not errores, f"No debería haber errores pero se obtuvieron: {errores}"
