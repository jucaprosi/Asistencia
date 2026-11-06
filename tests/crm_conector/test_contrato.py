# ¤crm-conector
# ¤¤integration-engineer
"""Prueba de contrato de CRMConnector parametrizada para cualquier proveedor (RF-CRM-01)."""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

import pytest

from features.crm_conector.base_internal import CRMConnector
from features.crm_conector.fake_internal import FakeCRM
from features.crm_conector.tipos import (
    Contacto,
    ContactoDuplicado,
    Oportunidad,
    OportunidadInexistente,
    PublicacionVenta,
)
from tests.crm_conector.dobles import DobleCRMAlternativo


# ¤crm-conector
@pytest.fixture(params=[FakeCRM, DobleCRMAlternativo])
def conector(request: pytest.FixtureRequest) -> CRMConnector:
    fabrica: Callable[[], CRMConnector] = request.param
    return fabrica()


# ¤crm-conector
def test_contrato_buscar_contacto_devuelve_tipo_dominio(conector: CRMConnector) -> None:
    # Caso 1: contacto inexistente
    res = conector.buscar_contacto(telefono_token="no_existe")
    assert res is None

    # Caso 2: crear y buscar
    c = Contacto(
        contacto_id="c_test_01",
        nombre_token="tok_nom",
        telefono_token="tok_tel_12345",
        email_token="tok_em_12345@glamping.ec",
    )
    creado = conector.crear_contacto(c)
    assert isinstance(creado, Contacto)
    assert creado.contacto_id == "c_test_01"
    assert creado.telefono_token == "tok_tel_12345"

    encontrado = conector.buscar_contacto(telefono_token="tok_tel_12345")
    assert isinstance(encontrado, Contacto)
    assert encontrado.contacto_id == "c_test_01"

    encontrado_em = conector.buscar_contacto(email_token="tok_em_12345@glamping.ec")
    assert isinstance(encontrado_em, Contacto)
    assert encontrado_em.contacto_id == "c_test_01"


# ¤crm-conector
def test_contrato_crear_contacto_rechaza_duplicados(conector: CRMConnector) -> None:
    c = Contacto(
        contacto_id="c_dup_01",
        nombre_token="tok_nom",
        telefono_token="tok_tel_dup",
    )
    conector.crear_contacto(c)

    # Reintentar mismo id o teléfono debe lanzar ContactoDuplicado
    with pytest.raises(ContactoDuplicado):
        conector.crear_contacto(c)


# ¤crm-conector
def test_contrato_ciclo_oportunidad(conector: CRMConnector) -> None:
    op = Oportunidad(
        oportunidad_id="op_test_01",
        contacto_id="c_test_01",
        propiedad_id="glamping_imbabura",
        etapa="Por validar",
        monto=Decimal("200.00"),
    )
    creada = conector.crear_oportunidad(op)
    assert isinstance(creada, Oportunidad)
    assert creada.oportunidad_id == "op_test_01"
    assert creada.etapa == "Por validar"
    assert creada.monto == Decimal("200.00")

    # Actualizar etapa y monto
    actualizada = conector.actualizar_oportunidad(
        "op_test_01",
        {"etapa": "Validada", "monto": Decimal("250.00")},
    )
    assert isinstance(actualizada, Oportunidad)
    assert actualizada.etapa == "Validada"
    assert actualizada.monto == Decimal("250.00")


# ¤crm-conector
def test_contrato_actualizar_oportunidad_inexistente_falla(conector: CRMConnector) -> None:
    with pytest.raises(OportunidadInexistente):
        conector.actualizar_oportunidad("no_existe", {"etapa": "Validada"})


# ¤crm-conector
def test_contrato_publicar_venta_y_anulacion(conector: CRMConnector) -> None:
    venta = {"venta_id": "v_123", "monto": "150.00", "cliente": "tok_cliente"}
    pub_v = conector.publicar_venta(venta)
    assert isinstance(pub_v, PublicacionVenta)
    assert pub_v.venta_id == "v_123"
    assert pub_v.estado == "ok"

    pub_a = conector.publicar_anulacion(venta)
    assert isinstance(pub_a, PublicacionVenta)
    assert pub_a.venta_id == "v_123"
    assert pub_a.estado == "ok"


# ¤crm-conector
def test_contrato_enviar_mensaje(conector: CRMConnector) -> None:
    msg_id = conector.enviar_mensaje("conv_100", "Hola desde el panel.")
    assert isinstance(msg_id, str)
    assert len(msg_id) > 0
