# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Resolución de identidad, roles RBAC y control de lista de bloqueo (RF-SEC-01)."""
from __future__ import annotations

import hashlib
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

from features.seguridad.audit_internal import AuditLogManager
from features.seguridad.tipos import (
    ActorSinPrivilegio,
    EventoAuditoria,
    Identidad,
    RemitenteBloqueado,
    Rol,
)


# ¤seguridad-canal
def normalizar_numero(numero: str) -> str:
    """Elimina caracteres no numéricos excepto el signo inicial +."""
    numero_limpio = numero.strip()
    if numero_limpio.startswith("+"):
        return "+" + re.sub(r"\D", "", numero_limpio[1:])
    return re.sub(r"\D", "", numero_limpio)


# ¤seguridad-canal
def hash_identidad(valor: str) -> str:
    """Genera hash SHA-256 de un número de teléfono o identificador."""
    norm = normalizar_numero(valor)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ¤seguridad-canal
class IdentidadManager:
    """Gestiona la autenticación, roles por canal y lista de bloqueo en la base de datos."""

    def __init__(
        self,
        conexion: sqlite3.Connection,
        audit_manager: AuditLogManager | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self._conn = conexion
        self._audit = audit_manager
        self._config = config or {}
        # Conjunto de números o hashes con reserva confirmada vigente
        self._reservas_activas: set[str] = set()

    def registrar_reserva_activa(self, numero: str) -> None:
        """Registra un número como poseedor de una reserva confirmada vigente."""
        h = hash_identidad(numero)
        self._reservas_activas.add(h)
        self._reservas_activas.add(normalizar_numero(numero))

    def quitar_reserva_activa(self, numero: str) -> None:
        """Remueve la reserva confirmada vigente."""
        h = hash_identidad(numero)
        self._reservas_activas.discard(h)
        self._reservas_activas.discard(normalizar_numero(numero))

    def esta_bloqueado(self, numero_hash: str) -> bool:
        """Comprueba si el hash consta en la tabla de bloqueos."""
        cursor = self._conn.execute(
            "SELECT motivo FROM seguridad.bloqueos WHERE numero_hash = ?",
            (numero_hash,),
        )
        return cursor.fetchone() is not None

    def identificar(self, remitente: str, canal: str = "huespedes") -> Identidad:
        """Resuelve la identidad y rol del remitente respetando el canal y bloqueos (RF-SEC-01)."""
        num_hash = hash_identidad(remitente)
        remitente_token = f"tok_rem_{num_hash[:16]}"

        # 1. Comprobar lista de bloqueos
        if self.esta_bloqueado(num_hash):
            if self._audit:
                self._audit.auditar(
                    EventoAuditoria(
                        actor_token=remitente_token,
                        rol=Rol.DESCONOCIDO,
                        accion="mensaje_bloqueado",
                        resultado="descartado",
                        propiedad_id=None,
                    )
                )
            return Identidad(
                remitente_token=remitente_token,
                rol=Rol.DESCONOCIDO,
                numero_hash=num_hash,
            )

        # 2. Comprobar en seguridad.usuarios (colaboradores privilegiados)
        cursor = self._conn.execute(
            """
            SELECT usuario_id, rol, sujeto_id, activo FROM seguridad.usuarios
            WHERE numero_hash = ? AND activo = TRUE
            """,
            (num_hash,),
        )
        fila = cursor.fetchone()
        if fila:
            rol_str = fila["rol"]
            try:
                rol_enum = Rol(rol_str)
            except ValueError:
                rol_enum = Rol.DESCONOCIDO
            return Identidad(
                remitente_token=remitente_token,
                rol=rol_enum,
                sujeto_id=fila["sujeto_id"] or str(fila["usuario_id"]),
                numero_hash=num_hash,
            )

        # 3. Si no es usuario interno:
        if canal != "huespedes":
            # En el canal de vendedores (o cualquier otro no-huespedes), un número sin rol es desconocido y se descarta
            return Identidad(
                remitente_token=remitente_token,
                rol=Rol.DESCONOCIDO,
                numero_hash=num_hash,
            )

        # 4. Canal de huéspedes (abierto)
        # Verificar si tiene reserva confirmada activa
        norm = normalizar_numero(remitente)
        if num_hash in self._reservas_activas or norm in self._reservas_activas:
            rol_huesped = Rol.HUESPED_ACTIVO
        else:
            rol_huesped = Rol.HUESPED_POTENCIAL

        # Registrar o verificar en tabla huespedes
        self._conn.execute(
            """
            INSERT INTO seguridad.huespedes (huesped_id, telefono_token, idioma)
            VALUES (?, ?, 'es')
            ON CONFLICT(telefono_token) DO NOTHING
            """,
            (str(uuid.uuid4()), remitente_token),
        )
        self._conn.commit()

        return Identidad(
            remitente_token=remitente_token,
            rol=rol_huesped,
            sujeto_id=remitente_token,
            numero_hash=num_hash,
        )

    def bloquear_numero(self, actor: Identidad, numero: str, motivo: str) -> None:
        """Bloquea un número de teléfono. Solo permitido para ADMINISTRADOR."""
        if actor.rol != Rol.ADMINISTRADOR:
            raise ActorSinPrivilegio("Solo el administrador puede bloquear números")

        num_hash = hash_identidad(numero)
        bloqueador_id = actor.sujeto_id or str(uuid.uuid4())
        # Asegurar formato uuid válido para bloqueado_por
        try:
            uuid.UUID(bloqueador_id)
        except ValueError:
            bloqueador_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, bloqueador_id))

        self._conn.execute(
            """
            INSERT INTO seguridad.bloqueos (numero_hash, motivo, bloqueado_por)
            VALUES (?, ?, ?)
            ON CONFLICT(numero_hash) DO UPDATE SET motivo = ?, bloqueado_por = ?, bloqueado_en = CURRENT_TIMESTAMP
            """,
            (num_hash, motivo, bloqueador_id, motivo, bloqueador_id),
        )
        self._conn.commit()

        if self._audit:
            self._audit.auditar(
                EventoAuditoria(
                    actor_token=actor.remitente_token,
                    rol=actor.rol,
                    accion="bloquear_numero",
                    resultado="bloqueado",
                    propiedad_id=None,
                )
            )

    def desbloquear_numero(self, actor: Identidad, numero: str) -> None:
        """Desbloquea un número previamente bloqueado. Solo permitido para ADMINISTRADOR."""
        if actor.rol != Rol.ADMINISTRADOR:
            raise ActorSinPrivilegio("Solo el administrador puede desbloquear números")

        num_hash = hash_identidad(numero)
        self._conn.execute("DELETE FROM seguridad.bloqueos WHERE numero_hash = ?", (num_hash,))
        self._conn.commit()

        if self._audit:
            self._audit.auditar(
                EventoAuditoria(
                    actor_token=actor.remitente_token,
                    rol=actor.rol,
                    accion="desbloquear_numero",
                    resultado="desbloqueado",
                    propiedad_id=None,
                )
            )

    def administrar_usuarios(
        self,
        actor: Identidad,
        numero: str,
        rol: Rol,
        alta: bool,
        sujeto_id: str | None = None,
        correo: str | None = None,
    ) -> None:
        """Gestiona altas y bajas de usuarios RBAC. Solo permitido para ADMINISTRADOR."""
        if actor.rol != Rol.ADMINISTRADOR:
            raise ActorSinPrivilegio("Solo el administrador puede administrar usuarios")

        num_hash = hash_identidad(numero)
        correo_hash = hashlib.sha256((correo or f"{num_hash[:8]}@glamping.internal").encode("utf-8")).hexdigest()
        alta_por_id = actor.sujeto_id or str(uuid.uuid4())
        try:
            uuid.UUID(alta_por_id)
        except ValueError:
            alta_por_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, alta_por_id))

        if alta:
            usuario_id = str(uuid.uuid4())
            self._conn.execute(
                """
                INSERT INTO seguridad.usuarios (
                    usuario_id, correo_hash, numero_hash, rol, sujeto_id, activo, alta_por
                ) VALUES (?, ?, ?, ?, ?, TRUE, ?)
                ON CONFLICT(numero_hash) DO UPDATE SET
                    rol = excluded.rol,
                    activo = TRUE,
                    baja_en = NULL,
                    sujeto_id = excluded.sujeto_id
                """,
                (usuario_id, correo_hash, num_hash, rol.value, sujeto_id, alta_por_id),
            )
        else:
            ahora = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                """
                UPDATE seguridad.usuarios
                SET activo = FALSE, baja_en = ?
                WHERE numero_hash = ?
                """,
                (ahora, num_hash),
            )

        self._conn.commit()

        if self._audit:
            self._audit.auditar(
                EventoAuditoria(
                    actor_token=actor.remitente_token,
                    rol=actor.rol,
                    accion="alta_usuario" if alta else "baja_usuario",
                    resultado="exito",
                    propiedad_id=None,
                )
            )


# ¤seguridad-canal
def crear_identidad_manager(
    conexion: sqlite3.Connection,
    audit_manager: AuditLogManager | None = None,
    config: Mapping[str, Any] | None = None,
) -> IdentidadManager:
    """Crea una instancia de IdentidadManager."""
    return IdentidadManager(conexion, audit_manager, config)
