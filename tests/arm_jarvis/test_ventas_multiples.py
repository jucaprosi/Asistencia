# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de ventas múltiples, detección de duplicados y reentrega idempotente (RF-ARM-02, RF-ARM-10)."""
from __future__ import annotations

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.tipos import EstadoVenta


# ¤arm-jarvis
class MensajeFake:
    def __init__(self, remitente: str, texto: str, mensaje_id: str = "msg_m_1") -> None:
        self.remitente = remitente
        self.texto = texto
        self.mensaje_id = mensaje_id


# ¤arm-jarvis
def test_varias_ventas_en_un_mensaje_crean_dos_tickets() -> None:
    """Escenario: Varias ventas en un mensaje (@US-05 @RF-ARM-10).

    Dado un mensaje con dos ventas distintas
    Cuando el ARM lo procesa
    Entonces crea dos ventas con dos tickets y responde con ambos
    """
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_mult", nombre="Vendedor Multiple")

    texto = "1) Domo Lago 2 noches a Juan Perez por 300 USD llega el 15. 2) Domo Montaña 1 noche a Ana Gomez por 150 USD llega el 18."
    msg = MensajeFake(remitente="tel_mult", texto=texto, mensaje_id="msg_dos_ventas")

    respuesta = servicio.procesar(msg)

    # Debe contener dos resúmenes con tickets
    assert respuesta.count("Ticket: V-") == 2
    assert "Domo Lago" in respuesta
    assert "Domo Montaña" in respuesta
    assert "300.00 USD" in respuesta
    assert "150.00 USD" in respuesta

    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 2
    tickets = {vt.ticket for vt in ventas}
    assert len(tickets) == 2


# ¤arm-jarvis
def test_posible_duplicado_se_senala_al_lider() -> None:
    """Escenario: Posible duplicado (@US-05 @RF-ARM-10).

    Dado una venta con igual cliente, producto, monto y fecha_venta en los últimos 7 días
    Cuando se registra otra igual, del mismo o de otro vendedor
    Entonces se crea marcada como posible duplicado
    Y el líder la ve señalada antes de validar
    """
    servicio = ArmJarvisService()
    v1 = servicio.registrar_vendedor(telefono_token="tel_d1", nombre="Vendedor 1")
    v2 = servicio.registrar_vendedor(telefono_token="tel_d2", nombre="Vendedor 2")

    # Primera venta
    msg1 = MensajeFake(
        remitente="tel_d1",
        texto="vendí Domo Lago 300 a Juan Perez",
        mensaje_id="msg_dup_1",
    )
    servicio.procesar(msg1)

    # Segunda venta con mismos datos por otro vendedor
    msg2 = MensajeFake(
        remitente="tel_d2",
        texto="vendí Domo Lago 300 a Juan Perez",
        mensaje_id="msg_dup_2",
    )
    resp2 = servicio.procesar(msg2)

    assert "Posible duplicado detectado" in resp2

    ventas_v2 = servicio.listar(vendedor_id=v2.vendedor_id)
    assert len(ventas_v2) == 1
    assert ventas_v2[0].posible_duplicado is True
    assert ventas_v2[0].posible_duplicado_de is not None


# ¤arm-jarvis
def test_reentrega_no_duplica_la_venta() -> None:
    """Escenario: La reentrega no duplica la venta (@US-05 @RF-ARM-10).

    Dado un mensaje ya procesado
    Cuando el trabajador lo reintenta
    Entonces la restricción de mensaje e índice impide un segundo ticket
    """
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_reintento", nombre="Vendedor Reintento")

    msg = MensajeFake(
        remitente="tel_reintento",
        texto="vendí Suite Balcón 202 por 200 a Lucia",
        mensaje_id="msg_unico_123",
    )

    # Primer intento
    resp1 = servicio.procesar(msg)
    assert "Ticket: V-" in resp1

    # Reintento con el mismo mensaje_id
    resp2 = servicio.procesar(msg)
    assert "Venta ya registrada previamente" in resp2

    # Solo existe una venta registrada
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 1


# ¤arm-jarvis
def test_falta_campo_obligatorio_pregunta_exacta() -> None:
    """Escenario: Falta un campo obligatorio (@US-05 @RF-ARM-02).

    Dado un mensaje de venta sin monto
    Cuando el ARM lo procesa
    Entonces pregunta solo por el monto y no registra hasta tenerlo
    """
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_incompleto", nombre="Vendedor Incompleto")

    msg = MensajeFake(
        remitente="tel_incompleto",
        texto="Cerré venta de Domo Lago para Pedro Gómez 2 noches pero no especificaron precio",
        mensaje_id="msg_sin_monto",
    )
    respuesta = servicio.procesar(msg)

    assert "¿Cuál fue el monto de la venta?" in respuesta

    # No se registra ninguna venta
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 0


# ¤arm-jarvis
def test_mensaje_que_no_es_venta_no_crea_registro() -> None:
    """Escenario: No es una venta (@US-05 @RF-ARM-02).

    Dado un saludo o una pregunta
    Cuando el ARM lo procesa
    Entonces no crea ninguna venta
    """
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_saludo", nombre="Vendedor Saludo")

    msg = MensajeFake(
        remitente="tel_saludo",
        texto="Hola equipo, buenos días a todos",
        mensaje_id="msg_saludo",
    )
    respuesta = servicio.procesar(msg)

    assert "Ticket: V-" not in respuesta
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 0
