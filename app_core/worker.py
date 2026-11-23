# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Worker de tareas programadas del pasillo central (T-310, TASK-004).

Ejecuta tareas en segundo plano de acuerdo con config_app.yaml:
- checkin_del_dia: envío programado de instrucciones de check-in (INV_ENVIO_UNICO).
- reintentos_cola_crm: procesamiento periódico de la cola persistente del CRM.
- cierre_periodo_comisiones: liquidación mensual de períodos vencidos de comisiones.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from typing import Any

from app_core.app_core_service import Contenedor, construir


# ¤pasillo-central
def checkin_del_dia(contenedor: Contenedor, fecha: date | None = None) -> int:
    """Envía instrucciones de check-in para reservas que llegan en la fecha indicada (INV_ENVIO_UNICO).

    Invoca la compuerta del agente, que comprueba si la plantilla ya fue enviada hoy para cada
    código de reserva antes de emitir a través del canal oficial de WhatsApp.
    """
    fecha_efectiva = fecha or date.today()
    if hasattr(contenedor.agente, "enviar_checkins_del_dia"):
        return contenedor.agente.enviar_checkins_del_dia(fecha_efectiva)
    return 0


# ¤pasillo-central
def reintentos_cola_crm(contenedor: Contenedor, ahora: datetime | None = None) -> int:
    """Procesa la cola persistente de publicaciones fallidas del CRM (RF-CRM-04)."""
    if hasattr(contenedor.crm, "procesar_cola"):
        return contenedor.crm.procesar_cola(ahora=ahora)
    return 0


# ¤pasillo-central
def cierre_periodo_comisiones(contenedor: Contenedor, periodo: str | None = None) -> Any:
    """Cierra el período de comisiones vencido invocando la compuerta de comisiones."""
    if hasattr(contenedor.comisiones, "cerrar_periodo"):
        return contenedor.comisiones.cerrar_periodo(periodo)
    return None


# ¤pasillo-central
def ejecutar_tareas_programadas(
    contenedor: Contenedor,
    tareas: list[str] | None = None,
) -> dict[str, Any]:
    """Ejecuta en lote las tareas programadas configuradas."""
    lista = tareas or ["checkin_del_dia", "reintentos_cola_crm"]
    resultados: dict[str, Any] = {}
    if "checkin_del_dia" in lista:
        resultados["checkin_del_dia"] = checkin_del_dia(contenedor)
    if "reintentos_cola_crm" in lista:
        resultados["reintentos_cola_crm"] = reintentos_cola_crm(contenedor)
    if "cierre_periodo_comisiones" in lista:
        resultados["cierre_periodo_comisiones"] = cierre_periodo_comisiones(contenedor)
    return resultados


# ¤pasillo-central
def main(argumentos: list[str] | None = None) -> int:
    """Punto de entrada CLI para ejecutar tareas programadas en modo worker."""
    analizador = argparse.ArgumentParser(description="Worker de tareas programadas de Glamping Imbabura")
    analizador.add_argument(
        "--tarea",
        choices=["checkin_del_dia", "reintentos_cola_crm", "cierre_periodo_comisiones", "todas"],
        default="todas",
        help="Tarea programada a ejecutar",
    )
    opciones = analizador.parse_args(argumentos)
    contenedor = construir()

    tareas = None
    if opciones.tarea != "todas":
        tareas = [opciones.tarea]

    resultados = ejecutar_tareas_programadas(contenedor, tareas=tareas)
    print(f"Worker completado: {resultados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
