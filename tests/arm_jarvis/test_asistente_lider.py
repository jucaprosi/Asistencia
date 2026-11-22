# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del asistente Jarvis para líderes y administradores (RF-ARM-09)."""
from __future__ import annotations

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.tipos import CambioNoPermitido, ConfirmacionRequerida, ErrorArm


# ¤arm-jarvis
class ActorFake:
    def __init__(self, sujeto_id: str, rol: str) -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤arm-jarvis
def test_pregunta_al_asistente_cuanto_vendio_vendedor() -> None:
    """Escenario: Pregunta al asistente (@US-15 @RF-ARM-09 @RF-PAN-06).

    Dado un líder autenticado
    Cuando pregunta '¿cuánto vendió Carlos en septiembre?'
    Entonces recibe datos del alcance de su rol
    """
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_carlos", nombre="Carlos Alvear")

    # Registrar venta de Carlos
    class Msg:
        remitente = "tel_carlos"
        texto = "vendí Domo Lago por 600 usd a cliente Juan el 15 de septiembre"
        mensaje_id = "msg_carlos_1"

    servicio.procesar(Msg())

    lider = ActorFake("lider_01", "lider")
    respuesta = servicio.preguntar_jarvis(lider, "¿cuánto vendió Carlos en septiembre?")

    assert "Carlos Alvear" in respuesta
    assert "600.00 USD" in respuesta
    assert "1 ventas registradas" in respuesta


# ¤arm-jarvis
def test_cambio_configuracion_acotado_requiere_confirmacion() -> None:
    """Escenario: Cambio de configuración acotado (@US-15 @RF-ARM-09).

    Dado un cambio permitido
    Cuando el líder lo pide
    Entonces ve qué cambiará y debe confirmar
    Y el cambio queda en arm.configuracion con autor y hora
    """
    servicio = ArmJarvisService()
    lider = ActorFake("lider_01", "lider")

    # 1. Petición en lenguaje natural informa qué cambiará y solicita confirmación
    pregunta = "por favor activar la notificación al validar"
    respuesta = servicio.preguntar_jarvis(lider, pregunta)
    assert "Esto cambiará 'notificaciones.al_validar' a True" in respuesta
    assert "¿Confirmas este cambio?" in respuesta

    # 2. Aplicar cambio sin confirmar lanza ConfirmacionRequerida
    cambio = {"clave": "notificaciones.al_validar", "valor": True}
    with pytest.raises(ConfirmacionRequerida):
        servicio.aplicar_cambio_configuracion(lider, cambio, confirmado=False)

    # 3. Aplicar con confirmado=True persiste en arm.configuracion
    servicio.aplicar_cambio_configuracion(lider, cambio, confirmado=True)
    val = servicio.repositorio.obtener_configuracion("notificaciones.al_validar")
    assert val is True


# ¤arm-jarvis
def test_cambio_reservado_regla_comision_se_rechaza() -> None:
    """Escenario: Cambio reservado (@US-15 @RF-ARM-09).

    Dado un pedido de cambiar una regla de comisión
    Cuando el líder lo solicita
    Entonces el asistente lo rechaza y remite al administrador
    """
    servicio = ArmJarvisService()
    lider = ActorFake("lider_01", "lider")

    respuesta = servicio.preguntar_jarvis(lider, "quiero cambiar la regla de comisión al 15%")
    assert "Solo el administrador puede modificar las reglas de comisión." in respuesta


# ¤arm-jarvis
def test_usuario_sin_rol_de_lider_es_rechazado() -> None:
    """Un vendedor o huésped no puede consultar al asistente del líder."""
    servicio = ArmJarvisService()
    vendedor = ActorFake("vend_01", "vendedor")

    with pytest.raises(ErrorArm) as exc:
        servicio.preguntar_jarvis(vendedor, "¿cuánto vendió el equipo?")

    assert "No tienes permisos de líder" in str(exc.value)
