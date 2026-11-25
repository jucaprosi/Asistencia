# ¤observabilidad
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Tope diario atómico del gasto en inferencia (ADR-0021, C2 y C3; RNF-16).

Se cuenta en micro-dólares enteros para que la comparación sea exacta. La reserva es un único
``UPDATE … WHERE gastado + costo <= tope RETURNING``: o entra entera o no entra, también entre procesos
en PostgreSQL. El día es el de Google Cloud: medianoche del Pacífico (America/Los_Angeles), como sus
cuotas diarias. Cualquier error de la base se trata como «no hay cupo» (falla cerrada).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from typing import Any, Callable
from zoneinfo import ZoneInfo

__all__ = ["CuotaDiaria", "dia_de_cuota"]

_MICRO = Decimal("1000000")
_LOG = logging.getLogger(__name__)
# Decisión del propietario (2026-11-25, ADR-0021): el día de las cuotas diarias de Google Cloud.
_ZONA_CUOTA = ZoneInfo("America/Los_Angeles")


# ¤observabilidad
def dia_de_cuota(instante: datetime) -> str:
    """Día (AAAA-MM-DD) en la zona de Google Cloud; un instante sin zona es un error, no se supone UTC."""
    if instante.tzinfo is None:
        raise ValueError("el instante necesita zona horaria")
    return instante.astimezone(_ZONA_CUOTA).date().isoformat()


# ¤observabilidad
def _a_micro(costo: Decimal) -> int:
    return int((Decimal(costo) * _MICRO).to_integral_value(rounding=ROUND_CEILING))


# ¤observabilidad
class CuotaDiaria:
    def __init__(self, obtener_conexion: Callable[[], Any], tope_usd: Decimal) -> None:
        self._obtener_conexion = obtener_conexion
        self._tope = _a_micro(tope_usd)
        self._candado = threading.Lock()
        self._conciliaciones_fallidas = 0

    # ¤observabilidad
    @property
    def conciliaciones_fallidas(self) -> int:
        """Conciliaciones que no llegaron a la base en este proceso (r3: las lee el detector de alertas)."""
        return self._conciliaciones_fallidas

    # ¤observabilidad
    @staticmethod
    def _dia() -> str:
        return dia_de_cuota(datetime.now(timezone.utc))

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
            self._conciliaciones_fallidas += 1
            _LOG.warning("conciliacion_fallida tipo=%s delta_micro=%s", type(exc).__name__, delta)
