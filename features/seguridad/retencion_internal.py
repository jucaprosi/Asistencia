# ¤seguridad-canal
# ¤¤security-engineer
"""Gestor de retención y purga automática periódica (RF-PRIV-03, INV_AUDIT_APPEND_ONLY)."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from features.seguridad.audit_internal import AuditLogManager
from features.seguridad.tipos import EventoAuditoria, Rol

DIAS_RETENCION_DEFECTO = {
    "eventos_entrantes": 7,
    "medios": 90,
    "conversaciones": 365,
    "trazas": 90,
    "boveda_sin_actividad": 730,
    "rate_limit": 7,
}


# ¤seguridad-canal
class GestorRetencion:
    """Ejecuta purgas periódicas según políticas de dominio.yaml sin alterar audit_log."""

    def __init__(
        self,
        conexion: sqlite3.Connection,
        audit: AuditLogManager,
        config_retencion: Mapping[str, int] | None = None,
        directorio_medios: Path | None = None,
    ) -> None:
        self._conn = conexion
        self._audit = audit
        self._politicas = dict(DIAS_RETENCION_DEFECTO)
        if config_retencion:
            self._politicas.update(config_retencion)
        self._dir_medios = directorio_medios

    def purgar(
        self,
        fecha_referencia: datetime | date | None = None,
        dias_retencion_override: Mapping[str, int] | None = None,
    ) -> dict[str, int]:
        """Purga datos expirados según las políticas de retención.
        
        CRITERIOS RF-PRIV-03:
        (a) Cada purga deja evento en el audit log con usuario/actor e información de elementos purgados.
        (b) El audit log NO se purga por esta vía bajo ninguna circunstancia (INV_AUDIT_APPEND_ONLY).
        """
        ref_dt = (
            datetime.combine(fecha_referencia, datetime.min.time(), tzinfo=timezone.utc)
            if isinstance(fecha_referencia, date) and not isinstance(fecha_referencia, datetime)
            else (fecha_referencia or datetime.now(timezone.utc))
        )
        politicas = dict(self._politicas)
        if dias_retencion_override:
            politicas.update(dias_retencion_override)

        resultado: dict[str, int] = {
            "medios": 0,
            "rate_limit": 0,
            "boveda_sin_actividad": 0,
        }

        # 1. Purga de archivos y registros de medios antiguos
        dias_medios = politicas.get("medios", 90)
        corte_medios = ref_dt - timedelta(days=dias_medios)
        if self._dir_medios and self._dir_medios.is_dir():
            for archivo in self._dir_medios.glob("*"):
                if archivo.is_file():
                    mtime = datetime.fromtimestamp(archivo.stat().st_mtime, tz=timezone.utc)
                    if mtime < corte_medios:
                        try:
                            archivo.unlink()
                            resultado["medios"] += 1
                        except OSError:
                            pass

        # 2. Purga de ventanas antiguas de rate_limit
        dias_rate = politicas.get("rate_limit", 7)
        corte_rate = (ref_dt - timedelta(days=dias_rate)).isoformat()
        cur_rate = self._conn.execute(
            "DELETE FROM seguridad.rate_limit WHERE inicio < ?", (corte_rate,)
        )
        resultado["rate_limit"] += cur_rate.rowcount

        # 3. Purga de tokens en bóveda sin actividad
        dias_boveda = politicas.get("boveda_sin_actividad", 730)
        corte_boveda = (ref_dt - timedelta(days=dias_boveda)).isoformat()
        cur_bov = self._conn.execute(
            "DELETE FROM seguridad.boveda_tokens WHERE ultimo_uso_en < ?", (corte_boveda,)
        )
        resultado["boveda_sin_actividad"] += cur_bov.rowcount

        self._conn.commit()

        # Registrar purga en audit_log (RF-PRIV-03 a)
        total_purgados = sum(resultado.values())
        self._audit.auditar(
            EventoAuditoria(
                actor_token="sistema:retencion",
                rol=Rol.SISTEMA,
                accion="purga_retencion",
                resultado="completado",
                herramienta="retencion_internal",
                hash_prompt=f"purgados:{total_purgados};medios:{resultado['medios']};rate:{resultado['rate_limit']};boveda:{resultado['boveda_sin_actividad']}",
            )
        )

        return resultado


# ¤seguridad-canal
def crear_gestor_retencion(
    conexion: sqlite3.Connection,
    audit: AuditLogManager,
    config: Mapping[str, Any] | None = None,
    directorio_medios: Path | None = None,
) -> GestorRetencion:
    """Crea una instancia de GestorRetencion."""
    cfg = (config or {}).get("retencion_dias")
    return GestorRetencion(conexion, audit, cfg, directorio_medios)
