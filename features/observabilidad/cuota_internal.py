# ¤observabilidad
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tope diario atómico del gasto en inferencia (ADR-0021, C2 y C3; RNF-16).

Se cuenta en micro-dólares enteros para que la comparación sea exacta. La reserva es un único
``UPDATE … WHERE gastado + costo <= tope RETURNING``: o entra entera o no entra, también entre procesos
en PostgreSQL. El día es el día UTC. Cualquier error de la base se trata como «no hay cupo» (falla cerrada).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from typing import Any, Callable

__all__ = ["CuotaDiaria"]

_MICRO = Decimal("1000000")
_LOG = logging.getLogger(__name__)


# ¤observabilidad
def _a_micro(costo: Decimal) -> int:
    return int((Decimal(costo) * _MICRO).to_integral_value(rounding=ROUND_CEILING))


# ¤observabilidad
class CuotaDiaria:
    def __init__(self, obtener_conexion: Callable[[], Any], tope_usd: Decimal) -> None:
        self._obtener_conexion = obtener_conexion
        self._tope = _a_micro(tope_usd)
        self._candado = threading.Lock()

    # ¤observabilidad
    @staticmethod
    def _dia() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    # ¤observabilidad
    def reservar(self, costo: Decimal) -> bool:
        micro = _a_micro(costo)
        try:
            with self._candado, self._obtener_conexion() as con:
                con.execute(
                    "INSERT INTO cuota_inferencia (dia, gastado_micro) VALUES (?, 0) ON CONFLICT (dia) DO NOTHING",
                    (self._dia(),),
                )
                fila = con.execute(
                    "UPDATE cuota_inferencia SET gastado_micro = gastado_micro + ? "
                    "WHERE dia = ? AND gastado_micro + ? <= ? RETURNING gastado_micro",
                    (micro, self._dia(), micro, self._tope),
                ).fetchone()
                return fila is not None
        except Exception:  # noqa: BLE001 - sin contador fiable no se gasta
            return False

    # ¤observabilidad
    def conciliar(self, reservado: Decimal, real: Decimal) -> None:
        """Devuelve lo reservado de más (o suma lo que faltó) cuando ya se conoce el costo real."""
        delta = _a_micro(real) - _a_micro(reservado)
        if delta == 0:
            return
        try:
            with self._candado, self._obtener_conexion() as con:
                con.execute(
                    "UPDATE cuota_inferencia SET gastado_micro = MAX(gastado_micro + ?, 0) WHERE dia = ?"
                    if not getattr(con, "es_postgres", False)
                    else "UPDATE cuota_inferencia SET gastado_micro = GREATEST(gastado_micro + ?, 0) WHERE dia = ?",
                    (delta, self._dia()),
                )
        except Exception as exc:  # noqa: BLE001 - K3: se conserva la reserva del peor caso
            _LOG.warning("conciliacion_fallida tipo=%s delta_micro=%s", type(exc).__name__, delta)
