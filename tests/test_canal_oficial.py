"""Árbitro de INV_CANAL_OFICIAL (ADR-0003): ninguna librería no oficial de WhatsApp entra al repositorio."""
from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import RAIZ, archivos_python

LIBRERIAS_PROHIBIDAS = ("baileys", "whatsapp-web.js", "whatsapp_web_js", "whatsmeow", "open-wa", "venom-bot", "wppconnect")
MANIFIESTOS = ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")


def _manifiestos() -> list[Path]:
    encontrados: list[Path] = []
    for nombre in MANIFIESTOS:
        for ruta in RAIZ.rglob(nombre):
            if not any(parte in {".git", "transcriptor_tiktok", "node_modules", ".venv"} for parte in ruta.parts):
                encontrados.append(ruta)
    return encontrados


def test_manifiestos_sin_librerias_no_oficiales() -> None:
    hallazgos = [
        f"{ruta.relative_to(RAIZ)} menciona {lib}"
        for ruta in _manifiestos()
        for lib in LIBRERIAS_PROHIBIDAS
        if lib in ruta.read_text(encoding="utf-8", errors="replace").lower()
    ]
    assert not hallazgos, "\n".join(hallazgos)


def test_codigo_sin_imports_de_librerias_no_oficiales() -> None:
    patron = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.M)
    hallazgos: list[str] = []
    for ruta in archivos_python("app_core", "features", "scripts"):
        for modulo in patron.findall(ruta.read_text(encoding="utf-8")):
            if any(lib.replace("-", "_").replace(".js", "") in modulo.lower() for lib in LIBRERIAS_PROHIBIDAS):
                hallazgos.append(f"{ruta.relative_to(RAIZ)} importa {modulo}")
    assert not hallazgos, "\n".join(hallazgos)


def test_el_proyecto_declara_la_api_oficial() -> None:
    """La compuerta del canal existe y nombra la Cloud API en su documentación."""
    compuerta = RAIZ / "features" / "canal_whatsapp" / "canal_whatsapp_service.py"
    assert "Cloud API" in compuerta.read_text(encoding="utf-8")
