"""Árbitro de INV_PANEL_SIN_LOGICA y RF-PAN-03.

Verifica por AST que la sala panel_operativo no contiene cálculos de negocio propios
y comprueba el escenario de desglose de comisión sirviendo directamente los datos del servidor.
"""
from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import DobleCanalWhatsappService, DobleComisionesService, DobleSeguridadService

SALA_PANEL = Path(__file__).resolve().parent.parent.parent / "features" / "panel_operativo"


def test_inv_panel_sin_logica_por_ast() -> None:
    # Recorre todos los archivos Python de la sala panel_operativo
    archivos = list(SALA_PANEL.glob("*.py"))
    assert len(archivos) >= 3, "Deben existir panel_operativo_service.py, sesiones_internal.py, bff_internal.py, etc."

    nombres_prohibidos = {"calcular_comision", "aplicar_descuento", "calcular_impuesto", "liquidar_periodo"}

    for archivo in archivos:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=archivo.name)
        for nodo in ast.walk(arbol):
            # No deben definirse funciones de cálculo contable o negocio
            if isinstance(nodo, ast.FunctionDef):
                assert nodo.name not in nombres_prohibidos, f"Función de negocio prohibida en {archivo.name}: {nodo.name}"

            # Verificación de que no haya fórmulas aritméticas de comisiones o porcentajes en el panel
            if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Mult):
                # Si multiplica, verificar que no sea una constante decimal de comisión/porcentaje
                if isinstance(nodo.right, ast.Constant) and isinstance(nodo.right.value, (float, int)):
                    assert nodo.right.value not in {0.05, 0.10, 0.15, 0.20}, (
                        f"Multiplicación de comisión sospechosa en {archivo.name}:{nodo.lineno}"
                    )


def test_desglose_comision_servido_sin_calculo_propio() -> None:
    # Dado una comisión escalonada fijada servida por comisiones
    config = dict(cargar_config())
    seguridad = DobleSeguridadService()
    canal = DobleCanalWhatsappService()
    comisiones = DobleComisionesService()

    servicio = PanelOperativoService(
        config,
        seguridad=seguridad,
        canal=canal,
        comisiones=comisiones,
    )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión como líder
    servicio.solicitar_codigo("lider@glamping.ec")
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp_login = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo})
    assert resp_login.status_code == 200

    # Cuando el líder abre el detalle de comisión
    resp = client.get("/panel/api/comisiones/V-2026-001/desglose")
    assert resp.status_code == 200
    datos = resp.json()

    # Entonces ve regla, versión, modo, acumulado y tramos servidos por el servidor
    assert datos["regla"] == "Regla Depa Centro"
    assert datos["version"] == 3
    assert datos["modo"] == "por_tramos"
    assert "tramos" in datos
    assert len(datos["tramos"]) == 2

    # Y la suma de los tramos servidos coincide con el total sin recalcular
    suma_tramos = sum(Decimal(str(t["comision"])) for t in datos["tramos"])
    total_fijado = Decimal(str(datos["total_comision"]))
    assert suma_tramos == total_fijado
