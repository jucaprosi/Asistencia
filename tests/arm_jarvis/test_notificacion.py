# ¤arm-jarvis
# ¤¤backend-developer
"""Pruebas de notificaciones privadas al vendedor al validar o rechazar (RF-ARM-06)."""
from __future__ import annotations

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.dobles_internal import DobleCanalWhatsApp
from features.arm_jarvis.notificador_internal import NotificadorVendedor
from features.arm_jarvis.tipos import Vendedor


# ¤arm-jarvis
class ActorFake:
    def __init__(self, sujeto_id: str = "lider_1", rol: str = "lider") -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤arm-jarvis
def test_notificacion_privada_al_validar_venta() -> None:
    """La notificación al validar se envía al vendedor en privado, nunca al grupo."""
    canal = DobleCanalWhatsApp()
    servicio = ArmJarvisService(canal=canal)
    v = servicio.registrar_vendedor(telefono_token="tel_notif_1", nombre="Vendedor Privado")

    class Msg:
        remitente = "tel_notif_1"
        texto = "vendí Domo Lago 300 a cliente Juan"
        mensaje_id = "msg_notif_1"

    servicio.procesar(Msg())
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 1

    lider = ActorFake()
    servicio.validar(ventas[0].venta_id, lider)

    # Debe haberse enviado exactamente un mensaje privado al teléfono del vendedor
    assert len(canal.mensajes_enviados) == 1
    envio = canal.mensajes_enviados[0]
    assert envio["destinatario"] == "tel_notif_1"
    assert "validada" in envio["texto"].lower()
    assert "Comisión:" in envio["texto"]


# ¤arm-jarvis
def test_notificacion_privada_al_rechazar_venta() -> None:
    """La notificación al rechazar incluye el motivo del rechazo en privado."""
    canal = DobleCanalWhatsApp()
    servicio = ArmJarvisService(canal=canal)
    v = servicio.registrar_vendedor(telefono_token="tel_notif_2", nombre="Vendedor Rechazado")

    class Msg:
        remitente = "tel_notif_2"
        texto = "vendí Suite 200 a cliente Pedro"
        mensaje_id = "msg_notif_2"

    servicio.procesar(Msg())
    ventas = servicio.listar(vendedor_id=v.vendedor_id)

    lider = ActorFake()
    servicio.rechazar(ventas[0].venta_id, lider, motivo="Cliente canceló antes del cobro")

    assert len(canal.mensajes_enviados) == 1
    envio = canal.mensajes_enviados[0]
    assert envio["destinatario"] == "tel_notif_2"
    assert "no pudo ser validada" in envio["texto"]
    assert "Cliente canceló antes del cobro" in envio["texto"]


# ¤arm-jarvis
def test_notificacion_fuera_de_ventana_usa_plantilla() -> None:
    """Si está fuera de la ventana de 24h, utiliza la plantilla oficial."""
    canal = DobleCanalWhatsApp()
    notificador = NotificadorVendedor(canal)
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_v_ventana", nombre="Vendedor Ventana")

    class Msg:
        remitente = "tel_v_ventana"
        texto = "vendí Tienda Safari 400"
        mensaje_id = "msg_v_1"

    servicio.procesar(Msg())
    venta = servicio.listar(vendedor_id=v.vendedor_id)[0]

    notificador.notificar_validacion(venta, v, fuera_de_ventana_24h=True)

    assert len(canal.plantillas_enviadas) == 1
    plantilla = canal.plantillas_enviadas[0]
    assert plantilla["destinatario"] == "tel_v_ventana"
    assert plantilla["plantilla"] == "comision_validada"


# ¤arm-jarvis
def test_fallo_de_envio_se_registra_para_reintento() -> None:
    """Un error en el canal WhatsApp se registra en notificaciones fallidas."""
    canal = DobleCanalWhatsApp(simular_fallo=True)
    servicio = ArmJarvisService(canal=canal)
    v = servicio.registrar_vendedor(telefono_token="tel_fallo", nombre="Vendedor Fallo")

    class Msg:
        remitente = "tel_fallo"
        texto = "vendí Domo Montaña 200 a Carlos"
        mensaje_id = "msg_fallo_1"

    servicio.procesar(Msg())
    venta = servicio.listar(vendedor_id=v.vendedor_id)[0]

    lider = ActorFake()
    # La validación no debe abortar si falla la notificación, sino registrar el fallo
    servicio.validar(venta.venta_id, lider)

    assert len(servicio._notificador.notificaciones_fallidas) == 1
    fallida = servicio._notificador.notificaciones_fallidas[0]
    assert fallida["venta_id"] == venta.venta_id
    assert "Error al enviar mensaje WhatsApp" in fallida["error"]
