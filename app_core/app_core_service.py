# ¤pasillo-central
# ¤¤solutions-architect
"""Compuerta del pasillo central: lo único que otros módulos (main.py, pruebas, worker) importan de app_core.

``contenedor.py`` queda como módulo privado del pasillo; esta compuerta reexporta su interfaz pública.
"""
from __future__ import annotations

from app_core.contenedor import (
    RUTA_CONFIG, ConfiguracionInvalida, Contenedor, cargar_config_app, construir, resolver_secretos,
)

__all__ = ["RUTA_CONFIG", "ConfiguracionInvalida", "Contenedor", "cargar_config_app", "construir", "resolver_secretos"]
