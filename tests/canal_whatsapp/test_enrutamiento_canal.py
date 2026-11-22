# ¤canal-whatsapp
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de enrutamiento y separación de canales ARM y Huéspedes (RF-GW-06)."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService
from features.canal_whatsapp.enrutamiento_canal_internal import (
    EnrutadorCanal,
    PLANTILLA_COMISION_VALIDADA,
    clasificar_canal,
)
from features.canal_whatsapp.persistencia_internal import RepositorioCanal
from features.canal_whatsapp.tipos import (
    Canal,
    MensajeEntrante,
    Plantilla,
    PlantillaNoAprobada,
    TipoContenido,
    VariablesPlantillaInvalidas,
)
from features.seguridad.tipos import Rol
from tests.canal_whatsapp.dobles import (
    ApiMetaSimulada,
    DobleObservabilidadService,
    DobleSeguridadService,
)


# ¤canal-whatsapp
def _crear_payload_webhook(mensajes: list[dict[str, str | dict[str, str]]]) -> bytes:
    data = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID_TEST",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "15550269999", "phone_number_id": "PNID_TEST"},
                            "messages": mensajes,
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    return json.dumps(data).encode("utf-8")


# ¤canal-whatsapp
def _firmar(cuerpo: bytes, secreto: str) -> str:
    firma = hmac.new(secreto.encode("utf-8"), cuerpo, hashlib.sha256).hexdigest()
    return f"sha256={firma}"


# ¤canal-whatsapp
def test_enrutamiento_modo_grupo_separa_canales() -> None:
    """RF-GW-06: En modo grupo, mensajes del grupo_id van a VENDEDORES y el resto a HUESPEDES."""
    grupo_vendedores = "12036304@g.us"
    config = {
        "secreto_app": "test_secret",
        "verify_token": "test_verify",
        "canal_vendedores": {"modo": "grupo", "grupo_id": grupo_vendedores},
    }
    seguridad = DobleSeguridadService()
    servicio = CanalWhatsappService(
        config,
        seguridad=seguridad,
        repositorio=RepositorioCanal(":memory:"),
    )

    mensajes_arm: list[MensajeEntrante] = []
    mensajes_huesped: list[MensajeEntrante] = []

    servicio.registrar_receptor(Canal.VENDEDORES, lambda m: mensajes_arm.append(m))
    servicio.registrar_receptor(Canal.HUESPEDES, lambda m: mensajes_huesped.append(m))

    # 1. Mensaje en el grupo de vendedores
    canal_grupo = servicio.clasificar_canal("593991112233", grupo_id=grupo_vendedores)
    assert canal_grupo == Canal.VENDEDORES

    msg_vendedor = MensajeEntrante(
        mensaje_id="m_vend_1",
        remitente="593991112233",
        canal=canal_grupo,
        tipo=TipoContenido.TEXTO,
        texto="vendí 2 noches en Domo Lago por 300 usd",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    servicio.despachar(msg_vendedor)

    # 2. Mensaje directo de un huésped (sin grupo_id)
    canal_huesped = servicio.clasificar_canal("593987654321", grupo_id=None)
    assert canal_huesped == Canal.HUESPEDES

    msg_huesped = MensajeEntrante(
        mensaje_id="m_huesp_1",
        remitente="593987654321",
        canal=canal_huesped,
        tipo=TipoContenido.TEXTO,
        texto="Hola, ¿tienen disponibilidad para este fin de semana?",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    servicio.despachar(msg_huesped)

    # 3. Mensaje de otro grupo distinto
    canal_otro_grupo = servicio.clasificar_canal("593999999999", grupo_id="otro_grupo@g.us")
    assert canal_otro_grupo == Canal.HUESPEDES

    # Criterios RF-GW-06:
    # (a) Ningún mensaje de vendedores llega al agente de huéspedes
    assert len(mensajes_huesped) == 1
    assert mensajes_huesped[0].mensaje_id == "m_huesp_1"
    assert all(m.canal == Canal.HUESPEDES for m in mensajes_huesped)

    # (b) Ningún mensaje de huésped llega al ARM
    assert len(mensajes_arm) == 1
    assert mensajes_arm[0].mensaje_id == "m_vend_1"
    assert all(m.canal == Canal.VENDEDORES for m in mensajes_arm)


# ¤canal-whatsapp
def test_enrutamiento_modo_uno_a_uno_separa_canales() -> None:
    """RF-GW-06: En modo 1a1, mensajes de vendedores registrados van a VENDEDORES y de huéspedes a HUESPEDES."""
    config = {
        "secreto_app": "test_secret",
        "verify_token": "test_verify",
        "canal_vendedores": {"modo": "uno_a_uno"},
    }
    seguridad = DobleSeguridadService()
    seguridad.registrar_rol("593991112233", Rol.VENDEDOR)
    seguridad.registrar_rol("593994445566", Rol.LIDER)
    seguridad.registrar_rol("593987654321", Rol.HUESPED_ACTIVO)

    servicio = CanalWhatsappService(
        config,
        seguridad=seguridad,
        repositorio=RepositorioCanal(":memory:"),
    )

    mensajes_arm: list[MensajeEntrante] = []
    mensajes_huesped: list[MensajeEntrante] = []

    servicio.registrar_receptor(Canal.VENDEDORES, lambda m: mensajes_arm.append(m))
    servicio.registrar_receptor(Canal.HUESPEDES, lambda m: mensajes_huesped.append(m))

    # Vendedor identificado vía seguridad_service
    canal_vendedor = servicio.clasificar_canal("593991112233")
    assert canal_vendedor == Canal.VENDEDORES

    # Líder de ventas identificado vía seguridad_service
    canal_lider = servicio.clasificar_canal("593994445566")
    assert canal_lider == Canal.VENDEDORES

    # Huésped activo identificado vía seguridad_service
    canal_huesped = servicio.clasificar_canal("593987654321")
    assert canal_huesped == Canal.HUESPEDES

    # Usuario no registrado (potencial huésped)
    canal_desconocido = servicio.clasificar_canal("593999999999")
    assert canal_desconocido == Canal.HUESPEDES

    # Despachar mensajes
    m_vend = MensajeEntrante(
        mensaje_id="m_v1",
        remitente="593991112233",
        canal=canal_vendedor,
        tipo=TipoContenido.TEXTO,
        texto="reporto venta 1 noche",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )
    m_huesp = MensajeEntrante(
        mensaje_id="m_h1",
        remitente="593987654321",
        canal=canal_huesped,
        tipo=TipoContenido.TEXTO,
        texto="¿a qué hora es el checkin?",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )

    servicio.despachar(m_vend)
    servicio.despachar(m_huesp)

    # Criterios RF-GW-06:
    assert len(mensajes_arm) == 1
    assert mensajes_arm[0].remitente == "593991112233"
    assert len(mensajes_huesped) == 1
    assert mensajes_huesped[0].remitente == "593987654321"


# ¤canal-whatsapp
def test_registro_explicito_vendedor_1a1() -> None:
    """Verifica que se puedan registrar vendedores explícitamente en el servicio."""
    config = {"canal_vendedores": {"modo": "1a1"}}
    servicio = CanalWhatsappService(config, repositorio=RepositorioCanal(":memory:"))

    # Inicialmente es clasificado como huésped
    assert servicio.clasificar_canal("tel_carlos_123") == Canal.HUESPEDES

    # Tras registrarlo como vendedor
    servicio.registrar_vendedor("tel_carlos_123")
    assert servicio.clasificar_canal("tel_carlos_123") == Canal.VENDEDORES


# ¤canal-whatsapp
def test_mamparo_estricto_falla_si_receptores_se_cruzan() -> None:
    """Verifica que el enrutador impida formalmente que un canal invoque el receptor del otro."""
    enrutador = EnrutadorCanal(modo="1a1")

    receptor_huesped = lambda m: "huesped"
    receptor_vendedor = lambda m: "arm"

    # Caso cruzado anómalo: receptor de vendedores asignado al handler de huéspedes
    receptores_cruzados = {
        Canal.VENDEDORES: receptor_huesped,
        Canal.HUESPEDES: receptor_huesped,
    }

    msg_vendedor = MensajeEntrante(
        mensaje_id="m1",
        remitente="vendedor",
        canal=Canal.VENDEDORES,
        tipo=TipoContenido.TEXTO,
        texto="test",
        medio_ref=None,
        ubicacion=None,
        recibido_en=datetime.now(timezone.utc),
    )

    with pytest.raises(RuntimeError, match="Violación RF-GW-06"):
        enrutador.despachar(msg_vendedor, receptores_cruzados)


# ¤canal-whatsapp
def test_definicion_plantilla_comision_validada() -> None:
    """Verifica la definición local de comision_validada y su control de aprobación (RF-GW-04)."""
    assert PLANTILLA_COMISION_VALIDADA.nombre == "comision_validada"
    assert PLANTILLA_COMISION_VALIDADA.categoria == "utility"
    assert PLANTILLA_COMISION_VALIDADA.variables == ("nombre", "ticket", "comision")
    assert PLANTILLA_COMISION_VALIDADA.aprobada is False

    cliente_meta = ApiMetaSimulada()
    servicio = CanalWhatsappService(
        {
            "secreto_app": "secret",
            "verify_token": "token",
            "plantillas": [
                {
                    "nombre": "comision_validada",
                    "idioma": "es",
                    "categoria": "utility",
                    "variables": ["nombre", "ticket", "comision"],
                    "aprobada": False,
                }
            ],
        },
        cliente_http=cliente_meta,
        repositorio=RepositorioCanal(":memory:"),
    )

    plantilla = Plantilla(
        nombre="comision_validada",
        idioma="es",
        variables=("Carlos Alvear", "V-2026-0001", "45.00 USD"),
    )

    # 1. Sin aprobación en vivo debe fallar con PlantillaNoAprobada (se valida en T-511)
    with pytest.raises(PlantillaNoAprobada):
        servicio.enviar_plantilla("593991112233", plantilla)

    # 2. Una vez aprobada en el catálogo
    servicio.aprobar_plantilla("comision_validada", aprobada=True)

    # Fallo si faltan variables
    plantilla_incompleta = Plantilla(
        nombre="comision_validada",
        idioma="es",
        variables=("Carlos Alvear", "V-2026-0001"),
    )
    with pytest.raises(VariablesPlantillaInvalidas):
        servicio.enviar_plantilla("593991112233", plantilla_incompleta)

    # Envío exitoso con variables correctas
    resultado = servicio.enviar_plantilla("593991112233", plantilla)
    assert resultado.estado == "sent"
    assert len(cliente_meta.mensajes_enviados) == 1
    params = cliente_meta.mensajes_enviados[0]["payload"]["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["Carlos Alvear", "V-2026-0001", "45.00 USD"]


# ¤canal-whatsapp
def test_webhook_ingesta_a_receptores_separados_en_modo_1a1() -> None:
    """Verifica que el ciclo completo webhook -> ingesta -> trabajador respete la separación de canales."""
    secreto = "meta_app_secret_123"
    config = {
        "secreto_app": secreto,
        "verify_token": "token123",
        "canal_vendedores": {"modo": "uno_a_uno"},
        "ingesta": {"reintentos_evento": 3, "agrupacion_segundos": 1},
    }
    seguridad = DobleSeguridadService()
    seguridad.registrar_rol("593991112233", Rol.VENDEDOR)

    servicio = CanalWhatsappService(
        config,
        seguridad=seguridad,
        repositorio=RepositorioCanal(":memory:"),
    )

    mensajes_arm: list[MensajeEntrante] = []
    mensajes_huesped: list[MensajeEntrante] = []

    servicio.registrar_receptor(Canal.VENDEDORES, lambda m: mensajes_arm.append(m))
    servicio.registrar_receptor(Canal.HUESPEDES, lambda m: mensajes_huesped.append(m))

    payload = _crear_payload_webhook([
        {
            "id": "wamid_vend_1",
            "from": "593991112233",
            "timestamp": "1730000000",
            "type": "text",
            "text": {"body": "vendí Domo Lago 400 usd"},
        },
        {
            "id": "wamid_huesp_1",
            "from": "593988887777",
            "timestamp": "1730000001",
            "type": "text",
            "text": {"body": "¿cuál es el precio de la noche?"},
        },
    ])
    firma = _firmar(payload, secreto)

    # 1. Recibir vía webhook
    procesados = servicio.recibir(payload, firma)
    assert len(procesados) == 2
    assert procesados[0].canal == Canal.VENDEDORES
    assert procesados[1].canal == Canal.HUESPEDES

    # 2. El trabajador asíncrono procesa y despacha
    n = servicio.procesar_ingesta()
    assert n == 2

    # 3. Separación estricta
    assert len(mensajes_arm) == 1
    assert mensajes_arm[0].mensaje_id == "wamid_vend_1"
    assert mensajes_arm[0].canal == Canal.VENDEDORES
    assert "vendí" in (mensajes_arm[0].texto or "")

    assert len(mensajes_huesped) == 1
    assert mensajes_huesped[0].mensaje_id == "wamid_huesp_1"
    assert mensajes_huesped[0].canal == Canal.HUESPEDES
    assert "precio" in (mensajes_huesped[0].texto or "")
