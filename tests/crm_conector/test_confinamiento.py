# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tests de confinamiento ADPA y pureza de tipos para la sala crm_conector."""
from __future__ import annotations

import ast
from pathlib import Path

from features.crm_conector.crm_conector_service import CRMConectorService, cargar_config


# ¤crm-conector
def test_sin_imports_privados_de_otras_salas() -> None:
    raiz_features = Path(__file__).resolve().parent.parent.parent / "features"
    carpeta_crm = raiz_features / "crm_conector"

    violaciones: list[str] = []
    for ruta in carpeta_crm.rglob("*.py"):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            modulo = ""
            if isinstance(nodo, ast.Import):
                for alias in nodo.names:
                    modulo = alias.name
            elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                modulo = nodo.module

            if modulo.startswith("features."):
                partes = modulo.split(".")
                if len(partes) >= 2:
                    sala_destino = partes[1]
                    if sala_destino != "crm_conector":
                        if len(partes) < 3 or not partes[2].endswith("_service"):
                            violaciones.append(f"{ruta.name} importa {modulo}")

    assert not violaciones, f"Violaciones de confinamiento ADPA: {violaciones}"


# ¤crm-conector
def test_configuracion_contiene_campos_requeridos() -> None:
    cfg = cargar_config()
    campos_requeridos = {
        "proveedor",
        "admin_id",
        "contacto_humano_escalamiento",
        "bandeja_handoff_activa",
        "minutos_estimados_atencion",
        "tiempo_limite_sin_tomar_minutos",
        "tiempo_limite_abandono_horas",
    }
    assert campos_requeridos <= set(cfg.keys())


# ¤crm-conector
def test_crm_conector_service_expone_interfaz_completa() -> None:
    metodos_requeridos = [
        "buscar_contacto",
        "crear_contacto",
        "crear_oportunidad",
        "actualizar_oportunidad",
        "publicar_venta",
        "publicar_anulacion",
        "enviar_mensaje",
        "solicitar_handoff",
        "solicitar_humano",
        "tomar_handoff",
        "devolver_al_asistente",
        "revisar_plazos_handoffs",
        "registrar_receptor",
    ]
    for metodo in metodos_requeridos:
        assert hasattr(CRMConectorService, metodo), f"Falta método {metodo} en CRMConectorService"
