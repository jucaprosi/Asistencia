# ¤anfitriones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Persistencia interna para la sala anfitriones (tablas del esquema anfitriones).

Gestiona anfitriones, hospedajes, solicitudes, estados_cuenta y lineas_cuenta en SQLite.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import sqlite3
from typing import Any
import uuid

from features.anfitriones.tipos import (
    Anfitrion,
    EstadoAnfitrion,
    EstadoCuenta,
    EstadoDeCuenta,
    EstadoHospedaje,
    EstadoSolicitud,
    Hospedaje,
    LineaCuenta,
    Solicitud,
)
from features.persistencia_sql.persistencia_sql_service import envolver

__all__ = ["PersistenciaAnfitriones"]


# ¤anfitriones
class PersistenciaAnfitriones:
    """Acceso a datos para el esquema anfitriones."""

    def __init__(self, origen: Any = None) -> None:
        # None: DATABASE_URL (PostgreSQL, esquema anfitriones) o SQLite en memoria; también URL, ruta o conexión.
        self._con = envolver(origen, ruta_busqueda="anfitriones")
        self._con.row_factory = sqlite3.Row
        if not self._con.es_postgres:
            self._inicializar_tablas()  # en PostgreSQL el esquema lo aplica scripts/migrar_db.py

    def _inicializar_tablas(self) -> None:
        with self._con:
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS anfitriones (
                    anfitrion_id TEXT PRIMARY KEY,
                    nombre_comercial TEXT NOT NULL,
                    telefono_token TEXT NOT NULL UNIQUE,
                    comision_porcentaje NUMERIC NOT NULL,
                    terminos_version TEXT NOT NULL,
                    terminos_aceptados_en TEXT NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'activo',
                    creado_en TEXT NOT NULL
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS hospedajes (
                    propiedad_id TEXT PRIMARY KEY,
                    anfitrion_id TEXT NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'borrador',
                    publicado_por TEXT,
                    publicado_en TEXT,
                    FOREIGN KEY (anfitrion_id) REFERENCES anfitriones (anfitrion_id)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS solicitudes (
                    solicitud TEXT PRIMARY KEY,
                    codigo_reserva TEXT NOT NULL UNIQUE,
                    propiedad_id TEXT NOT NULL,
                    anfitrion_id TEXT NOT NULL,
                    desde TEXT NOT NULL,
                    hasta TEXT NOT NULL,
                    total NUMERIC NOT NULL,
                    comision_porcentaje NUMERIC NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'solicitada',
                    vence_en TEXT NOT NULL,
                    respondida_en TEXT,
                    creado_en TEXT NOT NULL,
                    FOREIGN KEY (propiedad_id) REFERENCES hospedajes (propiedad_id),
                    FOREIGN KEY (anfitrion_id) REFERENCES anfitriones (anfitrion_id)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS estados_cuenta (
                    estado_cuenta_id TEXT PRIMARY KEY,
                    anfitrion_id TEXT NOT NULL,
                    periodo TEXT NOT NULL,
                    total NUMERIC NOT NULL,
                    estado TEXT NOT NULL DEFAULT 'emitido',
                    emitido_en TEXT NOT NULL,
                    vence_en TEXT NOT NULL,
                    pagado_en TEXT,
                    pago_registrado_por TEXT,
                    UNIQUE (anfitrion_id, periodo)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS lineas_cuenta (
                    linea_id TEXT PRIMARY KEY,
                    estado_cuenta_id TEXT NOT NULL,
                    solicitud TEXT NOT NULL,
                    tipo TEXT NOT NULL DEFAULT 'cargo',
                    base NUMERIC NOT NULL,
                    porcentaje NUMERIC NOT NULL,
                    comision NUMERIC NOT NULL,
                    UNIQUE (solicitud, tipo),
                    FOREIGN KEY (estado_cuenta_id) REFERENCES estados_cuenta (estado_cuenta_id)
                );
                """
            )
            self._con.execute(
                """
                CREATE TABLE IF NOT EXISTS secuencias (
                    nombre TEXT PRIMARY KEY,
                    valor INTEGER NOT NULL
                );
                """
            )

    def siguiente_codigo_solicitud(self, year: int | None = None) -> str:
        """Genera un código correlativo PL-YYYY-NNNN."""
        if year is None:
            year = datetime.now(timezone.utc).year
        nombre_sec = f"solicitud_{year}"
        with self._con:
            # Incremento atómico: dos instancias concurrentes nunca obtienen el mismo número.
            fila = self._con.execute(
                "INSERT INTO secuencias (nombre, valor) VALUES (?, 1) "
                "ON CONFLICT (nombre) DO UPDATE SET valor = secuencias.valor + 1 RETURNING valor",
                (nombre_sec,),
            ).fetchone()
            valor = int(fila["valor"])
        return f"PL-{year}-{valor:04d}"

    def guardar_anfitrion(self, anfitrion: Anfitrion) -> None:
        ahora_iso = (
            anfitrion.creado_en.isoformat()
            if anfitrion.creado_en
            else datetime.now(timezone.utc).isoformat()
        )
        terminos_iso = (
            anfitrion.terminos_aceptados_en.isoformat()
            if anfitrion.terminos_aceptados_en
            else ahora_iso
        )
        with self._con:
            self._con.execute(
                """
                INSERT INTO anfitriones (
                    anfitrion_id, nombre_comercial, telefono_token, comision_porcentaje,
                    terminos_version, terminos_aceptados_en, estado, creado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anfitrion_id) DO UPDATE SET
                    nombre_comercial = excluded.nombre_comercial,
                    telefono_token = excluded.telefono_token,
                    comision_porcentaje = excluded.comision_porcentaje,
                    terminos_version = excluded.terminos_version,
                    terminos_aceptados_en = excluded.terminos_aceptados_en,
                    estado = excluded.estado;
                """,
                (
                    anfitrion.anfitrion_id,
                    anfitrion.nombre_comercial,
                    anfitrion.telefono_token or "",
                    float(anfitrion.comision_porcentaje),
                    anfitrion.terminos_version,
                    terminos_iso,
                    anfitrion.estado.value,
                    ahora_iso,
                ),
            )

    def obtener_anfitrion(self, anfitrion_id: str) -> Anfitrion | None:
        cursor = self._con.execute(
            "SELECT * FROM anfitriones WHERE anfitrion_id = ?", (anfitrion_id,)
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return Anfitrion(
            anfitrion_id=fila["anfitrion_id"],
            nombre_comercial=fila["nombre_comercial"],
            comision_porcentaje=Decimal(str(fila["comision_porcentaje"])),
            terminos_version=fila["terminos_version"],
            estado=EstadoAnfitrion(fila["estado"]),
            telefono_token=fila["telefono_token"],
            terminos_aceptados_en=datetime.fromisoformat(fila["terminos_aceptados_en"]),
            creado_en=datetime.fromisoformat(fila["creado_en"]),
        )

    def obtener_anfitrion_por_telefono(self, telefono_token: str) -> Anfitrion | None:
        cursor = self._con.execute(
            "SELECT * FROM anfitriones WHERE telefono_token = ?", (telefono_token,)
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return self.obtener_anfitrion(fila["anfitrion_id"])

    def guardar_hospedaje(self, hospedaje: Hospedaje) -> None:
        pub_iso = hospedaje.publicado_en.isoformat() if hospedaje.publicado_en else None
        with self._con:
            self._con.execute(
                """
                INSERT INTO hospedajes (propiedad_id, anfitrion_id, estado, publicado_por, publicado_en)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(propiedad_id) DO UPDATE SET
                    anfitrion_id = excluded.anfitrion_id,
                    estado = excluded.estado,
                    publicado_por = excluded.publicado_por,
                    publicado_en = excluded.publicado_en;
                """,
                (
                    hospedaje.propiedad_id,
                    hospedaje.anfitrion_id,
                    hospedaje.estado.value,
                    hospedaje.publicado_por,
                    pub_iso,
                ),
            )

    def obtener_hospedaje(self, propiedad_id: str) -> Hospedaje | None:
        cursor = self._con.execute(
            "SELECT * FROM hospedajes WHERE propiedad_id = ?", (propiedad_id,)
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        pub_dt = (
            datetime.fromisoformat(fila["publicado_en"])
            if fila["publicado_en"]
            else None
        )
        return Hospedaje(
            propiedad_id=fila["propiedad_id"],
            anfitrion_id=fila["anfitrion_id"],
            estado=EstadoHospedaje(fila["estado"]),
            publicado_por=fila["publicado_por"],
            publicado_en=pub_dt,
        )

    def listar_publicados(self) -> tuple[Hospedaje, ...]:
        """INV_SOLO_PUBLICADO: visible(h) => estado(h) = publicado y estado(anfitrion(h)) = activo."""
        cursor = self._con.execute(
            """
            SELECT h.* FROM hospedajes h
            JOIN anfitriones a ON h.anfitrion_id = a.anfitrion_id
            WHERE h.estado = 'publicado' AND a.estado = 'activo';
            """
        )
        filas = cursor.fetchall()
        resultados: list[Hospedaje] = []
        for fila in filas:
            pub_dt = (
                datetime.fromisoformat(fila["publicado_en"])
                if fila["publicado_en"]
                else None
            )
            resultados.append(
                Hospedaje(
                    propiedad_id=fila["propiedad_id"],
                    anfitrion_id=fila["anfitrion_id"],
                    estado=EstadoHospedaje(fila["estado"]),
                    publicado_por=fila["publicado_por"],
                    publicado_en=pub_dt,
                )
            )
        return tuple(resultados)

    def guardar_solicitud(self, solicitud: Solicitud) -> None:
        ahora_iso = (
            solicitud.creado_en.isoformat()
            if solicitud.creado_en
            else datetime.now(timezone.utc).isoformat()
        )
        vence_iso = solicitud.vence_en.isoformat()
        resp_iso = (
            solicitud.respondida_en.isoformat() if solicitud.respondida_en else None
        )
        with self._con:
            self._con.execute(
                """
                INSERT INTO solicitudes (
                    solicitud, codigo_reserva, propiedad_id, anfitrion_id, desde, hasta,
                    total, comision_porcentaje, estado, vence_en, respondida_en, creado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(solicitud) DO UPDATE SET
                    estado = excluded.estado,
                    respondida_en = excluded.respondida_en;
                """,
                (
                    solicitud.solicitud,
                    solicitud.codigo_reserva,
                    solicitud.propiedad_id,
                    solicitud.anfitrion_id,
                    solicitud.desde.isoformat(),
                    solicitud.hasta.isoformat(),
                    float(solicitud.total),
                    float(solicitud.comision_porcentaje),
                    solicitud.estado.value,
                    vence_iso,
                    resp_iso,
                    ahora_iso,
                ),
            )

    def obtener_solicitud(self, solicitud_codigo: str) -> Solicitud | None:
        cursor = self._con.execute(
            "SELECT * FROM solicitudes WHERE solicitud = ?", (solicitud_codigo,)
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        resp_dt = (
            datetime.fromisoformat(fila["respondida_en"])
            if fila["respondida_en"]
            else None
        )
        creado_dt = (
            datetime.fromisoformat(fila["creado_en"])
            if fila["creado_en"]
            else None
        )
        return Solicitud(
            solicitud=fila["solicitud"],
            codigo_reserva=fila["codigo_reserva"],
            propiedad_id=fila["propiedad_id"],
            anfitrion_id=fila["anfitrion_id"],
            desde=date.fromisoformat(fila["desde"]),
            hasta=date.fromisoformat(fila["hasta"]),
            total=Decimal(str(fila["total"])),
            comision_porcentaje=Decimal(str(fila["comision_porcentaje"])),
            estado=EstadoSolicitud(fila["estado"]),
            vence_en=datetime.fromisoformat(fila["vence_en"]),
            respondida_en=resp_dt,
            creado_en=creado_dt,
        )

    def obtener_solicitud_por_reserva(self, codigo_reserva: str) -> Solicitud | None:
        cursor = self._con.execute(
            "SELECT * FROM solicitudes WHERE codigo_reserva = ?", (codigo_reserva,)
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return self.obtener_solicitud(fila["solicitud"])

    def actualizar_estado_solicitud(
        self,
        solicitud_codigo: str,
        nuevo_estado: EstadoSolicitud,
        respondida_en: datetime | None = None,
    ) -> None:
        resp_iso = respondida_en.isoformat() if respondida_en else None
        with self._con:
            if resp_iso:
                self._con.execute(
                    "UPDATE solicitudes SET estado = ?, respondida_en = ? WHERE solicitud = ?",
                    (nuevo_estado.value, resp_iso, solicitud_codigo),
                )
            else:
                self._con.execute(
                    "UPDATE solicitudes SET estado = ? WHERE solicitud = ?",
                    (nuevo_estado.value, solicitud_codigo),
                )

    def listar_solicitudes_expirables(self, ahora: datetime) -> tuple[Solicitud, ...]:
        ahora_iso = ahora.isoformat()
        cursor = self._con.execute(
            "SELECT solicitud FROM solicitudes WHERE estado = 'solicitada' AND vence_en <= ?",
            (ahora_iso,),
        )
        filas = cursor.fetchall()
        return tuple(self.obtener_solicitud(f["solicitud"]) for f in filas if self.obtener_solicitud(f["solicitud"]))

    def listar_estadias_a_completar(self, fecha_limite: date) -> tuple[Solicitud, ...]:
        limite_iso = fecha_limite.isoformat()
        cursor = self._con.execute(
            "SELECT solicitud FROM solicitudes WHERE estado = 'confirmada' AND hasta <= ?",
            (limite_iso,),
        )
        filas = cursor.fetchall()
        return tuple(self.obtener_solicitud(f["solicitud"]) for f in filas if self.obtener_solicitud(f["solicitud"]))

    def listar_solicitudes_por_anfitrion(self, anfitrion_id: str) -> tuple[Solicitud, ...]:
        cursor = self._con.execute(
            "SELECT solicitud FROM solicitudes WHERE anfitrion_id = ? ORDER BY creado_en DESC",
            (anfitrion_id,),
        )
        filas = cursor.fetchall()
        return tuple(self.obtener_solicitud(f["solicitud"]) for f in filas if self.obtener_solicitud(f["solicitud"]))

    def guardar_estado_cuenta(self, ec: EstadoDeCuenta) -> None:
        emitido_iso = ec.emitido_en.isoformat() if ec.emitido_en else datetime.now(timezone.utc).isoformat()
        vence_iso = ec.vence_en.isoformat()
        pagado_iso = ec.pagado_en.isoformat() if ec.pagado_en else None
        with self._con:
            self._con.execute(
                """
                INSERT INTO estados_cuenta (
                    estado_cuenta_id, anfitrion_id, periodo, total, estado,
                    emitido_en, vence_en, pagado_en, pago_registrado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anfitrion_id, periodo) DO UPDATE SET
                    total = excluded.total,
                    estado = excluded.estado,
                    pagado_en = excluded.pagado_en,
                    pago_registrado_por = excluded.pago_registrado_por;
                """,
                (
                    ec.estado_cuenta_id,
                    ec.anfitrion_id,
                    ec.periodo,
                    float(ec.total),
                    ec.estado.value,
                    emitido_iso,
                    vence_iso,
                    pagado_iso,
                    ec.pago_registrado_por,
                ),
            )
            for linea in ec.lineas:
                self._guardar_linea_transaccional(ec.estado_cuenta_id, linea)

    def _guardar_linea_transaccional(self, estado_cuenta_id: str, linea: LineaCuenta) -> None:
        linea_id = str(uuid.uuid4())
        self._con.execute(
            """
            INSERT INTO lineas_cuenta (linea_id, estado_cuenta_id, solicitud, tipo, base, porcentaje, comision)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(solicitud, tipo) DO UPDATE SET
                base = excluded.base,
                porcentaje = excluded.porcentaje,
                comision = excluded.comision;
            """,
            (
                linea_id,
                estado_cuenta_id,
                linea.solicitud,
                linea.tipo,
                float(linea.base),
                float(linea.porcentaje),
                float(linea.comision),
            ),
        )

    def guardar_linea_cuenta(self, estado_cuenta_id: str, linea: LineaCuenta) -> None:
        with self._con:
            self._guardar_linea_transaccional(estado_cuenta_id, linea)
            cursor = self._con.execute(
                "SELECT SUM(comision) as total FROM lineas_cuenta WHERE estado_cuenta_id = ?",
                (estado_cuenta_id,),
            )
            fila = cursor.fetchone()
            total = float(fila["total"] or 0.0)
            self._con.execute(
                "UPDATE estados_cuenta SET total = ? WHERE estado_cuenta_id = ?",
                (total, estado_cuenta_id),
            )

    def obtener_lineas_cuenta(self, estado_cuenta_id: str) -> tuple[LineaCuenta, ...]:
        cursor = self._con.execute(
            "SELECT * FROM lineas_cuenta WHERE estado_cuenta_id = ? ORDER BY tipo ASC, solicitud ASC",
            (estado_cuenta_id,),
        )
        filas = cursor.fetchall()
        return tuple(
            LineaCuenta(
                solicitud=fila["solicitud"],
                base=Decimal(str(fila["base"])),
                porcentaje=Decimal(str(fila["porcentaje"])),
                comision=Decimal(str(fila["comision"])),
                tipo=fila["tipo"],
            )
            for fila in filas
        )

    def obtener_estado_cuenta(self, anfitrion_id: str, periodo: str) -> EstadoDeCuenta | None:
        cursor = self._con.execute(
            "SELECT * FROM estados_cuenta WHERE anfitrion_id = ? AND periodo = ?",
            (anfitrion_id, periodo),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return self._construir_estado_cuenta(fila)

    def obtener_estado_cuenta_por_id(self, estado_cuenta_id: str) -> EstadoDeCuenta | None:
        cursor = self._con.execute(
            "SELECT * FROM estados_cuenta WHERE estado_cuenta_id = ?",
            (estado_cuenta_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return None
        return self._construir_estado_cuenta(fila)

    def _construir_estado_cuenta(self, fila: sqlite3.Row) -> EstadoDeCuenta:
        ec_id = fila["estado_cuenta_id"]
        lineas = self.obtener_lineas_cuenta(ec_id)
        emitido_dt = datetime.fromisoformat(fila["emitido_en"]) if fila["emitido_en"] else None
        pagado_dt = datetime.fromisoformat(fila["pagado_en"]) if fila["pagado_en"] else None
        vence_d = date.fromisoformat(fila["vence_en"])
        return EstadoDeCuenta(
            estado_cuenta_id=ec_id,
            anfitrion_id=fila["anfitrion_id"],
            periodo=fila["periodo"],
            total=Decimal(str(fila["total"])),
            estado=EstadoCuenta(fila["estado"]),
            vence_en=vence_d,
            lineas=lineas,
            emitido_en=emitido_dt,
            pagado_en=pagado_dt,
            pago_registrado_por=fila["pago_registrado_por"],
        )

    def actualizar_estado_cuenta(
        self,
        estado_cuenta_id: str,
        estado: EstadoCuenta,
        pagado_en: datetime | None = None,
        pago_registrado_por: str | None = None,
    ) -> None:
        pagado_iso = pagado_en.isoformat() if pagado_en else None
        with self._con:
            self._con.execute(
                """
                UPDATE estados_cuenta
                SET estado = ?, pagado_en = ?, pago_registrado_por = ?
                WHERE estado_cuenta_id = ?
                """,
                (estado.value, pagado_iso, pago_registrado_por, estado_cuenta_id),
            )

    def solicitud_tiene_cargo(self, solicitud: str) -> bool:
        cursor = self._con.execute(
            "SELECT 1 FROM lineas_cuenta WHERE solicitud = ? AND tipo = 'cargo' LIMIT 1",
            (solicitud,),
        )
        return cursor.fetchone() is not None

    def listar_estadias_completadas_por_periodo(self, periodo: str) -> tuple[Solicitud, ...]:
        anio, mes = (int(parte) for parte in periodo.split("-")[:2])
        siguiente = f"{anio + 1:04d}-01-01" if mes == 12 else f"{anio:04d}-{mes + 1:02d}-01"
        cursor = self._con.execute(
            """
            SELECT solicitud FROM solicitudes
            WHERE estado = 'completada' AND hasta >= ? AND hasta < ?
            ORDER BY hasta ASC, creado_en ASC
            """,
            (f"{anio:04d}-{mes:02d}-01", siguiente),
        )
        filas = cursor.fetchall()
        return tuple(self.obtener_solicitud(f["solicitud"]) for f in filas if self.obtener_solicitud(f["solicitud"]))

    def listar_estados_cuenta_por_periodo(self, periodo: str) -> tuple[EstadoDeCuenta, ...]:
        cursor = self._con.execute(
            "SELECT * FROM estados_cuenta WHERE periodo = ?", (periodo,)
        )
        filas = cursor.fetchall()
        return tuple(self._construir_estado_cuenta(f) for f in filas)

    def listar_estados_cuenta_morosos(self) -> tuple[EstadoDeCuenta, ...]:
        cursor = self._con.execute(
            "SELECT * FROM estados_cuenta WHERE estado IN ('emitido', 'vencido')",
        )
        filas = cursor.fetchall()
        return tuple(self._construir_estado_cuenta(f) for f in filas)

    def pausar_hospedajes_de_anfitrion(self, anfitrion_id: str) -> tuple[str, ...]:
        cursor = self._con.execute(
            "SELECT propiedad_id FROM hospedajes WHERE anfitrion_id = ? AND estado = 'publicado'",
            (anfitrion_id,),
        )
        filas = cursor.fetchall()
        pids = tuple(f["propiedad_id"] for f in filas)
        if pids:
            with self._con:
                self._con.execute(
                    "UPDATE hospedajes SET estado = 'pausado' WHERE anfitrion_id = ? AND estado = 'publicado'",
                    (anfitrion_id,),
                )
        return pids

    def listar_anfitriones_activos(self) -> tuple[Anfitrion, ...]:
        cursor = self._con.execute(
            "SELECT anfitrion_id FROM anfitriones WHERE estado = 'activo'"
        )
        filas = cursor.fetchall()
        return tuple(self.obtener_anfitrion(f["anfitrion_id"]) for f in filas if self.obtener_anfitrion(f["anfitrion_id"]))
