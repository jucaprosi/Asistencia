"""Pruebas de contrato: El doble de cada sala se comporta como su compuerta real.

Verifica que para cada compuerta _service.py consumida por otra sala:
1. El doble de prueba y la compuerta real implementen la misma firma y contratos de llamadas.
2. Ejecuten el mismo conjunto de casos y devuelvan resultados homogéneos con tipos puros.
3. Un doble alterado a propósito haga fallar el test (mutante muerto).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import pytest

# Dobles de prueba por sala consumidora
from tests.web_huespedes.dobles import DoblePMS as DoblePMSWeb, DobleAnfitriones
from tests.anfitriones.dobles import DoblePMS as DoblePMSAnf, ReservaDoble, DobleSeguridad as DobleSeguridadAnf
from tests.canal_whatsapp.dobles import DobleSeguridadService, DobleObservabilidadService
from tests.crm_conector.dobles import DobleCRMAlternativo

# Compuertas reales
from features.pms_conector.pms_conector_service import PMSConectorService
from features.seguridad.seguridad_service import SeguridadService
from features.anfitriones.anfitriones_service import AnfitrionesService, Hospedaje, EstadoHospedaje, Anfitrion
from features.observabilidad.observabilidad_service import ObservabilidadService
from features.crm_conector.crm_conector_service import CRMConectorService, Contacto


# --- 1. Contrato PMS: consultar disponibilidad y cotizar (consumido por web_huespedes y agente) ---
def test_contrato_pms_disponibilidad_y_cotizacion() -> None:
    doble = DoblePMSWeb()
    real = PMSConectorService()

    d_in = date(2026, 12, 1)
    d_out = date(2026, 12, 3)

    # Disponibilidad
    disp_real = real.consultar_disponibilidad("glamping_imbabura", d_in, d_out, 2)
    disp_doble = doble.consultar_disponibilidad("glamping_imbabura", d_in, d_out, 2)

    assert isinstance(disp_real.disponible, bool) and isinstance(disp_doble.disponible, bool)
    assert len(disp_real.unidades) > 0 and len(disp_doble.unidades) > 0
    assert hasattr(disp_real.unidades[0], "unidad_id") and hasattr(disp_doble.unidades[0], "unidad_id")

    # Cotización
    cot_real = real.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)
    cot_doble = doble.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)

    assert isinstance(cot_real.total, Decimal) and isinstance(cot_doble.total, Decimal)
    assert cot_real.moneda == cot_doble.moneda == "USD"


# --- 2. Contrato PMS: obtener reserva (consumido por anfitriones) ---
def test_contrato_pms_reserva() -> None:
    config = {"proveedor": "fake", "escrituras_habilitadas": {"crear_reserva_preliminar": True}}
    real = PMSConectorService(config=config)
    doble = DoblePMSAnf()

    res_real = real.crear_reserva_preliminar(
        "glamping_imbabura", "domo_lago", date(2026, 12, 1), date(2026, 12, 3), 2, "tok_h", "idem_c_1"
    )
    res_doble = ReservaDoble(
        codigo="RES-DOBLE-1",
        propiedad_id="glamping_imbabura",
        unidad_id="domo_lago",
        huesped_token="tok_h",
        desde=date(2026, 12, 1),
        hasta=date(2026, 12, 3),
        huespedes=2,
        total=Decimal("240.00"),
    )
    doble.agregar_reserva(res_doble)

    c_real = real.obtener_reserva(res_real.codigo)
    c_doble = doble.obtener_reserva("RES-DOBLE-1")

    assert c_real is not None and c_doble is not None
    assert c_real.propiedad_id == c_doble.propiedad_id == "glamping_imbabura"
    assert c_real.total == c_doble.total == Decimal("240.00")


# --- 3. Contrato Seguridad: identificar remitente (consumido por canal_whatsapp) ---
def test_contrato_seguridad_identificar() -> None:
    real = SeguridadService()
    doble = DobleSeguridadService()

    id_real = real.identificar("+593991234567")
    id_doble = doble.identificar("+593991234567")

    assert hasattr(id_real, "rol") and hasattr(id_doble, "rol")
    assert hasattr(id_real, "sujeto_id") and hasattr(id_doble, "sujeto_id")
    assert hasattr(id_real, "remitente_token") and hasattr(id_doble, "remitente_token")


# --- 4. Contrato Seguridad: tokenizar PII (consumido por anfitriones y agente) ---
def test_contrato_seguridad_tokenizar_pii() -> None:
    real = SeguridadService()
    doble = DobleSeguridadAnf()

    tel = "+593991234567"
    tok_real = real.tokenizar(tel, conversacion_id="c_test")
    tok_doble = doble.tokenizar(tel, conversacion_id="c_test")

    # Invariante INV_PII_FUERA_DEL_MODELO: el teléfono real nunca debe figurar en el token
    assert tel not in tok_real
    assert tel not in tok_doble
    assert isinstance(tok_real, str) and isinstance(tok_doble, str)


# --- 5. Contrato Anfitriones: listar hospedajes publicados (consumido por web_huespedes) ---
def test_contrato_anfitriones_publicados() -> None:
    real = AnfitrionesService({})
    doble = DobleAnfitriones()

    anf = Anfitrion(
        anfitrion_id="ANF-C1",
        nombre_comercial="Glamping Contrato",
        comision_porcentaje=Decimal("10.0"),
        terminos_version="v1.0",
    )
    doble.registrar_anfitrion(anf, "tok_1")
    real.registrar_anfitrion(anf, "tok_1", actor_id="admin")

    h = Hospedaje(propiedad_id="PROP-CONTRATO", anfitrion_id="ANF-C1", estado=EstadoHospedaje.PUBLICADO)
    doble.guardar_hospedaje(h)
    real.guardar_hospedaje(h, actor_id="admin")

    pubs_doble = doble.publicados()
    pubs_real = real.publicados()

    assert len(pubs_doble) == 1 and len(pubs_real) == 1
    assert pubs_doble[0].propiedad_id == pubs_real[0].propiedad_id == "PROP-CONTRATO"
    assert pubs_doble[0].estado == pubs_real[0].estado == EstadoHospedaje.PUBLICADO


# --- 6. Contrato Observabilidad: trazas y logs (consumido por todas las salas) ---
def test_contrato_observabilidad_traza_y_log() -> None:
    real = ObservabilidadService({"entorno": "test"})
    doble = DobleObservabilidadService()

    # Trazas
    id_real = real.iniciar_traza("msg_c1", "conv_c1", "whatsapp")
    id_doble = doble.iniciar_traza("msg_c1", "conv_c1", "whatsapp")
    assert isinstance(id_real, str) and isinstance(id_doble, str)
    assert len(id_real) > 0 and len(id_doble) > 0

    # Logs
    real.log("info", "test_evento", modulo="contratos")
    doble.log("info", "test_evento", modulo="contratos")


# --- 7. Contrato CRM Conector: buscar y crear contacto (consumido por agente y panel) ---
def test_contrato_crm_buscar_y_crear_contacto() -> None:
    real = CRMConectorService()
    doble = DobleCRMAlternativo()

    contacto = Contacto(
        contacto_id="C-TEST-1",
        nombre_token="Juan Perez",
        telefono_token="tok_c1",
        email_token="tok_email_1",
    )
    c_real = real.crear_contacto(contacto)
    c_doble = doble.crear_contacto(contacto)

    assert c_real.nombre_token == c_doble.nombre_token == "Juan Perez"
    assert c_real.contacto_id and c_doble.contacto_id



# --- 8. Mutante Muerto: Doble alterado a propósito hace fallar la prueba de contrato ---
def test_doble_alterado_hace_fallar_contrato_mutante() -> None:
    """Verifica (mutante muerto) que si un doble devuelve un tipo incompatible, el test de contrato falle."""
    class DoblePMSMutante(DoblePMSWeb):
        def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int):
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class CotizacionInvalida:
                total: str = "NO_ES_DECIMAL"  # Violación de tipo de dominio!
                moneda: str = "USD"
            return CotizacionInvalida()

    doble_mutado = DoblePMSMutante()
    real = PMSConectorService()

    d_in = date(2026, 12, 1)
    d_out = date(2026, 12, 3)

    cot_real = real.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)
    cot_doble = doble_mutado.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)

    with pytest.raises(AssertionError):
        # Debe fallar porque cot_doble.total no es Decimal
        assert isinstance(cot_real.total, Decimal) and isinstance(cot_doble.total, Decimal)
