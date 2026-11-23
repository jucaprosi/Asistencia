# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Generador de tickets numerados secuenciales por año (RF-ARM-05, INV_TICKET_UNICO)."""
from __future__ import annotations

import sqlite3
import threading
from typing import Callable, TypeVar

__all__ = ["GeneradorTickets"]

T = TypeVar("T")


# ¤arm-jarvis
class GeneradorTickets:
    """Genera tickets únicos y secuenciales V-AAAA-NNNN sin huecos ni duplicados."""

    def __init__(self, conexion: sqlite3.Connection, lock: threading.RLock | None = None) -> None:
        self._con = conexion
        self._lock = lock or threading.RLock()

    # ¤arm-jarvis
    def generar_ticket_con_transaccion(
        self,
        anio: int,
        accion_insercion: Callable[[str], T],
    ) -> tuple[str, T]:
        """Ejecuta la asignación del ticket y la inserción dentro de la misma transacción atómica.

        Si la acción de inserción falla o hace rollback, el contador no se incrementa y no
        se dejan huecos en la secuencia anual (INV_TICKET_UNICO).
        """
        with self._lock:
            self._con.execute(
                "INSERT INTO arm.secuencia_tickets (anio, ultimo) VALUES (?, 0) ON CONFLICT (anio) DO NOTHING;",
                (anio,),
            )
            self._con.commit()
            # El UPDATE ... RETURNING bloquea la fila del año hasta el commit (PostgreSQL) o toma el
            # candado de escritura (SQLite): dos asignaciones concurrentes nunca leen el mismo número.
            try:
                cur = self._con.execute(
                    "UPDATE arm.secuencia_tickets SET ultimo = ultimo + 1 WHERE anio = ? RETURNING ultimo;",
                    (anio,),
                )
                fila = cur.fetchone()
                nuevo_numero = fila[0] if isinstance(fila, (tuple, list)) else fila["ultimo"]
                ticket = f"V-{anio}-{nuevo_numero:04d}"
                resultado = accion_insercion(ticket)
                self._con.commit()
                return ticket, resultado
            except Exception:
                self._con.rollback()
                raise
