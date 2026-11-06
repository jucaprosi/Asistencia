# ¤seguridad-canal
# ¤¤security-engineer
"""Árbitro de RF-SEC-08 e INV_SECRETO_OPERATIVO: Bóveda de secretos y entrega condicionada."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from features.seguridad.seguridad_service import (
    ReservaNoAutorizada,
    SeguridadService,
)


# ¤seguridad-canal
@pytest.fixture
def servicio_seguridad() -> SeguridadService:
    return SeguridadService()


# ¤seguridad-canal
def test_secretos_almacenados_cifrados_en_boveda(servicio_seguridad: SeguridadService) -> None:
    svc = servicio_seguridad
    marcador_wifi = svc.guardar_secreto_operativo(
        "wifi_domo_1", "clave_wifi", "GlampingSecret2026!", titular_hash="h_san_pablo"
    )
    assert marcador_wifi == "[[SECRETO:wifi_domo_1]]"

    # Verificar que en la base de datos esté cifrado y no en texto plano
    cursor = svc.conexion.execute(
        "SELECT valor_cifrado FROM seguridad.boveda_tokens WHERE token = ?",
        (marcador_wifi,),
    )
    fila = cursor.fetchone()
    assert fila is not None
    assert b"GlampingSecret2026!" not in bytes(fila["valor_cifrado"])

    # Descifrado fiel
    descifrado = svc.obtener_secreto_operativo("wifi_domo_1")
    assert descifrado == "GlampingSecret2026!"


# ¤seguridad-canal
def test_los_secretos_operativos_no_pasan_por_el_modelo(servicio_seguridad: SeguridadService) -> None:
    """Escenario: Los secretos operativos no pasan por el modelo.

    Dado instrucciones con clave de wifi y código de acceso
    Cuando la herramienta responde al agente
    Entonces el modelo recibe solo marcadores [[SECRETO:...]]
    Y el historial persistido conserva los marcadores
    Y el valor real aparece solo en el mensaje saliente al titular
    """
    svc = servicio_seguridad

    # 1. Guardar secretos en la bóveda
    svc.guardar_secreto_operativo("wifi_imbabura", "clave_wifi", "W1f1_S3cur3!")
    svc.guardar_secreto_operativo("cerradura_principal", "codigo_acceso", "9876#")

    # 2. La herramienta genera la respuesta con marcadores
    respuesta_herramienta = (
        "Bienvenido. La red WiFi es 'Glamping_VIP' y la clave es [[SECRETO:wifi_imbabura]]. "
        "El código de la puerta es [[SECRETO:cerradura_principal]]."
    )

    # El modelo y el historial conservan los marcadores intactos
    texto_para_modelo = svc.tokenizar(respuesta_herramienta, "conv_123")
    assert "[[SECRETO:wifi_imbabura]]" in texto_para_modelo
    assert "[[SECRETO:cerradura_principal]]" in texto_para_modelo
    assert "W1f1_S3cur3!" not in texto_para_modelo
    assert "9876#" not in texto_para_modelo

    # 3. Solo en el mensaje saliente (filtrar_salida) se resuelven los secretos
    mensaje_saliente = svc.filtrar_salida(texto_para_modelo, "conv_123")
    assert "W1f1_S3cur3!" in mensaje_saliente
    assert "9876#" in mensaje_saliente
    assert "[[SECRETO:" not in mensaje_saliente


# ¤seguridad-canal
def test_codigo_reserva_ajeno_devuelve_reserva_no_autorizada_y_audita(
    servicio_seguridad: SeguridadService,
) -> None:
    """Escenario: Un código de reserva ajeno no abre las instrucciones.

    Dado un remitente que no es titular de la reserva R
    Cuando pide las instrucciones con el código de R
    Entonces recibe ReservaNoAutorizada sin datos de la propiedad
    Y el intento queda en el audit log
    Y tras 5 intentos fallidos en 24 horas se escala a humano
    """
    svc = servicio_seguridad
    remitente_ajeno = "tok_intruso_001"
    codigo_reserva = "RES-GLAMP-888"

    # Intento 1: falla y registra en audit_log
    with pytest.raises(ReservaNoAutorizada) as exc_info:
        svc.validar_acceso_reserva(
            codigo_reserva=codigo_reserva,
            remitente_token=remitente_ajeno,
            es_titular=False,
            reserva_confirmada=True,
        )
    assert exc_info.value.codigo_reserva == codigo_reserva
    assert exc_info.value.escalar is False

    # Verificar que el intento quedó registrado en seguridad.audit_log
    cursor = svc.conexion.execute(
        "SELECT * FROM seguridad.audit_log WHERE actor_token = ? AND resultado = 'denegado_titular_no_coincide'",
        (remitente_ajeno,),
    )
    filas_audit = cursor.fetchall()
    assert len(filas_audit) == 1
    assert filas_audit[0]["accion"] == "obtener_instrucciones_checkin"


# ¤seguridad-canal
def test_cinco_intentos_fallidos_en_24_horas_escalan_a_humano(
    servicio_seguridad: SeguridadService,
) -> None:
    svc = servicio_seguridad
    remitente_atacante = "tok_atacante_bruta"

    # Intentos 1 a 4
    for i in range(1, 5):
        with pytest.raises(ReservaNoAutorizada) as exc_info:
            svc.validar_acceso_reserva(
                codigo_reserva=f"RES-{i}",
                remitente_token=remitente_atacante,
                es_titular=False,
            )
        assert exc_info.value.escalar is False

    # Intento 5: debe detonar escalamiento a humano
    with pytest.raises(ReservaNoAutorizada) as exc_info5:
        svc.validar_acceso_reserva(
            codigo_reserva="RES-5",
            remitente_token=remitente_atacante,
            es_titular=False,
        )
    assert exc_info5.value.escalar is True
    assert "escalado a humano" in str(exc_info5.value)


# ¤seguridad-canal
def test_entrega_condicionada_a_reserva_confirmada_y_24h_de_llegada(
    servicio_seguridad: SeguridadService,
) -> None:
    svc = servicio_seguridad
    ahora = datetime.now(timezone.utc)
    remitente_valido = "tok_titular_valido"
    codigo_reserva = "RES-OK-101"

    # 1. Reserva no confirmada (ej. preliminar o cancelada)
    veredicto_preliminar = svc.validar_acceso_reserva(
        codigo_reserva=codigo_reserva,
        remitente_token=remitente_valido,
        es_titular=True,
        reserva_confirmada=False,
    )
    assert veredicto_preliminar.permitido is False
    assert "confirmada" in veredicto_preliminar.motivo

    # 2. Reserva confirmada pero llegada en 3 días (> 24h antes)
    fecha_futura = ahora + timedelta(days=3)
    veredicto_anticipado = svc.validar_acceso_reserva(
        codigo_reserva=codigo_reserva,
        remitente_token=remitente_valido,
        es_titular=True,
        fecha_llegada=fecha_futura,
        reserva_confirmada=True,
        instante=ahora,
    )
    assert veredicto_anticipado.permitido is False
    assert "24 horas antes de la llegada" in veredicto_anticipado.motivo

    # 3. Reserva confirmada y llegada en 12 horas (dentro de las 24h de llegada)
    fecha_proxima = ahora + timedelta(hours=12)
    veredicto_permitido = svc.validar_acceso_reserva(
        codigo_reserva=codigo_reserva,
        remitente_token=remitente_valido,
        es_titular=True,
        fecha_llegada=fecha_proxima,
        reserva_confirmada=True,
        instante=ahora,
    )
    assert veredicto_permitido.permitido is True
