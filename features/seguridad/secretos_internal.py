# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Gestión de secretos operativos cifrados en bóveda (RF-SEC-08, INV_SECRETO_OPERATIVO).

Las claves de WiFi y códigos de acceso viven cifrados en la bóveda de tokens.
El modelo y el historial solo ven marcadores [[SECRETO:...]], y el valor en claro
se resuelve únicamente en el mensaje saliente destinado al titular de una reserva confirmada
dentro de las 24 horas previas a la llegada.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping

from features.seguridad.audit_internal import AuditLogManager
from features.seguridad.pii_internal import (
    CLAVE_DEFECTO_BOVEDA,
    cifrar_valor,
    derivar_clave,
    descifrar_valor,
)
from features.seguridad.tipos import (
    EventoAuditoria,
    ReservaNoAutorizada,
    Rol,
    Veredicto,
)

__all__ = [
    "RX_MARCADOR_SECRETO",
    "GestorIntentosReserva",
    "GestorSecretosOperativos",
    "crear_gestor_secretos",
]

RX_MARCADOR_SECRETO = re.compile(r"\[\[SECRETO:([a-zA-Z0-9_\-\:]+)\]\]")


# ¤seguridad-canal
class GestorIntentosReserva:
    """Rastrea intentos no autorizados de acceso a reservas (5 en 24h escalan a humano)."""

    def __init__(self, limite_fallos: int = 5, ventana_horas: int = 24) -> None:
        self._limite = limite_fallos
        self._ventana = timedelta(hours=ventana_horas)
        self._intentos: dict[str, list[datetime]] = {}

    # ¤seguridad-canal
    def registrar_fallo(self, remitente_token: str, instante: datetime | None = None) -> bool:
        """Registra un fallo para el remitente y devuelve True si acumuló >= 5 en la ventana."""
        ahora = instante or datetime.now(timezone.utc)
        limite_tiempo = ahora - self._ventana
        historial = self._intentos.setdefault(remitente_token, [])
        historial = [t for t in historial if t >= limite_tiempo]
        historial.append(ahora)
        self._intentos[remitente_token] = historial
        return len(historial) >= self._limite

    # ¤seguridad-canal
    def conteo_fallos(self, remitente_token: str, instante: datetime | None = None) -> int:
        ahora = instante or datetime.now(timezone.utc)
        limite_tiempo = ahora - self._ventana
        historial = self._intentos.get(remitente_token, [])
        return len([t for t in historial if t >= limite_tiempo])


# ¤seguridad-canal
class GestorSecretosOperativos:
    """Bóveda criptográfica y compuerta de acceso para secretos operativos (RF-SEC-08)."""

    def __init__(
        self,
        conexion: sqlite3.Connection,
        audit_manager: AuditLogManager | None = None,
        config: Mapping[str, Any] | None = None,
        gestor_intentos: GestorIntentosReserva | None = None,
    ) -> None:
        self._conn = conexion
        self._audit = audit_manager
        self._config = config or {}
        cfg_pii = self._config.get("pii") if isinstance(self._config.get("pii"), dict) else {}
        clave_str = (
            cfg_pii.get("clave_boveda")
            or self._config.get("clave_boveda")
            or os.environ.get("PII_VAULT_KEY")
            or CLAVE_DEFECTO_BOVEDA
        )
        self._clave = derivar_clave(clave_str)
        self._gestor_intentos = gestor_intentos or GestorIntentosReserva()

    # ¤seguridad-canal
    def normalizar_identificador(self, token_o_marcador: str) -> str:
        """Extrae el identificador base de un token o marcador [[SECRETO:id]]."""
        m = RX_MARCADOR_SECRETO.match(token_o_marcador.strip())
        if m:
            return m.group(1)
        return token_o_marcador.strip()

    # ¤seguridad-canal
    def formato_marcador(self, identificador: str) -> str:
        """Genera el marcador opaco canónico [[SECRETO:identificador]]."""
        limpio = self.normalizar_identificador(identificador)
        return f"[[SECRETO:{limpio}]]"

    # ¤seguridad-canal
    def guardar_secreto(
        self,
        token_id: str,
        tipo: str,
        valor_plano: str,
        titular_hash: str = "global",
    ) -> str:
        """Cifra y almacena un secreto operativo ('clave_wifi' o 'codigo_acceso') en la bóveda."""
        if tipo not in ("clave_wifi", "codigo_acceso"):
            tipo = "clave_wifi" if "wifi" in token_id.lower() else "codigo_acceso"

        limpio = self.normalizar_identificador(token_id)
        marcador = self.formato_marcador(limpio)
        cifrado = cifrar_valor(valor_plano, self._clave)
        ahora = datetime.now(timezone.utc).isoformat()

        # Guardar bajo la clave limpia y bajo el formato marcador para máxima compatibilidad
        for clave in (limpio, marcador):
            self._conn.execute(
                """
                INSERT INTO seguridad.boveda_tokens (token, titular_hash, tipo, valor_cifrado, creado_en, ultimo_uso_en)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(token) DO UPDATE SET valor_cifrado = ?, ultimo_uso_en = ?
                """,
                (clave, titular_hash, tipo, cifrado, ahora, ahora, cifrado, ahora),
            )
        self._conn.commit()
        return marcador

    # ¤seguridad-canal
    def obtener_secreto(self, token_o_marcador: str) -> str | None:
        """Descifra y obtiene el valor real del secreto almacenado en la bóveda."""
        limpio = self.normalizar_identificador(token_o_marcador)
        marcador = self.formato_marcador(limpio)

        for clave in (marcador, limpio):
            cursor = self._conn.execute(
                "SELECT valor_cifrado FROM seguridad.boveda_tokens WHERE token = ?",
                (clave,),
            )
            fila = cursor.fetchone()
            if fila:
                ahora = datetime.now(timezone.utc).isoformat()
                self._conn.execute(
                    "UPDATE seguridad.boveda_tokens SET ultimo_uso_en = ? WHERE token = ?",
                    (ahora, clave),
                )
                self._conn.commit()
                return descifrar_valor(fila["valor_cifrado"], self._clave)
        return None

    # ¤seguridad-canal
    def rehidratar_secretos(self, texto: str) -> str:
        """Reemplaza los marcadores [[SECRETO:...]] por su valor en claro."""
        def _reemplazo(coincidencia: re.Match[str]) -> str:
            identificador = coincidencia.group(1)
            valor = self.obtener_secreto(identificador)
            return valor if valor is not None else coincidencia.group(0)

        return RX_MARCADOR_SECRETO.sub(_reemplazo, texto)

    # ¤seguridad-canal
    def validar_acceso_reserva(
        self,
        codigo_reserva: str,
        remitente_token: str,
        es_titular: bool,
        fecha_llegada: datetime | date | None = None,
        reserva_confirmada: bool = True,
        instante: datetime | None = None,
        traza_id: str = "",
    ) -> Veredicto:
        """Aplica las reglas de RF-SEC-08 para autorización y entrega de secretos operativos."""
        ahora = instante or datetime.now(timezone.utc)

        # 1. Validación de titularidad
        if not es_titular:
            escalar = self._gestor_intentos.registrar_fallo(remitente_token, instante=ahora)
            if self._audit:
                self._audit.auditar(
                    EventoAuditoria(
                        actor_token=remitente_token,
                        rol=Rol.HUESPED_ACTIVO,
                        accion="obtener_instrucciones_checkin",
                        herramienta="obtener_instrucciones_checkin",
                        resultado="denegado_titular_no_coincide",
                        traza_id=traza_id,
                    )
                )
            if escalar:
                raise ReservaNoAutorizada(
                    mensaje="5 intentos fallidos en 24 horas; escalado a humano",
                    codigo_reserva=codigo_reserva,
                    escalar=True,
                )
            raise ReservaNoAutorizada(
                mensaje="El remitente no es titular de la reserva consultada",
                codigo_reserva=codigo_reserva,
                escalar=False,
            )

        # 2. Estado de reserva
        if not reserva_confirmada:
            return Veredicto(
                permitido=False,
                motivo="La reserva no está confirmada; no se entregan secretos operativos",
                escalar=False,
            )

        # 3. Ventana de 24 horas antes de la llegada
        if fecha_llegada is not None:
            if isinstance(fecha_llegada, date) and not isinstance(fecha_llegada, datetime):
                fecha_dt = datetime(
                    fecha_llegada.year,
                    fecha_llegada.month,
                    fecha_llegada.day,
                    15,
                    0,
                    tzinfo=timezone.utc,
                )
            elif isinstance(fecha_llegada, datetime):
                fecha_dt = fecha_llegada if fecha_llegada.tzinfo else fecha_llegada.replace(tzinfo=timezone.utc)
            else:
                fecha_dt = ahora

            limite_entrega = fecha_dt - timedelta(hours=24)
            if ahora < limite_entrega:
                return Veredicto(
                    permitido=False,
                    motivo="Los secretos operativos solo se entregan desde 24 horas antes de la llegada",
                    escalar=False,
                )

        return Veredicto(permitido=True)


# ¤seguridad-canal
def crear_gestor_secretos(
    conexion: sqlite3.Connection,
    audit_manager: AuditLogManager | None = None,
    config: Mapping[str, Any] | None = None,
) -> GestorSecretosOperativos:
    """Crea una instancia de GestorSecretosOperativos."""
    return GestorSecretosOperativos(conexion, audit_manager, config)
