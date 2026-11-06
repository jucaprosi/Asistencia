# ¤herramientas-mcp
# ¤¤backend-developer
"""Pruebas del servidor MCP de herramientas_glamping (transporte stdio y JSON-RPC 2.0)."""
from __future__ import annotations

import io
import json
from typing import Any

import pytest

from features.herramientas_glamping.herramientas_glamping_service import (
    HerramientasGlampingService,
    cargar_config,
)
from features.herramientas_glamping.server import (
    ejecutar_stdio,
    procesar_mensaje_jsonrpc,
)
from features.seguridad.tipos import Identidad, Rol
from tests.herramientas_glamping.test_contratos import (
    DobleCRM,
    DoblePMS,
    DobleSeguridad,
)


# ¤herramientas-mcp
@pytest.fixture
def servicio_mcp() -> HerramientasGlampingService:
    config = dict(cargar_config())
    return HerramientasGlampingService(
        config=config,
        seguridad=DobleSeguridad(),
        pms=DoblePMS(),
        conocimiento=None,
        crm=DobleCRM(),
    )


# ¤herramientas-mcp
def test_jsonrpc_initialize(servicio_mcp: HerramientasGlampingService) -> None:
    peticion = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {},
    }
    resp = procesar_mensaje_jsonrpc(peticion, servicio_mcp)
    assert resp is not None
    assert resp["id"] == 1
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in resp["result"]["capabilities"]
    assert resp["result"]["serverInfo"]["name"] == "herramientas_glamping"


# ¤herramientas-mcp
def test_jsonrpc_ping(servicio_mcp: HerramientasGlampingService) -> None:
    peticion = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "ping",
    }
    resp = procesar_mensaje_jsonrpc(peticion, servicio_mcp)
    assert resp is not None
    assert resp["id"] == 2
    assert resp["result"] == {}


# ¤herramientas-mcp
def test_jsonrpc_tools_list(servicio_mcp: HerramientasGlampingService) -> None:
    peticion = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {"rol": "huesped_activo"},
    }
    resp = procesar_mensaje_jsonrpc(peticion, servicio_mcp)
    assert resp is not None
    assert resp["id"] == 3
    tools = resp["result"]["tools"]
    nombres = [t["name"] for t in tools]
    assert "consultar_disponibilidad" in nombres
    assert "obtener_instrucciones_checkin" in nombres


# ¤herramientas-mcp
def test_jsonrpc_tools_call_exitoso(servicio_mcp: HerramientasGlampingService) -> None:
    identidad = Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL)
    peticion = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "consultar_disponibilidad",
            "arguments": {
                "propiedad_id": "prop_1",
                "desde": "2026-11-10",
                "hasta": "2026-11-12",
                "huespedes": 2,
            },
            "identidad": identidad,
            "conversacion_id": "c_rpc",
        },
    }
    resp = procesar_mensaje_jsonrpc(peticion, servicio_mcp)
    assert resp is not None
    assert resp["id"] == 4
    assert resp["result"]["isError"] is False
    contenido = json.loads(resp["result"]["content"][0]["text"])
    assert contenido["disponible"] is True


# ¤herramientas-mcp
def test_jsonrpc_tools_call_error_entrada(servicio_mcp: HerramientasGlampingService) -> None:
    identidad = Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL)
    peticion = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "consultar_disponibilidad",
            "arguments": {
                "propiedad_id": "prop_1",
                # faltan desde y hasta
            },
            "identidad": identidad,
            "conversacion_id": "c_rpc",
        },
    }
    resp = procesar_mensaje_jsonrpc(peticion, servicio_mcp)
    assert resp is not None
    assert resp["id"] == 5
    assert resp["result"]["isError"] is True
    assert "entrada_invalida" in resp["result"]["content"][0]["text"]


# ¤herramientas-mcp
def test_jsonrpc_metodo_desconocido(servicio_mcp: HerramientasGlampingService) -> None:
    peticion = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "metodo_inexistente",
    }
    resp = procesar_mensaje_jsonrpc(peticion, servicio_mcp)
    assert resp is not None
    assert resp["id"] == 6
    assert resp["error"]["code"] == -32601


# ¤herramientas-mcp
def test_ejecutar_stdio(servicio_mcp: HerramientasGlampingService) -> None:
    lineas_in = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "initialize"}) + "\n"
    )
    stream_in = io.StringIO(lineas_in)
    stream_out = io.StringIO()

    ejecutar_stdio(servicio_mcp, stream_in, stream_out)

    respuestas = [json.loads(linea) for linea in stream_out.getvalue().strip().split("\n")]
    assert len(respuestas) == 2
    assert respuestas[0]["id"] == 1
    assert respuestas[0]["result"] == {}
    assert respuestas[1]["id"] == 2
    assert respuestas[1]["result"]["protocolVersion"] == "2024-11-05"
