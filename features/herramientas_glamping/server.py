# ¤herramientas-mcp
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Servidor MCP para la sala herramientas_glamping (soporta transporte stdio y http)."""
from __future__ import annotations

import json
import sys
from typing import Any, Mapping, TextIO

from features.herramientas_glamping.herramientas_glamping_service import (
    ErrorHerramientas,
    HerramientasGlampingService,
    cargar_config,
)

__all__ = [
    "procesar_mensaje_jsonrpc",
    "ejecutar_stdio",
    "main",
]


# ¤herramientas-mcp
def procesar_mensaje_jsonrpc(
    mensaje: Mapping[str, Any],
    service: HerramientasGlampingService,
    identidad: Any = "sistema",
    conversacion_id: str = "mcp_rpc",
) -> dict[str, Any] | None:
    """Procesa una petición o notificación JSON-RPC 2.0 según el estándar Model Context Protocol (MCP)."""
    msg_id = mensaje.get("id")
    metodo = mensaje.get("method")
    params = mensaje.get("params") or {}

    # Notificaciones (sin id)
    if msg_id is None:
        return None

    if mensaje.get("jsonrpc") != "2.0":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32600, "message": "Petición JSON-RPC inválida; se requiere jsonrpc='2.0'"},
        }

    if metodo == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "herramientas_glamping",
                    "version": "0.1.0",
                },
            },
        }

    if metodo == "ping":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {},
        }

    if metodo == "tools/list":
        # Se listan las herramientas habilitadas para el rol
        rol_consulta = params.get("rol", "huesped_activo")
        herramientas = service.listar(rol=rol_consulta)
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": h.nombre,
                        "description": h.descripcion,
                        "inputSchema": h.esquema_entrada,
                    }
                    for h in herramientas
                ]
            },
        }

    if metodo == "tools/call":
        nombre_h = params.get("name")
        argumentos = params.get("arguments") or {}
        id_llamada = params.get("identidad", identidad)
        conv_id = params.get("conversacion_id", conversacion_id)

        try:
            res = service.ejecutar(
                nombre=str(nombre_h),
                entrada=argumentos,
                identidad=id_llamada,
                conversacion_id=conv_id,
            )
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(res.salida, ensure_ascii=False),
                        }
                    ],
                    "isError": False,
                },
            }
        except ErrorHerramientas as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"{exc.codigo}: {exc.mensaje_usuario}",
                        }
                    ],
                    "isError": True,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"error_inesperado: {exc}",
                        }
                    ],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Método no encontrado: '{metodo}'"},
    }


# ¤herramientas-mcp
def ejecutar_stdio(
    service: HerramientasGlampingService,
    entrada: TextIO = sys.stdin,
    salida: TextIO = sys.stdout,
) -> None:
    """Bucle de transporte stdio línea por línea JSON-RPC."""
    for linea in entrada:
        linea = linea.strip()
        if not linea:
            continue
        try:
            peticion = json.loads(linea)
            respuesta = procesar_mensaje_jsonrpc(peticion, service)
            if respuesta is not None:
                salida.write(json.dumps(respuesta, ensure_ascii=False) + "\n")
                salida.flush()
        except json.JSONDecodeError:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Error al parsear JSON"},
            }
            salida.write(json.dumps(error_resp, ensure_ascii=False) + "\n")
            salida.flush()


# ¤herramientas-mcp
def main() -> int:
    config = cargar_config()
    transporte = config.get("transporte", "stdio")
    herramientas = [h.get("nombre") for h in config.get("herramientas", [])]
    print(
        f"servidor MCP herramientas_glamping: transporte={transporte} "
        f"herramientas_declaradas={len(herramientas)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
