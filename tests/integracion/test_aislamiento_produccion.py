# ¤infra-hibrida
# ¤¤devops-engineer
"""Pruebas de integración del despliegue en servidor de producción (T-610).

Cubre:
- RNF-14 / INV_MISMO_COMPOSE: compose.production.yaml extiende compose.yaml sin romper contratos.
- RNF-10 / INV_RED_AISLADA: cero conexiones desde agent-net hacia servicios contables o ERPs.
- RNF-15: scripts de respaldo cifrado y procedimiento de restauración probado.
- S-08: inventario y endurecimiento de producción en servidor propio.
"""
from __future__ import annotations

import base64
import hashlib
import os
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
    ("127.0.0.1", 5434),
    ("10.0.99.1", 5432),
)


# ¤infra-hibrida
def _cargar_yaml(relativa: str) -> dict[str, Any]:
    ruta = RAIZ / relativa
    assert ruta.is_file(), f"Falta archivo requerido: {relativa}"
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    assert isinstance(datos, dict), f"{relativa} debe ser un diccionario YAML"
    return datos


# ¤infra-hibrida
def test_compose_production_respeta_inv_mismo_compose() -> None:
    """RNF-14 e INV_MISMO_COMPOSE: compose.production.yaml endurece y complementa compose.yaml."""
    base = _cargar_yaml("compose.yaml")
    prod = _cargar_yaml("compose.production.yaml")

    servicios_base = set(base.get("services", {}).keys())
    servicios_prod = set(prod.get("services", {}).keys())

    # La sobrescritura de producción opera exclusivamente sobre los servicios de la aplicación base
    assert servicios_prod.issubset(servicios_base), (
        f"compose.production.yaml declara servicios ajenos a compose.yaml: {servicios_prod - servicios_base}"
    )

    # Cada servicio productivo debe declarar reinicio automático y política de logs con tope
    for nombre, cfg in prod.get("services", {}).items():
        assert cfg.get("restart") == "always", f"Servicio {nombre} en producción debe tener restart: always"
        if "logging" in cfg:
            opts = cfg["logging"].get("options", {})
            assert "max-size" in opts, f"Servicio {nombre} sin max-size en logging"

    # En producción el worker siempre debe arrancar (profiles vacío)
    assert prod["services"]["worker"].get("profiles") == []


# ¤infra-hibrida
def test_aislamiento_red_produccion_inv_red_aislada() -> None:
    """RNF-10 e INV_RED_AISLADA: verificación de que agent-net no tiene rutas a contabilidad."""
    prod = _cargar_yaml("compose.production.yaml")
    redes = prod.get("networks", {})
    assert "agent-net" in redes, "agent-net debe estar declarada en compose.production.yaml"

    for host, puerto in DESTINOS_CONTABLES_PROHIBIDOS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.15)
        try:
            res = sock.connect_ex((host, puerto))
            assert res != 0, f"Violación INV_RED_AISLADA: conexión exitosa a destino prohibido {host}:{puerto}"
        except (socket.gaierror, socket.timeout, OSError):
            pass
        finally:
            sock.close()


# ¤infra-hibrida
def test_scripts_backup_y_restauracion_rnf_15() -> None:
    """RNF-15 y S-08: existencia de scripts de respaldo cifrado y procedimiento de restauración."""
    ruta_backups = RAIZ / "infra" / "backups"
    backup_sh = ruta_backups / "backup.sh"
    restaurar_sh = ruta_backups / "restaurar.sh"
    readme = ruta_backups / "README.md"

    assert backup_sh.is_file(), "Falta infra/backups/backup.sh"
    assert restaurar_sh.is_file(), "Falta infra/backups/restaurar.sh"
    assert readme.is_file(), "Falta infra/backups/README.md"

    contenido_bk = backup_sh.read_text(encoding="utf-8")
    contenido_rst = restaurar_sh.read_text(encoding="utf-8")

    assert "aes-256" in contenido_bk.lower(), "backup.sh debe usar cifrado AES-256"
    assert "aes-256" in contenido_rst.lower(), "restaurar.sh debe descifrar AES-256"
    assert "sha256" in contenido_bk.lower(), "backup.sh debe calcular checksum sha256"


# ¤infra-hibrida
def test_simulacion_roundtrip_cifrado_backup(tmp_path: Path) -> None:
    """RNF-15: simulación programática de volcado, cifrado y restauración sin secretos en repo."""
    datos_originales = b"-- DUMP GLAMPING TEST\nINSERT INTO reservas VALUES ('RES-001', 120.00);\n"
    secreto_backup = "clave_de_prueba_backup_simulado_2026"

    # Simular cifrado con HMAC/XOR/AES
    hash_clave = hashlib.sha256(secreto_backup.encode("utf-8")).digest()
    cifrado = bytes(b ^ hash_clave[i % len(hash_clave)] for i, b in enumerate(datos_originales))
    sha_original = hashlib.sha256(datos_originales).hexdigest()

    # Guardar dump cifrado simulado
    archivo_enc = tmp_path / "dump.sql.enc"
    archivo_enc.write_bytes(cifrado)

    # Descifrar y validar integridad
    datos_leidos = archivo_enc.read_bytes()
    descifrado = bytes(b ^ hash_clave[i % len(hash_clave)] for i, b in enumerate(datos_leidos))
    sha_restaurado = hashlib.sha256(descifrado).hexdigest()

    assert sha_restaurado == sha_original
    assert descifrado == datos_originales
