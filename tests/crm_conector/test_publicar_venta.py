# ¤crm-conector
# ¤¤integration-engineer
"""Pruebas del árbitro para publicación de venta firmada e idempotente (RF-CRM-03, INV_VENTA_FIRMADA_IDEMPOTENTE)."""
from __future__ import annotations

import json
import sqlite3
from typing import Any
from uuid import uuid4

import pytest

from features.crm_conector.crm_conector_service import CRMConectorService
from features.crm_conector.firma_internal import verificar_firma
from features.crm_conector.http_internal import AdaptadorHttpCRM
from features.crm_conector.tipos import PublicacionVenta
from tests.crm_conector.dobles import DobleObservabilidadService


# ¤crm-conector
class ReceptorSimuladoCRM:
    """Receptor HTTP simulado que valida la firma HMAC-SHA256 y registra llamadas."""

    def __init__(self, secreto: str = "secreto_glamping_test_123") -> None:
        self.secreto = secreto
        self.llamadas: list[dict[str, Any]] = []
        self.rechazar_con_codigo: int | None = None
        self.mensaje_rechazo: str = ""

    def transporte(
        self,
        metodo: str,
        url: str,
        cabeceras: dict[str, str],
        cuerpo: bytes,
    ) -> tuple[int, str]:
        self.llamadas.append({
            "metodo": metodo,
            "url": url,
            "cabeceras": dict(cabeceras),
            "cuerpo": cuerpo,
        })

        if self.rechazar_con_codigo:
            return self.rechazar_con_codigo, self.mensaje_rechazo

        # Validar cabeceras requeridas por el contrato
        fecha = cabeceras.get("X-Glamping-Date")
        firma = cabeceras.get("X-Glamping-Signature")

        if not fecha or not firma:
            return 400, json.dumps({"error": "Cabeceras de firma requeridas ausentes"}, ensure_ascii=False)

        cuerpo_str = cuerpo.decode("utf-8")
        if not verificar_firma(self.secreto, fecha, cuerpo_str, firma):
            return 401, json.dumps({"error": "Firma HMAC-SHA256 inválida"}, ensure_ascii=False)

        payload = json.loads(cuerpo_str)
        return 200, json.dumps({
            "status": "recibido",
            "venta_id": payload.get("venta_id"),
            "evento": payload.get("evento"),
        }, ensure_ascii=False)


@pytest.fixture
def base_datos_memoria() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def receptor_crm() -> ReceptorSimuladoCRM:
    return ReceptorSimuladoCRM(secreto="secreto_glamping_test_123")


@pytest.fixture
def servicio_crm(base_datos_memoria: sqlite3.Connection, receptor_crm: ReceptorSimuladoCRM) -> CRMConectorService:
    adaptador = AdaptadorHttpCRM(
        url="https://api.crm.glamping.internal/webhook/inbound",
        secreto_hmac=receptor_crm.secreto,
        cabecera_firma="X-Glamping-Signature",
        transporte=receptor_crm.transporte,
    )
    config = {
        "proveedor": "fake",
        "webhook_ventas": {
            "url": "https://api.crm.glamping.internal/webhook/inbound",
            "secreto_hmac": receptor_crm.secreto,
            "cabecera_firma": "X-Glamping-Signature",
        },
        "cola": {
            "backoff_s": [1, 2, 4],
            "max_horas": 24,
        },
    }
    return CRMConectorService(
        config=config,
        observabilidad=DobleObservabilidadService(),
        conexion_bd=base_datos_memoria,
        adaptador_http=adaptador,
    )


# ¤crm-conector
def test_publicar_venta_exitosa_firmada_hmac(servicio_crm: CRMConectorService, receptor_crm: ReceptorSimuladoCRM) -> None:
    """RF-CRM-03: Envía publicacion_venta firmada con HMAC-SHA256 y registra respuesta en crm.publicaciones."""
    venta_id = f"vta_{uuid4().hex[:8]}"
    venta_datos = {
        "venta_id": venta_id,
        "ticket": "TCK-1001",
        "vendedor": "Carlos Vendedor",
        "cliente": "María Huésped",
        "telefono_cliente": "+593991234567",
        "monto": "150.00",
        "moneda": "USD",
        "producto": "Domo Estándar 2 noches",
        "fecha_venta": "2026-11-02T10:00:00Z",
        "comision": "15.00",
    }

    resultado = servicio_crm.publicar_venta(venta_datos)

    assert resultado.venta_id == venta_id
    assert resultado.estado == "ok"
    assert resultado.intentos == 1
    assert "200 OK" in (resultado.ultima_respuesta or "")

    # Verificar que el receptor recibió la llamada HTTP POST con firma HMAC válida
    assert len(receptor_crm.llamadas) == 1
    llamada = receptor_crm.llamadas[0]
    assert llamada["metodo"] == "POST"
    assert llamada["url"] == "https://api.crm.glamping.internal/webhook/inbound"
    assert "X-Glamping-Date" in llamada["cabeceras"]
    assert "X-Glamping-Signature" in llamada["cabeceras"]

    cuerpo_recibido = json.loads(llamada["cuerpo"].decode("utf-8"))
    assert cuerpo_recibido["venta_id"] == venta_id
    assert cuerpo_recibido["evento"] == "venta_validada"
    assert cuerpo_recibido["ticket"] == "TCK-1001"
    assert cuerpo_recibido["monto"] == "150.00"
    assert cuerpo_recibido["comision"] == "15.00"


# ¤crm-conector
def test_publicar_venta_idempotencia_no_duplica(servicio_crm: CRMConectorService, receptor_crm: ReceptorSimuladoCRM) -> None:
    """RF-CRM-03 Criterio (b), INV_VENTA_FIRMADA_IDEMPOTENTE: Repetir venta no crea segundo envío."""
    venta_id = f"vta_idemp_{uuid4().hex[:8]}"
    venta_datos = {
        "venta_id": venta_id,
        "ticket": "TCK-1002",
        "vendedor": "Juan Vendedor",
        "cliente": "Ana Cliente",
        "telefono_cliente": "+593997654321",
        "monto": "200.00",
        "moneda": "USD",
        "producto": "Tienda Safari",
        "fecha_venta": "2026-11-02T11:00:00Z",
        "comision": "20.00",
    }

    # Primera llamada: se envía
    resultado1 = servicio_crm.publicar_venta(venta_datos)
    assert resultado1.estado == "ok"
    assert len(receptor_crm.llamadas) == 1

    # Segunda llamada: no realiza segunda petición HTTP (idempotencia pura)
    resultado2 = servicio_crm.publicar_venta(venta_datos)
    assert resultado2.estado == "ok"
    assert resultado2.venta_id == venta_id
    assert len(receptor_crm.llamadas) == 1  # No hubo segunda llamada al CRM


# ¤crm-conector
def test_publicar_anulacion_firmada_e_idempotente(servicio_crm: CRMConectorService, receptor_crm: ReceptorSimuladoCRM) -> None:
    """RF-CRM-03: publicar_anulacion publica evento venta_anulada con firma e idempotencia."""
    venta_id = f"vta_anul_{uuid4().hex[:8]}"
    venta_datos = {
        "venta_id": venta_id,
        "ticket": "TCK-1003",
        "vendedor": "Pedro Vendedor",
        "cliente": "Luis Cliente",
        "monto": "120.00",
        "moneda": "USD",
        "producto": "Cabaña Bosque",
        "fecha_venta": "2026-11-02T12:00:00Z",
        "comision": "12.00",
    }

    # Publicar anulación
    resultado_anulacion = servicio_crm.publicar_anulacion(venta_datos)
    assert resultado_anulacion.venta_id == venta_id
    assert resultado_anulacion.estado == "ok"
    assert len(receptor_crm.llamadas) == 1

    llamada = receptor_crm.llamadas[0]
    payload = json.loads(llamada["cuerpo"].decode("utf-8"))
    assert payload["evento"] == "venta_anulada"
    assert payload["venta_id"] == venta_id

    # Segunda llamada idempotente para venta_anulada
    resultado_anulacion_2 = servicio_crm.publicar_anulacion(venta_datos)
    assert resultado_anulacion_2.estado == "ok"
    assert len(receptor_crm.llamadas) == 1


# ¤crm-conector
def test_firma_invalida_rechazada_por_receptor(receptor_crm: ReceptorSimuladoCRM) -> None:
    """Verifica que un mensaje con secreto o firma alterada sea rechazado de forma tajante."""
    fecha = "2026-11-02T12:00:00Z"
    cuerpo = json.dumps({"venta_id": "vta_bad", "evento": "venta_validada"}).encode("utf-8")
    cabeceras = {
        "Content-Type": "application/json",
        "X-Glamping-Date": fecha,
        "X-Glamping-Signature": "firma_falsa_invalida",
    }

    codigo, resp = receptor_crm.transporte("POST", "https://url.test", cabeceras, cuerpo)
    assert codigo == 401
    assert "Firma HMAC-SHA256 inválida" in resp
