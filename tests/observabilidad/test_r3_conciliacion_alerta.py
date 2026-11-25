# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""r3 del dictamen K3 (ADR-0021): una conciliación fallida llega a las alertas operativas."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator

from features.observabilidad.alertas_internal import DetectorAlertas
from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config

_AHORA = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


# ¤inferencia
def test_r3_el_detector_avisa_si_hubo_conciliaciones_fallidas() -> None:
    detector = DetectorAlertas(cargar_config())
    alertas = detector.verificar_todas(_AHORA, {"conciliaciones_fallidas": 2})
    assert [a.nombre for a in alertas] == ["conciliacion_fallida"]
    assert alertas[0].severidad == "aviso" and "2" in alertas[0].mensaje


# ¤inferencia
def test_r3_sin_fallos_no_hay_alerta() -> None:
    assert DetectorAlertas(cargar_config()).verificar_todas(_AHORA, {"conciliaciones_fallidas": 0}) == ()


# ¤inferencia
def test_r3_la_cuota_del_servicio_cuenta_el_fallo_y_lo_alerta() -> None:
    servicio = ObservabilidadService(cargar_config())
    cuota = servicio.cuota_inferencia(Decimal("1.00"))
    assert cuota.reservar(Decimal("0.50"))

    @contextmanager
    def caida() -> Iterator[None]:
        raise ConnectionError("base caída")
        yield  # pragma: no cover

    cuota._obtener_conexion = caida  # la base cae entre reservar y conciliar
    cuota.conciliar(Decimal("0.50"), Decimal("0.10"))
    assert cuota.conciliaciones_fallidas == 1
    assert "conciliacion_fallida" in [a.nombre for a in servicio.alertas_activas()]
