"""Fixtures compartidas: raíz del repositorio y catálogo de salas (fuente: governance/artefactos/PRD.md §2)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIOS_EXCLUIDOS = {".git", "transcriptor_tiktok", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist"}

SALAS_FASE_0 = (
    "canal_whatsapp", "seguridad", "agente", "conocimiento", "pms_conector", "crm_conector", "arm_jarvis",
    "comisiones", "observabilidad", "herramientas_glamping", "panel_operativo",
)


def archivos_python(*subdirectorios: str) -> list[Path]:
    """Todos los .py bajo los subdirectorios dados, sin los excluidos."""
    resultado: list[Path] = []
    for sub in subdirectorios:
        base = RAIZ / sub
        if not base.exists():
            continue
        for ruta in base.rglob("*.py"):
            if not any(parte in DIRECTORIOS_EXCLUIDOS for parte in ruta.parts):
                resultado.append(ruta)
    return sorted(resultado)


def salas_en_catalogo() -> tuple[str, ...]:
    """Lee las salas declaradas en governance/artefactos/PRD.md (filas con `features/<sala>`)."""
    prd = (RAIZ / "governance" / "artefactos" / "PRD.md").read_text(encoding="utf-8")
    return tuple(sorted(set(re.findall(r"`features/([a-z_]+)`", prd))))


@pytest.fixture(scope="session")
def raiz() -> Path:
    return RAIZ


@pytest.fixture(scope="session")
def salas() -> tuple[str, ...]:
    return SALAS_FASE_0
