"""Árbitro de INV_MISMO_COMPOSE e INV_RED_AISLADA (estático): los dos archivos compose son válidos y coherentes.

La validación con `docker compose config` la hace el arnés cuando docker está en el PATH (siempre en CI).
"""
from __future__ import annotations

import yaml

from tests.conftest import RAIZ

SERVICIOS_BASE = {"app", "mcp-tools", "worker", "proxy", "postgres-beta"}


def _cargar(nombre: str) -> dict:
    datos = yaml.safe_load((RAIZ / nombre).read_text(encoding="utf-8"))
    assert isinstance(datos, dict), f"{nombre} debe ser un mapa"
    return datos


def test_compose_base_declara_servicios_y_redes() -> None:
    base = _cargar("compose.yaml")
    assert SERVICIOS_BASE <= set(base["services"]), set(base["services"])
    assert {"agent-net", "glamping-beta-net"} <= set(base["networks"])


def test_solo_el_proxy_publica_puertos_externos() -> None:
    base = _cargar("compose.yaml")
    for nombre, servicio in base["services"].items():
        puertos = servicio.get("ports", [])
        if nombre == "proxy":
            assert puertos, "el proxy debe publicar 443"
        elif nombre == "postgres-beta":
            assert all(str(p).startswith("127.0.0.1:") for p in puertos), "postgres-beta solo en loopback"
        else:
            assert not puertos, f"{nombre} no debe publicar puertos: {puertos}"


def test_postgres_beta_no_esta_en_agent_net() -> None:
    base = _cargar("compose.yaml")
    redes = base["services"]["postgres-beta"].get("networks", [])
    assert "agent-net" not in redes and "glamping-beta-net" in redes


def test_todos_los_servicios_de_aplicacion_tienen_limites() -> None:
    base = _cargar("compose.yaml")
    for nombre in ("app", "mcp-tools", "worker"):
        limites = base["services"][nombre].get("deploy", {}).get("resources", {}).get("limits", {})
        assert {"cpus", "memory"} <= set(limites), f"{nombre} sin límites de CPU/RAM"


def test_sobrescritura_de_produccion_endurece_sin_redefinir_servicios() -> None:
    base = _cargar("compose.yaml")
    produccion = _cargar("compose.production.yaml")
    assert set(produccion["services"]) <= set(base["services"]), "producción no añade servicios nuevos"
    for nombre in ("app", "mcp-tools", "proxy"):
        assert produccion["services"][nombre].get("restart") == "always"
    assert "build" not in produccion["services"]["app"], "producción no cambia la imagen; solo endurece"


def test_env_example_cubre_las_variables_referenciadas() -> None:
    """Toda ${VARIABLE} sin valor por defecto en los YAML de salas aparece en .env.example."""
    import re
    patron = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-[^}]*)?\}")
    referidas: set[str] = set()
    for ruta in list((RAIZ / "features").rglob("config_*.yaml")) + [RAIZ / "app_core" / "config_app.yaml"]:
        referidas |= set(patron.findall(ruta.read_text(encoding="utf-8")))
    declaradas = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", (RAIZ / ".env.example").read_text(encoding="utf-8"), re.M))
    faltantes = referidas - declaradas
    assert not faltantes, f"variables sin documentar en .env.example: {sorted(faltantes)}"
