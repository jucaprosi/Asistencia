# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del árbitro para recepción y despacho de eventos firmados desde el CRM (RF-CRM-03, RF-CRM-05)."""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from typing import Any
from uuid import uuid4

import pytest

from features.crm_conector.crm_conector_service import CRMConectorService
from features.crm_conector.firma_internal import calcular_firma
from features.crm_conector.tipos import EventoCRM, FirmaEventoInvalida
from tests.crm_conector.dobles import DobleObservabilidadService


@pytest.fixture
def base_datos_memoria() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def obs_doble() -> DobleObservabilidadService:
    return DobleObservabilidadService()


@pytest.fixture
def secreto_eventos() -> str:
    return "secreto_webhook_eventos_crm_99"


@pytest.fixture
def servicio_eventos(
    base_datos_memoria: sqlite3.Connection,
    obs_doble: DobleObservabilidadService,
    secreto_eventos: str,
) -> CRMConectorService:
    config = {
        "proveedor": "fake",
        "eventos_entrantes": {
            "secreto": secreto_eventos,
        },
    }
    return CRMConectorService(
        config=config,
        observabilidad=obs_doble,
        conexion_bd=base_datos_memoria,
    )


# ¤crm-conector
def test_recibir_evento_firma_valida_persiste_y_despacha(
    servicio_eventos: CRMConectorService,
    base_datos_memoria: sqlite3.Connection,
    secreto_eventos: str,
) -> None:
    """RF-CRM-03: Evento firmado con HMAC-SHA256 válido es aceptado, persistido y despachado."""
    eventos_recibidos: list[EventoCRM] = []
    servicio_eventos.registrar_receptor("venta_validada", lambda ev: eventos_recibidos.append(ev))

    payload = {
        "evento_id": f"ev_{uuid4().hex[:8]}",
        "tipo": "venta_validada",
        "referencia": "VTA-7788",
        "actor": "ghl_admin",
        "datos": {"monto": "150.00", "estado": "aprobado"},
    }
    cuerpo = json.dumps(payload).encode("utf-8")
    firma = hmac.new(secreto_eventos.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()

    evento = servicio_eventos.recibir_evento(cuerpo=cuerpo, firma=firma)

    assert evento.tipo == "venta_validada"
    assert evento.referencia == "VTA-7788"
    assert evento.actor == "ghl_admin"
    assert len(eventos_recibidos) == 1
    assert eventos_recibidos[0].referencia == "VTA-7788"

    # Verificar que se persistió en crm.eventos
    cur = base_datos_memoria.execute(
        "SELECT evento_id, tipo, referencia FROM crm.eventos WHERE referencia = ?",
        ("VTA-7788",),
    )
    fila = cur.fetchone()
    assert fila is not None
    assert fila["tipo"] == "venta_validada"


# ¤crm-conector
def test_recibir_evento_con_fecha_iso_en_firma(
    servicio_eventos: CRMConectorService,
    secreto_eventos: str,
) -> None:
    """RF-CRM-03: Firma calculada con cabecera X-Glamping-Date + '.' + cuerpo."""
    fecha_iso = "2026-11-02T15:30:00Z"
    payload = {
        "evento_id": "ev_fecha_1",
        "tipo": "mensaje_gestor",
        "referencia": "conv_99",
        "datos": {"texto": "Huésped atendido por gestor"},
    }
    cuerpo_str = json.dumps(payload, sort_keys=True)
    cuerpo = cuerpo_str.encode("utf-8")
    firma = calcular_firma(secreto_eventos, fecha_iso, cuerpo_str)

    evento = servicio_eventos.recibir_evento(cuerpo=cuerpo, firma=firma, fecha_iso=fecha_iso)
    assert evento.tipo == "mensaje_gestor"
    assert evento.referencia == "conv_99"


# ¤crm-conector
def test_recibir_evento_firma_invalida_rechazo_estricto(
    servicio_eventos: CRMConectorService,
    base_datos_memoria: sqlite3.Connection,
) -> None:
    """RF-CRM-03: Firma alterada o errónea lanza FirmaEventoInvalida y no persiste en BD."""
    payload = {"evento_id": "ev_malicioso", "tipo": "venta_anulada", "referencia": "VTA-FAKE"}
    cuerpo = json.dumps(payload).encode("utf-8")

    with pytest.raises(FirmaEventoInvalida):
        servicio_eventos.recibir_evento(cuerpo=cuerpo, firma="firma_corrupta_invalida")

    # Verificar que nada se guardó en la base de datos
    cur = base_datos_memoria.execute("SELECT COUNT(*) as total FROM crm.eventos")
    assert cur.fetchone()["total"] == 0


# ¤crm-conector
def test_despacho_multiple_y_wildcard(
    servicio_eventos: CRMConectorService,
    secreto_eventos: str,
) -> None:
    """Verifica que el despacho funcione para receptores específicos y para el receptor wildcard '*'."""
    capturas_especificas: list[str] = []
    capturas_wildcard: list[str] = []

    servicio_eventos.registrar_receptor("incidencia_resuelta", lambda ev: capturas_especificas.append(ev.referencia))
    servicio_eventos.registrar_receptor("*", lambda ev: capturas_wildcard.append(ev.tipo))

    payload = {
        "evento_id": "ev_incidencia_1",
        "tipo": "incidencia_resuelta",
        "referencia": "INC-404",
        "datos": {"resolucion": "Ducha reparada"},
    }
    cuerpo = json.dumps(payload).encode("utf-8")
    firma = hmac.new(secreto_eventos.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()

    servicio_eventos.recibir_evento(cuerpo=cuerpo, firma=firma)

    assert capturas_especificas == ["INC-404"]
    assert capturas_wildcard == ["incidencia_resuelta"]
