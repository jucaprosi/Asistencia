# ¤infra-hibrida
# ¤¤qa-engineer
"""Árbitro de integración para T-810: Despliegue Cloud/HTTPS de la Terminal Móvil (RF-PAN-11, RF-PAN-12).

Verifica la infraestructura de proxy inverso TLS, cabeceras no-store para PWA, variables VAPID
y cumplimiento de invariantes de seguridad y privacidad:
1. Proxy TLS (Caddyfile y nginx.conf) con HSTS, terminación segura y cabeceras Cache-Control: no-store
   en /panel/sw.js y /panel/manifest.*, así como Service-Worker-Allowed: /panel/.
2. Invariante INV_SIN_SECRETOS_EN_REPO: Plantilla vapid.env.example sin secretos y escáner en verde.
3. Escenario @RF-PAN-11: Terminal móvil instalable (manifiesto con standalone e iconos 192/512,
   service worker con skipWaiting y clients.claim, y revocación del dispositivo al cerrar sesión).
4. Escenario @RF-PAN-12 @INV_AVISO_SIN_PII: Avisos móviles Web Push activados con un toque,
   carga útil restringida estrictamente a {tipo, cantidad, ruta} sin PII ni montos,
   apertura de pantalla exacta con sesión y tolerancia a fallos ante caídas del transporte push.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.panel_crm_router import montar_panel_y_crm
from features.panel_operativo.panel_operativo_service import (
    AvisoMovil,
    PanelOperativoService,
    cargar_config,
)

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_PROXY = RAIZ / "infra" / "proxy"
RUTA_ESTATICOS = RAIZ / "features" / "panel_operativo" / "estaticos"

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "token_acceso_meta_test",
    "META_VERIFY_TOKEN": "token_prueba_meta_123",
    "META_APP_SECRET": "secreto_meta_app_456",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


# ¤infra-hibrida
class DobleSeguridadTerminal:
    """Doble de seguridad para autenticación de terminal móvil."""

    def __init__(self) -> None:
        self.usuarios = {
            "lider@glamping.ec": {
                "usuario_id": "usr_lider_01",
                "correo": "lider@glamping.ec",
                "rol": "lider",
                "zonas": ("zona_a", "zona_b"),
                "telefono": "+593993333333",
                "activo": True,
            }
        }

    def obtener_usuario_por_correo(self, correo: str) -> Mapping[str, Any] | None:
        return self.usuarios.get(correo.strip().lower())

    def auditar(self, evento: Any) -> None:
        pass

    def obtener_usuarios_por_rol(self, rol: str) -> list[dict[str, Any]]:
        return [u for u in self.usuarios.values() if u.get("rol") == rol]


# ¤infra-hibrida
class DobleCanalTerminal:
    """Doble de canal para captura de códigos OTP."""

    def __init__(self) -> None:
        self.codigos_emitidos: list[str] = []

    def enviar_plantilla(self, destino: str, plantilla: Any) -> bool:
        if hasattr(plantilla, "variables") and plantilla.variables:
            self.codigos_emitidos.append(str(plantilla.variables[0]))
        return True

    def aprobar_plantilla(self, nombre: str) -> None:
        pass


# ¤infra-hibrida
class DobleObservabilidadTerminal:
    """Doble de observabilidad para registro de avisos."""

    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []

    def log(self, nivel: str, evento: str, **kwargs: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **kwargs})


# ¤infra-hibrida
class CapturadorPushTest:
    """Doble de transporte Web Push para verificar cargas útiles."""

    def __init__(self, debe_fallar: bool = False) -> None:
        self.debe_fallar = debe_fallar
        self.envios: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []

    def __call__(self, disp: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
        self.envios.append((disp, payload))
        if self.debe_fallar:
            raise RuntimeError("Fallo de conexión simulado con FCM/WebPush")
        return True


# ¤infra-hibrida
def test_configuracion_caddy_tls_y_cabeceras_no_store() -> None:
    """Verifica directivas de Caddyfile para HTTPS, PWA y cabeceras no-store."""
    caddyfile = RUTA_PROXY / "Caddyfile"
    assert caddyfile.is_file(), "Caddyfile debe existir en infra/proxy/"

    contenido = caddyfile.read_text(encoding="utf-8")

    # Cabeceras de seguridad y TLS
    assert "Strict-Transport-Security" in contenido
    assert "X-Frame-Options" in contenido
    assert "X-Content-Type-Options" in contenido

    # Service Worker sin almacenamiento en caché y ámbito /panel/
    assert "@service_worker path /panel/sw.js" in contenido
    assert 'Service-Worker-Allowed "/panel/"' in contenido
    assert 'Cache-Control "no-store, no-cache, must-revalidate"' in contenido

    # Manifiesto sin almacenamiento en caché
    assert "@manifest path /panel/manifest.webmanifest /panel/manifest.json" in contenido
    assert 'Content-Type "application/manifest+json; charset=utf-8"' in contenido

    # API con no-store
    assert "@panel_api path /panel/api/*" in contenido
    assert "reverse_proxy" in contenido


# ¤infra-hibrida
def test_configuracion_nginx_tls_y_cabeceras_no_store() -> None:
    """Verifica directivas de nginx.conf para HTTPS, redirección 80->443 y cabeceras PWA."""
    nginx_conf = RUTA_PROXY / "nginx.conf"
    assert nginx_conf.is_file(), "nginx.conf debe existir en infra/proxy/"

    contenido = nginx_conf.read_text(encoding="utf-8")

    # Redirección HTTP a HTTPS
    assert "listen 80;" in contenido
    assert "return 301 https://$host$request_uri;" in contenido

    # Servidor HTTPS y protocolos TLS modernos
    assert "listen 443 ssl http2;" in contenido
    assert "ssl_protocols       TLSv1.2 TLSv1.3;" in contenido
    assert "Strict-Transport-Security" in contenido

    # Service Worker location con no-store y ámbito
    assert "location = /panel/sw.js" in contenido
    assert 'add_header Cache-Control "no-store, no-cache, must-revalidate"' in contenido
    assert 'add_header Service-Worker-Allowed "/panel/"' in contenido

    # Manifiesto location con no-store
    assert "location ~ ^/panel/manifest" in contenido

    # API del Panel con no-store
    assert "location /panel/api/" in contenido


# ¤infra-hibrida
def test_plantilla_vapid_sin_secretos_en_repo() -> None:
    """Verifica plantilla vapid.env.example cumpliendo INV_SIN_SECRETOS_EN_REPO."""
    vapid_env = RUTA_PROXY / "vapid.env.example"
    assert vapid_env.is_file(), "vapid.env.example debe existir en infra/proxy/"

    lineas = [
        l.strip()
        for l in vapid_env.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    claves_declaradas = {l.split("=")[0].strip() for l in lineas}
    assert "VAPID_PUBLIC_KEY" in claves_declaradas
    assert "VAPID_PRIVATE_KEY" in claves_declaradas
    assert "VAPID_CLAIMS_SUB" in claves_declaradas

    # Ninguna línea debe contener literales privados mayores a 16 caracteres fuera de ${...}
    for linea in lineas:
        if "=" in linea:
            valor = linea.split("=", 1)[1].strip()
            assert "${" in valor or len(valor) < 16 or valor.startswith("mailto:")


# ¤infra-hibrida
def test_escaner_secretos_pasa_cero_hallazgos() -> None:
    """Comprueba que el escáner de secretos del repositorio certifique 0 hallazgos (INV_SIN_SECRETOS_EN_REPO)."""
    script_secretos = RAIZ / "scripts" / "verificar_secretos.py"
    resultado = subprocess.run([sys.executable, str(script_secretos)], capture_output=True, text=True)
    assert resultado.returncode == 0, f"Escáner de secretos falló: {resultado.stdout}\n{resultado.stderr}"
    assert "sin secretos detectados" in resultado.stdout


# ¤infra-hibrida
def test_estaticos_manifiesto_y_service_worker_instalable() -> None:
    """Verifica archivos estáticos requeridos por PWA (RF-PAN-11 a, b)."""
    # 1. Manifiesto web
    manifest_file = RUTA_ESTATICOS / "manifest.webmanifest"
    assert manifest_file.is_file(), "manifest.webmanifest debe existir en estaticos"
    data = json.loads(manifest_file.read_text(encoding="utf-8"))

    assert data.get("display") == "standalone"
    assert data.get("start_url") == "/panel"
    iconos = data.get("icons", [])
    assert len(iconos) >= 2
    tamanos = [i.get("sizes") for i in iconos]
    assert "192x192" in tamanos
    assert "512x512" in tamanos

    # Iconos físicos existentes
    icon192 = RUTA_ESTATICOS / "icon-192.png"
    icon512 = RUTA_ESTATICOS / "icon-512.png"
    assert icon192.is_file() and icon192.stat().st_size > 0
    assert icon512.is_file() and icon512.stat().st_size > 0

    # 2. Service Worker con skipWaiting y clients.claim
    sw_file = RUTA_ESTATICOS / "sw.js"
    assert sw_file.is_file(), "sw.js debe existir en estaticos"
    sw_code = sw_file.read_text(encoding="utf-8")
    assert "skipWaiting" in sw_code
    assert "clients.claim" in sw_code
    assert "/panel/api" in sw_code
    assert "no-store" in sw_code


# ¤infra-hibrida
def test_escenario_rf_pan_11_instalar_terminal_y_revocar_al_cerrar_sesion() -> None:
    """Escenario @RF-PAN-11: Instalar la terminal móvil y revocar al cerrar sesión.

    Dado un líder con sesión en el navegador del teléfono
    Cuando instala la app
    Entonces se abre a pantalla completa con las pantallas de su rol
    Y al cerrar sesión el dispositivo queda revocado
    """
    capturador = CapturadorPushTest()
    seguridad = DobleSeguridadTerminal()
    canal = DobleCanalTerminal()
    config = dict(cargar_config())
    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        webpush_sender=capturador,
    )

    # Iniciar sesión líder comercial
    servicio.solicitar_codigo("lider@glamping.ec")
    assert len(canal.codigos_emitidos) == 1
    codigo = canal.codigos_emitidos[0]
    sesion_lider, token = servicio.iniciar_sesion("lider@glamping.ec", str(codigo))
    assert sesion_lider.rol == "lider"

    # Suscribir dispositivo móvil (PWA instalada)
    endpoint = "https://fcm.googleapis.com/fcm/send/dispositivo-lider-terminal-11"
    sub_res = servicio.suscribir_dispositivo(
        sesion=sesion_lider,
        endpoint=endpoint,
        clave_p256dh="clave_p256_lider",
        clave_auth="clave_auth_lider",
    )
    assert sub_res["estado"] == "activo"

    # Comprobar dispositivo activo
    dispositivos_antes = servicio.dispositivos_usuario(sesion_lider)
    assert len(dispositivos_antes) == 1
    assert dispositivos_antes[0]["endpoint"] == endpoint

    # Al cerrar sesión el dispositivo queda revocado en la persistencia
    servicio.cerrar_sesion(sesion_lider, cookie_token=token)

    dispositivos_despues = servicio.dispositivos_usuario(sesion_lider)
    assert len(dispositivos_despues) == 0


# ¤infra-hibrida
def test_escenario_rf_pan_12_aviso_venta_por_validar_sin_pii() -> None:
    """Escenario @RF-PAN-12 @INV_AVISO_SIN_PII: Aviso de venta por validar.

    Dado un líder con avisos activos
    Cuando entra una venta por validar
    Entonces el aviso dice solo el tipo y la cantidad
    Y al tocarlo abre esa pantalla tras comprobar la sesión
    """
    capturador = CapturadorPushTest()
    seguridad = DobleSeguridadTerminal()
    canal = DobleCanalTerminal()
    config = dict(cargar_config())
    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        webpush_sender=capturador,
    )

    # Clave pública VAPID accesible con un toque
    vapid_pub = servicio.obtener_vapid_public_key()
    assert isinstance(vapid_pub, str) and len(vapid_pub) > 10

    # Sesión activa de líder
    servicio.solicitar_codigo("lider@glamping.ec")
    assert len(canal.codigos_emitidos) == 1
    codigo = canal.codigos_emitidos[0]
    sesion_lider, _ = servicio.iniciar_sesion("lider@glamping.ec", str(codigo))

    # Suscribir dispositivo para recibir avisos Web Push
    endpoint = "https://fcm.googleapis.com/fcm/send/terminal-lider-aviso"
    servicio.suscribir_dispositivo(
        sesion=sesion_lider,
        endpoint=endpoint,
        clave_p256dh="k_p256_test",
        clave_auth="k_auth_test",
    )

    # Entra una venta por validar
    aviso = AvisoMovil(tipo="ventas por validar", cantidad=1, ruta="/panel#ventas")
    enviados = servicio.enviar_aviso_movil(sesion_lider.usuario_id, aviso)
    assert enviados == 1

    # Carga capturada en el transporte Web Push
    assert len(capturador.envios) == 1
    disp_enviado, payload = capturador.envios[0]
    assert disp_enviado["endpoint"] == endpoint

    # INV_AVISO_SIN_PII: Carga útil estrictamente restringida a {tipo, cantidad, ruta}
    assert set(payload.keys()) == {"tipo", "cantidad", "ruta"}
    assert payload["tipo"] == "ventas por validar"
    assert payload["cantidad"] == 1
    assert payload["ruta"] == "/panel#ventas"

    # Comprobación de ausencia de PII, teléfonos, correos o montos
    for v in payload.values():
        val_str = str(v)
        assert "@" not in val_str
        assert "$" not in val_str
        assert "[[TOKEN:" not in val_str


# ¤infra-hibrida
def test_invariante_inv_aviso_sin_pii_estricto() -> None:
    """Verifica que el servicio rechace avisos con datos personales o montos."""
    servicio = PanelOperativoService(dict(cargar_config()))

    # 1. No admite montos con $
    with pytest.raises(ValueError) as exc1:
        servicio.enviar_aviso_movil(
            "usr_lider_01",
            AvisoMovil(tipo="venta de $300 por validar", cantidad=1, ruta="/panel#ventas"),
        )
    assert "INV_AVISO_SIN_PII" in str(exc1.value)

    # 2. No admite correos con @
    with pytest.raises(ValueError) as exc2:
        servicio.enviar_aviso_movil(
            "usr_lider_01",
            AvisoMovil(tipo="ventas por validar", cantidad=1, ruta="/panel#usuario@glamping.ec"),
        )
    assert "INV_AVISO_SIN_PII" in str(exc2.value)

    # 3. No admite tokens de datos sensibles
    with pytest.raises(ValueError) as exc3:
        servicio.enviar_aviso_movil(
            "usr_lider_01",
            AvisoMovil(tipo="ventas por validar", cantidad=1, ruta="/panel#[[TOKEN:usr_1]]"),
        )
    assert "INV_AVISO_SIN_PII" in str(exc3.value)


# ¤infra-hibrida
def test_tolerancia_fallos_transporte_webpush_no_afecta_negocio() -> None:
    """RF-PAN-12 (d): Un fallo de red en el transporte Web Push no rompe el flujo."""
    capturador_fallo = CapturadorPushTest(debe_fallar=True)
    seguridad = DobleSeguridadTerminal()
    canal = DobleCanalTerminal()
    observabilidad = DobleObservabilidadTerminal()
    servicio = PanelOperativoService(
        dict(cargar_config()),
        seguridad=seguridad,
        canal=canal,
        observabilidad=observabilidad,
        webpush_sender=capturador_fallo,
    )

    servicio.solicitar_codigo("lider@glamping.ec")
    assert len(canal.codigos_emitidos) == 1
    codigo = canal.codigos_emitidos[0]
    sesion_lider, _ = servicio.iniciar_sesion("lider@glamping.ec", str(codigo))

    servicio.suscribir_dispositivo(
        sesion=sesion_lider,
        endpoint="https://fcm.googleapis.com/fcm/send/endpoint-caido",
        clave_p256dh="k1",
        clave_auth="k2",
    )

    aviso = AvisoMovil(tipo="ventas por validar", cantidad=2, ruta="/panel#ventas")
    # No propaga excepción hacia el flujo de negocio
    enviados = servicio.enviar_aviso_movil(sesion_lider.usuario_id, aviso)
    assert enviados == 0

    # Se registró advertencia en observabilidad
    logs_warn = [l for l in observabilidad.logs if l.get("nivel") == "WARNING"]
    assert len(logs_warn) >= 1


# ¤infra-hibrida
def test_integracion_http_pwa_despliegue_completo() -> None:
    """Verifica el flujo HTTP completo de la PWA del panel a través del contenedor pasillo central."""
    app = FastAPI()
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    contenedor.canal.aprobar_plantilla("codigo_acceso_panel")

    usuarios = {
        "lider@glamping.ec": {
            "usuario_id": "usr_lider_01",
            "correo": "lider@glamping.ec",
            "rol": "lider",
            "zonas": ("zona_a", "zona_b"),
            "telefono": "+593993333333",
            "activo": True,
        }
    }
    contenedor.seguridad.obtener_usuario_por_correo = lambda c: usuarios.get(c.strip().lower())

    codigos_emitidos: list[str] = []
    original_enviar = contenedor.canal.enviar_plantilla

    def _capturar(dest: str, p: Any) -> Any:
        if hasattr(p, "variables") and p.variables:
            codigos_emitidos.append(str(p.variables[0]))
        return original_enviar(dest, p)

    contenedor.canal.enviar_plantilla = _capturar

    montar_panel_y_crm(app, contenedor)
    client = TestClient(app)

    # 1. Manifiesto servido con content-type correcto
    resp_man = client.get("/panel/manifest.webmanifest")
    assert resp_man.status_code == 200
    assert "application/manifest+json" in resp_man.headers.get("content-type", "")
    man_data = resp_man.json()
    assert man_data["display"] == "standalone"
    assert man_data["start_url"] == "/panel"

    # 2. Service Worker servido con cabecera de ámbito /panel/
    resp_sw = client.get("/panel/sw.js")
    assert resp_sw.status_code == 200
    assert "application/javascript" in resp_sw.headers.get("content-type", "")
    assert resp_sw.headers.get("Service-Worker-Allowed") == "/panel/"

    # 3. Clave pública VAPID accesible para activación con un toque
    resp_vapid = client.get("/panel/api/dispositivos/vapid-public-key")
    assert resp_vapid.status_code == 200
    assert "public_key" in resp_vapid.json()

    # 4. Solicitud de código y autenticación
    resp_sol = client.post("/panel/api/sesion/codigo", json={"correo": "lider@glamping.ec"})
    assert resp_sol.status_code == 200
    assert len(codigos_emitidos) == 1
    codigo = codigos_emitidos[0]

    resp_auth = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": str(codigo)})
    assert resp_auth.status_code == 200
    csrf = resp_auth.json()["csrf"]

    # 5. Suscripción de terminal móvil
    endpoint = "https://fcm.googleapis.com/fcm/send/dispositivo-http-test"
    resp_sub = client.post(
        "/panel/api/dispositivos/suscribir",
        headers={"x-csrf-token": csrf},
        json={
            "endpoint": endpoint,
            "keys": {"p256dh": "p256_sample", "auth": "auth_sample"},
        },
    )
    assert resp_sub.status_code == 200
    assert resp_sub.json().get("estado") == "activo"

    # 6. Cierre de sesión revoca el dispositivo
    resp_del = client.delete("/panel/api/sesion", headers={"x-csrf-token": csrf})
    assert resp_del.status_code == 200

    dispositivos_post = contenedor.panel._persistencia.obtener_dispositivos_activos_de_usuario("usr_lider_01")
    assert len(dispositivos_post) == 0
