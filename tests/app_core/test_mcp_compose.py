# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del servicio MCP en compose, egreso y paso de semilla sintética del RAG (T-210, RNF-10, RNF-14)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from app_core.app_core_service import construir
from features.herramientas_glamping.server import main as mcp_server_main, procesar_mensaje_jsonrpc
from scripts.arnes_glamping import ejecutar_semilla_rag, verificar_egreso
from tests.conftest import RAIZ

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "x",
    "META_VERIFY_TOKEN": "x",
    "META_APP_SECRET": "x",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


# ¤pasillo-central
def _cargar_yaml(nombre: str) -> dict[str, Any]:
    ruta = RAIZ / nombre
    assert ruta.is_file(), f"Falta archivo {nombre}"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    assert isinstance(datos, dict), f"{nombre} debe ser un diccionario"
    return datos


# ¤pasillo-central
def test_mcp_tools_declarado_y_configurado_en_compose() -> None:
    """Verifica que el servicio mcp-tools esté declarado en compose.yaml con límites y comando correcto (RNF-10, RNF-14)."""
    base = _cargar_yaml("compose.yaml")
    assert "mcp-tools" in base["services"], "mcp-tools debe existir en services de compose.yaml"

    servicio = base["services"]["mcp-tools"]
    assert servicio.get("image") == "glamping-imbabura-agent:local"
    assert servicio.get("command") == ["python", "-m", "features.herramientas_glamping.server"]
    assert servicio.get("networks") == ["agent-net"]
    assert servicio.get("env_file") == ".env"

    # Límites de CPU y RAM obligatorios (RNF-10)
    limites = servicio.get("deploy", {}).get("resources", {}).get("limits", {})
    assert "cpus" in limites and "memory" in limites, "mcp-tools debe declarar límites de cpus y memory"

    # Healthcheck para verificar operatividad
    healthcheck = servicio.get("healthcheck", {})
    assert "test" in healthcheck, "mcp-tools debe declarar healthcheck"


# ¤pasillo-central
def test_mcp_tools_operativo_en_jsonrpc_y_main() -> None:
    """Comprueba que el servidor MCP herramientas_glamping es ejecutable y responde peticiones JSON-RPC."""
    # 1. Ejecución del punto de entrada principal (main)
    assert mcp_server_main() == 0

    # 2. Protocolo JSON-RPC con compuerta instanciada por el contenedor de app_core
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    svc = contenedor.herramientas
    resp_init = procesar_mensaje_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, svc)
    assert resp_init is not None
    assert resp_init.get("jsonrpc") == "2.0"
    assert "tools" in resp_init.get("result", {}).get("capabilities", {})

    # 3. Protocolo JSON-RPC: tools/list
    resp_tools = procesar_mensaje_jsonrpc(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"rol": "huesped_potencial"}},
        svc,
    )
    assert resp_tools is not None
    herramientas = resp_tools.get("result", {}).get("tools", [])
    assert len(herramientas) > 0
    nombres = [h["name"] for h in herramientas]
    assert "consultar_disponibilidad" in nombres or "cotizar" in nombres


# ¤pasillo-central
def test_aislamiento_de_red_sin_rutas_contables_rnf_10() -> None:
    """Verifica 0 rutas de red desde agent-net a servicios contables (RNF-10)."""
    base = _cargar_yaml("compose.yaml")

    # Las redes declaradas son únicamente agent-net y glamping-beta-net
    redes_declaradas = set(base.get("networks", {}).keys())
    assert redes_declaradas == {"agent-net", "glamping-beta-net"}

    # Ningún servicio en agent-net tiene acceso a servicios contables
    for nombre, svc in base["services"].items():
        redes = svc.get("networks", [])
        assert not any("contab" in r.lower() or "erp" in r.lower() for r in redes), (
            f"El servicio {nombre} tiene rutas de red contables prohibidas por RNF-10"
        )


# ¤pasillo-central
def test_portabilidad_mcp_tools_en_produccion_rnf_14() -> None:
    """El mismo compose.yaml + compose.production.yaml levanta en beta y producción (RNF-14)."""
    base = _cargar_yaml("compose.yaml")
    produccion = _cargar_yaml("compose.production.yaml")

    assert "mcp-tools" in produccion["services"]
    prod_mcp = produccion["services"]["mcp-tools"]
    assert prod_mcp.get("restart") == "always"
    assert "logging" in prod_mcp, "Producción debe endurecer logging en mcp-tools"


# ¤pasillo-central
def test_lista_egreso_contiene_pms_y_embeddings_y_cero_contabilidad() -> None:
    """Verifica que config_app.yaml declare lista de egreso con PMS, embeddings y 0 destinos contables (RNF-10)."""
    cfg_app = _cargar_yaml("app_core/config_app.yaml")
    egreso = cfg_app.get("egreso_permitido", [])

    assert isinstance(egreso, list) and len(egreso) >= 2, "egreso_permitido debe ser lista con destinos"

    # PMS presente
    tiene_pms = any("pms" in d.lower() for d in egreso)
    assert tiene_pms, "La lista de egreso debe contener el destino del PMS"

    # Embeddings / proveedor de modelo presente
    tiene_embeddings = any("aiplatform" in d.lower() or "embedding" in d.lower() for d in egreso)
    assert tiene_embeddings, "La lista de egreso debe contener el destino de embeddings / modelo IA"

    # RNF-10: 0 destinos contables
    destinos_contables = [d for d in egreso if any(c in d.lower() for c in ("contab", "erp", "sap", "accounting"))]
    assert not destinos_contables, f"Lista de egreso no debe incluir destinos contables: {destinos_contables}"

    # Verificación directa de la función del arnés
    codigo, mensaje = verificar_egreso()
    assert codigo == 0, f"verificar_egreso falló: {mensaje}"
    assert "destinos autorizados" in mensaje


# ¤pasillo-central
def test_arnes_incluye_paso_semilla_sintetica_rag() -> None:
    """Verifica que el arnés incluya el paso de semilla sintética del RAG y ejecute con éxito (T-210)."""
    import inspect
    from scripts import arnes_glamping

    codigo_fuente = inspect.getsource(arnes_glamping.main)
    assert "semilla_sintetica_rag" in codigo_fuente, "arnes_glamping.py debe incluir el paso 'semilla_sintetica_rag'"

    # Ejecución directa del paso de semilla sintética del RAG
    cod, out = ejecutar_semilla_rag()
    assert cod == 0, f"ejecutar_semilla_rag falló con código {cod}: {out}"
    assert "Indexación completada" in out or "APROBADA" in out
