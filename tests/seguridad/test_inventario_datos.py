# ¤seguridad-canal
# ¤¤security-engineer
"""Pruebas de completitud del inventario de datos y encargados (RF-PRIV-02, RF-PRIV-06, RNF-18)."""
from __future__ import annotations

from pathlib import Path
import pytest

RUTA_INVENTARIO = Path(__file__).resolve().parent.parent.parent / "docs" / "privacidad" / "INVENTARIO.md"


def test_inventario_completo_tablas_con_datos_personales_y_encargados() -> None:
    """Escenario: Inventario completo (@RF-PRIV-02 @RF-PRIV-06).
    
    Dado una tabla con datos personales o un proveedor que los recibe
    Cuando corre la verificación
    Entonces debe constar en docs/privacidad/INVENTARIO.md
    """
    assert RUTA_INVENTARIO.is_file(), f"Falta el archivo de inventario en {RUTA_INVENTARIO}"
    contenido = RUTA_INVENTARIO.read_text(encoding="utf-8")

    # 1. Todas las tablas de seguridad con datos personales deben estar inventariadas
    tablas_requeridas = [
        "seguridad.usuarios",
        "seguridad.huespedes",
        "seguridad.bloqueos",
        "seguridad.boveda_tokens",
        "seguridad.rate_limit",
        "seguridad.consentimientos",
        "seguridad.solicitudes_titular",
        "seguridad.audit_log",
    ]
    for tabla in tablas_requeridas:
        assert tabla in contenido, f"La tabla {tabla} no consta en {RUTA_INVENTARIO.name}"

    # 2. Cada tratamiento debe declarar finalidad, base jurídica, ubicación y retención
    secciones_clave = [
        "Finalidad",
        "Base Jurídica",
        "Ubicación",
        "Retención",
        "Medidas de Seguridad",
    ]
    for sec in secciones_clave:
        assert sec in contenido, f"Falta la columna/sección de {sec} en el inventario"

    # 3. Proveedores y encargados (RF-PRIV-06)
    encargados_requeridos = [
        "Meta Platforms",
        "Anthropic",
        "PMS",
        "CRM",
    ]
    for encargado in encargados_requeridos:
        assert encargado in contenido, f"El encargado {encargado} no consta en el inventario de privacidad"

    # 4. Cumplimiento LOPDP y Derechos del Titular (ARCOP)
    assert "LOPDP" in contenido
    assert "ARCOP" in contenido
