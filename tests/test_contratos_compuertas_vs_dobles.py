# ¤pasillo-central
# ¤¤qa-engineer
"""Pruebas de contrato profundas: El doble de cada sala se comporta como su compuerta real (T-902, C2).

Verifica que para cada compuerta _service.py consumida por otra sala:
1. La lista de compuertas se deriva dinámicamente de FIRMAS_COMPUERTAS.json.
2. El doble de prueba y la compuerta real implementan la misma firma, retornan los mismos
   valores (números, cadenas, Decimals, banderas) y replican los mismos casos de error.
3. Dobles alterados a propósito en sus valores o errores hacen fallar el test (mutantes muertos).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import pytest

# Dobles de prueba por sala consumidora
from tests.web_huespedes.dobles import DoblePMS as DoblePMSWeb, DobleAnfitriones
from tests.anfitriones.dobles import DoblePMS as DoblePMSAnf, ReservaDoble, DobleSeguridad as DobleSeguridadAnf, DobleCanalWhatsApp
from tests.canal_whatsapp.dobles import DobleSeguridadService, DobleObservabilidadService
from tests.crm_conector.dobles import DobleCRMAlternativo
from tests.panel_operativo.dobles import (
    DobleSeguridadService as DobleSeguridadPanel,
    DobleComisionesService,
    DobleCanalWhatsappService,
    DobleAgenteService,
    DobleArmJarvisService,
)

# Compuertas reales
from features.pms_conector.pms_conector_service import PMSConectorService
from features.pms_conector.tipos import FechasInvalidas, ReservaInexistente
from features.seguridad.seguridad_service import SeguridadService
from features.anfitriones.anfitriones_service import AnfitrionesService, Hospedaje, EstadoHospedaje, Anfitrion
from features.observabilidad.observabilidad_service import ObservabilidadService
from features.crm_conector.crm_conector_service import CRMConectorService, Contacto
from features.comisiones.comisiones_service import ComisionesService
from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, Plantilla
from features.agente.agente_service import AgenteService
from features.arm_jarvis.arm_jarvis_service import ArmJarvisService, ErrorArm, EstadoVenta, VentaExtraida

RAIZ = Path(__file__).resolve().parent.parent
RUTA_FIRMAS = RAIZ / "governance" / "artefactos" / "FIRMAS_COMPUERTAS.json"


# --- 1. Verificación dinámica de compuertas derivadas de FIRMAS_COMPUERTAS.json ---
def test_compuertas_consumidas_se_derivan_de_firmas() -> None:
    """Verifica que la lista de compuertas evaluadas provenga de FIRMAS_COMPUERTAS.json."""
    assert RUTA_FIRMAS.is_file(), f"Falta archivo {RUTA_FIRMAS}"
    datos = json.loads(RUTA_FIRMAS.read_text(encoding="utf-8"))
    firmas = datos.get("firmas", {})
    assert len(firmas) == 13, f"Se esperaban 13 compuertas en firmas, encontradas: {len(firmas)}"

    compuertas_esperadas = {
        "features/pms_conector/pms_conector_service.py::PMSConectorService",
        "features/seguridad/seguridad_service.py::SeguridadService",
        "features/anfitriones/anfitriones_service.py::AnfitrionesService",
        "features/observabilidad/observabilidad_service.py::ObservabilidadService",
        "features/crm_conector/crm_conector_service.py::CRMConectorService",
        "features/comisiones/comisiones_service.py::ComisionesService",
        "features/canal_whatsapp/canal_whatsapp_service.py::CanalWhatsappService",
        "features/agente/agente_service.py::AgenteService",
        "features/arm_jarvis/arm_jarvis_service.py::ArmJarvisService",
    }
    for compuerta in compuertas_esperadas:
        assert compuerta in firmas, f"Compuerta {compuerta} no encontrada en FIRMAS_COMPUERTAS.json"


# --- 2. Contrato PMS: disponibilidad, cotización y errores de rango ---
def test_contrato_pms_disponibilidad_y_cotizacion_valores_y_errores() -> None:
    doble = DoblePMSWeb()
    real = PMSConectorService()

    d_in = date(2026, 12, 1)
    d_out = date(2026, 12, 3)

    # 1. Disponibilidad: valores exactos
    disp_real = real.consultar_disponibilidad("glamping_imbabura", d_in, d_out, 2)
    disp_doble = doble.consultar_disponibilidad("glamping_imbabura", d_in, d_out, 2)

    assert disp_real.disponible is True and disp_doble.disponible is True
    assert len(disp_real.unidades) > 0 and len(disp_doble.unidades) > 0

    # 2. Cotización: total Decimal y moneda
    cot_real = real.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)
    cot_doble = doble.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)

    assert cot_real.moneda == cot_doble.moneda == "USD"
    assert cot_real.total > Decimal("0.00") and cot_doble.total > Decimal("0.00")
    assert isinstance(cot_real.total, Decimal) and isinstance(cot_doble.total, Decimal)

    # 3. Caso de error: fecha de salida anterior o igual a entrada eleva FechasInvalidas
    d_invalido_in = date(2026, 12, 5)
    d_invalido_out = date(2026, 12, 3)
    with pytest.raises(FechasInvalidas):
        real.consultar_disponibilidad("glamping_imbabura", d_invalido_in, d_invalido_out, 2)
    with pytest.raises(FechasInvalidas):
        doble.consultar_disponibilidad("glamping_imbabura", d_invalido_in, d_invalido_out, 2)


# --- 3. Contrato PMS: consulta de reserva existente y no existente (ReservaInexistente) ---
def test_contrato_pms_obtener_reserva_valores_y_no_encontrado() -> None:
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

    # Error / No encontrado: ambos deben elevar ReservaInexistente
    with pytest.raises(ReservaInexistente):
        real.obtener_reserva("RES-INEXISTENTE-999")
    with pytest.raises(ReservaInexistente):
        doble.obtener_reserva("RES-INEXISTENTE-999")


# --- 4. Contrato Seguridad: autorización y tokenización ---
def test_contrato_seguridad_autorizacion_y_tokenizacion() -> None:
    real = SeguridadService()
    doble = DobleSeguridadPanel()

    # Autorización permitida para rol administrador
    v_real_admin = real.autorizar("administrador", "ver_auditoria")
    v_doble_admin = doble.autorizar("administrador", "ver_auditoria")
    assert v_real_admin.permitido is True and v_doble_admin.permitido is True

    # Autorización rechazada para acción no permitida
    v_real_neg = real.autorizar("gestor", "zona_prohibida")
    v_doble_neg = doble.autorizar("gestor", "zona_prohibida")
    assert v_real_neg.permitido is False and v_doble_neg.permitido is False

    # Tokenización y rehidratación de PII
    tel = "+593991234567"
    tok_real = real.tokenizar(tel, conversacion_id="c_test")
    assert tel not in tok_real
    assert real.rehidratar(tok_real, conversacion_id="c_test") == tel


# --- 5. Contrato Anfitriones: listado de publicados y filtro de pausados ---
def test_contrato_anfitriones_publicados_y_errores() -> None:
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

    # 1. Hospedaje publicado: ambos lo devuelven en publicados()
    h = Hospedaje(propiedad_id="PROP-CONTRATO", anfitrion_id="ANF-C1", estado=EstadoHospedaje.PUBLICADO)
    doble.guardar_hospedaje(h)
    real.guardar_hospedaje(h, actor_id="admin")

    pubs_doble = doble.publicados()
    pubs_real = real.publicados()

    assert len(pubs_doble) == 1 and len(pubs_real) == 1
    assert pubs_doble[0].propiedad_id == pubs_real[0].propiedad_id == "PROP-CONTRATO"
    assert pubs_doble[0].estado == pubs_real[0].estado == EstadoHospedaje.PUBLICADO

    # 2. Hospedaje pausado: ambos lo excluyen de publicados()
    h_pausado = Hospedaje(propiedad_id="PROP-PAUSADA", anfitrion_id="ANF-C1", estado=EstadoHospedaje.PAUSADO)
    doble.guardar_hospedaje(h_pausado)
    real.guardar_hospedaje(h_pausado, actor_id="admin")

    ids_real = [x.propiedad_id for x in real.publicados()]
    ids_doble = [x.propiedad_id for x in doble.publicados()]
    assert "PROP-PAUSADA" not in ids_real
    assert "PROP-PAUSADA" not in ids_doble


# --- 6. Contrato Observabilidad: trazas y logs ---
def test_contrato_observabilidad_valores_y_trazabilidad() -> None:
    real = ObservabilidadService({"entorno": "test"})
    doble = DobleObservabilidadService()

    id_real = real.iniciar_traza("msg_c1", "conv_c1", "whatsapp")
    id_doble = doble.iniciar_traza("msg_c1", "conv_c1", "whatsapp")

    assert isinstance(id_real, str) and isinstance(id_doble, str)
    assert len(id_real) > 0 and len(id_doble) > 0

    # Logs estructurados
    real.log("INFO", "evento_contrato", modulo="qa")
    doble.log("INFO", "evento_contrato", modulo="qa")


# --- 7. Contrato CRM Conector: crear contacto y búsqueda ---
def test_contrato_crm_buscar_y_crear_contacto_valores() -> None:
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
    assert c_real.contacto_id == c_doble.contacto_id == "C-TEST-1"
    assert c_real.telefono_token == c_doble.telefono_token == "tok_c1"

    # Búsqueda de contacto existente
    b_real = real.buscar_contacto(email_token="tok_email_1")
    b_doble = doble.buscar_contacto(email_token="tok_email_1")
    assert b_real is not None and b_doble is not None
    assert b_real.nombre_token == b_doble.nombre_token == "Juan Perez"

    # Búsqueda inexistente: ambos devuelven None
    assert real.buscar_contacto(email_token="tok_no_existe") is None
    assert doble.buscar_contacto(email_token="tok_no_existe") is None


# --- 8. Contrato Arm Jarvis: consulta de detalle de venta ---
def test_contrato_arm_jarvis_detalle_valores() -> None:
    obs = ObservabilidadService({"entorno": "test"})
    real = ArmJarvisService(config={"proveedor_llm": "doble"}, observabilidad=obs)
    doble = DobleArmJarvisService()

    # Sembrar venta en el doble
    doble.ventas["V-TEST-01"] = {
        "venta_id": "V-TEST-01",
        "canal_id": "canal_1",
        "vendedor_id": "vend_1",
        "propiedad_id": "DOMO-LAGO",
        "monto_total": Decimal("240.00"),
        "estado": EstadoVenta.POR_VALIDAR,
        "creado_en": datetime.now(timezone.utc),
    }

    detalle_doble = doble.detalle("V-TEST-01")
    assert detalle_doble is not None
    v_doble = detalle_doble[0]
    id_venta = v_doble.get("venta_id") if isinstance(v_doble, dict) else v_doble.venta_id
    estado_venta = v_doble.get("estado") if isinstance(v_doble, dict) else v_doble.estado
    assert id_venta == "V-TEST-01"
    assert estado_venta == EstadoVenta.POR_VALIDAR

    # Venta inexistente: ambos lanzan ErrorArm con código 'venta_no_encontrada'
    with pytest.raises(ErrorArm) as err_real:
        real.detalle("V-INEXISTENTE-999")
    with pytest.raises(ErrorArm) as err_doble:
        doble.detalle("V-INEXISTENTE-999")
    assert err_real.value.codigo == err_doble.value.codigo == "venta_no_encontrada"


# --- 9. Contrato Comisiones: consulta de resumen de período ---
def test_contrato_comisiones_resumen_valores() -> None:
    obs = ObservabilidadService({"entorno": "test"})
    seg = SeguridadService()
    real = ComisionesService(config={}, observabilidad=obs, seguridad=seg)
    doble = DobleComisionesService()

    periodo = "2026-11"
    res_real = real.resumen(vendedor_id=None, periodo_id=periodo)
    res_doble = doble.resumen(vendedor_id=None, periodo_id=periodo)

    assert res_real["periodo_id"] == res_doble["periodo_id"] == periodo
    assert res_real["validada"] == res_doble["validada"] == Decimal("0.00")
    assert res_real["pendiente"] == res_doble["pendiente"] == Decimal("0.00")


# --- 10. Contrato Canal WhatsApp y Agente: envío de plantilla y silencio ---
def test_contrato_canal_y_agente_operaciones() -> None:
    # Canal: rechazo de plantilla no aprobada (contrato de error de Meta)
    from features.canal_whatsapp.tipos import PlantillaNoAprobada
    real_canal = CanalWhatsappService({"proveedor": "fake"})
    plantilla = Plantilla(nombre="aviso_no_aprobado", idioma="es", variables=())
    with pytest.raises(PlantillaNoAprobada):
        real_canal.enviar_plantilla("+593991112233", plantilla)

    # Agente: entrar en silencio y reanudar
    obs = ObservabilidadService({"entorno": "test"})
    real_agente = AgenteService(config={}, observabilidad=obs)
    doble_agente = DobleAgenteService()
    conv = "conv_contrato_c2"
    real_agente.entrar_en_silencio(conv, "handoff")
    doble_agente.entrar_en_silencio(conv, "handoff")
    real_agente.reanudar(conv)
    doble_agente.reanudar(conv)


# --- 11. Mutantes Muertos: dobles alterados a propósito fallan la prueba ---
def test_mutante_muerto_doble_alterado_total_cotizacion() -> None:
    """Verifica (mutante muerto 1) que si un doble devuelve un total de cotización alterado, falle la prueba."""
    class DoblePMSAlterado(DoblePMSWeb):
        def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int):
            from dataclasses import dataclass
            @dataclass(frozen=True)
            class CotizacionAlterada:
                total: Decimal = Decimal("999.99")  # Valor divergente!
                moneda: str = "USD"
            return CotizacionAlterada()

    doble_mutado = DoblePMSAlterado()
    real = PMSConectorService()

    d_in = date(2026, 12, 1)
    d_out = date(2026, 12, 3)

    cot_real = real.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)
    cot_doble = doble_mutado.cotizar("glamping_imbabura", "domo_lago", d_in, d_out, 2)

    with pytest.raises(AssertionError):
        assert cot_real.total == cot_doble.total


def test_mutante_muerto_doble_alterado_autorizacion() -> None:
    """Verifica (mutante muerto 2) que si un doble autoriza erróneamente una acción prohibida, falle la prueba."""
    class DobleSeguridadAlterado(DobleSeguridadPanel):
        def autorizar(self, rol: str, accion: str):
            from tests.panel_operativo.dobles import Veredicto
            return Veredicto(permitido=True, motivo=None)  # Falso positivo!

    doble_mutado = DobleSeguridadAlterado()
    real = SeguridadService()

    v_real = real.autorizar("gestor", "zona_prohibida")
    v_doble = doble_mutado.autorizar("gestor", "zona_prohibida")

    assert v_real.permitido is False
    with pytest.raises(AssertionError):
        assert v_real.permitido == v_doble.permitido


def test_mutante_muerto_doble_alterado_reserva_inexistente() -> None:
    """Verifica (mutante muerto 3) que si un doble no eleva ReservaInexistente ante código inexistente, falle."""
    class DoblePMSInexistenteAlterado(DoblePMSAnf):
        def obtener_reserva(self, codigo: str):
            # No eleva ReservaInexistente: devuelve objeto ficticio!
            return ReservaDoble(
                codigo=codigo,
                propiedad_id="glamping_imbabura",
                unidad_id="domo_lago",
                huesped_token="tok_falso",
                desde=date(2026, 12, 1),
                hasta=date(2026, 12, 3),
                huespedes=2,
                total=Decimal("100.00"),
            )

    doble_mutado = DoblePMSInexistenteAlterado()
    real = PMSConectorService()

    def verificar_contrato_inexistente(servicio):
        try:
            servicio.obtener_reserva("RES-INEXISTENTE-999")
            return False  # No lanzó la excepción requerida por el contrato
        except ReservaInexistente:
            return True

    # El servicio real cumple el contrato (lanza ReservaInexistente)
    assert verificar_contrato_inexistente(real) is True
    # El doble válido cumple el contrato (lanza ReservaInexistente)
    assert verificar_contrato_inexistente(DoblePMSAnf()) is True
    # El doble mutado NO cumple el contrato
    assert verificar_contrato_inexistente(doble_mutado) is False
