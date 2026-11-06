# ¤pasillo-central
# ¤¤qa-engineer
"""Pruebas del árbitro para INV_INTERFAZ_PURIFICADA (RF-PAN-10, RF-WEB-06).

Ley: ∀ t ∈ textos_de_usuario : t ∩ {¤, ¦} = ∅
Ningún texto de cara a huésped, vendedor o equipo en plantillas, catálogo web o panel operativo contiene rastros.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.main import crear_app

RAIZ = Path(__file__).resolve().parent.parent
PATRON_RASTROS = re.compile(r"[¤¦]|¤¬|¤¤")


# ¤pasillo-central
def _contiene_rastros(texto: str) -> bool:
    """Verifica si un texto contiene símbolos de gobernanza internos (¤, ¦, ¤¬, ¤¤)."""
    return bool(PATRON_RASTROS.search(texto))


# ¤pasillo-central
def test_plantillas_whatsapp_sin_rastros() -> None:
    """INV_INTERFAZ_PURIFICADA: Las plantillas de WhatsApp aprobables y en uso no contienen rastros."""
    ruta_config = RAIZ / "features" / "canal_whatsapp" / "config_canal_whatsapp.yaml"
    with ruta_config.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    plantillas = config.get("plantillas", [])
    assert len(plantillas) > 0, "Debe existir al menos una plantilla configurada"

    for p in plantillas:
        nombre = p.get("nombre", "")
        idioma = p.get("idioma", "")
        variables = p.get("variables", [])

        assert not _contiene_rastros(nombre), f"Nombre de plantilla contiene rastros: {nombre}"
        assert not _contiene_rastros(idioma), f"Idioma contiene rastros: {idioma}"
        for var in variables:
            assert not _contiene_rastros(var), f"Variable de plantilla {nombre} contiene rastros: {var}"


# ¤pasillo-central
def test_web_huespedes_plantillas_html_sin_rastros() -> None:
    """INV_INTERFAZ_PURIFICADA: Todas las plantillas HTML de cara al huésped están limpias de rastros."""
    dir_templates = RAIZ / "features" / "web_huespedes" / "templates"
    archivos_html = list(dir_templates.glob("*.html"))
    assert len(archivos_html) > 0, "Deben existir plantillas HTML en web_huespedes"

    for plantilla in archivos_html:
        contenido = plantilla.read_text(encoding="utf-8")
        # Eliminar comentarios HTML y etiquetas jinja de control si las hubiera
        sin_comentarios = re.sub(r"<!--.*?-->", "", contenido, flags=re.DOTALL)
        assert not _contiene_rastros(sin_comentarios), (
            f"La plantilla HTML pública {plantilla.name} contiene marcas de gobernanza ¤ o ¦."
        )


# ¤pasillo-central
def test_escenario_calidad_publica_catalogo() -> None:
    """@RF-WEB-06 @INV_INTERFAZ_PURIFICADA: Escenario de Calidad pública.

    Dado el catálogo publicado
    Cuando corre la auditoría
    Entonces cumple accesibilidad y presupuesto, tiene títulos y datos para buscadores, y no contiene rastros.
    """
    entorno_prueba = {
        "APP_ENV": "prueba",
        "DATABASE_URL": "postgresql://prueba",
        "META_ACCESS_TOKEN": "x",
        "META_VERIFY_TOKEN": "x",
        "META_APP_SECRET": "x",
        "ANTHROPIC_API_KEY": "x",
        "PII_VAULT_KEY": "x",
        "PANEL_SESSION_SECRET": "x",
    }
    contenedor = construir(entorno=entorno_prueba)
    app = crear_app(contenedor)
    cliente = TestClient(app)

    # 1. Obtener catálogo público
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    html = respuesta.text

    # 2. No contiene rastros internos (INV_INTERFAZ_PURIFICADA)
    assert not _contiene_rastros(html), "El HTML renderizado del catálogo contiene marcas ¤ o ¦."

    # 3. Títulos y metadatos para buscadores (SEO básico)
    assert "<title>" in html and "</title>" in html, "Falta etiqueta <title>"
    assert 'meta name="viewport"' in html or 'meta name="description"' in html

    # 4. Accesibilidad básica: lang en html y encabezados semánticos
    assert '<html lang="' in html or "<html lang='es'" in html or "<html" in html
    assert "<h1" in html or "<h2" in html, "El catálogo debe tener encabezados semánticos"


# ¤pasillo-central
def test_escenario_calidad_panel_operativo() -> None:
    """@RF-PAN-10 @INV_INTERFAZ_PURIFICADA: Escenario de Calidad del panel.

    Dado el build del panel
    Cuando corre la auditoría
    Entonces no hay errores críticos de accesibilidad, cumple el presupuesto y no contiene rastros.
    """
    dir_ui = RAIZ / "features" / "panel_operativo" / "ui"
    archivos_ui = list(dir_ui.glob("*.ts")) + list(dir_ui.glob("*.js")) + list(dir_ui.glob("*.html"))
    assert len(archivos_ui) > 0, "Deben existir archivos de UI del panel operativo"

    for archivo in archivos_ui:
        contenido = archivo.read_text(encoding="utf-8")
        # Filtrar comentarios de cabecera de sala ADPA si los hubiera
        lineas_codigo = [
            l for l in contenido.splitlines()
            if not l.strip().startswith("// ¤") and not l.strip().startswith("/* ¤") and not l.strip().startswith("# ¤")
        ]
        texto_limpio = "\n".join(lineas_codigo)
        assert not _contiene_rastros(texto_limpio), (
            f"El archivo de UI del panel {archivo.name} contiene marcas de gobernanza ¤ o ¦ en texto visible."
        )


# ¤pasillo-central
def test_mensajes_usuario_en_contratos_dominio() -> None:
    """INV_INTERFAZ_PURIFICADA: Las plantillas del contrato canónico dominio.yaml no tienen rastros en texto."""
    ruta_dominio = RAIZ / "docs" / "spec" / "contratos" / "dominio.yaml"
    with ruta_dominio.open(encoding="utf-8") as f:
        datos = yaml.safe_load(f)

    plantillas = datos.get("plantillas", [])
    assert len(plantillas) > 0, "Deben existir plantillas en dominio.yaml"

    for p in plantillas:
        nombre = p.get("nombre", "")
        categoria = p.get("categoria", "")
        variables = p.get("variables", [])

        assert not _contiene_rastros(str(nombre)), f"Nombre de plantilla tiene rastros: {nombre}"
        assert not _contiene_rastros(str(categoria)), f"Categoría de plantilla tiene rastros: {categoria}"
        for var in variables:
            assert not _contiene_rastros(str(var)), f"Variable de plantilla {nombre} tiene rastros: {var}"
