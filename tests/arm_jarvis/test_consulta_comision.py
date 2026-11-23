# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de consulta de comisión propia y aislamiento entre vendedores (RF-ARM-07, INV_COMISION_PROPIA)."""
from __future__ import annotations

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.dobles_internal import DobleSeguridad


# ¤arm-jarvis
class ActorFake:
    def __init__(self, sujeto_id: str = "lider_1", rol: str = "lider") -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤arm-jarvis
def test_consulta_comision_propia_retorna_solo_datos_suyos() -> None:
    """Escenario: Consulta propia (@US-07 @CU-06 @RF-ARM-07 @INV_COMISION_PROPIA).

    Dado ventas propias en el período
    Cuando el vendedor pregunta '¿cuánto llevo?'
    Entonces recibe validada, pendiente y número de ventas, solo suyas
    """
    servicio = ArmJarvisService()
    v1 = servicio.registrar_vendedor(telefono_token="tel_vend_1", nombre="Ana Ruiz")
    v2 = servicio.registrar_vendedor(telefono_token="tel_vend_2", nombre="Carlos Gómez")

    # Registrar venta para v1 (450 USD -> comision 45.00)
    class MsgV1:
        remitente = "tel_vend_1"
        texto = "vendí 3 noches en el depa del centro a María López, 450, llega el 15"
        mensaje_id = "msg_v1"

    # Registrar venta para v2 (1000 USD -> comision 100.00)
    class MsgV2:
        remitente = "tel_vend_2"
        texto = "vendí Domo Lago por 1000 a cliente VIP"
        mensaje_id = "msg_v2"

    servicio.procesar(MsgV1())
    servicio.procesar(MsgV2())

    # Validar la venta de v1
    lider = ActorFake()
    venta_v1 = servicio.listar(vendedor_id=v1.vendedor_id)[0]
    servicio.validar(venta_v1.venta_id, lider)

    # Vendedor 1 consulta sus comisiones
    class ConsultaV1:
        remitente = "tel_vend_1"
        texto = "¿cuánto llevo ganado este mes?"
        mensaje_id = "msg_q1"

    respuesta_v1 = servicio.procesar(ConsultaV1())

    # Debe contener solo sus 45.00 USD validados y 0 pendientes
    assert "Ana Ruiz" in respuesta_v1
    assert "Validadas: 45.00 USD" in respuesta_v1
    assert "Pendientes: 0.00 USD" in respuesta_v1
    assert "Total ventas: 1" in respuesta_v1

    # Asegurar que NO se filtran los 1000 USD ni comisiones de v2 (sin fuga de datos)
    assert "100.00" not in respuesta_v1
    assert "1000.00" not in respuesta_v1
    assert "Carlos" not in respuesta_v1


# ¤arm-jarvis
def test_consulta_ajena_se_rechaza_y_se_audita() -> None:
    """Escenario: Consulta ajena (@US-07 @RF-ARM-07).

    Dado un vendedor que pregunta por otro
    Cuando el ARM responde
    Entonces no revela datos ajenos y el intento queda en el audit log
    """
    seguridad = DobleSeguridad()
    servicio = ArmJarvisService(seguridad=seguridad)

    servicio.registrar_vendedor(telefono_token="tel_curioso", nombre="Vendedor Curioso")
    servicio.registrar_vendedor(telefono_token="tel_otro", nombre="Carlos Gómez")

    class MsgConsultaAjena:
        remitente = "tel_curioso"
        texto = "¿Cuánto es la comisión de Carlos?"
        mensaje_id = "msg_q_ajena"

    respuesta = servicio.procesar(MsgConsultaAjena())

    assert "Solo puedes consultar tu propia comisión." in respuesta

    # Comprobar que el intento quedó registrado en el audit log de seguridad
    assert len(seguridad.auditorias) == 1
    aud = seguridad.auditorias[0]
    assert aud["evento"] == "intento_consulta_comision_ajena"
    assert aud["vendedor_consultado"] == "Carlos"
