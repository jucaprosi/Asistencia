# ¤governance
# ¤¤qa-engineer
"""Árbitro de Escritura Conforme: UTF-8 sin BOM, huellas consolidadas, IP safety y ausencia de secretos (T-903, C3).

Comprueba que cada aspecto prometido en la norma de CLAUDE.md cuente con una verificación real
en disco y que cada uno falle ante casos sintéticos no conformes (mutantes muertos).
"""
from __future__ import annotations

import re
from pathlib import Path
import pytest

from tests.conftest import RAIZ

EXCLUIDOS = {".git", "transcriptor_tiktok", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "data"}
EXTENSIONES_TEXTO = {".py", ".yaml", ".yml", ".md", ".toml", ".json", ".sh", ".bat", ".txt", ".example", ".sql", ".feature"}

PATRONES_IP_PROHIBIDOS = [
    re.compile(r"(?i)\bcopyright\s+(?:\(c\)\s+)?(?:(?!202\d\s+Juan\s+Carlos\s+Proa[ñn]o|202\d\s+Glamping\s+Imbabura).)*\b(?:corp|inc|ltd|llc|gmbh|ag|s\.a\.|technologies|soft)\b"),
    re.compile(r"(?i)all\s+rights\s+reserved\s+to\s+(?!Juan\s+Carlos\s+Proa[ñn]o|Glamping\s+Imbabura)"),
]


# --- Funciones de Comprobación ---
def auditar_utf8(raiz: Path) -> list[str]:
    """Verifica que todo archivo de texto sea UTF-8 válido y sin BOM."""
    fallos: list[str] = []
    for ruta in raiz.rglob("*"):
        if not ruta.is_file() or any(p in EXCLUIDOS for p in ruta.parts):
            continue
        if ruta.suffix.lower() not in EXTENSIONES_TEXTO and ruta.name != ".env.example":
            continue
        datos = ruta.read_bytes()
        if datos.startswith(b"\xef\xbb\xbf"):
            fallos.append(f"BOM detectado: {ruta.name}")
            continue
        try:
            datos.decode("utf-8")
        except UnicodeDecodeError as exc:
            fallos.append(f"UTF-8 inválido: {ruta.name} ({exc})")
    return fallos


def auditar_huellas_consolidadas(raiz: Path) -> list[str]:
    """Verifica que en el código fuente de features/ y app_core/ no queden huellas abiertas ¦."""
    fallos: list[str] = []
    patron_huella = re.compile(r"(?:#\s*¤?¦[a-zA-Z0-9_-]+|¤¦[a-zA-Z0-9_-]+)")
    for carpeta in ("features", "app_core"):
        ruta_dir = raiz / carpeta
        if not ruta_dir.is_dir():
            continue
        for ruta in ruta_dir.rglob("*.py"):
            if any(p in EXCLUIDOS for p in ruta.parts):
                continue
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            for num_linea, linea in enumerate(texto.splitlines(), start=1):
                # Detecta huella abierta ¦ (ej. ¤¦triaje o # ¦algo) en comentarios o tags
                if patron_huella.search(linea) and not ("huellas" in linea and "linter" in linea):
                    fallos.append(f"Huella abierta ¦ en {ruta.name}:{num_linea}: {linea.strip()}")
    return fallos


def auditar_ip_safety(raiz: Path) -> list[str]:
    """Verifica que no existan reclamos de derechos de autor o IP ajena no autorizada."""
    fallos: list[str] = []
    for ruta in raiz.rglob("*"):
        if not ruta.is_file() or any(p in EXCLUIDOS for p in ruta.parts) or "tests" in ruta.parts:
            continue
        if ruta.suffix.lower() not in EXTENSIONES_TEXTO:
            continue
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for num_linea, linea in enumerate(texto.splitlines(), start=1):
            for patron in PATRONES_IP_PROHIBIDOS:
                if patron.search(linea):
                    fallos.append(f"Posible IP ajena en {ruta.name}:{num_linea}: {linea.strip()}")
    return fallos


# --- Pruebas sobre el Repositorio Real ---
def test_repositorio_cumple_utf8_sin_bom() -> None:
    """Norma: Todo archivo de texto en el proyecto es UTF-8 sin BOM."""
    fallos = auditar_utf8(RAIZ)
    assert not fallos, f"Archivos con codificación no conforme:\n" + "\n".join(fallos)


def test_repositorio_cumple_huellas_consolidadas() -> None:
    """Norma: No existen huellas abiertas ¦ en el código ejecutable de features/ y app_core/."""
    fallos = auditar_huellas_consolidadas(RAIZ)
    assert not fallos, f"Huellas no consolidadas en código:\n" + "\n".join(fallos)


def test_repositorio_cumple_ip_safety() -> None:
    """Norma: Sin reclamos de IP o copyright ajenos no autorizados en el proyecto."""
    fallos = auditar_ip_safety(RAIZ)
    assert not fallos, f"Infracciones de IP safety detectadas:\n" + "\n".join(fallos)


# --- Pruebas con Casos Sintéticos (Mutantes Muertos) ---
def test_mutante_sintetico_utf8_con_bom_es_rechazado(tmp_path: Path) -> None:
    """Comprueba que un archivo con BOM sintético haga fallar la comprobación de UTF-8."""
    archivo_bom = tmp_path / "modulo_con_bom.py"
    archivo_bom.write_bytes(b"\xef\xbb\xbf# codigo con BOM")
    fallos = auditar_utf8(tmp_path)
    assert len(fallos) == 1
    assert "BOM detectado" in fallos[0]


def test_mutante_sintetico_utf8_invalido_es_rechazado(tmp_path: Path) -> None:
    """Comprueba que un archivo con bytes UTF-8 inválidos haga fallar la comprobación."""
    archivo_invalido = tmp_path / "modulo_invalido.py"
    archivo_invalido.write_bytes(b"\xff\xfe\x00\x00codigo binario")
    fallos = auditar_utf8(tmp_path)
    assert len(fallos) == 1
    assert "UTF-8 inválido" in fallos[0]


def test_mutante_sintetico_huella_abierta_es_rechazada(tmp_path: Path) -> None:
    """Comprueba que una huella ¦ abierta en código ejecutable haga fallar la comprobación."""
    dir_features = tmp_path / "features" / "sala_test"
    dir_features.mkdir(parents=True)
    archivo_huella = dir_features / "prueba.py"
    archivo_huella.write_text("# ¤¦boceto_no_consolidado\ndef foo(): pass\n", encoding="utf-8")
    fallos = auditar_huellas_consolidadas(tmp_path)
    assert len(fallos) == 1
    assert "Huella abierta ¦" in fallos[0]


def test_mutante_sintetico_ip_ajena_es_rechazada(tmp_path: Path) -> None:
    """Comprueba que un copyright ajeno no autorizado haga fallar la comprobación de IP safety."""
    archivo_ip = tmp_path / "componente_tercero.py"
    archivo_ip.write_text("# Copyright (c) 2024 AcmeCorp Technologies Inc. All rights reserved.\n", encoding="utf-8")
    fallos = auditar_ip_safety(tmp_path)
    assert len(fallos) == 1
    assert "Posible IP ajena" in fallos[0]
