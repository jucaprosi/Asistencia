"""Prueba E2E de handoffs por zona y ciclo de vida de conversación (US-09, US-10).

Simula el flujo completo del gestor de zona: autenticación con código WhatsApp, inspección de bandeja,
toma de conversación (silenciando al agente), respuesta y devolución al asistente, además de validar
el bloqueo 403 al intentar acceder a una zona no asignada.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleAgenteService,
    DobleCanalWhatsappService,
    DobleObservabilidadService,
    DoblePMSConectorService,
    DobleSeguridadService,
)


def test_flujo_e2e_gestor_handoff_y_aislamiento_zonas() -> None:
    # 1. Inicializar sistema con dobles de compuertas
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    agente = DobleAgenteService()
    canal = DobleCanalWhatsappService()
    pms = DoblePMSConectorService()

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        agente=agente,
        canal=canal,
        pms=pms,
        observabilidad=DobleObservabilidadService(),
    )

    # Registrar dos handoffs: uno en zona_a y otro en zona_b
    servicio.registrar_handoff_interno(
        conversacion_id="conv_e2e_a",
        propiedad="Domo del Lago",
        zona_id="zona_a",
        motivo="Petición de early check-in",
        resumen="El huésped pregunta si puede ingresar a las 11:00 am.",
        huesped_nombre="Carlos Alvear",
        huesped_telefono="+593991234567",
        mensajes=[
            {"remitente": "huesped", "texto": "Hola [token_huesped], ¿puedo llegar antes?", "hora": "hace 10 min"},
        ],
    )
    servicio.registrar_handoff_interno(
        conversacion_id="conv_e2e_b",
        propiedad="Cabaña Andina",
        zona_id="zona_b",
        motivo="Consulta de leña",
        resumen="Preguntan si la chimenea incluye leña.",
        huesped_nombre="Diana Morales",
        huesped_telefono="+593992345678",
    )

    app = crear_app_panel(servicio)
    client = TestClient(app)

    # 2. Paso P-01: Solicitar código de acceso para gestor de zona A
    resp_cod = client.post("/panel/api/sesion/codigo", json={"correo": "gestor_a@glamping.ec"})
    assert resp_cod.status_code == 200
    assert len(canal.plantillas_enviadas) == 1
    codigo = canal.plantillas_enviadas[0][1].variables[0]

    # Confirmar código y obtener sesión
    resp_login = client.post("/panel/api/sesion", json={"correo": "gestor_a@glamping.ec", "codigo": codigo})
    assert resp_login.status_code == 200
    datos_sesion = resp_login.json()
    assert datos_sesion["rol"] == "gestor"
    assert "zona_a" in datos_sesion["zonas"]
    csrf = datos_sesion["csrf"]

    # 3. Paso P-02: Consultar inicio
    resp_inicio = client.get("/panel/api/inicio")
    assert resp_inicio.status_code == 200
    tarjetas = resp_inicio.json()["tarjetas"]
    assert any("esperando en tu zona" in t["titulo"].lower() for t in tarjetas)

    # 4. Paso P-08: Listar bandeja de handoffs de su zona
    resp_handoffs = client.get("/panel/api/handoffs")
    assert resp_handoffs.status_code == 200
    lista = resp_handoffs.json()
    assert len(lista) == 1
    assert lista[0]["conversacion_id"] == "conv_e2e_a"
    assert lista[0]["zona_id"] == "zona_a"

    # Verificar que el gestor recibe 403 al intentar consultar la zona B
    resp_403 = client.get("/panel/api/handoffs?zona=zona_b")
    assert resp_403.status_code == 403

    resp_403_det = client.get("/panel/api/handoffs/conv_e2e_b")
    assert resp_403_det.status_code == 403

    # 5. Paso P-09: Abrir detalle de conversación de su zona y verificar rehidratación de PII
    resp_detalle = client.get("/panel/api/handoffs/conv_e2e_a")
    assert resp_detalle.status_code == 200
    det = resp_detalle.json()
    assert det["propiedad"] == "Domo del Lago"
    assert "Carlos Alvear" in det["huesped_nombre"]
    # Comprobar que en el texto del mensaje se rehidrató el token
    assert "María López" in det["mensajes"][0]["texto"] or "Carlos Alvear" in det["mensajes"][0]["texto"] or "[token_huesped]" not in det["mensajes"][0]["texto"]

    # 6. Tomar conversación (silencia al agente)
    resp_tomar = client.post(
        "/panel/api/handoffs/conv_e2e_a/tomar",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "idemp-e2e-tomar"},
    )
    assert resp_tomar.status_code == 200
    assert agente.silenciadas.get("conv_e2e_a") == "tomado_por_gestor"

    # 7. Responder al huésped por WhatsApp
    resp_responder = client.post(
        "/panel/api/handoffs/conv_e2e_a/responder",
        json={"texto": "Estimado Carlos, con gusto le permitimos el ingreso a las 11:00 am."},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "idemp-e2e-responder"},
    )
    assert resp_responder.status_code == 200
    assert len(canal.enviados) == 1
    assert "11:00 am" in canal.enviados[0].texto

    # 8. Devolver conversación al asistente (reanuda al agente)
    resp_devolver = client.post(
        "/panel/api/handoffs/conv_e2e_a/devolver",
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": "idemp-e2e-devolver"},
    )
    assert resp_devolver.status_code == 200
    assert "conv_e2e_a" in agente.reanudadas
    assert "conv_e2e_a" not in agente.silenciadas

    # Comprobar estado final "devuelto"
    resp_final = client.get("/panel/api/handoffs/conv_e2e_a")
    assert resp_final.json()["estado"] == "devuelto"
