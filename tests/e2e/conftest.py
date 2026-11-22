# ¤pasillo-central
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Configuración de fixtures para pruebas de extremo a extremo con Playwright y uvicorn aislado."""
from __future__ import annotations

import socket
import threading
import time
import urllib.request
from typing import Generator
import pytest
import uvicorn
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from app_core.app_core_service import construir
from app_core.main import crear_app

ENTORNO_TEST = {
    "APLICACION_ENTORNO": "prueba",
    "BD_URL": "sqlite:///:memory:",
    "PMS_PROVEEDOR": "doble",
    "CRM_PROVEEDOR": "doble",
    "SECRETO_HMAC": "secreto-test-playwright-32-bytes-minimo!!",
    "LLM_PROVEEDOR": "doble",
}


@pytest.fixture(scope="session")
def servidor_test() -> Generator[str, None, None]:
    """Levanta un servidor FastAPI en un hilo daemon con base de datos aislada y puerto efímero."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    puerto = sock.getsockname()[1]
    sock.close()

    contenedor = construir(entorno=ENTORNO_TEST)
    app = crear_app(contenedor)

    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=puerto,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()

    base_url = f"http://127.0.0.1:{puerto}"
    listo = False
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=0.5) as resp:
                if resp.status == 200:
                    listo = True
                    break
        except Exception:
            time.sleep(0.1)

    if not listo:
        server.should_exit = True
        raise RuntimeError(f"El servidor de prueba no respondió en {base_url}/health")

    yield base_url

    server.should_exit = True
    time.sleep(0.2)


@pytest.fixture
def pagina_playwright() -> Generator[Page, None, None]:
    """Lanza una instancia limpia de Chromium con 0 reintentos."""
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=True)
        context: BrowserContext = browser.new_context(
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True,
        )
        page: Page = context.new_page()
        page.set_default_timeout(10000)

        yield page

        context.close()
        browser.close()
