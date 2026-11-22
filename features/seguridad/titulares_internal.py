# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Gestión de derechos de los titulares ARCO y criptoborrado (RF-PRIV-04, RF-PRIV-05, INV_CRIPTOBORRADO)."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from features.seguridad.audit_internal import AuditLogManager
from features.seguridad.tipos import EventoAuditoria, Rol

TIPOS_SOLICITUD = ("acceso", "rectificacion", "eliminacion", "oposicion", "portabilidad")
ESTADOS_SOLICITUD = ("recibida", "en_curso", "atendida", "atendida_parcial", "rechazada")
PLAZO_OPERATIVO_DIAS = 15


# ¤seguridad-canal
@dataclass(frozen=True)
class SolicitudTitular:
    solicitud_id: str
    titular_hash: str
    tipo: str
    estado: str
    recibida_en: datetime
    limite_en: datetime
    atendida_en: datetime | None = None
    atendida_por: str | None = None
    motivo: str | None = None


# ¤seguridad-canal
class GestorTitulares:
    """Gestiona el ciclo de vida de solicitudes ARCO y ejecuta criptoborrado irreversible."""

    def __init__(
        self,
        conexion: sqlite3.Connection,
        audit: AuditLogManager,
        pii_redactor: Any = None,
    ) -> None:
        self._conn = conexion
        self._audit = audit
        self._pii = pii_redactor

    def registrar_solicitud(
        self,
        titular_hash: str,
        tipo: str,
        recibida_en: datetime | None = None,
    ) -> SolicitudTitular:
        """Registra una solicitud de ejercicio de derechos del titular (RF-PRIV-05)."""
        if tipo not in TIPOS_SOLICITUD:
            raise ValueError(f"Tipo de solicitud '{tipo}' inválido. Debe ser uno de {TIPOS_SOLICITUD}")

        sid = str(uuid.uuid4())
        ahora = recibida_en or datetime.now(timezone.utc)
        limite = ahora + timedelta(days=PLAZO_OPERATIVO_DIAS)

        self._conn.execute(
            """
            INSERT INTO seguridad.solicitudes_titular (
                solicitud_id, titular_hash, tipo, estado, recibida_en, limite_en
            ) VALUES (?, ?, ?, 'recibida', ?, ?)
            """,
            (sid, titular_hash, tipo, ahora.isoformat(), limite.isoformat()),
        )
        self._conn.commit()

        self._audit.auditar(
            EventoAuditoria(
                actor_token=titular_hash,
                rol=Rol.SISTEMA,
                accion="registro_solicitud_titular",
                resultado="recibida",
                herramienta="titulares_internal",
                hash_prompt=f"tipo:{tipo};solicitud_id:{sid}",
            )
        )

        return SolicitudTitular(
            solicitud_id=sid,
            titular_hash=titular_hash,
            tipo=tipo,
            estado="recibida",
            recibida_en=ahora,
            limite_en=limite,
        )

    def listar_solicitudes(self, estado: str | None = None) -> list[SolicitudTitular]:
        """Lista solicitudes registradas, opcionalmente filtrando por estado."""
        if estado:
            cur = self._conn.execute(
                "SELECT * FROM seguridad.solicitudes_titular WHERE estado = ? ORDER BY recibida_en ASC",
                (estado,),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM seguridad.solicitudes_titular ORDER BY recibida_en ASC"
            )
        filas = cur.fetchall()
        return [self._mapear_fila(f) for f in filas]

    def solicitudes_proximas_a_vencer(
        self, dias_aviso: int = 3, ahora: datetime | None = None
    ) -> list[SolicitudTitular]:
        """Devuelve las solicitudes pendientes cuyo plazo vencerá en los próximos días (RF-PRIV-05 b)."""
        ahora_dt = ahora or datetime.now(timezone.utc)
        corte_aviso = ahora_dt + timedelta(days=dias_aviso)

        cur = self._conn.execute(
            """
            SELECT * FROM seguridad.solicitudes_titular
            WHERE estado IN ('recibida', 'en_curso')
              AND limite_en <= ?
            ORDER BY limite_en ASC
            """,
            (corte_aviso.isoformat(),),
        )
        return [self._mapear_fila(f) for f in cur.fetchall()]

    def ejecutar_criptoborrado(
        self, titular_hash: str, actor_id: str = "administrador"
    ) -> dict[str, Any]:
        """Borra irreversiblemente las filas de la bóveda de tokens del titular (RF-PRIV-04, INV_CRIPTOBORRADO).
        
        CRITERIOS:
        (a) El audit log NO se modifica bajo ninguna circunstancia (audit_log' = audit_log).
        (b) Rehidratar un token borrado devuelve un marcador neutro ([DATO_BORRADO]).
        """
        cur = self._conn.execute(
            "DELETE FROM seguridad.boveda_tokens WHERE titular_hash = ?", (titular_hash,)
        )
        tokens_borrados = cur.rowcount
        self._conn.commit()

        # Invalidar cachés en memoria del PIIRedactor si está presente
        if self._pii is not None:
            if hasattr(self._pii, "limpiar_cache_titular"):
                self._pii.limpiar_cache_titular(titular_hash)
            elif hasattr(self._pii, "_tokens_por_conv"):
                # Limpiar referencias de conversaciones
                self._pii._tokens_por_conv.clear()
                self._pii._valores_por_conv.clear()

        # Registrar evento de auditoría del criptoborrado
        self._audit.auditar(
            EventoAuditoria(
                actor_token=actor_id,
                rol=Rol.ADMINISTRADOR,
                accion="criptoborrado",
                resultado="ejecutado",
                herramienta="titulares_internal",
                hash_prompt=f"titular_hash:{titular_hash};tokens_eliminados:{tokens_borrados}",
            )
        )

        return {"titular_hash": titular_hash, "tokens_eliminados": tokens_borrados}

    def atender_solicitud(
        self,
        solicitud_id: str,
        atendida_por: str = "usr_admin",
        sujeto_a_conservacion: bool = False,
        motivo_conservacion: str | None = None,
    ) -> SolicitudTitular:
        """Atiende la solicitud del titular aplicando criptoborrado o conservación legal (RF-PRIV-05 a)."""
        cur = self._conn.execute(
            "SELECT * FROM seguridad.solicitudes_titular WHERE solicitud_id = ?", (solicitud_id,)
        )
        fila = cur.fetchone()
        if not fila:
            raise ValueError(f"Solicitud '{solicitud_id}' no encontrada.")

        tipo = fila["tipo"]
        titular_hash = fila["titular_hash"]
        ahora = datetime.now(timezone.utc)

        if tipo == "eliminacion":
            if sujeto_a_conservacion:
                estado_nuevo = "atendida_parcial"
                motivo = motivo_conservacion or "Datos sujetos a obligación legal de conservación fiscal/reserva activa."
            else:
                self.ejecutar_criptoborrado(titular_hash, actor_id=atendida_por)
                estado_nuevo = "atendida"
                motivo = "Criptoborrado completado exitosamente."
        else:
            estado_nuevo = "atendida"
            motivo = f"Solicitud de {tipo} atendida satisfactoriamente."

        self._conn.execute(
            """
            UPDATE seguridad.solicitudes_titular
            SET estado = ?, atendida_en = ?, atendida_por = ?, motivo = ?
            WHERE solicitud_id = ?
            """,
            (estado_nuevo, ahora.isoformat(), atendida_por, motivo, solicitud_id),
        )
        self._conn.commit()

        self._audit.auditar(
            EventoAuditoria(
                actor_token=atendida_por,
                rol=Rol.ADMINISTRADOR,
                accion=f"solicitud_{estado_nuevo}",
                resultado="completado",
                herramienta="titulares_internal",
                hash_prompt=f"solicitud_id:{solicitud_id};motivo:{motivo}",
            )
        )

        cur_act = self._conn.execute(
            "SELECT * FROM seguridad.solicitudes_titular WHERE solicitud_id = ?", (solicitud_id,)
        )
        return self._mapear_fila(cur_act.fetchone())

    def _mapear_fila(self, fila: sqlite3.Row) -> SolicitudTitular:
        rec_en = datetime.fromisoformat(fila["recibida_en"]) if fila["recibida_en"] else datetime.now(timezone.utc)
        lim_en = datetime.fromisoformat(fila["limite_en"]) if fila["limite_en"] else rec_en
        at_en = datetime.fromisoformat(fila["atendida_en"]) if fila["atendida_en"] else None
        return SolicitudTitular(
            solicitud_id=fila["solicitud_id"],
            titular_hash=fila["titular_hash"],
            tipo=fila["tipo"],
            estado=fila["estado"],
            recibida_en=rec_en,
            limite_en=lim_en,
            atendida_en=at_en,
            atendida_por=fila["atendida_por"],
            motivo=fila["motivo"],
        )


# ¤seguridad-canal
def crear_gestor_titulares(
    conexion: sqlite3.Connection,
    audit: AuditLogManager,
    pii_redactor: Any = None,
) -> GestorTitulares:
    """Crea una instancia de GestorTitulares."""
    return GestorTitulares(conexion, audit, pii_redactor)
