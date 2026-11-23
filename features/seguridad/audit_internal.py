# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Registro append-only de auditoría e informes (RF-SEC-06, INV_AUDIT_APPEND_ONLY)."""
from __future__ import annotations

import csv
import io
import sqlite3
import uuid
from datetime import date, datetime, timezone

from features.seguridad.tipos import EventoAuditoria, Rol


# ¤seguridad-canal
class AuditLogManager:
    """Gestiona la inserción inalterable en seguridad.audit_log y la generación de reportes."""

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._conn = conexion

    def auditar(self, evento: EventoAuditoria) -> None:
        """Inserta un nuevo evento de auditoría de forma atómica y append-only."""
        audit_id = evento.audit_id or str(uuid.uuid4())
        instante = (evento.instante or datetime.now(timezone.utc)).isoformat()
        rol_valor = evento.rol.value if isinstance(evento.rol, Rol) else str(evento.rol)

        self._conn.execute(
            """
            INSERT INTO seguridad.audit_log (
                audit_id, instante, actor_token, rol, accion, herramienta,
                propiedad_id, resultado, hash_prompt, traza_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_id,
                instante,
                evento.actor_token,
                rol_valor,
                evento.accion,
                evento.herramienta,
                evento.propiedad_id,
                evento.resultado,
                evento.hash_prompt,
                evento.traza_id,
            ),
        )
        self._conn.commit()

    def informe_semanal(self, desde: date, hasta: date) -> bytes:
        """Exporta en formato CSV los registros de auditoría comprendidos entre dos fechas."""
        desde_str = datetime.combine(desde, datetime.min.time(), tzinfo=timezone.utc).isoformat()
        hasta_str = datetime.combine(hasta, datetime.max.time(), tzinfo=timezone.utc).isoformat()

        cursor = self._conn.execute(
            """
            SELECT audit_id, instante, actor_token, rol, accion, herramienta,
                   propiedad_id, resultado, hash_prompt, traza_id
            FROM seguridad.audit_log
            WHERE instante >= ? AND instante <= ?
            ORDER BY instante ASC
            """,
            (desde_str, hasta_str),
        )
        filas = cursor.fetchall()

        buffer = io.StringIO()
        escritor = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
        escritor.writerow([
            "audit_id", "instante", "actor_token", "rol", "accion", "herramienta",
            "propiedad_id", "resultado", "hash_prompt", "traza_id"
        ])
        for f in filas:
            escritor.writerow([
                f["audit_id"], f["instante"], f["actor_token"], f["rol"],
                f["accion"], f["herramienta"] or "", f["propiedad_id"] or "",
                f["resultado"], f["hash_prompt"] or "", f["traza_id"] or ""
            ])

        return buffer.getvalue().encode("utf-8")


# ¤seguridad-canal
def crear_audit_manager(conexion: sqlite3.Connection) -> AuditLogManager:
    """Crea una instancia de AuditLogManager."""
    return AuditLogManager(conexion)
