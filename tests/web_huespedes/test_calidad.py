"""Árbitro de RF-WEB-06 e INV_INTERFAZ_PURIFICADA.

Auditoría de calidad pública: móvil primero, WCAG 2.1 AA, títulos y datos estructurados para buscadores,
presupuesto LCP y purificación estricta de interfaz (cero rastros de gobernanza ¤ y ¦).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from fastapi.testclient import TestClient

from features.web_huespedes.web_huespedes_service import WebHuespedesService, cargar_config

RUTA_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "features" / "web_huespedes" / "templates"


def test_inv_interfaz_purificada_sin_rastros_en_plantillas_ni_html() -> None:
    # Dado el catálogo y las plantillas
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    # 1. Verificar archivos de plantillas Jinja2
    plantillas = list(RUTA_TEMPLATES.glob("*.html"))
    assert len(plantillas) >= 3, "Deben existir al menos base.html, catalogo.html y ficha.html"

    for p in plantillas:
        texto = p.read_text(encoding="utf-8")
        assert "¤" not in texto, f"Rastro '¤' encontrado en plantilla {p.name}"
        assert "¦" not in texto, f"Huella '¦' encontrada en plantilla {p.name}"

    # 2. Verificar HTML renderizado en las distintas rutas
    respuestas = [
        client.get("/").text,
        client.get("/propiedades/EJ-01").text,
        client.get("/propiedades/NO_EXISTE").text,
    ]

    for html in respuestas:
        assert "¤" not in html, "Rastro '¤' encontrado en HTML servido al usuario"
        assert "¦" not in html, "Huella '¦' encontrada en HTML servido al usuario"


def test_accesibilidad_y_movil_primero() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    for ruta in ("/", "/propiedades/EJ-01"):
        resp = client.get(ruta)
        assert resp.status_code == 200
        html = resp.text

        # Móvil primero: etiqueta viewport
        assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html

        # Idioma español configurado
        assert '<html lang="es">' in html

        # Título principal h1 presente
        assert "<h1" in html

        # Todas las imágenes deben tener atributo alt no vacío
        etiquetas_img = re.findall(r"<img[^>]+>", html)
        for img in etiquetas_img:
            assert 'alt="' in img, f"Imagen sin atributo alt: {img}"
            match_alt = re.search(r'alt="([^"]*)"', img)
            assert match_alt and match_alt.group(1).strip(), f"Atributo alt vacío en imagen: {img}"

        # Botones y enlaces con objetivos táctiles accesibles (definidos en estilos como min 44px)
        assert "min-height: 44px" in html or "min-height:44px" in html


def test_titulos_y_datos_estructurados_para_buscadores() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    # Inicio
    resp_inicio = client.get("/")
    assert "<title>Catálogo de Hospedajes — Glamping Imbabura</title>" in resp_inicio.text

    scripts_ld_inicio = re.findall(r'<script type="application/ld\+json">(.*?)</script>', resp_inicio.text, re.DOTALL)
    assert len(scripts_ld_inicio) >= 1
    datos_ld_inicio = json.loads(scripts_ld_inicio[0])
    assert datos_ld_inicio["@context"] == "https://schema.org"
    assert datos_ld_inicio["@type"] == "ItemList"

    # Ficha
    resp_ficha = client.get("/propiedades/EJ-01")
    assert "<title>Domo de ejemplo — Glamping Imbabura</title>" in resp_ficha.text

    scripts_ld_ficha = re.findall(r'<script type="application/ld\+json">(.*?)</script>', resp_ficha.text, re.DOTALL)
    assert len(scripts_ld_ficha) >= 1
    datos_ld_ficha = json.loads(scripts_ld_ficha[0])
    assert datos_ld_ficha["@context"] == "https://schema.org"
    assert datos_ld_ficha["@type"] == "LodgingBusiness"
    assert datos_ld_ficha["name"] == "Domo de ejemplo"


def test_presupuesto_lcp_y_cero_scripts_externos() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    resp = client.get("/")
    # Presupuesto: HTML completo menor a 40 KB para asegurar LCP <= 2.5s en 4G
    assert len(resp.content) < 40000

    # Cero scripts externos o CDNs que bloqueen el renderizado
    scripts_externos = re.findall(r'<script[^>]+src=["\']http', resp.text)
    assert len(scripts_externos) == 0

    # Cero fuentes web externas (usa tipografía de sistema)
    assert "fonts.googleapis.com" not in resp.text
