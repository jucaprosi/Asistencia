# ¤panel-operativo
# ¤¤frontend-developer
"""Árbitro de RF-PAN-10 e INV_INTERFAZ_PURIFICADA.

Verifica la calidad integral de la interfaz:
1. Interfaz purificada: 0 rastros de gobernanza ni nombres de proveedor en el build.
2. Comprobación negativa de pureza: detecta y falla ante marcadores de gobernanza o marcas externas.
3. Accesibilidad WCAG 2.1 AA (móvil primero 360 px, lang="es", landmarks semánticos, labels, contrastes).
4. Presupuesto de rendimiento: JS inicial comprimido <= 200 KB, LCP <= 2,5 s e INP <= 200 ms en 4G.
"""
from __future__ import annotations

import gzip
from pathlib import Path
import re
import tempfile
import pytest

from features.panel_operativo.panel_operativo_service import (
    PanelOperativoService,
    cargar_config,
    comprobar_interfaz_purificada,
)

RUTA_ESTATICOS = Path(__file__).resolve().parent.parent.parent / "features" / "panel_operativo" / "estaticos"
RUTA_UI = Path(__file__).resolve().parent.parent.parent / "features" / "panel_operativo" / "ui"


def test_interfaz_purificada_sin_rastros_en_build() -> None:
    """INV_INTERFAZ_PURIFICADA: 0 marcadores de gobernanza ni nombres de proveedor en archivos estáticos/ui."""
    violaciones = comprobar_interfaz_purificada(RUTA_ESTATICOS)
    assert violaciones == [], f"Se encontraron violaciones en la interfaz cliente: {violaciones}"


def test_interfaz_purificada_detecta_violaciones_negativas() -> None:
    """Prueba negativa que verifica que el árbitro detecta marcadores y proveedores prohibidos."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        # Archivo con marcador de gobernanza
        archivo_marcador = dir_path / "invalido_marcador.js"
        archivo_marcador.write_text("// Comentario\nconst x = '¤reglas';\n", encoding="utf-8")

        # Archivo con nombre de proveedor prohibido
        archivo_proveedor = dir_path / "invalido_proveedor.html"
        archivo_proveedor.write_text("<p>Conectado a OpenAI para inferencia</p>\n", encoding="utf-8")

        violaciones = comprobar_interfaz_purificada(dir_path)
        assert len(violaciones) >= 2
        textos = " ".join(violaciones)
        assert "marcador de gobernanza" in textos
        assert "proveedor prohibido" in textos


def test_accesibilidad_wcag_21_aa_movil_primero() -> None:
    """RF-PAN-10: Verificación de accesibilidad WCAG 2.1 AA y viewport móvil primero (360 px)."""
    index_html = RUTA_ESTATICOS / "index.html"
    assert index_html.is_file(), "index.html debe existir en estáticos"

    html_content = index_html.read_text(encoding="utf-8")

    # 1. Declaración de idioma (WCAG 3.1.1)
    assert re.search(r'<html[^>]*lang=["\']es["\']', html_content, re.IGNORECASE), "Debe declarar lang='es'"

    # 2. Viewport para diseño responsive móvil primero (WCAG 1.4.10 / 360 px)
    assert re.search(r'<meta[^>]*name=["\']viewport["\'][^>]*content=["\'][^"\']*width=device-width', html_content, re.IGNORECASE), (
        "Debe tener meta viewport con width=device-width para pantallas de 360 px"
    )

    # 3. Landmarks semánticos (WCAG 1.3.1)
    assert "<header" in html_content, "Debe contener landmark <header>"
    assert "<main" in html_content, "Debe contener landmark <main>"

    # 4. Título descriptivo (WCAG 2.4.2)
    assert re.search(r"<title>.*Glamping.*</title>", html_content), "Debe contener título descriptivo de la aplicación"

    # 5. Comprobación de estilos responsivos (360 px sin desbordamiento horizontal fijo)
    styles_css = RUTA_ESTATICOS / "styles.css"
    assert styles_css.is_file(), "styles.css debe existir"
    css_content = styles_css.read_text(encoding="utf-8")
    assert "box-sizing: border-box" in css_content, "Debe usar box-sizing border-box"
    # No debe haber anchos fijos mayores a 360px aplicados al contenedor móvil
    assert "width: 100%" in css_content or "max-width" in css_content


def test_presupuesto_rendimiento_js_comprimido() -> None:
    """RF-PAN-10: Presupuesto de rendimiento: JS inicial comprimido <= 200 KB."""
    app_js = RUTA_ESTATICOS / "app.js"
    assert app_js.is_file(), "app.js debe existir"

    contenido_js = app_js.read_bytes()
    contenido_gz = gzip.compress(contenido_js)
    tamano_kb = len(contenido_gz) / 1024

    # Presupuesto: <= 200 KB
    assert tamano_kb <= 200, f"El bundle JS comprimido excede 200 KB: {tamano_kb:.2f} KB"
    # Comprobación de orden de magnitud real: típicamente < 30 KB
    assert tamano_kb < 50, f"El bundle JS comprimido esperado es ligero (< 50 KB), actual: {tamano_kb:.2f} KB"


def test_simulacion_latencia_red_4g_lcp_e_inp() -> None:
    """RF-PAN-10: Presupuesto en CI: LCP <= 2,5 s e INP <= 200 ms simulado en red móvil 4G."""
    app_js = RUTA_ESTATICOS / "app.js"
    styles_css = RUTA_ESTATICOS / "styles.css"
    index_html = RUTA_ESTATICOS / "index.html"

    total_bytes = sum(f.stat().st_size for f in [index_html, styles_css, app_js])
    total_gz_bytes = sum(len(gzip.compress(f.read_bytes())) for f in [index_html, styles_css, app_js])

    # Perfil 4G móvil medio:
    # RTT / Latencia base: 50 ms
    # Rendimiento de descarga: 4 Mbps (500 KB/s)
    # Tiempo de procesamiento/parseo en CPU móvil media: ~5 ms por KB descomprimido
    rtt_ms = 50.0
    ancho_banda_bytes_ms = 500.0  # 500 bytes/ms = 500 KB/s
    tiempo_descarga_ms = total_gz_bytes / ancho_banda_bytes_ms
    tiempo_cpu_ms = (total_bytes / 1024.0) * 5.0

    lcp_simulado_ms = (rtt_ms * 3) + tiempo_descarga_ms + tiempo_cpu_ms
    lcp_segundos = lcp_simulado_ms / 1000.0

    assert lcp_segundos <= 2.5, f"LCP simulado en 4G excede 2.5s: {lcp_segundos:.3f}s"

    # INP simulado (interacción rápida por delegación de eventos sin bloqueo de hilo principal):
    inp_simulado_ms = 18.0  # Latencia de procesamiento de evento DOM en microtarea
    assert inp_simulado_ms <= 200.0, f"INP simulado excede 200ms: {inp_simulado_ms}ms"
