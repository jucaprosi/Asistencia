# ¤seguridad-canal
# ¤¤security-engineer
"""Control de tasa no anulable por remitente (RF-SEC-03, INV_RATE_LIMIT_NO_ANULABLE)."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping

from features.seguridad.tipos import LimiteExcedido, Rol, Veredicto

# Límites canónicos e inmutables del sistema (RF-SEC-03)
LIMITE_SEGUNDO = 2
LIMITE_MINUTO = 30
LIMITE_DIA = 300


# ¤seguridad-canal
class RateLimiter:
    """Implementa el control de tasa respaldado por tabla con INSERT ON CONFLICT DO UPDATE.
    
    Garantía canónica: Ningún rol ni parámetro de configuración puede anular este límite.
    """

    def __init__(self, conexion: sqlite3.Connection, config: Mapping[str, Any] | None = None) -> None:
        self._conn = conexion
        self._config = config or {}

    def verificar(
        self,
        remitente_hash: str,
        rol: Rol | str | None = None,
        instante: datetime | None = None,
        **kwargs: Any,
    ) -> Veredicto:
        """Verifica y actualiza el contador de mensajes en las ventanas segundo, minuto y día.
        
        Cualquier intento de evasión o anulación vía kwargs (ej. desactivar=True, bypass=True)
        es ignorado y el límite se aplica estrictamente.
        """
        # Si kwargs intenta desactivar, ignorar y registrar intento
        if instante is None:
            instante = datetime.now(timezone.utc)
        elif instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)

        ventanas = (
            ("segundo", instante.strftime("%Y-%m-%d %H:%M:%S"), LIMITE_SEGUNDO),
            ("minuto", instante.strftime("%Y-%m-%d %H:%M:00"), LIMITE_MINUTO),
            ("dia", instante.strftime("%Y-%m-%d 00:00:00"), LIMITE_DIA),
        )

        excedido = False
        aviso_necesario = False

        for nombre_ventana, inicio_str, limite_maximo in ventanas:
            # Atomic upsert con contador
            self._conn.execute(
                """
                INSERT INTO seguridad.rate_limit (remitente_hash, ventana, inicio, contador, aviso_enviado)
                VALUES (?, ?, ?, 1, FALSE)
                ON CONFLICT(remitente_hash, ventana, inicio) DO UPDATE SET contador = rate_limit.contador + 1
                """,
                (remitente_hash, nombre_ventana, inicio_str),
            )

            cursor = self._conn.execute(
                """
                SELECT contador, aviso_enviado FROM seguridad.rate_limit
                WHERE remitente_hash = ? AND ventana = ? AND inicio = ?
                """,
                (remitente_hash, nombre_ventana, inicio_str),
            )
            fila = cursor.fetchone()
            if fila:
                contador = fila["contador"]
                aviso_ya_enviado = bool(fila["aviso_enviado"])

                if contador > limite_maximo:
                    excedido = True
                    if not aviso_ya_enviado:
                        aviso_necesario = True
                        self._conn.execute(
                            """
                            UPDATE seguridad.rate_limit SET aviso_enviado = TRUE
                            WHERE remitente_hash = ? AND ventana = ? AND inicio = ?
                            """,
                            (remitente_hash, nombre_ventana, inicio_str),
                        )

        self._conn.commit()

        if excedido:
            if aviso_necesario:
                return Veredicto(
                    permitido=False,
                    motivo="LimiteExcedido: se ha superado la cuota de mensajes permitida. Recibe un solo aviso.",
                    escalar=False,
                )
            return Veredicto(
                permitido=False,
                motivo="LimiteExcedido: mensaje descartado hasta el fin de la ventana.",
                escalar=False,
            )

        return Veredicto(permitido=True)

    def exigir(
        self,
        remitente_hash: str,
        rol: Rol | str | None = None,
        instante: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        """Lanza LimiteExcedido si el límite fue superado."""
        veredicto = self.verificar(remitente_hash, rol=rol, instante=instante, **kwargs)
        if not veredicto.permitido:
            raise LimiteExcedido(veredicto.motivo or "Límite de tasa excedido")


# ¤seguridad-canal
def crear_rate_limiter(conexion: sqlite3.Connection, config: Mapping[str, Any] | None = None) -> RateLimiter:
    """Crea una instancia de RateLimiter ligada a la base de datos."""
    return RateLimiter(conexion, config)
