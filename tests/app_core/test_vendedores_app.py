# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del pasillo central: canal de vendedores y receptores ARM (RF-GW-06, RF-ARM-06).

Verifica:
- RF-GW-06: Separación de canales de vendedores y huéspedes.
- US-06, RF-ARM-03, RF-ARM-06: Rechazar venta en estado 'por_validar' pasa a 'rechazada',
  comisión fijada en 0.00, vendedor recibe el motivo en privado y fuera de la ventana
  de 24 horas se usa la plantilla oficial 'venta_rechazada'.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import pytest

from app_core.contenedor import Contenedor, construir
from features.arm_jarvis.tipos import EstadoVenta
from features.canal_whatsapp.canal_whatsapp_service import Canal
from features.canal_whatsapp.tipos import MensajeEntrante, TipoContenido

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "META_ACCESS_TOKEN": "token_prueba",
    "META_VERIFY_TOKEN": "verify_prueba",
    "META_APP_SECRET": "secret_prueba",
    "ANTHROPIC_API_KEY": "sk_prueba",
    "PII_VAULT_KEY": "pii_prueba",
    "PANEL_SESSION_SECRET": "session_prueba",
    "CANAL_VENDEDORES_MODO": "uno_a_uno",
    "CANAL_VENDEDORES_GRUPO_ID": "",
}


# ¤pasillo-central
class _ActorLiderPrueba:
    """Actor que representa al líder para autorizar transiciones en ARM."""

    def __init__(self, sujeto_id: str = "lider_central_1", rol: str = "lider") -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤pasillo-central
def test_canales_separados_rf_gw_06_modo_uno_a_uno() -> None:
    """RF-GW-06: Los mensajes de vendedores nunca llegan al agente y los de huéspedes nunca llegan al ARM."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    assert isinstance(contenedor, Contenedor)

    # Vendedor registrado en el canal y en ARM
    tel_vendedor = "593991112233"
    tel_huesped = "593988887777"
    contenedor.canal.registrar_vendedor(tel_vendedor)
    contenedor.arm.registrar_vendedor(telefono_token=tel_vendedor, nombre="Carlos Vendedor")

    mensajes_arm: list[Any] = []
    mensajes_agente: list[Any] = []

    # Envolver los receptores para registrar qué mensajes les llegan
    fn_arm_original = contenedor.arm.procesar
    fn_agente_original = contenedor.agente.atender

    def _arm_espia(msg: Any) -> Any:
        mensajes_arm.append(msg)
        return fn_arm_original(msg)

    def _agente_espia(msg: Any) -> Any:
        mensajes_agente.append(msg)
        return fn_agente_original(msg)

    # Reemplazar en los receptores registrados en el canal
    contenedor.canal._receptores[Canal.VENDEDORES] = _arm_espia
    contenedor.canal._receptores[Canal.HUESPEDES] = _agente_espia

    # 1. Mensaje del canal de vendedores
    canal_v = contenedor.canal.clasificar_canal(tel_vendedor)
    assert canal_v == Canal.VENDEDORES

    msg_vend = MensajeEntrante(
        mensaje_id="m_vend_1",
        remitente=tel_vendedor,
        canal=canal_v,
        tipo=TipoContenido.TEXTO,
        texto="vendí Domo Lago 300 a cliente Juan Perez",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    contenedor.canal.despachar(msg_vend)

    # 2. Mensaje del canal de huéspedes
    canal_h = contenedor.canal.clasificar_canal(tel_huesped)
    assert canal_h == Canal.HUESPEDES

    msg_huesp = MensajeEntrante(
        mensaje_id="m_huesp_1",
        remitente=tel_huesped,
        canal=canal_h,
        tipo=TipoContenido.TEXTO,
        texto="Hola, ¿tienen disponibilidad para este fin de semana?",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    contenedor.canal.despachar(msg_huesp)

    # Criterio RF-GW-06:
    # (a) Ningún mensaje de vendedores llega al agente de huéspedes
    assert len(mensajes_agente) == 1
    assert mensajes_agente[0].mensaje_id == "m_huesp_1"
    assert all(getattr(m, "canal", None) == Canal.HUESPEDES for m in mensajes_agente)

    # (b) Ningún mensaje de huésped llega al ARM
    assert len(mensajes_arm) == 1
    assert mensajes_arm[0].mensaje_id == "m_vend_1"
    assert all(getattr(m, "canal", None) == Canal.VENDEDORES for m in mensajes_arm)


# ¤pasillo-central
def test_canales_separados_rf_gw_06_modo_grupo() -> None:
    """RF-GW-06: En modo grupo, mensajes del grupo_id van a ARM y los individuales van al agente."""
    grupo_id = "12036304@g.us"
    entorno = dict(ENTORNO_PRUEBA)
    entorno["CANAL_VENDEDORES_MODO"] = "grupo"
    entorno["CANAL_VENDEDORES_GRUPO_ID"] = grupo_id

    contenedor = construir(entorno=entorno)
    assert contenedor.config_app["canal_vendedores"]["modo"] == "grupo"
    contenedor.arm.registrar_vendedor(telefono_token="593991112233", nombre="Mario Vendedor")

    mensajes_arm: list[Any] = []
    mensajes_agente: list[Any] = []

    fn_arm_original = contenedor.arm.procesar
    fn_agente_original = contenedor.agente.atender

    def _arm_espia(msg: Any) -> Any:
        mensajes_arm.append(msg)
        return fn_arm_original(msg)

    def _agente_espia(msg: Any) -> Any:
        mensajes_agente.append(msg)
        return fn_agente_original(msg)

    contenedor.canal._receptores[Canal.VENDEDORES] = _arm_espia
    contenedor.canal._receptores[Canal.HUESPEDES] = _agente_espia

    # Mensaje en el grupo de vendedores
    canal_g = contenedor.canal.clasificar_canal("593991112233", grupo_id=grupo_id)
    assert canal_g == Canal.VENDEDORES

    msg_grupo = MensajeEntrante(
        mensaje_id="m_g1",
        remitente="593991112233",
        canal=canal_g,
        tipo=TipoContenido.TEXTO,
        texto="vendí Suite 200 a cliente Mario",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    contenedor.canal.despachar(msg_grupo)

    # Mensaje directo de huésped
    canal_d = contenedor.canal.clasificar_canal("593988887777", grupo_id=None)
    assert canal_d == Canal.HUESPEDES

    msg_directo = MensajeEntrante(
        mensaje_id="m_d1",
        remitente="593988887777",
        canal=canal_d,
        tipo=TipoContenido.TEXTO,
        texto="¿Tienen hidromasaje?",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    contenedor.canal.despachar(msg_directo)

    # Verificación
    assert len(mensajes_agente) == 1
    assert mensajes_agente[0].mensaje_id == "m_d1"
    assert len(mensajes_arm) == 1
    assert mensajes_arm[0].mensaje_id == "m_g1"


# ¤pasillo-central
def test_rechazar_venta_us_06_rf_arm_03_rf_arm_06() -> None:
    """US-06, RF-ARM-03, RF-ARM-06: Venta por_validar rechazada pasa a 'rechazada', comision 0.00 y vendedor recibe motivo."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    vendedor = contenedor.arm.registrar_vendedor(
        telefono_token="593991112233",
        nombre="Carlos Alvear",
    )

    # 1. Ingresar venta que queda en estado 'por_validar'
    class MensajeVenta:
        remitente = "593991112233"
        texto = "vendí Domo Lago 350 a cliente Juan Perez"
        mensaje_id = "msg_venta_01"

    contenedor.arm.procesar(MensajeVenta())

    ventas = contenedor.arm.listar(vendedor_id=vendedor.vendedor_id, estado=EstadoVenta.POR_VALIDAR)
    assert len(ventas) == 1
    venta = ventas[0]
    assert venta.estado == EstadoVenta.POR_VALIDAR
    assert venta.comision_estimada is not None

    # 2. El líder rechaza la venta con motivo
    lider = _ActorLiderPrueba()
    motivo_rechazo = "Depósito no acreditado en cuenta bancaria"
    venta_rechazada = contenedor.arm.rechazar(venta.venta_id, lider, motivo=motivo_rechazo)

    # 3. Verificaciones de estado y comisión
    assert venta_rechazada.estado == EstadoVenta.RECHAZADA
    assert venta_rechazada.comision_fijada == Decimal("0.00")

    # 4. El vendedor recibe el motivo en privado, nunca al grupo
    mensajes_privados = [
        m for m in contenedor.arm._canal.mensajes_enviados
        if m["destinatario"] == "593991112233"
    ]
    assert len(mensajes_privados) >= 1
    ultimo = mensajes_privados[-1]
    assert motivo_rechazo in ultimo["texto"]
    assert venta.ticket in ultimo["texto"]

    # 5. Criterio (b): Sin fallos no gestionados
    assert len(contenedor.arm._notificador.notificaciones_fallidas) == 0


# ¤pasillo-central
def test_rechazo_fuera_de_ventana_usa_plantilla_venta_rechazada() -> None:
    """RF-ARM-06, RF-GW-03: Fuera de la ventana de 24 horas se despacha con la plantilla oficial 'venta_rechazada'."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    vendedor = contenedor.arm.registrar_vendedor(
        telefono_token="593994445566",
        nombre="Diana Vendedora",
    )

    class MensajeVenta:
        remitente = "593994445566"
        texto = "vendí Tienda Safari 420 a cliente Pedro"
        mensaje_id = "msg_venta_02"

    contenedor.arm.procesar(MensajeVenta())
    ventas = contenedor.arm.listar(vendedor_id=vendedor.vendedor_id, estado=EstadoVenta.POR_VALIDAR)
    assert len(ventas) == 1
    venta = ventas[0]

    # Simular notificación fuera de ventana de 24 horas
    motivo_rechazo = "Fecha solicitada no disponible en PMS"
    contenedor.arm._notificador.notificar_rechazo(
        venta,
        vendedor,
        motivo=motivo_rechazo,
        fuera_de_ventana_24h=True,
    )

    # Debe haberse despachado con la plantilla 'venta_rechazada'
    plantillas = contenedor.arm._canal.plantillas_enviadas
    assert len(plantillas) >= 1
    p_rechazo = next(p for p in plantillas if p["plantilla"] == "venta_rechazada")
    assert p_rechazo["destinatario"] == "593994445566"
    assert venta.ticket in p_rechazo["parametros"]
    assert motivo_rechazo in p_rechazo["parametros"]


# ¤pasillo-central
def test_enlace_compuertas_arm_comisiones_anfitriones() -> None:
    """Verifica que las compuertas de arm_jarvis, comisiones y anfitriones queden enlazadas en el contenedor."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)

    assert contenedor.arm is not None
    assert contenedor.comisiones is not None
    assert contenedor.anfitriones is not None
    assert contenedor.canal is not None
    assert "canal_vendedores" in contenedor.config_app
    assert contenedor.config_app["canal_vendedores"]["modo"] == "uno_a_uno"
