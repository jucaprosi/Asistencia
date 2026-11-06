# ¤crm-conector
# ¤¤integration-engineer
"""Tests de asignación de handoffs por zona e invariante INV_HANDOFF_UNICO (RF-CRM-06, RF-MCP-06)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from features.crm_conector.crm_conector_service import CRMConectorService
from features.crm_conector.tipos import (
    Contacto,
    HandoffExistente,
    HandoffInexistente,
    Zona,
)
from tests.crm_conector.dobles import DobleObservabilidadService


# ¤crm-conector
@pytest.fixture
def servicio_crm() -> tuple[CRMConectorService, DobleObservabilidadService]:
    obs = DobleObservabilidadService()
    config = {
        "proveedor": "fake",
        "admin_id": "00000000-0000-0000-0000-000000000001",
        "contacto_humano_escalamiento": "+593999999999",
        "bandeja_handoff_activa": True,
        "minutos_estimados_atencion": 15,
        "tiempo_limite_sin_tomar_minutos": 15,
        "tiempo_limite_abandono_horas": 24,
        "propiedades_zonas": {
            "glamping_imbabura": "imbabura_norte",
            "dep_ibarra_centro": "ibarra_urbano",
        },
    }
    servicio = CRMConectorService(config, observabilidad=obs)
    return servicio, obs


# ¤crm-conector
def test_handoff_al_gestor_de_la_zona(servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]) -> None:
    servicio, obs = servicio_crm
    eventos_capturados: list[dict] = []
    servicio.registrar_receptor("mensaje_gestor", lambda ev: eventos_capturados.append(dict(ev.datos)))

    # Dado una propiedad resuelta en la zona 'imbabura_norte'
    # Cuando el huésped pide una persona (o por baja confianza / inyección)
    handoff_id = servicio.solicitar_handoff(
        conversacion_id="conv_huesped_01",
        propiedad_id="glamping_imbabura",
        motivo="peticion_explicita",
        resumen="El huésped solicita hablar con una persona.",
    )

    h = servicio.obtener_handoff(handoff_id)
    assert h is not None
    assert h.estado == "pendiente"
    assert h.zona_id == "imbabura_norte"
    # Debe estar asignado al gestor principal de imbabura_norte
    zona = servicio.obtener_zona("imbabura_norte")
    assert zona is not None
    assert h.asignado_a == zona.gestor_principal_id

    # El gestor recibe la plantilla handoff_asignado
    assert any(log["campos"].get("plantilla") == "handoff_asignado" for log in obs.logs)
    assert any(ev.get("plantilla") == "handoff_asignado" for ev in eventos_capturados)


# ¤crm-conector
def test_handoff_sin_zona_resuelta_asigna_al_administrador(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, obs = servicio_crm

    # Dado una conversación sin propiedad resuelta
    handoff_id = servicio.solicitar_handoff(
        conversacion_id="conv_sin_zona_01",
        propiedad_id=None,
        zona_id=None,
        motivo="baja_confianza",
        resumen="No se pudo determinar propiedad.",
    )

    h = servicio.obtener_handoff(handoff_id)
    assert h is not None
    assert h.estado == "pendiente"
    assert h.zona_id is None
    assert h.asignado_a == "00000000-0000-0000-0000-000000000001"


# ¤crm-conector
def test_nadie_toma_el_handoff_en_15_minutos_pasa_a_respaldo(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, obs = servicio_crm

    # Dado un handoff pendiente
    handoff_id = servicio.solicitar_handoff(
        conversacion_id="conv_tiempo_01",
        propiedad_id="glamping_imbabura",
        motivo="peticion_explicita",
        resumen="Esperando atención.",
    )
    zona = servicio.obtener_zona("imbabura_norte")
    assert zona is not None

    # Cuando pasan 16 minutos sin tomar
    h_inicial = servicio.obtener_handoff(handoff_id)
    assert h_inicial is not None
    tiempo_futuro = h_inicial.inicio + timedelta(minutes=16)

    res = servicio.revisar_plazos_handoffs(ahora=tiempo_futuro)
    assert res["reasignados_respaldo"] == 1

    # Entonces se asigna al gestor de respaldo y se dispara una alerta
    h_actualizado = servicio.obtener_handoff(handoff_id)
    assert h_actualizado is not None
    assert h_actualizado.asignado_a == zona.gestor_respaldo_id

    alertas = [log for log in obs.logs if log["evento"] == "alerta_handoff_no_tomado"]
    assert len(alertas) >= 1
    assert alertas[0]["campos"]["gestor_respaldo"] == zona.gestor_respaldo_id


# ¤crm-conector
def test_atencion_abandonada_24_horas_devuelve_al_asistente(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, obs = servicio_crm

    handoff_id = servicio.solicitar_handoff(
        conversacion_id="conv_abandono_01",
        propiedad_id="glamping_imbabura",
        motivo="peticion_explicita",
        resumen="Atención iniciada.",
    )
    # Gestor toma el handoff
    servicio.tomar_handoff(handoff_id, gestor_id="gestor_01")
    h_tomado = servicio.obtener_handoff(handoff_id)
    assert h_tomado is not None
    assert h_tomado.estado == "tomado"

    # Cuando pasan 25 horas sin actividad
    tiempo_abandono = (h_tomado.tomado_en or h_tomado.inicio) + timedelta(hours=25)
    res = servicio.revisar_plazos_handoffs(ahora=tiempo_abandono)
    assert res["devueltos_vencimiento"] == 1

    # Entonces vuelve al asistente con devuelto_por 'vencimiento'
    h_devuelto = servicio.obtener_handoff(handoff_id)
    assert h_devuelto is not None
    assert h_devuelto.estado == "devuelto"
    assert h_devuelto.devuelto_por == "vencimiento"


# ¤crm-conector
def test_escalamiento_antes_de_la_fase_4_sin_bandeja_activa() -> None:
    obs = DobleObservabilidadService()
    config = {
        "proveedor": "fake",
        "bandeja_handoff_activa": False,
        "contacto_humano_escalamiento": "+593988776655",
    }
    servicio = CRMConectorService(config, observabilidad=obs)

    # Dado una instalación sin bandeja de handoff activa
    # Cuando el agente solicita humano
    salida = servicio.solicitar_humano(
        motivo="peticion_explicita",
        resumen="Quiero hablar con alguien.",
        conversacion_id="conv_sin_bandeja",
    )

    # Entonces entrega el contacto humano configurado y registra el motivo en la traza
    assert salida["contacto_humano"] == "+593988776655"
    assert salida["bandeja_activa"] is False
    assert any(log["evento"] == "escalamiento_sin_bandeja" for log in obs.logs)


# ¤crm-conector
def test_cancelar_o_cambiar_reserva_abre_handoff_fuera_alcance(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, _ = servicio_crm

    # Dado un huésped con reserva que pide cancelar o cambiar fechas
    salida = servicio.solicitar_humano(
        motivo="fuera_alcance",
        resumen="Huésped solicita cancelar su reserva.",
        propiedad_id="glamping_imbabura",
        conversacion_id="conv_cancelacion_01",
    )

    assert salida["canal"] == "panel"
    assert salida["minutos_estimados"] == 15
    h = servicio.obtener_handoff(salida["handoff_id"])
    assert h is not None
    assert h.motivo == "fuera_alcance"


# ¤crm-conector
def test_inv_handoff_unico_bloquea_segundo_handoff_abierto(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, _ = servicio_crm

    # Primer handoff abierto
    servicio.solicitar_handoff(
        conversacion_id="conv_unica_01",
        propiedad_id="glamping_imbabura",
        motivo="peticion_explicita",
        resumen="Primer intento.",
    )

    # Segundo intento sobre la misma conversación sin haber devuelto el anterior
    with pytest.raises(HandoffExistente):
        servicio.solicitar_handoff(
            conversacion_id="conv_unica_01",
            propiedad_id="glamping_imbabura",
            motivo="baja_confianza",
            resumen="Segundo intento.",
        )


# ¤crm-conector
def test_devolver_al_asistente_permite_nuevo_handoff_y_llama_callback(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, _ = servicio_crm
    reanudar_llamado: list[str] = []

    h_id = servicio.solicitar_handoff(
        conversacion_id="conv_ciclo_01",
        propiedad_id="glamping_imbabura",
        motivo="peticion_explicita",
        resumen="Atención rápida.",
    )

    servicio.tomar_handoff(h_id, gestor_id="gestor_01")
    servicio.devolver_al_asistente(
        h_id,
        gestor_id="gestor_01",
        devuelto_por="gestor",
        reanudar_callback=lambda conv: reanudar_llamado.append(conv),
    )

    assert reanudar_llamado == ["conv_ciclo_01"]

    # Ahora que está devuelto, debe permitir un nuevo handoff sin violar INV_HANDOFF_UNICO
    nuevo_h_id = servicio.solicitar_handoff(
        conversacion_id="conv_ciclo_01",
        propiedad_id="glamping_imbabura",
        motivo="baja_confianza",
        resumen="Segunda atención.",
    )
    assert nuevo_h_id != h_id


# ¤crm-conector
def test_herramientas_mcp_buscar_y_crear_oportunidad(
    servicio_crm: tuple[CRMConectorService, DobleObservabilidadService]
) -> None:
    servicio, _ = servicio_crm

    # Buscar contacto no existente
    res_b = servicio.buscar_contacto_crm(telefono_token="tok_no_existe")
    assert res_b == {"encontrado": False}

    # Crear contacto y buscar
    c = Contacto(
        contacto_id="cnt_mcp_01",
        nombre_token="tok_nom",
        telefono_token="tok_tel_mcp",
    )
    servicio.crear_contacto(c)
    res_encontrado = servicio.buscar_contacto_crm(telefono_token="tok_tel_mcp")
    assert res_encontrado == {"encontrado": True, "contacto_id": "cnt_mcp_01"}

    # Crear oportunidad MCP
    res_op = servicio.crear_oportunidad_crm(
        contacto_id="cnt_mcp_01",
        propiedad_id="glamping_imbabura",
        etapa="Por validar",
        monto=180.50,
    )
    assert "oportunidad_id" in res_op
