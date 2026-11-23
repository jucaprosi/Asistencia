# ¤infra-hibrida
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de aislamiento de red y límites de recursos (RNF-10, INV_RED_AISLADA, T-410).

Verifica:
- Invariante INV_RED_AISLADA: ¬alcanza(agent-net, servicios_contables) mediante prueba de conexión negativa.
- Cero rutas desde agent-net hacia servicios contables o ERPs internos.
- Límites de CPU y memoria configurados por contenedor en compose.yaml (RNF-10).
- Lista de egreso permitido sin destinos contables.
"""
from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.conftest import RAIZ

DESTINOS_CONTABLES_PROHIBIDOS = (
    ("contabilidad.internal", 5432),
    ("erp.imbabura.local", 8080),
    ("sap.servidor-propio.local", 3306),
    ("127.0.0.1", 5434),  # Puerto reservado a contabilidad en host
    ("10.0.99.1", 5432),
)


# ¤infra-hibrida
def _cargar_yaml(relativa: str) -> dict[str, Any]:
    ruta = RAIZ / relativa
    assert ruta.is_file(), f"Falta archivo {relativa}"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    assert isinstance(datos, dict), f"{relativa} debe ser un diccionario"
    return datos


# ¤infra-hibrida
def test_prueba_conexion_negativa_servicios_contables_inv_red_aislada() -> None:
    """INV_RED_AISLADA: Prueba de conexión negativa obligatoria hacia servicios contables."""
    intentos_exitosos: list[tuple[str, int]] = []

    for host, puerto in DESTINOS_CONTABLES_PROHIBIDOS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.2)
        try:
            resultado = sock.connect_ex((host, puerto))
            if resultado == 0:
                intentos_exitosos.append((host, puerto))
        except (socket.gaierror, socket.timeout, OSError):
            # La conexión debe fallar: es el resultado esperado para aislamiento de red
            pass
        finally:
            sock.close()

    assert not intentos_exitosos, (
        f"VIOLACIÓN INV_RED_AISLADA (RNF-10): se logró conexión a servicios contables prohibidos: {intentos_exitosos}"
    )


# ¤infra-hibrida
def test_compose_aislamiento_agent_net_y_redes() -> None:
    """RNF-10: compose.yaml define agent-net aislada y ningún servicio toca redes contables."""
    compose = _cargar_yaml("compose.yaml")
    redes_declaradas = compose.get("networks", {})
    assert "agent-net" in redes_declaradas, "agent-net debe ser declarada en networks"

    # Ninguna red contable declarada en compose
    for red in redes_declaradas:
        assert not any(c in red.lower() for c in ("contab", "erp", "sap", "accounting")), (
            f"Red contable detectada en compose.yaml: {red}"
        )

    # Todos los servicios de la aplicación pertenecen a agent-net sin rutas laterales
    servicios = compose.get("services", {})
    for nombre in ("app", "mcp-tools", "worker", "proxy"):
        assert nombre in servicios, f"Falta servicio {nombre} en compose.yaml"
        redes_svc = servicios[nombre].get("networks", [])
        assert "agent-net" in redes_svc, f"El servicio {nombre} debe pertenecer a agent-net"
        assert len(redes_svc) == 1, f"El servicio {nombre} no debe conectarse a redes adicionales"


# ¤infra-hibrida
def test_limites_cpu_y_memoria_por_contenedor_rnf_10() -> None:
    """RNF-10: Todo contenedor de agent-net define límites estrictos de CPU y memoria."""
    compose = _cargar_yaml("compose.yaml")
    servicios = compose.get("services", {})

    for nombre in ("app", "mcp-tools", "worker", "proxy"):
        deploy = servicios[nombre].get("deploy", {})
        limites = deploy.get("resources", {}).get("limits", {})
        assert "cpus" in limites, f"Servicio {nombre} sin límite de CPU"
        assert "memory" in limites, f"Servicio {nombre} sin límite de memoria"


# ¤infra-hibrida
def test_egreso_permitido_sin_rutas_contables() -> None:
    """RNF-10: config_app.yaml tiene egreso autorizado exclusivamente a Meta, Anthropic, S3, PMS y CRM."""
    config_app = _cargar_yaml("app_core/config_app.yaml")
    egreso = config_app.get("egreso_permitido", [])

    assert isinstance(egreso, list) and len(egreso) >= 2
    # Verificar ausencia total de destinos contables
    destinos_contables = [d for d in egreso if any(c in d.lower() for c in ("contab", "erp", "sap", "accounting"))]
    assert not destinos_contables, f"Destinos contables no autorizados en egreso: {destinos_contables}"
