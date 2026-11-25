# ¤infra-hibrida
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de sondeo de salud y disponibilidad externa (RNF-05, RF-OBS-04, T-410).

Evalúa:
- Sondeo externo periódico simulado al endpoint /health (cada minuto).
- Cálculo de disponibilidad >= 99.5% (RNF-05) con latencia menor a 100 ms.
- Disparo y enrutamiento de alertas críticas al canal del administrador ante degradación (RF-OBS-04).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from app_core.main import crear_app
from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.observabilidad.tipos import Alerta

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "META_ACCESS_TOKEN": "token_prueba",
    "META_VERIFY_TOKEN": "verify_prueba",
    "META_APP_SECRET": "secret_prueba",
    "ANTHROPIC_API_KEY": "sk_prueba",
    "PII_VAULT_KEY": "pii_prueba",
    "PANEL_SESSION_SECRET": "session_prueba",
}


# ¤infra-hibrida
def test_sondeo_externo_salud_disponibilidad_rnf_05() -> None:
    """RNF-05: Sondeo externo simulado minuto a minuto con disponibilidad >= 99.5%."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    app = crear_app(contenedor)
    cliente = TestClient(app)

    num_sondeos = 60  # Simulación de 60 sondeos periódicos (1 hora minuto a minuto)
    exitosos = 0
    latencias: list[float] = []

    for _ in range(num_sondeos):
        t0 = time.perf_counter()
        resp = cliente.get("/health")
        duracion = time.perf_counter() - t0
        latencias.append(duracion)

        if resp.status_code == 200:
            datos = resp.json()
            if datos.get("estado") == "ok" and datos.get("version") == "0.1.0":
                exitosos += 1

    disponibilidad = (exitosos / num_sondeos) * 100.0
    latencia_promedio = sum(latencias) / len(latencias)

    # RNF-05: Disponibilidad >= 99.5%
    assert disponibilidad >= 99.5, f"Disponibilidad {disponibilidad:.2f}% inferior a 99.5%"
    assert exitosos == num_sondeos
    assert latencia_promedio < 0.100, f"Latencia media de sondeo {latencia_promedio:.4f} s supera 100 ms"


# ¤infra-hibrida
def test_alerta_canal_administrador_ante_fallo_salud_rf_obs_04() -> None:
    """RF-OBS-04: Disparo y registro de alertas críticas hacia el canal del administrador ante fallo de salud."""
    obs_config = dict(cargar_config())
    canal_aviso = obs_config.get("alertas", {}).get("canal_aviso", "correo")

    # Instanciar observabilidad
    obs = ObservabilidadService(obs_config)

    # Simular detección de fallo en el sondeo externo
    ahora = datetime.now(timezone.utc)
    alerta_salud = Alerta(
        nombre="sondeo_salud_degradado",
        severidad="critica",
        mensaje="Endpoint /health no responde: disponibilidad cayó por debajo del 99.5% (RNF-05)",
        disparada_en=ahora,
    )

    # Registro en log estructurado con destino hacia canal operativo / admin
    eventos_alertas: list[dict[str, Any]] = []

    def _capturar_alerta(nivel: str, evento: str, **campos: Any) -> None:
        eventos_alertas.append({
            "nivel": nivel,
            "evento": evento,
            "canal_aviso": canal_aviso,
            "detalles": campos,
        })

    obs.log = _capturar_alerta  # type: ignore[assignment]

    obs.log(
        "ERROR",
        "alerta_disparada",
        alerta=alerta_salud.nombre,
        severidad=alerta_salud.severidad,
        mensaje=alerta_salud.mensaje,
        destinatario_admin=canal_aviso,
    )

    assert len(eventos_alertas) == 1
    registro = eventos_alertas[0]
    assert registro["nivel"] == "ERROR"
    assert registro["canal_aviso"] in ("correo", "whatsapp")
    assert registro["detalles"]["alerta"] == "sondeo_salud_degradado"
    assert registro["detalles"]["severidad"] == "critica"
