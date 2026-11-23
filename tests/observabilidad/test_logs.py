# ¤observabilidad
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-OBS-01: Logs estructurados en JSON por línea, ausencia de PII y rechazo de teléfonos en claro."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from features.observabilidad.logs_internal import PATRON_EMAIL, PATRON_TELEFONO, LoggerObservabilidad
from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.observabilidad.tipos import LogConPII


# ¤observabilidad
def test_logs_sin_datos_personales() -> None:
    """Escenario: Logs sin datos personales (@RF-OBS-01).

    Dado un mensaje con teléfono y correo
    Cuando se registra
    Entonces la línea JSON no contiene esos valores
    """
    config = dict(cargar_config())
    logger = LoggerObservabilidad(config)

    telefono_real = "0991234567"
    correo_real = "huesped_vip@ejemplo.com"
    texto_con_pii = f"El contacto es {telefono_real} y correo {correo_real}"

    # Registro con redacción activa (sanitizado antes de persistir la línea)
    linea_json = logger.registrar(
        nivel="INFO",
        evento="mensaje_recibido",
        redactar=True,
        texto=texto_con_pii,
        conversacion_id="conv_100",
    )

    datos = json.loads(linea_json)
    assert telefono_real not in linea_json
    assert correo_real not in linea_json
    assert "[REDACTADO_TEL]" in datos["texto"]
    assert "[REDACTADO_EMAIL]" in datos["texto"]


# ¤observabilidad
def test_log_con_telefono_en_claro_es_rechazado() -> None:
    """Criterio de aceptación T-103: 'un log con un teléfono en claro es rechazado'."""
    config = dict(cargar_config())
    servicio = ObservabilidadService(config)

    # Intento de registrar un teléfono en claro sin redacción previa
    with pytest.raises(LogConPII) as exc_info:
        servicio.log(
            "INFO",
            "intento_login",
            telefono="+593991234567",
            conversacion_id="conv_200",
        )

    assert "log_con_pii" in str(exc_info.value) or "PII" in str(exc_info.value)


# ¤observabilidad
def test_log_con_correo_en_claro_es_rechazado() -> None:
    """Valida que un correo electrónico en claro también es rechazado bajo INV_PII_FUERA_DEL_MODELO."""
    config = dict(cargar_config())
    servicio = ObservabilidadService(config)

    with pytest.raises(LogConPII):
        servicio.log(
            "WARNING",
            "notificacion_cliente",
            email="contacto_directo@glamping.com",
        )


# ¤observabilidad
def test_ningun_log_en_buffer_contiene_patrones_de_telefono_o_correo() -> None:
    """Criterio RF-OBS-01 (a): un test valida que ningún log contiene patrones de teléfono o correo."""
    config = dict(cargar_config())
    logger = LoggerObservabilidad(config)

    # Registrar varios eventos válidos con tokens o datos seguros
    logger.registrar("INFO", "webhook_recibido", conversacion_id="c1", sala="canal_whatsapp", duracion_ms=12)
    logger.registrar("INFO", "token_asociado", conversacion_id="c1", token="[[TOKEN_TEL_1]]", sala="seguridad")
    logger.registrar("INFO", "mensaje_procesado", conversacion_id="c1", sala="agente", duracion_ms=450)

    lineas = logger.lineas()
    assert len(lineas) == 3

    for linea in lineas:
        # Validación con expresiones regulares canónicas
        assert not PATRON_TELEFONO.search(linea), f"Fuga de teléfono detectada en log: {linea}"
        assert not PATRON_EMAIL.search(linea), f"Fuga de correo detectada en log: {linea}"


# ¤observabilidad
def test_campos_estructurados_del_log() -> None:
    """Criterio RF-OBS-01: JSON por línea con conversacion_id, propiedad_id, rol, sala, evento, duracion_ms."""
    config = dict(cargar_config())
    logger = LoggerObservabilidad(config)

    linea_json = logger.registrar(
        nivel="INFO",
        evento="herramienta_ejecutada",
        conversacion_id="conv_abc",
        propiedad_id="glamping_imbabura",
        rol="huesped_potencial",
        sala="herramientas_glamping",
        duracion_ms=85,
        herramienta="consultar_disponibilidad",
    )

    datos = json.loads(linea_json)
    assert datos["nivel"] == "INFO"
    assert datos["evento"] == "herramienta_ejecutada"
    assert datos["conversacion_id"] == "conv_abc"
    assert datos["propiedad_id"] == "glamping_imbabura"
    assert datos["rol"] == "huesped_potencial"
    assert datos["sala"] == "herramientas_glamping"
    assert datos["duracion_ms"] == 85
    assert datos["herramienta"] == "consultar_disponibilidad"
    assert "timestamp" in datos


# ¤observabilidad
def test_destino_archivo_escribe_en_volumen_separado() -> None:
    """Criterio RF-OBS-01 (b): los logs van a volúmenes configurados."""
    with tempfile.TemporaryDirectory() as temp_dir:
        ruta_archivo = Path(temp_dir) / "glamping_test.log"
        config = {
            "logs": {
                "nivel": "INFO",
                "destino": "archivo",
                "ruta": str(ruta_archivo),
                "redaccion_verificada": True,
            }
        }
        logger = LoggerObservabilidad(config)
        logger.registrar("INFO", "evento_archivo", conversacion_id="c_file")

        assert ruta_archivo.is_file()
        contenido = ruta_archivo.read_text(encoding="utf-8")
        assert "evento_archivo" in contenido
        assert "c_file" in contenido
