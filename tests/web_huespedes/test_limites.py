"""Árbitro de RF-WEB-05 e INV_WEB_LIMITE_POR_IP.

Verifica la protección de tasa por IP, respuesta 429 ante exceso, ausencia de llamadas al PMS
y almacenamiento exclusivo de la IP como hash HMAC.
"""
from __future__ import annotations

from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from features.web_huespedes.web_huespedes_service import WebHuespedesService, cargar_config


def test_exceso_de_consultas_recibe_429_y_pms_no_recibe_consultas() -> None:
    # Dado una IP que supera el límite por minuto
    pms_mock = MagicMock()
    config = dict(cargar_config())
    config["limites"] = {
        "por_ip_minuto": 3,
        "retencion_h": 24,
        "ip_hmac_secreto": "secreto_de_prueba_limites",
    }
    servicio = WebHuespedesService(config, pms=pms_mock)
    client = TestClient(servicio.crear_app())

    ip_atacante = "198.51.100.42"
    cabeceras = {"x-forwarded-for": ip_atacante}

    # Primeras 3 consultas permitidas
    for _ in range(3):
        resp = client.get("/", headers=cabeceras)
        assert resp.status_code == 200

    # Cuando sigue consultando y supera el límite
    resp_bloqueada = client.get("/", headers=cabeceras)

    # Entonces recibe 429 y el PMS no recibe esas consultas
    assert resp_bloqueada.status_code == 429
    assert "superado el límite" in resp_bloqueada.text
    pms_mock.assert_not_called()


def test_ip_se_guarda_solo_como_hash() -> None:
    # Dado el servicio ejecutando consultas
    config = dict(cargar_config())
    config["limites"] = {
        "por_ip_minuto": 10,
        "ip_hmac_secreto": "salt_auditoria_segura",
    }
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    ip_real = "203.0.113.88"
    client.get("/", headers={"x-forwarded-for": ip_real})

    # Cuando revisamos los registros de la tabla limites_ip
    filas = servicio._repositorio._con.execute("SELECT ip_hash FROM limites_ip").fetchall()
    assert len(filas) >= 1

    # Entonces la IP real nunca se guarda en texto plano; solo existe el hash HMAC
    for (ip_hash,) in filas:
        assert ip_real not in ip_hash
        assert len(ip_hash) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in ip_hash)


def test_sin_cookies_de_sesion_ni_cuentas() -> None:
    config = dict(cargar_config())
    servicio = WebHuespedesService(config)
    client = TestClient(servicio.crear_app())

    resp_inicio = client.get("/")
    assert "set-cookie" not in resp_inicio.headers

    resp_ficha = client.get("/propiedades/EJ-01")
    assert "set-cookie" not in resp_ficha.headers

    resp_contacto = client.post("/contacto", data={"propiedad_id": "EJ-01"}, follow_redirects=False)
    assert "set-cookie" not in resp_contacto.headers
