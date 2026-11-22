# ¤comisiones
# ¤¤backend-developer
"""Persistencia interna para la sala comisiones (tablas del esquema comisiones).

Gestiona reglas, periodos y comisiones en SQLite con triggers de inmutabilidad (RF-COM-01, RF-COM-02).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import sqlite3
from typing import Any, Mapping

from features.comisiones.tipos import (
    Comision,
    Escalon,
    EstadoComision,
    ModoEscalon,
    Periodo,
    ReglaComision,
    TipoRegla,
)
from features.persistencia_sql.persistencia_sql_service import envolver

__all__ = ["PersistenciaComisiones"]



# ¤comisiones
def _limites_mes(mes: str) -> tuple[str, str]:
    """'2026-03' -> ('2026-03-01', '2026-04-01'): rango portable en SQLite (texto ISO) y PostgreSQL (date)."""
    anio, numero = (int(parte) for parte in mes.split("-")[:2])
    siguiente = (anio + 1, 1) if numero == 12 else (anio, numero + 1)
    return f"{anio:04d}-{numero:02d}-01", f"{siguiente[0]:04d}-{siguiente[1]:02d}-01"


# ¤comisiones
class PersistenciaComisiones:
    """Acceso a datos SQLite para comisiones, reglas y periodos."""

    def __init__(self, origen: Any = None) -> None:
        # None: DATABASE_URL (PostgreSQL, esquema comisiones) o SQLite en memoria; también URL, ruta o conexión.
        self._con = envolver(origen, ruta_busqueda="comisiones")
        self._con.row_factory = sqlite3.Row
        if not self._con.es_postgres:
            self._inicializar_tablas()  # en PostgreSQL el esquema lo aplica scripts/migrar_db.py

    def _inicializar_tablas(self) -> None:
        with self._con:
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS reglas (
                    regla_id TEXT NOT NULL,
                    version INTEGER NOT NULL CHECK (version >= 1),
                    vendedor_id TEXT,
                    propiedad_id TEXT,
                    producto_patron TEXT,
                    tipo TEXT NOT NULL CHECK (tipo IN ('porcentaje', 'fijo', 'escalonada')),
                    valor NUMERIC,
                    escalones TEXT NOT NULL DEFAULT '[]',
                    modo_escalon TEXT NOT NULL DEFAULT 'graduado' CHECK (modo_escalon IN ('graduado', 'volumen')),
                    vigente_desde TEXT NOT NULL,
                    vigente_hasta TEXT,
                    creada_por TEXT NOT NULL,
                    creada_en TEXT NOT NULL,
                    PRIMARY KEY (regla_id, version)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS periodos (
                    periodo_id TEXT PRIMARY KEY,
                    cerrado_en TEXT,
                    cerrado_por TEXT,
                    resumen_json TEXT
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS comisiones (
                    comision_id TEXT PRIMARY KEY,
                    venta_id TEXT NOT NULL,
                    vendedor_id TEXT NOT NULL,
                    fecha_venta TEXT NOT NULL,
                    monto_venta NUMERIC NOT NULL,
                    regla_id TEXT NOT NULL,
                    regla_version INTEGER NOT NULL,
                    monto NUMERIC NOT NULL,
                    base_acumulada NUMERIC NOT NULL DEFAULT 0,
                    periodo_id TEXT NOT NULL,
                    periodo_origen TEXT NOT NULL,
                    estado TEXT NOT NULL CHECK (estado IN ('estimada', 'fijada', 'pagada', 'ajustada')),
                    ajuste_de TEXT,
                    motivo TEXT,
                    FOREIGN KEY (regla_id, regla_version) REFERENCES reglas (regla_id, version),
                    FOREIGN KEY (periodo_id) REFERENCES periodos (periodo_id),
                    FOREIGN KEY (ajuste_de) REFERENCES comisiones (comision_id)
                );
                """
            )
            self._con.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS comision_unica_por_venta
                ON comisiones (venta_id) WHERE ajuste_de IS NULL;
                """
            )
            # Triggers de protección de períodos cerrados
            self._con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS proteger_periodo_cerrado_update
                BEFORE UPDATE ON comisiones
                FOR EACH ROW
                WHEN (SELECT cerrado_en FROM periodos WHERE periodo_id = OLD.periodo_id) IS NOT NULL
                BEGIN
                    SELECT RAISE(ABORT, 'PeriodoCerrado: periodo cerrado');
                END;
                """
            )
            self._con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS proteger_periodo_cerrado_delete
                BEFORE DELETE ON comisiones
                FOR EACH ROW
                WHEN (SELECT cerrado_en FROM periodos WHERE periodo_id = OLD.periodo_id) IS NOT NULL
                BEGIN
                    SELECT RAISE(ABORT, 'PeriodoCerrado: periodo cerrado');
                END;
                """
            )
            self._con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS proteger_periodo_cerrado_insert
                BEFORE INSERT ON comisiones
                FOR EACH ROW
                WHEN (SELECT cerrado_en FROM periodos WHERE periodo_id = NEW.periodo_id) IS NOT NULL
                BEGIN
                    SELECT RAISE(ABORT, 'PeriodoCerrado: periodo cerrado');
                END;
                """
            )
            # Triggers de protección de reglas inmutables
            self._con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS proteger_regla_update
                BEFORE UPDATE ON reglas
                FOR EACH ROW
                BEGIN
                    SELECT RAISE(ABORT, 'ReglaInmutable: crea una versión nueva');
                END;
                """
            )
            self._con.execute(
                """
                CREATE TRIGGER IF NOT EXISTS proteger_regla_delete
                BEFORE DELETE ON reglas
                FOR EACH ROW
                BEGIN
                    SELECT RAISE(ABORT, 'ReglaInmutable: crea una versión nueva');
                END;
                """
            )

    # ¤comisiones
    def guardar_regla(self, regla: ReglaComision, creada_por: str = "sistema") -> None:
        escalones_json = json.dumps(
            [{"desde": str(e.desde_monto), "porcentaje": str(e.porcentaje)} for e in regla.escalones]
        )
        with self._con:
            self._con.execute(
                """
                INSERT INTO reglas (
                    regla_id, version, vendedor_id, propiedad_id, producto_patron,
                    tipo, valor, escalones, modo_escalon, vigente_desde, vigente_hasta,
                    creada_por, creada_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    regla.regla_id,
                    regla.version,
                    regla.vendedor_id,
                    regla.propiedad_id,
                    regla.producto_patron,
                    regla.tipo.value,
                    str(regla.valor) if regla.valor is not None else None,
                    escalones_json,
                    regla.modo_escalon.value,
                    regla.vigente_desde.isoformat(),
                    regla.vigente_hasta.isoformat() if regla.vigente_hasta else None,
                    creada_por,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    # ¤comisiones
    def obtener_reglas(self) -> list[ReglaComision]:
        cursor = self._con.execute("SELECT * FROM reglas ORDER BY regla_id, version ASC")
        return [self._fila_a_regla(row) for row in cursor.fetchall()]

    # ¤comisiones
    def obtener_regla(self, regla_id: str, version: int) -> ReglaComision | None:
        cursor = self._con.execute(
            "SELECT * FROM reglas WHERE regla_id = ? AND version = ?", (regla_id, version)
        )
        row = cursor.fetchone()
        return self._fila_a_regla(row) if row else None

    # ¤comisiones
    def _fila_a_regla(self, row: sqlite3.Row) -> ReglaComision:
        escalones_data = json.loads(row["escalones"]) if row["escalones"] else []
        escalones = tuple(
            Escalon(desde_monto=Decimal(str(e["desde"])), porcentaje=Decimal(str(e["porcentaje"])))
            for e in escalones_data
        )
        return ReglaComision(
            regla_id=row["regla_id"],
            version=row["version"],
            tipo=TipoRegla(row["tipo"]),
            valor=Decimal(str(row["valor"])) if row["valor"] is not None else Decimal("0"),
            vigente_desde=date.fromisoformat(row["vigente_desde"]),
            vigente_hasta=date.fromisoformat(row["vigente_hasta"]) if row["vigente_hasta"] else None,
            vendedor_id=row["vendedor_id"],
            propiedad_id=row["propiedad_id"],
            producto_patron=row["producto_patron"],
            escalones=escalones,
            modo_escalon=ModoEscalon(row["modo_escalon"]),
        )

    # ¤comisiones
    def asegurar_periodo(self, periodo_id: str) -> Periodo:
        periodo = self.obtener_periodo(periodo_id)
        if periodo:
            return periodo
        with self._con:
            self._con.execute(
                "INSERT INTO periodos (periodo_id, cerrado_en, cerrado_por, resumen_json) VALUES (?, NULL, NULL, NULL) ON CONFLICT (periodo_id) DO NOTHING",
                (periodo_id,),
            )
        return self.obtener_periodo(periodo_id) or Periodo(periodo_id=periodo_id)

    # ¤comisiones
    def obtener_periodo(self, periodo_id: str) -> Periodo | None:
        cursor = self._con.execute("SELECT * FROM periodos WHERE periodo_id = ?", (periodo_id,))
        row = cursor.fetchone()
        if not row:
            return None
        resumen = json.loads(row["resumen_json"]) if row["resumen_json"] else {}
        cerrado_en = datetime.fromisoformat(row["cerrado_en"]) if row["cerrado_en"] else None
        return Periodo(
            periodo_id=row["periodo_id"],
            cerrado_en=cerrado_en,
            cerrado_por=row["cerrado_por"],
            resumen=resumen,
        )

    # ¤comisiones
    def cerrar_periodo(self, periodo_id: str, cerrado_por: str, resumen: Mapping[str, Any]) -> Periodo:
        ahora = datetime.now(timezone.utc).isoformat()
        resumen_json = json.dumps(resumen)
        with self._con:
            self._con.execute(
                """
                UPDATE periodos
                SET cerrado_en = ?, cerrado_por = ?, resumen_json = ?
                WHERE periodo_id = ?
                """,
                (ahora, cerrado_por, resumen_json, periodo_id),
            )
        periodo = self.obtener_periodo(periodo_id)
        if not periodo:
            raise RuntimeError(f"No se pudo recuperar periodo {periodo_id}")
        return periodo

    # ¤comisiones
    def obtener_periodos_abiertos(self) -> list[str]:
        cursor = self._con.execute(
            "SELECT periodo_id FROM periodos WHERE cerrado_en IS NULL ORDER BY periodo_id ASC"
        )
        return [row["periodo_id"] for row in cursor.fetchall()]

    # ¤comisiones
    def guardar_comision(self, comision: Comision) -> None:
        self.asegurar_periodo(comision.periodo_id)
        with self._con:
            self._con.execute(
                """
                INSERT INTO comisiones (
                    comision_id, venta_id, vendedor_id, fecha_venta, monto_venta,
                    regla_id, regla_version, monto, base_acumulada, periodo_id,
                    periodo_origen, estado, ajuste_de, motivo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comision.comision_id,
                    comision.venta_id,
                    comision.vendedor_id,
                    comision.fecha_venta.isoformat() if comision.fecha_venta else date.today().isoformat(),
                    str(comision.monto_venta),
                    comision.regla_id,
                    comision.regla_version,
                    str(comision.monto),
                    str(comision.base_acumulada),
                    comision.periodo_id,
                    comision.periodo_origen or comision.periodo_id,
                    comision.estado.value,
                    comision.ajuste_de,
                    comision.motivo,
                ),
            )

    # ¤comisiones
    def actualizar_comision_fijada(
        self,
        comision_id: str,
        monto: Decimal,
        base_acumulada: Decimal,
        periodo_id: str,
        periodo_origen: str,
    ) -> None:
        self.asegurar_periodo(periodo_id)
        with self._con:
            self._con.execute(
                """
                UPDATE comisiones
                SET monto = ?, base_acumulada = ?, periodo_id = ?, periodo_origen = ?, estado = 'fijada'
                WHERE comision_id = ?
                """,
                (str(monto), str(base_acumulada), periodo_id, periodo_origen, comision_id),
            )

    # ¤comisiones
    def obtener_comision(self, comision_id: str) -> Comision | None:
        cursor = self._con.execute("SELECT * FROM comisiones WHERE comision_id = ?", (comision_id,))
        row = cursor.fetchone()
        return self._fila_a_comision(row) if row else None

    # ¤comisiones
    def obtener_comision_por_venta(self, venta_id: str) -> Comision | None:
        cursor = self._con.execute(
            "SELECT * FROM comisiones WHERE venta_id = ? AND ajuste_de IS NULL", (venta_id,)
        )
        row = cursor.fetchone()
        return self._fila_a_comision(row) if row else None

    # ¤comisiones
    def obtener_comisiones_periodo(self, periodo_id: str) -> list[Comision]:
        cursor = self._con.execute(
            "SELECT * FROM comisiones WHERE periodo_id = ? ORDER BY fecha_venta ASC, comision_id ASC",
            (periodo_id,),
        )
        return [self._fila_a_comision(row) for row in cursor.fetchall()]

    # ¤comisiones
    def obtener_comisiones_vendedor(self, vendedor_id: str, periodo_id: str) -> list[Comision]:
        cursor = self._con.execute(
            """
            SELECT * FROM comisiones
            WHERE vendedor_id = ? AND periodo_id = ?
            ORDER BY fecha_venta ASC, comision_id ASC
            """,
            (vendedor_id, periodo_id),
        )
        return [self._fila_a_comision(row) for row in cursor.fetchall()]

    # ¤comisiones
    def obtener_base_acumulada(self, vendedor_id: str, regla_id: str, mes_fecha_venta: str) -> Decimal:
        """Obtiene la base acumulada de ventas fijadas o ajustadas para la terna (vendedor, regla, mes)."""
        cursor = self._con.execute(
            """
            SELECT COALESCE(SUM(monto_venta), 0) as total_base
            FROM comisiones
            WHERE vendedor_id = ?
              AND regla_id = ?
              AND fecha_venta >= ? AND fecha_venta < ?
              AND estado IN ('fijada', 'pagada', 'ajustada')
            """,
            (vendedor_id, regla_id, *_limites_mes(mes_fecha_venta)),
        )
        row = cursor.fetchone()
        return Decimal(str(row["total_base"])).quantize(Decimal("0.01")) if row else Decimal("0.00")

    # ¤comisiones
    def obtener_total_comisiones_mes(self, vendedor_id: str, regla_id: str, mes_fecha_venta: str) -> Decimal:
        """Obtiene la suma neta de comisiones fijadas o ajustadas del mes de venta original."""
        cursor = self._con.execute(
            """
            SELECT COALESCE(SUM(monto), 0) as total_comision
            FROM comisiones
            WHERE vendedor_id = ?
              AND regla_id = ?
              AND periodo_origen = ?
              AND estado IN ('fijada', 'pagada', 'ajustada')
            """,
            (vendedor_id, regla_id, mes_fecha_venta),
        )
        row = cursor.fetchone()
        return Decimal(str(row["total_comision"])).quantize(Decimal("0.01")) if row else Decimal("0.00")

    # ¤comisiones
    def _fila_a_comision(self, row: sqlite3.Row) -> Comision:
        return Comision(
            comision_id=row["comision_id"],
            venta_id=row["venta_id"],
            vendedor_id=row["vendedor_id"],
            fecha_venta=date.fromisoformat(row["fecha_venta"]),
            monto_venta=Decimal(str(row["monto_venta"])).quantize(Decimal("0.01")),
            regla_id=row["regla_id"],
            regla_version=row["regla_version"],
            monto=Decimal(str(row["monto"])).quantize(Decimal("0.01")),
            base_acumulada=Decimal(str(row["base_acumulada"])).quantize(Decimal("0.01")),
            periodo_id=row["periodo_id"],
            periodo_origen=row["periodo_origen"],
            estado=EstadoComision(row["estado"]),
            ajuste_de=row["ajuste_de"],
            motivo=row["motivo"],
        )
