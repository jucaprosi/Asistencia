# ¤panel-operativo
# ¤¤frontend-developer
"""Árbitro E2E de la Terminal Móvil PWA instalable, pantalla P-12 y comportamiento sin red (RF-PAN-11, RF-PAN-13).

Verifica:
1. PWA instalable: Manifiesto web y service worker válidos, con pantalla completa e iconos (RF-PAN-11 a).
2. Actualización inmediata: La nueva versión del service worker se activa de inmediato con skipWaiting y clients.claim (RF-PAN-11 b).
3. Revocación por cierre de sesión: Cerrar sesión revoca el dispositivo móvil en la persistencia (RF-PAN-11 c).
4. Terminal sin red: Muestra en solo lectura los datos que tenía en memoria con aviso visible (RF-PAN-13, P-12).
5. Invariante INV_MOVIL_SIN_ESCRITURA_SIN_RED: Ninguna acción se ejecuta ni se encola sin red; botones deshabilitados.
6. Invariante INV_MOVIL_SIN_PII_EN_DISCO: La caché almacena únicamente el shell estático; la API jamás se persiste.
"""
from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from dataclasses import dataclass
from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.componentes_internal import (
    BannerSinConexion,
    BarraInferiorNavegacion,
    TarjetaAvisosWebPush,
    TarjetaInstalacionPWA,
    renderP12TerminalMovil,
)
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config


# ¤panel-operativo
@dataclass(frozen=True)
class EstadoTerminalMovil:
    conectado: bool
    rol: str
    usuario_id: str
    ventas_en_memoria: tuple[dict, ...] = ()
    avisos_activados: bool = False
    instalado_pwa: bool = False
from tests.panel_operativo.dobles import (
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleSeguridadService,
)

RUTA_ESTATICOS = Path(__file__).resolve().parent.parent.parent / "features" / "panel_operativo" / "estaticos"


# ¤panel-operativo
@pytest.fixture
def entorno_terminal():
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    comisiones = DobleComisionesService()
    arm = DobleArmJarvisService(comisiones=comisiones, canal=canal)

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        comisiones=comisiones,
        arm=arm,
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión de Líder comercial
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp_sesion = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo})
    csrf = resp_sesion.json()["csrf"]
    usuario_id = resp_sesion.json()["usuario_id"]

    return client, csrf, usuario_id, servicio, canal


# ¤panel-operativo
def test_pwa_manifiesto_y_service_worker_validos(entorno_terminal) -> None:
    # RF-PAN-11 (a)
    client, _, _, _, _ = entorno_terminal

    # 1. Comprobar que el endpoint /panel/manifest.webmanifest entrega un JSON válido
    resp_manifest = client.get("/panel/manifest.webmanifest")
    assert resp_manifest.status_code == 200
    assert "application/manifest+json" in resp_manifest.headers.get("content-type", "")
    manifest_data = resp_manifest.json()

    assert manifest_data.get("name") == "Panel Operativo — Glamping Imbabura"
    assert manifest_data.get("short_name") == "Panel"
    assert manifest_data.get("display") == "standalone"
    assert manifest_data.get("start_url") == "/panel"

    iconos = manifest_data.get("icons", [])
    assert len(iconos) >= 2
    tamanos = [i.get("sizes") for i in iconos]
    assert "192x192" in tamanos
    assert "512x512" in tamanos

    # 2. Comprobar que los iconos físicos existen y son válidos
    icon192 = RUTA_ESTATICOS / "icon-192.png"
    icon512 = RUTA_ESTATICOS / "icon-512.png"
    assert icon192.is_file() and icon192.stat().st_size > 0
    assert icon512.is_file() and icon512.stat().st_size > 0

    # 3. Comprobar que el service worker /panel/sw.js se sirve con cabecera de ámbito correcta
    resp_sw = client.get("/panel/sw.js")
    assert resp_sw.status_code == 200
    assert "application/javascript" in resp_sw.headers.get("content-type", "")
    assert resp_sw.headers.get("Service-Worker-Allowed") == "/panel/"


# ¤panel-operativo
def test_service_worker_aplica_nueva_version_y_solo_guarda_shell(entorno_terminal) -> None:
    # RF-PAN-11 (b), INV_MOVIL_SIN_PII_EN_DISCO
    sw_file = RUTA_ESTATICOS / "sw.js"
    assert sw_file.is_file()
    sw_content = sw_file.read_text(encoding="utf-8")

    # (b) Nueva versión se aplica de inmediato al abrir
    assert "skipWaiting" in sw_content, "El service worker debe invocar skipWaiting en install"
    assert "clients.claim" in sw_content, "El service worker debe invocar clients.claim en activate"

    # INV_MOVIL_SIN_PII_EN_DISCO: La API nunca se guarda en caché
    assert "/panel/api" in sw_content
    assert "no-store" in sw_content

    # INV_MOVIL_SIN_ESCRITURA_SIN_RED: Sin background sync
    assert "sync" not in sw_content.lower() or "backgroundsync" not in sw_content.lower()


# ¤panel-operativo
def test_cerrar_sesion_revoca_el_dispositivo(entorno_terminal) -> None:
    # RF-PAN-11 (c)
    client, csrf, usuario_id, servicio, _ = entorno_terminal
    headers = {"x-csrf-token": csrf}

    # 1. El líder registra su dispositivo móvil para Web Push
    endpoint = "https://fcm.googleapis.com/fcm/send/terminal-lider-01"
    sub_resp = client.post(
        "/panel/api/dispositivos/suscribir",
        headers=headers,
        json={
            "endpoint": endpoint,
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM=",
                "auth": "tBHItJI5svbpez7KI4CCXg==",
            },
        },
    )
    assert sub_resp.status_code == 200

    # Comprobar que el dispositivo está activo en la persistencia
    dispositivos_activos = servicio._persistencia.obtener_dispositivos_activos_de_usuario(usuario_id)
    assert any(d["endpoint"] == endpoint for d in dispositivos_activos)

    # 2. Cuando el líder cierra sesión
    resp_cerrar = client.delete("/panel/api/sesion", headers=headers)
    assert resp_cerrar.status_code == 200

    # 3. Entonces el dispositivo queda revocado
    activos_tras_cierre = servicio._persistencia.obtener_dispositivos_activos_de_usuario(usuario_id)
    assert len(activos_tras_cierre) == 0

    todos = servicio._persistencia.obtener_todos_dispositivos()
    disp_lider = next((d for d in todos if d["endpoint"] == endpoint), None)
    assert disp_lider is not None
    assert disp_lider["revocado_en"] is not None


# ¤panel-operativo
def test_sin_red_muestra_solo_lectura_en_memoria_y_bloquea_escritura() -> None:
    # RF-PAN-13, INV_MOVIL_SIN_ESCRITURA_SIN_RED, INV_MOVIL_SIN_PII_EN_DISCO
    # Dado la terminal con ventas cargadas y sin conexión
    estado_offline = EstadoTerminalMovil(
        conectado=False,
        rol="lider",
        usuario_id="usr_lider_01",
        ventas_en_memoria=[
            {"venta_id": "V-2026-0107", "ticket": "V-2026-0107", "monto": "280.00", "estado": "por_validar"}
        ],
        avisos_activados=True,
        instalado_pwa=True,
    )

    # Cuando se renderiza la interfaz P-12 en modo offline
    html_p12 = renderP12TerminalMovil(estado_offline, vista_actual="ventas")

    # Entonces muestra el banner de aviso de solo lectura
    assert "Sin conexi&oacute;n &middot; solo lectura" in html_p12 or "Sin conexión · solo lectura" in html_p12
    assert "modo-sin-red" in html_p12

    # Y el ticket que estaba en memoria se visualiza
    assert "V-2026-0107" in html_p12
    assert "$280.00" in html_p12

    # Y el botón de acción está deshabilitado
    assert "disabled" in html_p12
    assert "Validar (deshabilitado)" in html_p12

    # Barra inferior muestra accesos de su rol
    assert "Ventas" in html_p12
    assert "Comisiones" in html_p12
    assert "Jarvis" in html_p12


# ¤panel-operativo
def test_componentes_p12_instalacion_y_avisos() -> None:
    # Componentes modulares de P-12
    html_inst = TarjetaInstalacionPWA(descartada=False)
    assert "Instalar en pantalla de inicio" in html_inst
    assert "solicitarInstalacionPWA()" in html_inst

    # Descartada no emite HTML
    assert TarjetaInstalacionPWA(descartada=True) == ""

    # Tarjeta de aviso de permisos
    html_aviso_inactivo = TarjetaAvisosWebPush(activados=False)
    assert "Activar avisos" in html_aviso_inactivo
    assert "activarAvisosWebPush()" in html_aviso_inactivo

    html_aviso_activo = TarjetaAvisosWebPush(activados=True)
    assert "Avisos activos en este teléfono" in html_aviso_activo or "Avisos activos en este tel&eacute;fono" in html_aviso_activo
