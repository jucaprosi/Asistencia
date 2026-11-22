# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de redacción de PII, bóveda cifrada y rehidratación (RF-SEC-05, INV_PII_FUERA_DEL_MODELO)."""
from __future__ import annotations

import json
import pytest

from features.seguridad.seguridad_service import (
    SeguridadService,
    Veredicto,
)
from tests.seguridad.dobles import DobleModeloHTTP, DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_captura_cliente_http_del_doble_de_modelo_sin_telefono_ni_pii_en_claro(
    servicio: SeguridadService,
) -> None:
    """Hecho cuando: test_pii.py captura el cliente HTTP de un doble de modelo sin ningún teléfono en claro.
    
    Escenario: Nada de PII hacia el modelo (@RF-SEC-05 @INV_PII_FUERA_DEL_MODELO)
    Dado un mensaje con nombre, teléfono, correo, cédula, tarjeta y dirección
    Cuando se llama al modelo
    Entonces el payload capturado no contiene ninguno de esos valores
    Y la respuesta rehidratada restituye el valor exacto
    """
    remitente = "+593991234567"
    nombre_real = "Carlos Andrade"
    telefono_real = "0991234567"
    correo_real = "carlos.andrade@glamping.ec"
    cedula_real = "1712345678"
    tarjeta_real = "4532 1234 5678 9012"
    direccion_real = "Av. Amazonas N24-15 y Colón"

    mensaje_original = (
        f"Hola, mi nombre es {nombre_real}, mi teléfono es {telefono_real}, "
        f"correo {correo_real}, cédula {cedula_real}, pagaré con tarjeta {tarjeta_real} "
        f"y vivo en {direccion_real}."
    )

    conversacion_id = "conv_test_pii_http_001"

    # 1. El mensaje entra a través de la compuerta de seguridad
    limpio = servicio.filtrar_entrada(
        remitente,
        mensaje_original,
        canal="huespedes",
        conversacion_id=conversacion_id,
    )
    assert not isinstance(limpio, Veredicto)
    texto_para_modelo = limpio.texto_tokenizado

    # 2. Configurar el doble del cliente HTTP del modelo
    respuesta_simulada_con_tokens = (
        "Estimado [NOMBRE_1], hemos recibido tu solicitud. Confirmamos contacto "
        "al [TELEFONO_1] y correo [CORREO_1], documento [DOCUMENTO_1], forma de pago [TARJETA_1] "
        "y dirección registrada en [DIRECCION_1]."
    )
    doble_http = DobleModeloHTTP(respuesta_modelo=respuesta_simulada_con_tokens)

    # 3. Simular la llamada HTTP al modelo LLM con el payload
    payload_http = {
        "model": "claude-3-7-sonnet-20250219",
        "messages": [
            {"role": "user", "content": texto_para_modelo}
        ],
        "temperature": 0.2,
    }
    respuesta_bruta = doble_http.post_messages(payload_http)

    # 4. Verificación coercitiva de INV_PII_FUERA_DEL_MODELO sobre el payload HTTP capturado
    assert len(doble_http.payloads_capturados) == 1
    payload_capturado_str = json.dumps(doble_http.payloads_capturados[0], ensure_ascii=False)

    # Criterio estricto: Ningún teléfono ni PII en claro en el payload HTTP
    assert telefono_real not in payload_capturado_str, f"Fuga de teléfono detectada: {telefono_real}"
    assert correo_real not in payload_capturado_str, f"Fuga de correo detectada: {correo_real}"
    assert cedula_real not in payload_capturado_str, f"Fuga de cédula detectada: {cedula_real}"
    assert tarjeta_real not in payload_capturado_str, f"Fuga de tarjeta detectada: {tarjeta_real}"
    assert nombre_real not in payload_capturado_str, f"Fuga de nombre detectada: {nombre_real}"
    assert direccion_real not in payload_capturado_str, f"Fuga de dirección detectada: {direccion_real}"

    # Tokens presentes en su lugar
    assert "[TELEFONO_1]" in payload_capturado_str
    assert "[CORREO_1]" in payload_capturado_str
    assert "[DOCUMENTO_1]" in payload_capturado_str
    assert "[TARJETA_1]" in payload_capturado_str
    assert "[NOMBRE_1]" in payload_capturado_str
    assert "[DIRECCION_1]" in payload_capturado_str

    # 5. La salida del modelo atraviesa filtrar_salida para rehidratación
    salida_rehidratada = servicio.filtrar_salida(respuesta_bruta, conversacion_id)

    # Restitución exacta de todos los valores originales sin pérdida
    assert nombre_real in salida_rehidratada
    assert telefono_real in salida_rehidratada
    assert correo_real in salida_rehidratada
    assert cedula_real in salida_rehidratada
    assert tarjeta_real in salida_rehidratada
    assert direccion_real in salida_rehidratada

    # Y ningún token de marcador queda sin resolver
    assert "[TELEFONO_1]" not in salida_rehidratada
    assert "[NOMBRE_1]" not in salida_rehidratada


def test_boveda_almacena_valores_cifrados_en_base_de_datos(servicio: SeguridadService) -> None:
    """Verifica que en seguridad.boveda_tokens los valores son binarios cifrados."""
    conv_id = "conv_cifrado_check"
    telefono_secreto = "0987654321"
    servicio.tokenizar(f"Mi celular es {telefono_secreto}", conv_id)

    cursor = servicio.conexion.execute(
        "SELECT token, tipo, valor_cifrado FROM seguridad.boveda_tokens WHERE tipo = 'telefono'"
    )
    filas = cursor.fetchall()
    assert len(filas) >= 1
    for f in filas:
        valor_blob = f["valor_cifrado"]
        assert isinstance(valor_blob, bytes)
        # El blob binario NO contiene el teléfono en texto plano
        assert telefono_secreto.encode("utf-8") not in valor_blob


def test_purificacion_de_marcas_en_filtrar_salida(servicio: SeguridadService) -> None:
    """filtrar_salida remueve huellas internas de gobernanza como \u00a4 o \u00a6."""
    conv_id = "conv_purificar_01"
    marca_huella = chr(0x00A6)
    marca_rastro = chr(0x00A4)
    texto_con_marcas = f"Gracias por su reserva {marca_rastro}seguridad-canal y feliz estadía {marca_huella}huella_abierta"
    resultado = servicio.filtrar_salida(texto_con_marcas, conv_id)
    assert chr(0x00A4) not in resultado
    assert chr(0x00A6) not in resultado
    assert chr(0x00AC) not in resultado
    assert "Gracias por su reserva" in resultado
