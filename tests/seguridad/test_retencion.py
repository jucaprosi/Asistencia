# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PRIV-03 e INV_AUDIT_APPEND_ONLY (Retención y purga automática).

Verifica:
1. Purga de medios y datos más antiguos que su período de retención según dominio.yaml.
2. Cada purga deja registro de auditoría en seguridad.audit_log con detalles de elementos purgados.
3. El audit log NO se purga bajo ninguna circunstancia (invariante append-only inalterable).
"""
from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from features.seguridad.retencion_internal import GestorRetencion, crear_gestor_retencion
from features.seguridad.seguridad_service import SeguridadService
from tests.seguridad.dobles import DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_retencion_automatica_elimina_medios_antiguos_y_audita(servicio: SeguridadService) -> None:
    """Escenario: Retención automática (@US-17 @RF-PRIV-03).
    
    Dado un medio más antiguo que su retención
    Cuando corre la tarea diaria
    Entonces el medio se elimina y la purga queda en el audit log
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_medios = Path(tmpdir)
        # Crear un archivo de medio viejo (hace 100 días, retención es 90 días)
        medio_viejo = dir_medios / "audio_huesped_viejo.ogg"
        medio_viejo.write_bytes(b"DATOS_AUDIO_VIEJO")
        hace_100_dias = time.time() - (100 * 86400)
        os.utime(medio_viejo, (hace_100_dias, hace_100_dias))

        # Crear un archivo de medio reciente (hace 10 días)
        medio_reciente = dir_medios / "foto_voucher_reciente.jpg"
        medio_reciente.write_bytes(b"DATOS_FOTO_RECIENTE")
        hace_10_dias = time.time() - (10 * 86400)
        os.utime(medio_reciente, (hace_10_dias, hace_10_dias))

        gestor = GestorRetencion(
            servicio.conexion,
            servicio._audit,
            config_retencion={"medios": 90},
            directorio_medios=dir_medios,
        )

        # Cuando corre la tarea diaria de retención
        ahora = datetime.now(timezone.utc)
        resultado = gestor.purgar(fecha_referencia=ahora)

        # Entonces el medio viejo se elimina
        assert not medio_viejo.exists(), "El medio más antiguo que su retención debe eliminarse"
        assert resultado["medios"] >= 1

        # Y el medio reciente se conserva
        assert medio_reciente.exists(), "El medio dentro del plazo de retención debe conservarse"

        # Y la purga queda registrada en el audit log
        cursor = servicio.conexion.execute(
            "SELECT accion, resultado, hash_prompt FROM seguridad.audit_log WHERE accion = 'purga_retencion'"
        )
        filas = cursor.fetchall()
        assert len(filas) >= 1
        ultimo = filas[-1]
        assert ultimo["resultado"] == "completado"
        assert "medios:1" in ultimo["hash_prompt"]


def test_retencion_nunca_purga_audit_log(servicio: SeguridadService) -> None:
    """RF-PRIV-03 (b) e INV_AUDIT_APPEND_ONLY: El audit log no se purga por esta vía."""
    # 1. Insertar eventos de auditoría antiguos (hace 800 días)
    hace_800_dias = (datetime.now(timezone.utc) - timedelta(days=800)).isoformat()
    servicio.conexion.execute(
        """
        INSERT INTO seguridad.audit_log (
            audit_id, instante, actor_token, rol, accion, herramienta, resultado
        ) VALUES ('audit_antiguo_1', ?, 'actor_test', 'vendedor', 'consulta', 'pms', 'ok')
        """,
        (hace_800_dias,),
    )
    servicio.conexion.commit()

    total_audit_antes = servicio.conexion.execute(
        "SELECT COUNT(*) as c FROM seguridad.audit_log"
    ).fetchone()["c"]
    assert total_audit_antes >= 1

    # 2. Ejecutar la purga con fecha de referencia muy en el futuro
    futuro = datetime.now(timezone.utc) + timedelta(days=3650)
    servicio.purgar_retencion(fecha_referencia=futuro)

    # 3. Verificar que el audit_log no ha perdido ninguna fila (de hecho aumentó por el evento de purga)
    total_audit_despues = servicio.conexion.execute(
        "SELECT COUNT(*) as c FROM seguridad.audit_log"
    ).fetchone()["c"]
    assert total_audit_despues > total_audit_antes, (
        "El audit log no debe ser purgado por retención y debe contener el nuevo evento"
    )

    fila_antigua = servicio.conexion.execute(
        "SELECT audit_id FROM seguridad.audit_log WHERE audit_id = 'audit_antiguo_1'"
    ).fetchone()
    assert fila_antigua is not None, "El registro de auditoría antiguo debe permanecer intacto"
