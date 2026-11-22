# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de RF-GW-08: Orden secuencial y agrupación de mensajes en ráfaga (ventana de 3 s)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import Canal, MensajeEntrante
from tests.canal_whatsapp.dobles import DobleObservabilidadService, DobleSeguridadService


def payload_meta(mensaje_id: str, remitente: str, texto: str, ts: datetime) -> bytes:
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
                                    "timestamp": str(int(ts.timestamp())),
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
def servicio() -> CanalWhatsappService:
    config = dict(cargar_config())
    return CanalWhatsappService(
        config,
        seguridad=DobleSeguridadService(),
        observabilidad=DobleObservabilidadService(),
    )


def test_mensajes_en_ventana_de_tres_segundos_forman_un_solo_turno(
    servicio: CanalWhatsappService,
) -> None:
    """RF-GW-08: 3 mensajes recibidos en menos de 3 s forman un solo turno y generan una sola llamada al receptor."""
    remitente = "593991122334"
    t0 = datetime.now(timezone.utc)

    # 3 mensajes seguidos en intervalos de 0.8 s (total < 3 s)
    mensajes_data = [
        ("m1", "Hola buenas tardes", t0),
        ("m2", "¿Tienen cabañas disponibles para mañana?", t0 + timedelta(milliseconds=800)),
        ("m3", "Somos 2 personas", t0 + timedelta(milliseconds=1600)),
    ]

    for mid, txt, ts in mensajes_data:
        cuerpo = payload_meta(mid, remitente, txt, ts)
        servicio.repositorio.guardar_evento(
            mensaje_id=mid,
            conversacion_clave=remitente,
            cuerpo_cifrado=cuerpo,
            estado="pendiente",
            recibido_en=ts,
        )

    turnos_recibidos: list[MensajeEntrante] = []
    servicio.registrar_receptor(Canal.HUESPEDES, lambda m: turnos_recibidos.append(m))

    procesados = servicio.procesar_ingesta()

    assert procesados == 3
    # El receptor fue llamado UNA SOLA VEZ ("responde una sola vez")
    assert len(turnos_recibidos) == 1

    turno = turnos_recibidos[0]
    # Los mensajes llegaron juntos y en orden
    assert len(turno.mensajes_agrupados) == 3
    assert [m.texto for m in turno.mensajes_agrupados] == [
        "Hola buenas tardes",
        "¿Tienen cabañas disponibles para mañana?",
        "Somos 2 personas",
    ]
    assert "Hola buenas tardes\n¿Tienen cabañas disponibles para mañana?\nSomos 2 personas" in (turno.texto or "")


def test_mensajes_separados_por_mas_de_tres_segundos_forman_turnos_distintos(
    servicio: CanalWhatsappService,
) -> None:
    """RF-GW-08: Mensajes separados por más de 3 segundos se atienden como turnos independientes."""
    remitente = "593997788990"
    t0 = datetime.now(timezone.utc)

    # Dos mensajes con 4 segundos de separación
    cuerpo1 = payload_meta("m_sep_1", remitente, "Primer turno", t0)
    cuerpo2 = payload_meta("m_sep_2", remitente, "Segundo turno", t0 + timedelta(seconds=4))

    servicio.repositorio.guardar_evento(
        mensaje_id="m_sep_1",
        conversacion_clave=remitente,
        cuerpo_cifrado=cuerpo1,
        estado="pendiente",
        recibido_en=t0,
    )
    servicio.repositorio.guardar_evento(
        mensaje_id="m_sep_2",
        conversacion_clave=remitente,
        cuerpo_cifrado=cuerpo2,
        estado="pendiente",
        recibido_en=t0 + timedelta(seconds=4),
    )

    turnos: list[MensajeEntrante] = []
    servicio.registrar_receptor(Canal.HUESPEDES, lambda m: turnos.append(m))

    servicio.procesar_ingesta()

    assert len(turnos) == 2
    assert turnos[0].texto == "Primer turno"
    assert turnos[1].texto == "Segundo turno"
