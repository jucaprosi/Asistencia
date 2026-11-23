# ¤comisiones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Gestión de períodos mensuales, cierre inmutable y enrutamiento de ventas tardías (RF-COM-02).

Garantiza que un período cerrado quede inmutable y que ventas tardías o ajustes
entren al período abierto más antiguo conservando su periodo_origen.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
import threading
from typing import Any, Mapping

from features.comisiones.persistencia_internal import PersistenciaComisiones
from features.comisiones.tipos import EstadoComision, Periodo

__all__ = [
    "GestorBloqueos",
    "calcular_resumen_periodo",
    "periodo_de_fecha",
    "resolver_periodo_destino",
]


# ¤comisiones
def periodo_de_fecha(fecha: date) -> str:
    """Devuelve el identificador de período YYYY-MM para una fecha dada."""
    return f"{fecha.year:04d}-{fecha.month:02d}"


# ¤comisiones
def resolver_periodo_destino(
    persistencia: PersistenciaComisiones,
    fecha_venta: date,
) -> tuple[str, str, bool]:
    """Determina (periodo_destino, periodo_origen, es_tardia).

    Si el mes de la venta está abierto, entra en él. Si ya cerró, entra en el
    período abierto más antiguo con periodo_origen correspondiente al mes de la venta.
    """
    mes_origen = periodo_de_fecha(fecha_venta)
    periodo_actual = persistencia.obtener_periodo(mes_origen)

    if periodo_actual is None or periodo_actual.cerrado_en is None:
        # Aseguramos que exista abierto
        persistencia.asegurar_periodo(mes_origen)
        return mes_origen, mes_origen, False

    # El período de origen está cerrado: buscar el abierto más antiguo
    abiertos = persistencia.obtener_periodos_abiertos()
    if abiertos:
        # Filtrar solo periodos posteriores o el más antiguo abierto disponible
        return abiertos[0], mes_origen, True

    # Si no hay abiertos, creamos el siguiente mes cronológico al de origen
    y, m = int(mes_origen[:4]), int(mes_origen[5:7])
    if m == 12:
        y += 1
        m = 1
    else:
        m += 1
    siguiente_mes = f"{y:04d}-{m:02d}"
    persistencia.asegurar_periodo(siguiente_mes)
    return siguiente_mes, mes_origen, True


# ¤comisiones
def calcular_resumen_periodo(
    persistencia: PersistenciaComisiones,
    periodo_id: str,
) -> dict[str, Any]:
    """Genera el resumen estructurado de un período por vendedor y totales globales."""
    comisiones = persistencia.obtener_comisiones_periodo(periodo_id)

    por_vendedor: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "total": Decimal("0.00"),
        "ventas": 0,
        "ajustes": Decimal("0.00"),
        "base_acumulada": Decimal("0.00"),
    })

    total_fijadas = Decimal("0.00")
    total_estimadas = Decimal("0.00")
    total_ventas = 0
    total_ajustes = 0
    total_monto_ventas = Decimal("0.00")

    for c in comisiones:
        if c.estado in (EstadoComision.FIJADA, EstadoComision.PAGADA, EstadoComision.AJUSTADA):
            por_vendedor[c.vendedor_id]["total"] += c.monto
            if c.ajuste_de is None:
                por_vendedor[c.vendedor_id]["ventas"] += 1
                por_vendedor[c.vendedor_id]["base_acumulada"] += c.monto_venta
                total_ventas += 1
                total_monto_ventas += c.monto_venta
            else:
                por_vendedor[c.vendedor_id]["ajustes"] += c.monto
                por_vendedor[c.vendedor_id]["base_acumulada"] += c.monto_venta
                total_ajustes += 1
                total_monto_ventas += c.monto_venta
            total_fijadas += c.monto
        elif c.estado == EstadoComision.ESTIMADA:
            total_estimadas += c.monto

    # Formatear a serializables en JSON
    vendedores_dict = {
        v_id: {
            "total": str(datos["total"]),
            "ventas": datos["ventas"],
            "ajustes": str(datos["ajustes"]),
            "base_acumulada": str(datos["base_acumulada"]),
        }
        for v_id, datos in por_vendedor.items()
    }

    return {
        "periodo_id": periodo_id,
        "total_comisiones": str(total_fijadas),
        "total_estimadas": str(total_estimadas),
        "total_ventas": str(total_monto_ventas),
        "numero_ventas": total_ventas,
        "numero_ajustes": total_ajustes,
        "vendedores": vendedores_dict,
    }


# ¤comisiones
class GestorBloqueos:
    """Sincroniza cálculos concurrentes sobre (vendedor_id, regla_id, mes_de_fecha_venta)."""

    def __init__(self) -> None:
        self._master_lock = threading.Lock()
        self._locks: dict[tuple[str, str, str], threading.Lock] = {}

    def obtener_lock(self, vendedor_id: str, regla_id: str, mes_fecha_venta: str) -> threading.Lock:
        clave = (vendedor_id, regla_id, mes_fecha_venta)
        with self._master_lock:
            if clave not in self._locks:
                self._locks[clave] = threading.Lock()
            return self._locks[clave]
