# ¤arm-jarvis
# ¤¤backend-developer
"""Pruebas de ingesta y validación de remitentes en el canal de vendedores (RF-ARM-01)."""
from __future__ import annotations

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.dobles_internal import DobleSeguridad


# ¤arm-jarvis
class MensajeVendedorFake:
    def __init__(self, remitente: str, texto: str, mensaje_id: str = "msg_1") -> None:
        self.remitente = remitente
        self.texto = texto
        self.mensaje_id = mensaje_id
        self.conversacion_id = f"conv_{remitente}"


# ¤arm-jarvis
def test_remitente_vendedor_activo_se_procesa_exitosamente() -> None:
    """Escenario: Vendedor registrado escribe en el canal y se genera el ticket."""
    servicio = ArmJarvisService()
    servicio.registrar_vendedor(telefono_token="tel_vendedor_01", nombre="Carlos Alvear", activo=True)

    msg = MensajeVendedorFake(
        remitente="tel_vendedor_01",
        texto="Vendí 2 noches en Domo Lago por 240 USD a Juan Perez llega el 15",
    )
    respuesta = servicio.procesar(msg)

    assert "Venta registrada." in respuesta
    assert "Ticket: V-" in respuesta
    assert "Domo Lago" in respuesta
    assert "240.00 USD" in respuesta


# ¤arm-jarvis
def test_remitente_no_registrado_se_registra_por_hash_y_se_descarta() -> None:
    """Escenario: Remitente no registrado en el canal de vendedores (@RF-ARM-01).

    Dado un número sin rol de vendedor
    Cuando escribe en el canal de vendedores
    Entonces el mensaje se registra por hash y se descarta sin respuesta
    """
    seguridad = DobleSeguridad()
    servicio = ArmJarvisService(seguridad=seguridad)

    msg = MensajeVendedorFake(
        remitente="tel_desconocido_999",
        texto="Hola, vendí Domo Lago por 300 a Pedro",
    )
    respuesta = servicio.procesar(msg)

    # Se descarta sin respuesta
    assert respuesta == ""

    # Se registra en auditoría por hash
    assert len(seguridad.auditorias) == 1
    evento = seguridad.auditorias[0]
    assert evento["evento"] == "remitente_no_vendedor_descartado"
    assert "hash_remitente" in evento


# ¤arm-jarvis
def test_vendedor_inactivo_se_descarta_sin_procesar() -> None:
    """Un vendedor registrado pero inactivo no puede registrar ventas."""
    servicio = ArmJarvisService()
    servicio.registrar_vendedor(telefono_token="tel_inactivo_02", nombre="Inactivo", activo=False)

    msg = MensajeVendedorFake(
        remitente="tel_inactivo_02",
        texto="Vendí Suite Colonial por 100",
    )
    respuesta = servicio.procesar(msg)
    assert respuesta == ""
