# ¤panel-operativo
# ¤¤frontend-developer
"""Pruebas E2E del Inbox Completo de Huéspedes en el panel operativo propio (T-701, TASK-008, ADR-0010).

Verifica:
- Supervisión integral de todas las conversaciones de huéspedes (resueltas por bot o en handoff) sin requerir CRM externo.
- Aislamiento de zona por rol de usuario (INV_PANEL_POR_ROL: gestor limitado a sus zonas, admin ve todas).
- Detalle de conversación con historial cronológico y rehidratación de PII autorizada.
- Gestión de etiquetas personalizadas y notas internas entre el equipo.
- Envío de respuesta manual que sale directamente por el canal de WhatsApp del negocio.
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


# ¤panel-operativo
def _crear_sistema_inbox() -> tuple[PanelOperativoService, DobleCanalWhatsappService, DobleSeguridadService]:
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

    # Conversación 1: Domo del Lago (zona_a) - Resuelta autónomamente por el bot
    servicio.registrar_conversacion_inbox(
        conversacion_id="conv_inbox_01",
        propiedad_id="glamping_imbabura",
        zona_id="zona_a",
        huesped_nombre="Esteban Paredes",
        huesped_telefono="+593991112233",
        estado="activa",
        modo="activo",
        mensajes=[
            {"remitente": "huesped", "texto": "Hola, ¿el domo cuenta con jacuzzi privado?", "hora": "10:00"},
            {"remitente": "asistente", "texto": "¡Hola Esteban! Sí, todos nuestros domos incluyen jacuzzi privado con vista al lago.", "hora": "10:01"},
        ],
    )

    # Conversación 2: Cabaña del Bosque (zona_a) - En handoff con solicitud humana
    servicio.registrar_conversacion_inbox(
        conversacion_id="conv_inbox_02",
        propiedad_id="glamping_imbabura",
        zona_id="zona_a",
        huesped_nombre="Mariana Lopez",
        huesped_telefono="+593992223344",
        estado="handoff",
        modo="silencio",
        mensajes=[
            {"remitente": "huesped", "texto": "Necesito cambiar las fechas de mi reserva urgente con una persona.", "hora": "11:15"},
            {"remitente": "asistente", "texto": "Entendido Mariana, te transfiero de inmediato con un gestor.", "hora": "11:16"},
        ],
    )

    # Conversación 3: Departamento San Pablo (zona_b) - Otra zona
    servicio.registrar_conversacion_inbox(
        conversacion_id="conv_inbox_03",
        propiedad_id="depa_san_pablo",
        zona_id="zona_b",
        huesped_nombre="Roberto Gomez",
        huesped_telefono="+593993334455",
        estado="resuelta",
        modo="activo",
        mensajes=[
            {"remitente": "huesped", "texto": "Gracias por el código de wifi, todo perfecto.", "hora": "09:30"},
            {"remitente": "asistente", "texto": "¡Un gusto atenderte! Disfruta tu estadía.", "hora": "09:31"},
        ],
    )

    return servicio, canal, seguridad


# ¤panel-operativo
def _iniciar_sesion(client: TestClient, canal: DobleCanalWhatsappService, correo: str) -> str:
    canal.plantillas_enviadas.clear()
    resp_cod = client.post("/panel/api/sesion/codigo", json={"correo": correo})
    assert resp_cod.status_code == 200
    codigo = canal.plantillas_enviadas[0][1].variables[0]
    resp_login = client.post("/panel/api/sesion", json={"correo": correo, "codigo": codigo})
    assert resp_login.status_code == 200
    return resp_login.json()["csrf"]


# ¤panel-operativo
def test_inbox_listar_todas_las_conversaciones_y_busqueda() -> None:
    """Verifica que el Inbox lista todas las conversaciones de huéspedes con filtros y búsqueda."""
    servicio, canal, _ = _crear_sistema_inbox()
    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión como Administrador (ve todas las zonas)
    _iniciar_sesion(client, canal, "admin@glamping.ec")

    # 1. Listar todas las conversaciones sin filtro
    resp = client.get("/panel/api/conversaciones")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 3
    ids = {item["conversacion_id"] for item in items}
    assert ids == {"conv_inbox_01", "conv_inbox_02", "conv_inbox_03"}

    # 2. Filtrar por estado 'handoff'
    resp_handoff = client.get("/panel/api/conversaciones?estado=handoff")
    assert resp_handoff.status_code == 200
    items_h = resp_handoff.json()
    assert len(items_h) == 1
    assert items_h[0]["conversacion_id"] == "conv_inbox_02"

    # 3. Filtrar por propiedad
    resp_prop = client.get("/panel/api/conversaciones?propiedad_id=depa_san_pablo")
    assert resp_prop.status_code == 200
    items_p = resp_prop.json()
    assert len(items_p) == 1
    assert items_p[0]["conversacion_id"] == "conv_inbox_03"

    # 4. Búsqueda por texto libre (en mensajes o nombre)
    resp_busq = client.get("/panel/api/conversaciones?busqueda=jacuzzi")
    assert resp_busq.status_code == 200
    items_b = resp_busq.json()
    assert len(items_b) == 1
    assert items_b[0]["conversacion_id"] == "conv_inbox_01"


# ¤panel-operativo
def test_inbox_aislamiento_zona_inv_panel_por_rol() -> None:
    """Verifica el cumplimiento de INV_PANEL_POR_ROL en el Inbox (gestor confinado a su zona)."""
    servicio, canal, _ = _crear_sistema_inbox()
    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión como Gestor de zona_a
    _iniciar_sesion(client, canal, "gestor_a@glamping.ec")

    # 1. Al listar conversaciones, solo debe ver las de zona_a
    resp = client.get("/panel/api/conversaciones")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    for item in items:
        assert item["zona_id"] == "zona_a"

    # 2. Intentar consultar detalle de una conversación de zona_b debe responder 403
    resp_403 = client.get("/panel/api/conversaciones/conv_inbox_03")
    assert resp_403.status_code == 403

    # 3. Intentar responder o modificar etiquetas en zona_b debe responder 403
    resp_etq_403 = client.post("/panel/api/conversaciones/conv_inbox_03/etiquetas", json={"etiqueta": "Prueba"})
    assert resp_etq_403.status_code == 403


# ¤panel-operativo
def test_inbox_detalle_con_historial_y_rehidratacion_pii() -> None:
    """Verifica que el detalle de conversación entrega el historial completo y rehidrata PII autorizada."""
    servicio, canal, seguridad = _crear_sistema_inbox()

    # Inyectar token de PII en mensaje para verificar rehidratación
    servicio.registrar_conversacion_inbox(
        conversacion_id="conv_inbox_pii",
        propiedad_id="glamping_imbabura",
        zona_id="zona_a",
        huesped_nombre="Valeria Salazar",
        huesped_telefono="+593994445566",
        mensajes=[
            {"remitente": "huesped", "texto": "Mi teléfono de respaldo es [token_tel_valeria].", "instante": "2026-11-03T12:00:00Z"}
        ],
    )
    seguridad.registrar_token_prueba("conv_inbox_pii", "[token_tel_valeria]", "+593994445566")

    app = crear_app_panel(servicio)
    client = TestClient(app)
    _iniciar_sesion(client, canal, "gestor_a@glamping.ec")

    resp = client.get("/panel/api/conversaciones/conv_inbox_pii")
    assert resp.status_code == 200
    detalle = resp.json()
    assert detalle["conversacion_id"] == "conv_inbox_pii"
    assert detalle["huesped_nombre"] == "Valeria Salazar"
    assert len(detalle["mensajes"]) == 1
    # PII rehidratada bajo sesión de gestor autorizado
    assert "+593994445566" in detalle["mensajes"][0]["texto"]


# ¤panel-operativo
def test_inbox_gestion_etiquetas_y_notas_internas() -> None:
    """Verifica la asignación/remoción de etiquetas y el registro de notas internas entre gestores."""
    servicio, canal, _ = _crear_sistema_inbox()
    app = crear_app_panel(servicio)
    client = TestClient(app)
    csrf = _iniciar_sesion(client, canal, "gestor_a@glamping.ec")

    # 1. Asignar etiquetas a la conversación conv_inbox_01
    resp_etq1 = client.post(
        "/panel/api/conversaciones/conv_inbox_01/etiquetas",
        json={"etiqueta": "VIP"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_etq1.status_code == 200
    assert "VIP" in resp_etq1.json()["etiquetas"]

    resp_etq2 = client.post(
        "/panel/api/conversaciones/conv_inbox_01/etiquetas",
        json={"etiqueta": "Aniversario"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_etq2.status_code == 200
    assert set(resp_etq2.json()["etiquetas"]) == {"VIP", "Aniversario"}

    # 2. Agregar una nota interna
    resp_nota = client.post(
        "/panel/api/conversaciones/conv_inbox_01/notas",
        json={"texto": "El huésped celebra su aniversario, preparar botella de vino de cortesía."},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_nota.status_code == 200
    nota = resp_nota.json()["nota"]
    assert "botella de vino" in nota["texto"]
    assert nota["autor_nombre"] != ""

    # 3. Comprobar que el detalle refleja las etiquetas y las notas
    resp_det = client.get("/panel/api/conversaciones/conv_inbox_01")
    assert resp_det.status_code == 200
    datos = resp_det.json()
    assert set(datos["etiquetas"]) == {"VIP", "Aniversario"}
    assert len(datos["notas"]) == 1
    assert "botella de vino" in datos["notas"][0]["texto"]

    # 4. Remover una etiqueta
    resp_del_etq = client.delete(
        "/panel/api/conversaciones/conv_inbox_01/etiquetas/Aniversario",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_del_etq.status_code == 200
    assert resp_del_etq.json()["etiquetas"] == ["VIP"]


# ¤panel-operativo
def test_inbox_respuesta_manual_sale_por_canal_whatsapp() -> None:
    """Verifica que responder desde el Inbox envía el mensaje por el canal de WhatsApp oficial."""
    servicio, canal, _ = _crear_sistema_inbox()
    app = crear_app_panel(servicio)
    client = TestClient(app)
    csrf = _iniciar_sesion(client, canal, "gestor_a@glamping.ec")

    canal.mensajes_enviados.clear()

    # Enviar respuesta manual al huésped de conv_inbox_02
    resp = client.post(
        "/panel/api/conversaciones/conv_inbox_02/responder",
        json={"texto": "Hola Mariana, con gusto gestionamos tu cambio de fechas. ¿Qué días prefieres?"},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["mensaje_enviado"] is True

    # Verificar que el mensaje fue despachado al canal con el teléfono del huésped
    assert len(canal.mensajes_enviados) == 1
    envio = canal.mensajes_enviados[0]
    assert envio.destinatario == "+593992223344"
    assert "cambio de fechas" in envio.texto

    # Verificar que se incorporó al historial de la conversación
    resp_det = client.get("/panel/api/conversaciones/conv_inbox_02")
    assert resp_det.status_code == 200
    mensajes = resp_det.json()["mensajes"]
    assert any("cambio de fechas" in m["texto"] for m in mensajes)
