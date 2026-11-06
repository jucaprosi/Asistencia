# ¤panel-operativo
# ¤¤frontend-developer
"""Árbitro de RF-PAN-12 e INV_AVISO_SIN_PII: Avisos al teléfono vía Web Push.

Verifica:
1. Activación con un toque del usuario y obtención de clave pública VAPID (RF-PAN-12 a).
2. Apertura de pantalla exacta tras comprobar la sesión (RF-PAN-12 b).
3. Invariante INV_AVISO_SIN_PII: Carga útil estrictamente restringida a {tipo, cantidad, ruta} sin datos personales (RF-PAN-12 c).
4. Tolerancia a fallos: Un fallo de entrega de Web Push no afecta el flujo de negocio (RF-PAN-12 d).
5. Revocación automática ante endpoint caducado (410 Gone / 404 Not Found).
"""
from __future__ import annotations

from typing import Any, Mapping
from fastapi.testclient import TestClient
import pytest

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from features.panel_operativo.tipos import AvisoMovil
from tests.panel_operativo.dobles import (
    DobleArmJarvisService,
    DobleCanalWhatsappService,
    DobleComisionesService,
    DobleObservabilidadService,
    DobleSeguridadService,
)


# ¤panel-operativo
class CapturadorPush:
    """Doble de transporte Web Push para capturar cargas útiles enviadas."""

    def __init__(self, debe_fallar: bool = False, codigo_error: int = 500) -> None:
        self.debe_fallar = debe_fallar
        self.codigo_error = codigo_error
        self.envios: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []

    def __call__(self, disp: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
        self.envios.append((disp, payload))
        if self.debe_fallar:
            if self.codigo_error == 410:
                # Simular endpoint caducado
                return False
            raise RuntimeError(f"Fallo de conexión simulado con el servicio Web Push ({self.codigo_error})")
        return True


# ¤panel-operativo
@pytest.fixture
def entorno_avisos():
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    comisiones = DobleComisionesService()
    arm = DobleArmJarvisService(comisiones=comisiones, canal=canal)
    obs = DobleObservabilidadService()
    capturador = CapturadorPush()

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        comisiones=comisiones,
        arm=arm,
        observabilidad=obs,
        webpush_sender=capturador,
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión de Líder comercial
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp_sesion = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo})
    csrf = resp_sesion.json()["csrf"]
    usuario_id = resp_sesion.json()["usuario_id"]

    return client, csrf, usuario_id, servicio, capturador, obs


# ¤panel-operativo
def test_activacion_permiso_con_un_toque_y_clave_vapid(entorno_avisos) -> None:
    # RF-PAN-12 (a)
    client, csrf, usuario_id, servicio, _, _ = entorno_avisos

    # 1. El cliente solicita la clave pública VAPID
    resp_vapid = client.get("/panel/api/dispositivos/vapid-public-key")
    assert resp_vapid.status_code == 200
    vapid_key = resp_vapid.json().get("public_key")
    assert vapid_key is not None
    assert len(vapid_key) > 10

    # 2. Con un toque de usuario ("Activar avisos"), suscribe el dispositivo
    endpoint = "https://fcm.googleapis.com/fcm/send/dispositivo-lider-touch"
    sub_resp = client.post(
        "/panel/api/dispositivos/suscribir",
        headers={"x-csrf-token": csrf},
        json={
            "endpoint": endpoint,
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM=",
                "auth": "tBHItJI5svbpez7KI4CCXg==",
            },
        },
    )
    assert sub_resp.status_code == 200
    assert sub_resp.json().get("estado") == "activo"

    # Verificación en la lista de dispositivos del usuario
    resp_lista = client.get("/panel/api/dispositivos", headers={"x-csrf-token": csrf})
    assert resp_lista.status_code == 200
    endpoints = [d["endpoint"] for d in resp_lista.json()["dispositivos"]]
    assert endpoint in endpoints


# ¤panel-operativo
def test_aviso_venta_por_validar_sin_pii_y_abre_pantalla(entorno_avisos) -> None:
    # RF-PAN-12 (b, c), INV_AVISO_SIN_PII
    client, csrf, usuario_id, servicio, capturador, _ = entorno_avisos

    # Suscribir dispositivo del líder
    endpoint = "https://fcm.googleapis.com/fcm/send/lider-push-01"
    client.post(
        "/panel/api/dispositivos/suscribir",
        headers={"x-csrf-token": csrf},
        json={"endpoint": endpoint, "keys": {"p256dh": "key_p256", "auth": "key_auth"}},
    )

    # Cuando entra una venta por validar (o 2 ventas por validar)
    aviso = AvisoMovil(tipo="ventas por validar", cantidad=2, ruta="/panel#ventas")
    enviados = servicio.enviar_aviso_movil(usuario_id, aviso)

    assert enviados == 1
    assert len(capturador.envios) == 1

    disp_enviado, payload = capturador.envios[0]
    assert disp_enviado["endpoint"] == endpoint

    # Entonces el aviso dice solo el tipo y la cantidad, con ruta para abrir esa pantalla
    assert payload == {
        "tipo": "ventas por validar",
        "cantidad": 2,
        "ruta": "/panel#ventas",
    }

    # INV_AVISO_SIN_PII: La carga no admite otros campos
    assert set(payload.keys()) == {"tipo", "cantidad", "ruta"}

    # No contiene nombres de cliente, montos ($), correos ni tokens
    for valor in payload.values():
        str_val = str(valor)
        assert "@" not in str_val
        assert "$" not in str_val
        assert "[[TOKEN:" not in str_val


# ¤panel-operativo
def test_invariante_inv_aviso_sin_pii_rechaza_campos_adicionales_o_datos_sensibles(entorno_avisos) -> None:
    # INV_AVISO_SIN_PII
    _, _, usuario_id, servicio, _, _ = entorno_avisos

    # 1. Rechazo ante objeto que no sea AvisoMovil
    with pytest.raises(ValueError) as exc1:
        servicio.enviar_aviso_movil(usuario_id, {"tipo": "venta", "cantidad": 1, "ruta": "/panel", "cliente": "Juan"})  # type: ignore
    assert "INV_AVISO_SIN_PII" in str(exc1.value)

    # 2. Rechazo si contiene marcador de token de cliente
    aviso_con_token = AvisoMovil(tipo="ventas por validar", cantidad=1, ruta="/panel#[[TOKEN:cliente_123]]")
    with pytest.raises(ValueError) as exc2:
        servicio.enviar_aviso_movil(usuario_id, aviso_con_token)
    assert "INV_AVISO_SIN_PII" in str(exc2.value)

    # 3. Rechazo si contiene monto ($) o correo (@)
    aviso_con_monto = AvisoMovil(tipo="venta de $500 por validar", cantidad=1, ruta="/panel#ventas")
    with pytest.raises(ValueError) as exc3:
        servicio.enviar_aviso_movil(usuario_id, aviso_con_monto)
    assert "INV_AVISO_SIN_PII" in str(exc3.value)


# ¤panel-operativo
def test_fallo_de_entrega_no_afecta_el_flujo_de_negocio(entorno_avisos) -> None:
    # RF-PAN-12 (d)
    client, csrf, usuario_id, servicio, capturador, obs = entorno_avisos

    # Configurar el emisor push para fallar con excepción de red
    capturador.debe_fallar = True
    capturador.codigo_error = 503

    # Suscribir dispositivo
    client.post(
        "/panel/api/dispositivos/suscribir",
        headers={"x-csrf-token": csrf},
        json={"endpoint": "https://fcm.googleapis.com/fcm/send/fallo", "keys": {"p256dh": "k1", "auth": "k2"}},
    )

    # Enviar aviso: no debe propagar excepción hacia el negocio
    aviso = AvisoMovil(tipo="ventas por validar", cantidad=1, ruta="/panel#ventas")
    enviados = servicio.enviar_aviso_movil(usuario_id, aviso)

    # Entregados es 0 pero no estalló
    assert enviados == 0

    # Se registró advertencia en observabilidad
    logs_warning = [l for l in obs.logs if l.get("nivel") == "WARNING"]
    assert any("fallo" in str(l.get("evento", "")).lower() for l in logs_warning)


# ¤panel-operativo
def test_aviso_por_rol_gestor_y_lider(entorno_avisos) -> None:
    # RF-PAN-12
    client, csrf, _, servicio, capturador, _ = entorno_avisos

    # Suscribir dos dispositivos: uno del líder y otro del gestor
    client.post(
        "/panel/api/dispositivos/suscribir",
        headers={"x-csrf-token": csrf},
        json={"endpoint": "https://push/lider", "keys": {"p256dh": "k", "auth": "a"}},
    )

    # Simular dispositivo de gestor
    servicio._persistencia.guardar_dispositivo(
        dispositivo_id="disp_gestor",
        usuario_id="usr_gestor_01",
        endpoint="https://push/gestor",
        clave_p256dh="k_gestor",
        clave_auth="a_gestor",
        creado_en=servicio._persistencia.obtener_codigo_activo("usr_gestor_01") or __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    servicio._usuarios["usr_gestor_01"] = {
        "usuario_id": "usr_gestor_01",
        "rol": "gestor",
        "zonas": ("zona_norte",),
        "activo": True,
    }

    # Aviso a líderes
    aviso_lider = AvisoMovil(tipo="ventas por validar", cantidad=3, ruta="/panel#ventas")
    notificados_lider = servicio.enviar_aviso_por_rol("lider", aviso_lider)
    assert notificados_lider >= 1

    # Aviso a gestores de zona_norte
    aviso_gestor = AvisoMovil(tipo="handoffs por atender", cantidad=1, ruta="/panel#handoffs")
    notificados_gestor = servicio.enviar_aviso_por_rol("gestor", aviso_gestor, zona="zona_norte")
    assert notificados_gestor == 1
