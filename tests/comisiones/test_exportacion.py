# ¤comisiones
# ¤¤backend-developer
"""Pruebas para exportación de comisiones a CSV y JSON validado (RF-COM-03)."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
import io
import json
from pathlib import Path
import jsonschema
import pytest

from features.comisiones.comisiones_service import (
    ComisionesService,
)
from features.comisiones.persistencia_internal import PersistenciaComisiones
from features.comisiones.tipos import (
    Escalon,
    ModoEscalon,
    ReglaComision,
    TipoRegla,
)
from tests.comisiones.dobles import DobleObservabilidad, DobleSeguridad

RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_ESQUEMA = RAIZ / "features" / "comisiones" / "esquema_exportacion.json"


# ¤comisiones
@pytest.fixture
def servicio() -> ComisionesService:
    persistencia = PersistenciaComisiones(":memory:")
    seguridad = DobleSeguridad()
    observabilidad = DobleObservabilidad()
    config = {"moneda": "USD", "periodo": "mensual"}
    srv = ComisionesService(config, seguridad=seguridad, observabilidad=observabilidad, persistencia=persistencia)

    regla = ReglaComision(
        regla_id="regla-graduada",
        version=1,
        tipo=TipoRegla.ESCALONADA,
        valor=Decimal("0.0"),
        modo_escalon=ModoEscalon.GRADUADO,
        vigente_desde=date(2026, 1, 1),
        escalones=(
            Escalon(desde_monto=Decimal("0.0"), porcentaje=Decimal("5.0")),
            Escalon(desde_monto=Decimal("1000.0"), porcentaje=Decimal("10.0")),
        ),
    )
    srv.crear_regla("admin", regla)

    # Ventas en orden desordenado para comprobar determinismo posterior
    c2 = srv.calcular("v-2", "vend-1", None, "prod", Decimal("700.10"), date(2026, 10, 10))
    srv.fijar(c2.comision_id)
    c1 = srv.calcular("v-1", "vend-1", None, "prod", Decimal("333.33"), date(2026, 10, 5))
    srv.fijar(c1.comision_id)
    c3 = srv.calcular("v-3", "vend-1", None, "prod", Decimal("566.57"), date(2026, 10, 15))
    srv.fijar(c3.comision_id)

    return srv


# ¤comisiones
def test_escenario_exportacion_periodo_cerrado_valida_contra_esquema(servicio: ComisionesService) -> None:
    """Escenario: Exportación del período (@RF-COM-03).

    Dado un período cerrado
    Cuando se exporta
    Entonces el archivo valida contra esquema_exportacion.json
    """
    # 1. Dado un período cerrado
    periodo_cerrado = servicio.cerrar_periodo("2026-10", "admin")
    assert periodo_cerrado.cerrado_en is not None

    # 2. Cuando se exporta en formato JSON
    contenido_bytes = servicio.exportar("2026-10", "json")
    doc = json.loads(contenido_bytes.decode("utf-8"))

    # 3. Entonces el archivo valida contra esquema_exportacion.json
    assert RUTA_ESQUEMA.is_file(), f"No se encontró el esquema en {RUTA_ESQUEMA}"
    esquema = json.loads(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=esquema)

    assert doc["periodo_id"] == "2026-10"
    assert doc["moneda"] == "USD"
    assert doc["totales"]["total_comisiones"] == "110.00"
    assert doc["totales"]["total_ventas"] == "1600.00"
    assert doc["totales"]["numero_lineas"] == 3


# ¤comisiones
def test_exportar_csv_determinista_y_cuadra_con_json(servicio: ComisionesService) -> None:
    """Verifica que la exportación CSV sea determinista y cuadre al centavo con el JSON."""
    csv_bytes = servicio.exportar("2026-10", "csv")
    texto = csv_bytes.decode("utf-8")
    lector = csv.DictReader(io.StringIO(texto))
    filas = list(lector)

    assert len(filas) == 3

    # Orden determinista: la primera debe ser v-1 (fecha 2026-10-05), luego v-2 (10), luego v-3 (15)
    assert filas[0]["venta_id"] == "v-1"
    assert filas[1]["venta_id"] == "v-2"
    assert filas[2]["venta_id"] == "v-3"

    total_comision_csv = sum(Decimal(f["monto"]) for f in filas)
    total_ventas_csv = sum(Decimal(f["monto_venta"]) for f in filas)

    assert total_comision_csv == Decimal("110.00")
    assert total_ventas_csv == Decimal("1600.00")

    # Comparar con JSON
    json_bytes = servicio.exportar("2026-10", "json")
    doc_json = json.loads(json_bytes.decode("utf-8"))

    assert Decimal(doc_json["totales"]["total_comisiones"]) == total_comision_csv
    assert Decimal(doc_json["totales"]["total_ventas"]) == total_ventas_csv


# ¤comisiones
def test_exportar_con_ajustes_por_anulacion_valida_contra_esquema(servicio: ComisionesService) -> None:
    """Verifica que una anulación genere un ajuste en la exportación y siga validando contra el esquema."""
    # Anular una venta en el período abierto
    servicio.anular_venta("v-1", "admin", "Cancelación por solicitud del cliente")

    contenido_bytes = servicio.exportar("2026-10", "json")
    doc = json.loads(contenido_bytes.decode("utf-8"))

    # Validar contra esquema_exportacion.json
    esquema = json.loads(RUTA_ESQUEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=esquema)

    # Ahora hay 4 líneas (3 ventas + 1 ajuste)
    assert doc["totales"]["numero_lineas"] == 4
    lineas_ajuste = [l for l in doc["lineas"] if l.get("ajuste_de") is not None]
    assert len(lineas_ajuste) == 1

    ajuste = lineas_ajuste[0]
    assert ajuste["estado"] == "ajustada"
    assert ajuste["motivo"] == "Cancelación por solicitud del cliente"
    assert Decimal(ajuste["monto_comision"]) < Decimal("0.00")

    # El CSV también incluye la línea de ajuste
    csv_bytes = servicio.exportar("2026-10", "csv")
    filas_csv = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    assert len(filas_csv) == 4
    assert any(f["estado"] == "ajustada" and f["ajuste_de"] for f in filas_csv)


# ¤comisiones
def test_exportar_formato_no_soportado_lanza_error(servicio: ComisionesService) -> None:
    """Verifica que un formato inválido lance ValueError."""
    with pytest.raises(ValueError, match="Formato no soportado"):
        servicio.exportar("2026-10", "xml")  # type: ignore[arg-type]
