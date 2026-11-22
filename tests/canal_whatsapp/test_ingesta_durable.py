# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de RF-GW-07: Ingesta durable, recuperación ante caídas del trabajador y alerta de muerte."""
from __future__ import annotations

import json
import time
from uuid import uuid4

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import Canal, MensajeEntrante
from tests.canal_whatsapp.dobles import DobleObservabilidadService, DobleSeguridadService


def payload_meta(mensaje_id: str, remitente: str, texto: str) -> bytes:
    datos = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_1",
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": mensaje_id,
                                    "from": remitente,
                                    "timestamp": str(int(time.time())),
                                    "type": "text",
                                    "text": {"body": texto},
                                }
                            ]
                        }
                    }
                ],
            }
        ],
    }
    return json.dumps(datos).encode("utf-8")


@pytest.fixture
def obs_doble() -> DobleObservabilidadService:
    return DobleObservabilidadService()


@pytest.fixture
def servicio(obs_doble: DobleObservabilidadService) -> CanalWhatsappService:
    config = dict(cargar_config())
    config["verify_token"] = "token_v"
    config["secreto_app"] = "secreto_s"
    return CanalWhatsappService(
        config,
        seguridad=DobleSeguridadService(),
        observabilidad=obs_doble,
    )


def test_evento_queda_persistido_como_pendiente_y_se_procesa_fuera_del_webhook(
    servicio: CanalWhatsappService,
) -> None:
    """RF-GW-07: Todo evento se guarda en canal.eventos_entrantes y un trabajador lo procesa."""
    msg_id = f"wamid.{uuid4().hex}"
    remitente = "593991234567"
    cuerpo = payload_meta(msg_id, remitente, "Mensaje para trabajador")

    servicio.repositorio.guardar_evento(
        mensaje_id=msg_id,
        conversacion_clave=remitente,
        cuerpo_cifrado=cuerpo,
        estado="pendiente",
    )

    evento = servicio.repositorio.obtener_evento(msg_id)
    assert evento is not None
    assert evento.estado == "pendiente"

    mensajes_recibidos: list[MensajeEntrante] = []
    servicio.registrar_receptor(Canal.HUESPEDES, lambda m: mensajes_recibidos.append(m))

    procesados = servicio.procesar_ingesta()
    assert procesados == 1
    assert len(mensajes_recibidos) == 1
    assert mensajes_recibidos[0].mensaje_id == msg_id

    evento_actualizado = servicio.repositorio.obtener_evento(msg_id)
    assert evento_actualizado is not None
    assert evento_actualizado.estado == "procesado"
    assert evento_actualizado.procesado_en is not None


def test_caida_del_trabajador_reintenta_hasta_cinco_veces_y_pasa_a_muerto(
    servicio: CanalWhatsappService, obs_doble: DobleObservabilidadService,
) -> None:
    """RF-GW-07: Evento en 'procesando' cuyo trabajador murió se reintenta hasta 5 veces y luego muere con alerta."""
    msg_id = f"wamid.{uuid4().hex}"
    remitente = "593991234567"
    cuerpo = payload_meta(msg_id, remitente, "Mensaje caído")

    servicio.repositorio.guardar_evento(
        mensaje_id=msg_id,
        conversacion_clave=remitente,
        cuerpo_cifrado=cuerpo,
        estado="procesando",
        intentos=0,
    )

    # Reintentos 1 a 4: vuelve a pendiente
    for i in range(1, 5):
        recuperados = servicio.recuperar_caidas()
        assert recuperados == 1
        ev = servicio.repositorio.obtener_evento(msg_id)
        assert ev is not None
        assert ev.estado == "pendiente"
        assert ev.intentos == i
        # Simulamos que otro trabajador lo tomó y volvió a morir
        servicio.repositorio.actualizar_estado_evento(ev.evento_id, "procesando")

    # Reintento 5: agota intentos -> pasa a muerto y dispara alerta
    recuperados_final = servicio.recuperar_caidas()
    assert recuperados_final == 0

    ev_muerto = servicio.repositorio.obtener_evento(msg_id)
    assert ev_muerto is not None
    assert ev_muerto.estado == "muerto"
    assert ev_muerto.intentos == 5

    alertas = obs_doble.alertas_activas()
    assert len(alertas) >= 1
    assert alertas[0].nombre == "EVENTO_MUERTO"
    assert alertas[0].severidad == "critica"
