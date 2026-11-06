# ¤seguridad-canal
# ¤¤security-engineer
"""Pruebas unitarias de la allowlist de acciones por rol (RF-SEC-02, INV_ALLOWLIST_POR_ACCION)."""
from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from features.seguridad.seguridad_service import (
    AccionNoAutorizada,
    Rol,
    SeguridadService,
)
from tests.seguridad.dobles import DobleObservabilidad

RUTA_DOMINIO = Path(__file__).resolve().parent.parent.parent / "docs" / "spec" / "contratos" / "dominio.yaml"


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_mapa_allowlist_coincide_exactamente_con_dominio_yaml(servicio: SeguridadService) -> None:
    """Verifica que el mapa rol -> acciones permitidas es idéntico a dominio.yaml."""
    assert RUTA_DOMINIO.is_file(), f"No se encuentra dominio.yaml en {RUTA_DOMINIO}"
    contrato = yaml.safe_load(RUTA_DOMINIO.read_text(encoding="utf-8"))
    allowlist_dominio = contrato.get("allowlist", {})

    roles_esperados = [
        Rol.HUESPED_POTENCIAL,
        Rol.HUESPED_ACTIVO,
        Rol.VENDEDOR,
        Rol.LIDER,
        Rol.GESTOR,
        Rol.ADMINISTRADOR,
        Rol.ANFITRION,
        Rol.SISTEMA,
        Rol.DESCONOCIDO,
    ]

    for rol in roles_esperados:
        acciones_dominio = tuple(allowlist_dominio.get(rol.value, []))
        for accion in acciones_dominio:
            veredicto = servicio.autorizar(rol, accion)
            assert veredicto.permitido is True, f"Acción {accion} debería estar permitida para {rol.value}"


def test_huesped_potencial_rechaza_herramienta_prohibida(servicio: SeguridadService) -> None:
    """Escenario: El modelo pide una herramienta prohibida.
    
    Dado un huésped potencial
    Cuando el modelo solicita "registrar_venta"
    Entonces la compuerta rechaza con AccionNoAutorizada y no se ejecuta
    """
    rol = Rol.HUESPED_POTENCIAL
    herramienta_prohibida = "registrar_venta"

    # 1. Comprobación vía Veredicto
    veredicto = servicio.autorizar(rol, herramienta_prohibida)
    assert veredicto.permitido is False
    assert "AccionNoAutorizada" in (veredicto.motivo or "")

    # 2. Comprobación vía compuerta estricta / exigir_autorizacion
    with pytest.raises(AccionNoAutorizada):
        servicio.exigir_autorizacion(rol, herramienta_prohibida)

    with pytest.raises(AccionNoAutorizada):
        servicio.autorizar(rol, herramienta_prohibida, estricto=True)


def test_administrador_autorizado_con_comodin_universal(servicio: SeguridadService) -> None:
    """El administrador tiene comodín '*' y puede ejecutar cualquier acción."""
    veredicto_1 = servicio.autorizar(Rol.ADMINISTRADOR, "cualquier_herramienta_futura")
    assert veredicto_1.permitido is True

    veredicto_2 = servicio.autorizar(Rol.ADMINISTRADOR, "registrar_venta")
    assert veredicto_2.permitido is True


def test_diferencia_de_privilegios_entre_huesped_potencial_y_activo(servicio: SeguridadService) -> None:
    """Huésped activo puede obtener checkin y reportar incidencia; potencial no."""
    potencial = Rol.HUESPED_POTENCIAL
    activo = Rol.HUESPED_ACTIVO

    # Potencial rechazado
    assert servicio.autorizar(potencial, "obtener_instrucciones_checkin").permitido is False
    assert servicio.autorizar(potencial, "reportar_incidencia").permitido is False

    # Activo permitido
    assert servicio.autorizar(activo, "obtener_instrucciones_checkin").permitido is True
    assert servicio.autorizar(activo, "reportar_incidencia").permitido is True


def test_vendedor_solo_ejecuta_herramientas_comerciales_permitidas(servicio: SeguridadService) -> None:
    """El vendedor puede registrar ventas pero no validar ni acceder a comisiones de terceros."""
    assert servicio.autorizar(Rol.VENDEDOR, "registrar_venta").permitido is True
    assert servicio.autorizar(Rol.VENDEDOR, "consultar_comision_propia").permitido is True
    assert servicio.autorizar(Rol.VENDEDOR, "validar_venta").permitido is False
    assert servicio.autorizar(Rol.VENDEDOR, "ver_comisiones_todas").permitido is False
