# ¤herramientas-mcp
# ¤¤backend-developer
"""Ejecutable del servidor MCP de la sala herramientas_glamping. Importa solo su propia compuerta.

Fase 0: arranca, lee su configuración y termina; el transporte MCP real llega en TASK-003.
"""
from __future__ import annotations

from features.herramientas_glamping.herramientas_glamping_service import cargar_config


# ¤herramientas-mcp
def main() -> int:
    config = cargar_config()
    herramientas = [h.get("nombre") for h in config.get("herramientas", [])]
    print(
        f"servidor MCP herramientas_glamping: transporte={config.get('transporte')} "
        f"herramientas_declaradas={len(herramientas)} (transporte real en TASK-003)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
