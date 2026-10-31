"""Árbitro de INV_SALA_CONFORME, INV_PANEL_SIN_LOGICA (estructura) y de las reglas ADPA/huellas en código.

Replica localmente lo que el adpa_linter y el huellas_linter de ZERAG exigen, para que el arnés sea autosuficiente:
- cada sala tiene `<sala>_service.py`, `config_<sala>.yaml` y `__init__.py`, y su compuerta se importa;
- ninguna sala importa módulos privados de otra (solo `features.<otra>.<otra>_service`);
- app_core/ importa de features/ únicamente compuertas `_service`;
- cada .py de features/ y app_core/ declara su rol `# ¤¤...` en las primeras 15 líneas;
- cada def/clase de primer nivel en features/, app_core/ y scripts/ lleva un rastro `# ¤...` encima;
- no hay huellas `¦` abiertas en código.
"""
from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest
import yaml

from tests.conftest import RAIZ, SALAS_FASE_0, archivos_python, salas_en_catalogo

RASTRO_RX = re.compile(r"(?<![¤¦¬])¤[a-z][a-z0-9_]*(?:-[a-z][a-z0-9_]*){0,2}")
ROL_RX = re.compile(r"¤¤[a-z][a-z0-9_-]*")
HUELLA_RX = re.compile(r"(?<!¤)¦[A-Za-z0-9_]")


def _camel(sala: str) -> str:
    return "".join(parte.capitalize() for parte in sala.split("_"))


def _nombre_clase(sala: str) -> str:
    especiales = {"pms_conector": "PMSConectorService", "crm_conector": "CRMConectorService"}
    return especiales.get(sala, f"{_camel(sala)}Service")


def _sala_de(ruta: Path) -> str | None:
    partes = ruta.relative_to(RAIZ).parts
    if partes[0] == "features" and len(partes) > 2:
        return partes[1]
    return None


def _imports(ruta: Path) -> list[str]:
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.append(nodo.module)
    return modulos


@pytest.mark.parametrize("sala", SALAS_FASE_0)
def test_sala_tiene_compuerta_config_e_init(sala: str) -> None:
    carpeta = RAIZ / "features" / sala
    assert carpeta.is_dir(), f"falta la sala features/{sala}"
    assert (carpeta / "__init__.py").is_file()
    assert (carpeta / f"{sala}_service.py").is_file(), f"falta la compuerta {sala}_service.py"
    config = carpeta / f"config_{sala}.yaml"
    assert config.is_file(), f"falta config_{sala}.yaml"
    datos = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert isinstance(datos, dict) and datos, f"config_{sala}.yaml debe ser un mapa no vacío"


@pytest.mark.parametrize("sala", SALAS_FASE_0)
def test_compuerta_importable_con_clase_y_cargador(sala: str) -> None:
    modulo = importlib.import_module(f"features.{sala}.{sala}_service")
    assert hasattr(modulo, _nombre_clase(sala)), f"la compuerta de {sala} debe exponer {_nombre_clase(sala)}"
    assert callable(getattr(modulo, "cargar_config", None))
    assert isinstance(modulo.cargar_config(), dict)


def test_catalogo_del_prd_coincide_con_las_salas_fisicas() -> None:
    """El PRD vivo declara las salas; las condicionales (operaciones) aún no existen y se toleran."""
    declaradas = set(salas_en_catalogo())
    fisicas = {p.name for p in (RAIZ / "features").iterdir() if p.is_dir() and not p.name.startswith("__")}
    assert fisicas <= declaradas, f"salas sin declarar en governance/artefactos/PRD.md: {fisicas - declaradas}"
    assert set(SALAS_FASE_0) <= declaradas


def test_sin_imports_cruzados_entre_salas() -> None:
    violaciones: list[str] = []
    for ruta in archivos_python("features"):
        propia = _sala_de(ruta)
        for modulo in _imports(ruta):
            partes = modulo.split(".")
            if partes[0] != "features" or len(partes) < 3:
                continue
            sala_destino, submodulo = partes[1], partes[2]
            if sala_destino != propia and not submodulo.endswith("_service"):
                violaciones.append(f"{ruta.relative_to(RAIZ)} importa {modulo}")
    assert not violaciones, "imports laterales prohibidos:\n" + "\n".join(violaciones)


def test_app_core_solo_importa_compuertas() -> None:
    violaciones: list[str] = []
    for ruta in archivos_python("app_core"):
        for modulo in _imports(ruta):
            partes = modulo.split(".")
            if partes[0] == "features":
                if len(partes) < 3 or not partes[2].endswith("_service"):
                    violaciones.append(f"{ruta.relative_to(RAIZ)} importa {modulo}")
    assert not violaciones, "app_core debe importar solo compuertas:\n" + "\n".join(violaciones)


def test_rol_declarado_en_cabecera() -> None:
    sin_rol = [
        str(ruta.relative_to(RAIZ))
        for ruta in archivos_python("features", "app_core")
        if not any(ROL_RX.search(linea) for linea in ruta.read_text(encoding="utf-8").splitlines()[:15])
    ]
    assert not sin_rol, "archivos sin rol ¤¤ en las primeras 15 líneas:\n" + "\n".join(sin_rol)


def test_rastro_encima_de_cada_definicion_de_primer_nivel() -> None:
    faltantes: list[str] = []
    for ruta in archivos_python("features", "app_core", "scripts"):
        texto = ruta.read_text(encoding="utf-8")
        lineas = texto.splitlines()
        for nodo in ast.parse(texto).body:
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            indice = nodo.lineno - 1
            ventana = lineas[max(0, indice - 2):indice]
            if not any(RASTRO_RX.search(linea) and not RASTRO_RX.search(linea).group(0).endswith("/") for linea in ventana):
                faltantes.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno} {nodo.name}")
    assert not faltantes, "definiciones sin rastro ¤ encima:\n" + "\n".join(faltantes)


def test_sin_huellas_abiertas_en_codigo() -> None:
    abiertas = [
        f"{ruta.relative_to(RAIZ)}:{n}"
        for ruta in archivos_python("features", "app_core", "scripts")
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), start=1)
        if HUELLA_RX.search(linea)
    ]
    assert not abiertas, "huellas ¦ sin consolidar:\n" + "\n".join(abiertas)


def test_sin_bom_en_codigo_ni_configuracion() -> None:
    con_bom: list[str] = []
    for patron in ("*.py", "*.yaml", "*.toml", "*.json", "*.md"):
        for ruta in RAIZ.rglob(patron):
            if any(parte in {".git", "transcriptor_tiktok", "node_modules", ".venv", "__pycache__", "data"} for parte in ruta.parts):
                continue
            if ruta.read_bytes().startswith(b"\xef\xbb\xbf"):
                con_bom.append(str(ruta.relative_to(RAIZ)))
    assert not con_bom, "archivos con BOM:\n" + "\n".join(con_bom)
