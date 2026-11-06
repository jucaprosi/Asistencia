# ¤comisiones
# ¤¤backend-developer
"""Exportación reproducible de comisiones a CSV y JSON validado (RF-COM-03)."""
from __future__ import annotations

import csv
from decimal import Decimal
import io
import json
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator

from features.comisiones.persistencia_internal import PersistenciaComisiones
from features.comisiones.tipos import EstadoComision

__all__ = ["exportar_periodo"]

RUTA_ESQUEMA = Path(__file__).with_name("esquema_exportacion.json")


# ¤comisiones
def exportar_periodo(
    persistencia: PersistenciaComisiones,
    periodo_id: str,
    formato: Literal["csv", "json"],
    moneda: str = "USD",
) -> bytes:
    """Exporta las comisiones fijadas y ajustadas del período al formato especificado."""
    comisiones = [
        c
        for c in persistencia.obtener_comisiones_periodo(periodo_id)
        if c.estado in (EstadoComision.FIJADA, EstadoComision.PAGADA, EstadoComision.AJUSTADA)
    ]
    # Orden determinista: por fecha de venta y comision_id
    comisiones.sort(key=lambda c: (c.fecha_venta or date.min, c.comision_id))

    total_comisiones = sum((c.monto for c in comisiones), Decimal("0.00"))
    total_ventas = sum((c.monto_venta for c in comisiones), Decimal("0.00"))

    if formato == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow([
            "comision_id",
            "venta_id",
            "vendedor_id",
            "fecha_venta",
            "monto_venta",
            "regla_id",
            "regla_version",
            "monto",
            "base_acumulada",
            "periodo_id",
            "periodo_origen",
            "estado",
            "ajuste_de",
            "motivo",
        ])
        for c in comisiones:
            writer.writerow([
                c.comision_id,
                c.venta_id,
                c.vendedor_id,
                c.fecha_venta.isoformat() if c.fecha_venta else "",
                f"{c.monto_venta:.2f}",
                c.regla_id,
                c.regla_version,
                f"{c.monto:.2f}",
                f"{c.base_acumulada:.2f}",
                c.periodo_id,
                c.periodo_origen or c.periodo_id,
                c.estado.value,
                c.ajuste_de or "",
                c.motivo or "",
            ])
        return output.getvalue().encode("utf-8")

    if formato == "json":
        lineas = [
            {
                "comision_id": c.comision_id,
                "venta_id": c.venta_id,
                "vendedor_id": c.vendedor_id,
                "fecha_venta": c.fecha_venta.isoformat() if c.fecha_venta else "",
                "monto_venta": f"{c.monto_venta:.2f}",
                "monto_comision": f"{c.monto:.2f}",
                "estado": c.estado.value,
                "periodo_id": c.periodo_id,
                "periodo_origen": c.periodo_origen or c.periodo_id,
                "ajuste_de": c.ajuste_de,
                "motivo": c.motivo,
            }
            for c in comisiones
        ]
        documento = {
            "periodo_id": periodo_id,
            "moneda": moneda,
            "lineas": lineas,
            "totales": {
                "total_comisiones": f"{total_comisiones:.2f}",
                "total_ventas": f"{total_ventas:.2f}",
                "numero_lineas": len(lineas),
            },
        }

        # Validación estricta contra el esquema JSON
        if RUTA_ESQUEMA.exists():
            esquema = json.loads(RUTA_ESQUEMA.read_text(encoding="utf-8"))
            validador = Draft202012Validator(esquema)
            errores = list(validador.iter_errors(documento))
            if errores:
                from features.comisiones.comisiones_service import ExportacionInvalida
                detalle = "; ".join(e.message for e in errores)
                raise ExportacionInvalida(f"Error al validar exportación JSON: {detalle}")

        return json.dumps(documento, indent=2, ensure_ascii=False).encode("utf-8")

    raise ValueError(f"Formato no soportado: {formato}")
