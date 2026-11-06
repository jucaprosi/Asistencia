# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Árbitro de RF-AG-08, US-03 e INV_ENVIO_UNICO (Planificador idempotente de check-in)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from features.agente.agente_service import AgenteService, cargar_config
from features.canal_whatsapp.tipos import Plantilla, ResultadoEnvio


# ¤agente-enrutador
@dataclass
class ReservaDoble:
    codigo: str
    huesped_telefono: str
    huesped_nombre: str
    propiedad_id: str


# ¤agente-enrutador
class DoblePMS:
    def __init__(self, reservas: list[ReservaDoble]) -> None:
        self.reservas = reservas

    def reservas_con_llegada(self, fecha: date) -> tuple[ReservaDoble, ...]:
        return tuple(self.reservas)


# ¤agente-enrutador
class DobleCanalWhatsApp:
    def __init__(self) -> None:
        self.plantillas_enviadas: list[dict[str, Any]] = []

    def enviar_plantilla(self, destinatario: str, plantilla: Plantilla) -> ResultadoEnvio:
        self.plantillas_enviadas.append({
            "destinatario": destinatario,
            "plantilla": plantilla,
        })
        return ResultadoEnvio(mensaje_id=f"msg-{len(self.plantillas_enviadas)}", estado="sent")


# ¤agente-enrutador
def test_planificador_envia_checkins_del_dia_con_plantilla() -> None:
    config = cargar_config()
    canal = DobleCanalWhatsApp()
    pms = DoblePMS([
        ReservaDoble(
            codigo="RES-GLAMP-101",
            huesped_telefono="+593991111111",
            huesped_nombre="Ana Perez",
            propiedad_id="glamping",
        ),
        ReservaDoble(
            codigo="RES-DEP-202",
            huesped_telefono="+593992222222",
            huesped_nombre="Luis Gómez",
            propiedad_id="departamento_centro",
        ),
    ])

    servicio = AgenteService(config=config, canal=canal, pms=pms)
    hoy = date(2026, 12, 1)

    enviados = servicio.enviar_checkins_del_dia(hoy)
    assert enviados == 2
    assert len(canal.plantillas_enviadas) == 2

    p1 = canal.plantillas_enviadas[0]
    assert p1["destinatario"] == "+593991111111"
    assert p1["plantilla"].nombre == "instrucciones_checkin"
    assert "Ana Perez" in p1["plantilla"].variables
    assert "glamping" in p1["plantilla"].variables

    p2 = canal.plantillas_enviadas[1]
    assert p2["destinatario"] == "+593992222222"
    assert p2["plantilla"].nombre == "instrucciones_checkin"
    assert "Luis Gómez" in p2["plantilla"].variables
    assert "departamento_centro" in p2["plantilla"].variables


# ¤agente-enrutador
def test_inv_envio_unico_reinicio_del_planificador_no_duplica() -> None:
    """Escenario: El planificador se reinicia (@US-03 @RF-AG-08 @INV_ENVIO_UNICO).

    Dado instrucciones de check-in ya enviadas hoy para una reserva
    Cuando el planificador corre otra vez
    Entonces no se envían de nuevo
    """
    config = cargar_config()
    canal = DobleCanalWhatsApp()
    pms = DoblePMS([
        ReservaDoble(
            codigo="RES-GLAMP-999",
            huesped_telefono="+593993333333",
            huesped_nombre="Carlos Alvear",
            propiedad_id="glamping",
        ),
    ])

    servicio = AgenteService(config=config, canal=canal, pms=pms)
    hoy = date(2026, 12, 1)

    # Primer disparo del planificador
    enviados_primera_vez = servicio.enviar_checkins_del_dia(hoy)
    assert enviados_primera_vez == 1
    assert len(canal.plantillas_enviadas) == 1

    # Segundo disparo simulando reintento o reinicio del planificador
    enviados_segunda_vez = servicio.enviar_checkins_del_dia(hoy)
    assert enviados_segunda_vez == 0
    # No se disparó un nuevo mensaje por canal
    assert len(canal.plantillas_enviadas) == 1
