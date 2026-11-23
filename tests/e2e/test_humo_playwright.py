# ¤bbap-glamping
# ¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Suite de humo de extremo a extremo con Playwright (Punto 8).

Ejecuta 4 flujos críticos con 0 reintentos contra una instancia de servidor real y base de datos aislada:
1. Web pública de huéspedes: catálogo de propiedades y formulario de búsqueda (TC-MAN-01).
2. Ficha de propiedad: detalles y botón de transición a WhatsApp con código de contexto (TC-MAN-02).
3. Panel operativo PWA: carga del shell, manifest y pantalla de acceso/login (TC-MAN-08, TC-MAN-10).
4. Endpoint de observabilidad: estado observable en /health.
"""
from __future__ import annotations

import json
from playwright.sync_api import Page, expect


def test_humo_01_catalogo_web_publico(servidor_test: str, pagina_playwright: Page) -> None:
    """Flujo Crítico 1: Carga de la web pública y visualización del catálogo (TC-MAN-01)."""
    pagina_playwright.goto(f"{servidor_test}/")

    # Validar título de página y encabezado de marca
    expect(pagina_playwright).to_have_title("Catálogo de Hospedajes — Glamping Imbabura")
    marca = pagina_playwright.locator(".marca").first
    expect(marca).to_contain_text("Glamping Imbabura")

    # Validar presencia de alojamientos publicados (mínimo 3 unidades)
    tarjetas = pagina_playwright.locator(".titulo-propiedad")
    assert tarjetas.count() >= 3, f"Se esperaban al menos 3 propiedades, encontradas: {tarjetas.count()}"

    # Validar presencia de botones de acción en las tarjetas
    expect(pagina_playwright.locator("a:has-text('Ver detalles')").first).to_be_visible()
    expect(pagina_playwright.locator("button:has-text('Consultar por WhatsApp')").first).to_be_visible()

    # Validar página de búsqueda con filtros (desde, hasta, huéspedes)
    pagina_playwright.goto(f"{servidor_test}/buscar")
    expect(pagina_playwright.locator("input[name='desde']")).to_be_visible()
    expect(pagina_playwright.locator("input[name='hasta']")).to_be_visible()
    expect(pagina_playwright.locator("input[name='huespedes']")).to_be_visible()


def test_humo_02_ficha_propiedad_y_enlace_whatsapp(servidor_test: str, pagina_playwright: Page) -> None:
    """Flujo Crítico 2: Visualización de ficha y transición hacia WhatsApp con código W- (TC-MAN-02)."""
    pagina_playwright.goto(f"{servidor_test}/propiedades/DOMO-LAGO")

    # Validar que cargue la ficha de la propiedad
    encabezado = pagina_playwright.locator("h1").first
    expect(encabezado).to_contain_text("Domo del Lago")

    # Validar presencia de sección de contacto y formulario
    formulario = pagina_playwright.locator("form.formulario-contacto")
    expect(formulario).to_be_visible()

    boton_whatsapp = pagina_playwright.locator("button:has-text('Continuar a WhatsApp')")
    expect(boton_whatsapp).to_be_visible()

    # Al hacer clic, el navegador envía el formulario a /contacto y sigue la redirección hacia WhatsApp
    boton_whatsapp.click()
    pagina_playwright.wait_for_timeout(500)
    url_actual = pagina_playwright.url
    assert "whatsapp" in url_actual, f"La URL de destino no es WhatsApp: {url_actual}"
    assert "W-" in url_actual, f"El mensaje no incluye código W- de trazabilidad: {url_actual}"


def test_humo_03_panel_operativo_pwa_y_login(servidor_test: str, pagina_playwright: Page) -> None:
    """Flujo Crítico 3: Carga del panel PWA, manifest y pantalla de autenticación (TC-MAN-08, TC-MAN-10)."""
    pagina_playwright.goto(f"{servidor_test}/panel")

    # Validar título y etiqueta manifest
    expect(pagina_playwright).to_have_title("Panel Operativo — Glamping Imbabura")
    manifest = pagina_playwright.locator("link[rel='manifest']")
    expect(manifest).to_have_attribute("href", "/panel/manifest.webmanifest")

    # Esperar que app.js renderice la pantalla de acceso en el DOM
    pantalla_acceso = pagina_playwright.locator(".pantalla-acceso")
    expect(pantalla_acceso).to_be_visible(timeout=5000)

    # Validar campos de autenticación sin password (código OTP por email)
    input_email = pagina_playwright.locator("input[type='email']")
    expect(input_email).to_be_visible()

    boton_codigo = pagina_playwright.locator("button:has-text('Enviarme el código')")
    expect(boton_codigo).to_be_visible()


def test_humo_04_salud_observabilidad_health(servidor_test: str, pagina_playwright: Page) -> None:
    """Flujo Crítico 4: Verificación del endpoint observable de salud del sistema."""
    respuesta = pagina_playwright.goto(f"{servidor_test}/health")
    assert respuesta is not None, "No se obtuvo respuesta de /health"
    assert respuesta.status == 200, f"Estado inesperado: {respuesta.status}"

    contenido = pagina_playwright.locator("body").inner_text()
    datos = json.loads(contenido)
    assert datos.get("estado") == "ok"
    assert datos.get("version") == "0.1.0"
