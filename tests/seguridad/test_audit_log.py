# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de inmutabilidad append-only del audit log e informes (RF-SEC-06, INV_AUDIT_APPEND_ONLY)."""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime, timezone
import pytest

from features.seguridad.seguridad_service import (
    EventoAuditoria,
    Rol,
    SeguridadService,
)
from tests.seguridad.dobles import DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_audit_log_inalterable_la_base_de_datos_rechaza_modificar_y_borrar(
    servicio: SeguridadService,
) -> None:
    """Escenario: Audit log inalterable (@RF-SEC-06 @INV_AUDIT_APPEND_ONLY).
    
    Dado el rol de aplicación
    Cuando intenta modificar o borrar una fila del audit log
    Entonces la base de datos lo rechaza
    """
    evento = EventoAuditoria(
        actor_token="tok_actor_1",
        rol=Rol.VENDEDOR,
        accion="registrar_venta",
        herramienta="registrar_venta",
        propiedad_id="prop_01",
        resultado="exito",
        hash_prompt="hash123",
        traza_id="tr_456",
        audit_id="audit_inmutable_001",
    )
    servicio.auditar(evento)

    # Comprobar que la inserción fue exitosa
    cursor = servicio.conexion.execute(
        "SELECT audit_id, accion, actor_token FROM seguridad.audit_log WHERE audit_id = ?",
        ("audit_inmutable_001",),
    )
    fila = cursor.fetchone()
    assert fila is not None
    assert fila["accion"] == "registrar_venta"

    # 1. Intento de modificar (UPDATE): la base de datos debe rechazarlo
    with pytest.raises(sqlite3.DatabaseError) as exc_upd:
        servicio.conexion.execute(
            "UPDATE seguridad.audit_log SET actor_token = 'hacked' WHERE audit_id = 'audit_inmutable_001'"
        )
    assert "UPDATE denegada" in str(exc_upd.value) or "REVOKE" in str(exc_upd.value)

    # 2. Intento de borrar (DELETE): la base de datos debe rechazarlo
    with pytest.raises(sqlite3.DatabaseError) as exc_del:
        servicio.conexion.execute(
            "DELETE FROM seguridad.audit_log WHERE audit_id = 'audit_inmutable_001'"
        )
    assert "DELETE denegada" in str(exc_del.value) or "REVOKE" in str(exc_del.value)


def test_informe_semanal_genera_csv_con_todas_las_columnas_requeridas(
    servicio: SeguridadService,
) -> None:
    """RF-SEC-06: Existe un informe semanal exportable para revisión manual."""
    # Registrar varios eventos en distintas fechas
    t1 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 3, 15, 30, 0, tzinfo=timezone.utc)

    servicio.auditar(
        EventoAuditoria(
            actor_token="tok_v1",
            rol=Rol.VENDEDOR,
            accion="cotizar",
            herramienta="cotizar",
            propiedad_id="glamping_imbabura",
            resultado="ok",
            instante=t1,
        )
    )
    servicio.auditar(
        EventoAuditoria(
            actor_token="tok_admin",
            rol=Rol.ADMINISTRADOR,
            accion="alta_usuario",
            resultado="exito",
            instante=t2,
        )
    )

    desde = date(2026, 11, 1)
    hasta = date(2026, 11, 7)
    csv_bytes = servicio.informe_semanal(desde, hasta)

    assert isinstance(csv_bytes, bytes)
    contenido = csv_bytes.decode("utf-8")
    lector = list(csv.reader(io.StringIO(contenido)))

    # Verificar cabecera
    cabecera = lector[0]
    columnas_esperadas = [
        "audit_id", "instante", "actor_token", "rol", "accion", "herramienta",
        "propiedad_id", "resultado", "hash_prompt", "traza_id"
    ]
    assert cabecera == columnas_esperadas

    # Al menos los 2 registros
    assert len(lector) >= 3
    acciones_en_reporte = [fila[4] for fila in lector[1:]]
    assert "cotizar" in acciones_en_reporte
    assert "alta_usuario" in acciones_en_reporte
