# ¤persistencia-sql
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de migraciones de ADR-0023 (esqueleto; las reglas se implementan tras las pruebas en rojo)."""
from __future__ import annotations

from pathlib import Path


# ¤persistencia-sql
def cargar_base(ref: str = "origin/main") -> dict[str, str] | None:
    """Contenido de esquema.sql y de las migraciones en la rama base, o None si no está disponible."""
    return None


# ¤persistencia-sql
def verificar_migraciones(carpeta: Path, ruta_esquema: Path, base: dict[str, str] | None) -> list[str]:
    """Lista de violaciones de ADR-0023 (vacía si todo cumple)."""
    return []
