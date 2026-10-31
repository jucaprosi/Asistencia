"""Árbitro de INV_SIN_CLIENTES_OTA (RF-PMS-04): el agente no habla con Airbnb, Booking ni VRBO; lo hace el PMS."""
from __future__ import annotations

import re

from tests.conftest import RAIZ, archivos_python

OTAS = ("airbnb", "booking", "vrbo", "expedia", "homeaway")


def test_sin_imports_de_clientes_ota() -> None:
    patron = re.compile(r"^\s*(?:import|from)\s+([\w.]+)", re.M)
    hallazgos = [
        f"{ruta.relative_to(RAIZ)} importa {modulo}"
        for ruta in archivos_python("app_core", "features", "scripts")
        for modulo in patron.findall(ruta.read_text(encoding="utf-8"))
        if any(ota in modulo.lower() for ota in OTAS)
    ]
    assert not hallazgos, "\n".join(hallazgos)


def test_sin_dependencias_ota_en_pyproject() -> None:
    texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8").lower()
    seccion = texto.split("dependencies", 1)[1] if "dependencies" in texto else ""
    hallazgos = [ota for ota in OTAS if ota in seccion]
    assert not hallazgos, f"dependencias de OTA prohibidas: {hallazgos}"
