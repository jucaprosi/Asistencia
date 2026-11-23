# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del árbitro para la cola de reintentos, backoff y ventana de 24h (RF-CRM-04, INV_VENTA_NO_SE_PIERDE)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from features.crm_conector.crm_conector_service import CRMConectorService
from features.crm_conector.http_internal import AdaptadorHttpCRM
from features.crm_conector.tipos import (
    ContactoDuplicado,
    CRMNoDisponible,
    LimiteDeTasa,
    WebhookRechazado,
)
from tests.crm_conector.dobles import DobleObservabilidadService


# ¤crm-conector
class TransporteControlable:
    """Transporte HTTP con fallos inyectables para verificar la cola y backoff."""

    def __init__(self) -> None:
        self.devolver_codigo: int = 200
        self.devolver_cuerpo: str = '{"status":"ok"}'
        self.conteo_llamadas: int = 0

    def transporte(
        self,
        metodo: str,
        url: str,
        cabeceras: dict[str, str],
        cuerpo: bytes,
    ) -> tuple[int, str]:
        self.conteo_llamadas += 1
        return self.devolver_codigo, self.devolver_cuerpo


@pytest.fixture
def base_datos_memoria() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def obs_doble() -> DobleObservabilidadService:
    return DobleObservabilidadService()


@pytest.fixture
def transporte_ctrl() -> TransporteControlable:
    return TransporteControlable()


@pytest.fixture
def servicio_con_cola(
    base_datos_memoria: sqlite3.Connection,
    obs_doble: DobleObservabilidadService,
    transporte_ctrl: TransporteControlable,
) -> CRMConectorService:
    adaptador = AdaptadorHttpCRM(
        url="https://api.crm.glamping.internal/webhook",
        secreto_hmac="test_secreto_cola",
        transporte=transporte_ctrl.transporte,
    )
    config = {
        "proveedor": "fake",
        "webhook_ventas": {
            "url": "https://api.crm.glamping.internal/webhook",
            "secreto_hmac": "test_secreto_cola",
        },
        "cola": {
            "backoff_s": [30, 120, 600, 3600],
            "max_horas": 24,
        },
    }
    return CRMConectorService(
        config=config,
        observabilidad=obs_doble,
        conexion_bd=base_datos_memoria,
        adaptador_http=adaptador,
    )


# ¤crm-conector
def test_traduccion_errores_tipados_http(transporte_ctrl: TransporteControlable) -> None:
    """RF-CRM-04: AdaptadorHttpCRM traduce códigos HTTP a excepciones tipadas."""
    adaptador = AdaptadorHttpCRM(
        url="https://api.crm.test",
        secreto_hmac="key",
        transporte=transporte_ctrl.transporte,
    )

    # 429 -> LimiteDeTasa
    transporte_ctrl.devolver_codigo = 429
    transporte_ctrl.devolver_cuerpo = "Too many requests"
    with pytest.raises(LimiteDeTasa):
        adaptador.enviar_publicacion({"test": 1})

    # 400 / 422 -> WebhookRechazado
    transporte_ctrl.devolver_codigo = 400
    transporte_ctrl.devolver_cuerpo = "Bad Request"
    with pytest.raises(WebhookRechazado):
        adaptador.enviar_publicacion({"test": 2})

    transporte_ctrl.devolver_codigo = 422
    transporte_ctrl.devolver_cuerpo = "Unprocessable Entity"
    with pytest.raises(WebhookRechazado):
        adaptador.enviar_publicacion({"test": 3})

    # 409 -> ContactoDuplicado
    transporte_ctrl.devolver_codigo = 409
    transporte_ctrl.devolver_cuerpo = "Duplicate contact"
    with pytest.raises(ContactoDuplicado):
        adaptador.enviar_publicacion({"test": 4})

    # >=500 -> CRMNoDisponible
    transporte_ctrl.devolver_codigo = 503
    transporte_ctrl.devolver_cuerpo = "Service Unavailable"
    with pytest.raises(CRMNoDisponible):
        adaptador.enviar_publicacion({"test": 5})


# ¤crm-conector
def test_publicacion_fallida_entra_en_cola_con_backoff(
    servicio_con_cola: CRMConectorService,
    transporte_ctrl: TransporteControlable,
    base_datos_memoria: sqlite3.Connection,
) -> None:
    """RF-CRM-04 Criterio (a): Publicación fallida queda pendiente con próximo intento según backoff."""
    transporte_ctrl.devolver_codigo = 500
    transporte_ctrl.devolver_cuerpo = "Internal Server Error"

    venta_id = f"vta_fail_{uuid4().hex[:8]}"
    venta_datos = {
        "venta_id": venta_id,
        "ticket": "TCK-FAIL-1",
        "vendedor": "Pedro Vendedor",
        "monto": "80.00",
    }

    resultado = servicio_con_cola.publicar_venta(venta_datos)
    assert resultado.estado == "pendiente"
    assert resultado.intentos == 1
    assert resultado.proximo_intento is not None

    # Verificar en base de datos
    cur = base_datos_memoria.execute(
        "SELECT estado, intentos, proximo_intento FROM crm.publicaciones WHERE venta_id = ?",
        (venta_id,),
    )
    fila = cur.fetchone()
    assert fila["estado"] == "pendiente"
    assert fila["intentos"] == 1


# ¤crm-conector
def test_procesar_cola_reintenta_y_recupera_a_ok(
    servicio_con_cola: CRMConectorService,
    transporte_ctrl: TransporteControlable,
    base_datos_memoria: sqlite3.Connection,
) -> None:
    """RF-CRM-04 Criterio (a): procesar_cola() reintenta cuando vence proximo_intento y actualiza a ok."""
    transporte_ctrl.devolver_codigo = 500
    venta_id = f"vta_recov_{uuid4().hex[:8]}"
    venta_datos = {"venta_id": venta_id, "ticket": "TCK-RECOV-1"}

    servicio_con_cola.publicar_venta(venta_datos)

    # Intentar procesar la cola de inmediato: el próximo intento aún no ha vencido (+30s)
    ahora_actual = datetime.now(timezone.utc)
    procesadas = servicio_con_cola.procesar_cola(ahora=ahora_actual)
    assert procesadas == 0

    # Avanzar el tiempo 35 segundos para superar el backoff de 30s
    tiempo_futuro = ahora_actual + timedelta(seconds=35)

    # Recuperar el servicio HTTP: el CRM vuelve a responder 200 OK
    transporte_ctrl.devolver_codigo = 200
    transporte_ctrl.devolver_cuerpo = '{"status":"accepted"}'

    procesadas = servicio_con_cola.procesar_cola(ahora=tiempo_futuro)
    assert procesadas == 1

    # Verificar que el registro quedó ok
    cur = base_datos_memoria.execute(
        "SELECT estado, intentos, proximo_intento, ultima_respuesta FROM crm.publicaciones WHERE venta_id = ?",
        (venta_id,),
    )
    fila = cur.fetchone()
    assert fila["estado"] == "ok"
    assert fila["intentos"] == 2
    assert fila["proximo_intento"] is None
    assert "200 OK" in fila["ultima_respuesta"]


# ¤crm-conector
def test_ventana_24_horas_y_invariante_venta_no_se_pierde(
    servicio_con_cola: CRMConectorService,
    transporte_ctrl: TransporteControlable,
    base_datos_memoria: sqlite3.Connection,
    obs_doble: DobleObservabilidadService,
) -> None:
    """RF-CRM-04 Criterio (b), INV_VENTA_NO_SE_PIERDE: Tras 24h queda 'error', emite alerta y NO se borra."""
    transporte_ctrl.devolver_codigo = 500
    venta_id = f"vta_24h_{uuid4().hex[:8]}"
    venta_datos = {"venta_id": venta_id, "ticket": "TCK-24H"}

    servicio_con_cola.publicar_venta(venta_datos)

    # Simular que han transcurrido 25 horas desde la creación
    creado_hace_25h = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    base_datos_memoria.execute(
        "UPDATE crm.publicaciones SET creado_en = ?, proximo_intento = ? WHERE venta_id = ?",
        (creado_hace_25h, creado_hace_25h, venta_id),
    )
    base_datos_memoria.commit()

    # Procesar cola: debe detectar que pasaron > 24 horas
    ahora_actual = datetime.now(timezone.utc)
    procesadas = servicio_con_cola.procesar_cola(ahora=ahora_actual)
    assert procesadas == 0  # No se completó con éxito hacia el CRM

    # Verificar estado 'error' y persistencia en BD (INV_VENTA_NO_SE_PIERDE)
    cur = base_datos_memoria.execute(
        "SELECT estado, ultima_respuesta FROM crm.publicaciones WHERE venta_id = ?",
        (venta_id,),
    )
    fila = cur.fetchone()
    assert fila is not None, "La venta nunca debe ser borrada de la base de datos (INV_VENTA_NO_SE_PIERDE)"
    assert fila["estado"] == "error"
    assert "Ventana de 24h agotada" in fila["ultima_respuesta"]

    # Verificar alerta crítica registrada en observabilidad
    assert len(obs_doble.alertas) > 0
    alerta = next(
        (a for a in obs_doble.alertas if a.get("tipo") == "VENTA_NO_PUBLICADA" or a.get("evento") == "VENTA_NO_PUBLICADA"),
        None,
    )
    assert alerta is not None


# ¤crm-conector
def test_reintento_manual_desde_panel(
    servicio_con_cola: CRMConectorService,
    transporte_ctrl: TransporteControlable,
    base_datos_memoria: sqlite3.Connection,
) -> None:
    """RF-CRM-04 Criterio (b): Reintento manual desde panel sobre venta en error fuerza envío inmediato."""
    # Insertar directamente una venta en 'error'
    venta_id = f"vta_manual_{uuid4().hex[:8]}"
    payload = json.dumps({"venta_id": venta_id, "evento": "venta_validada", "ticket": "TCK-MANUAL"})
    base_datos_memoria.execute(
        """
        INSERT INTO crm.publicaciones (venta_id, evento, payload_json, estado, intentos, ultima_respuesta, creado_en)
        VALUES (?, 'venta_validada', ?, 'error', 5, 'Ventana de 24h agotada', ?)
        """,
        (venta_id, payload, datetime.now(timezone.utc).isoformat()),
    )
    base_datos_memoria.commit()

    # Transporte ahora responde exitoso
    transporte_ctrl.devolver_codigo = 200
    transporte_ctrl.devolver_cuerpo = '{"status":"manual_ok"}'

    # Disparar reintento manual
    pub = servicio_con_cola.reintentar_publicacion(venta_id, "venta_validada")

    assert pub.estado == "ok"
    assert pub.intentos == 6
    assert "200 OK" in (pub.ultima_respuesta or "")

    # Comprobar en base de datos
    cur = base_datos_memoria.execute(
        "SELECT estado, proximo_intento FROM crm.publicaciones WHERE venta_id = ?",
        (venta_id,),
    )
    fila = cur.fetchone()
    assert fila["estado"] == "ok"
    assert fila["proximo_intento"] is None
