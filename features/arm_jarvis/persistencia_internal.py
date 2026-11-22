# ¤arm-jarvis
# ¤¤backend-developer
"""Persistencia relacional y operaciones sobre el esquema arm."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from features.arm_jarvis.tipos import (
    EstadoVenta,
    Tablero,
    Transicion,
    Vendedor,
    Venta,
    VentaExtraida,
    VentaNoEncontrada,
)
from features.persistencia_sql.persistencia_sql_service import envolver

__all__ = ["RepositorioArm", "inicializar_esquema_arm"]


# ¤arm-jarvis
def inicializar_esquema_arm(conexion: sqlite3.Connection) -> None:
    """Crea y valida las tablas del esquema arm en SQLite."""
    if getattr(conexion, "es_postgres", False):
        return  # el esquema lo aplica scripts/migrar_db.py (docs/spec/esquema.sql)
    conexion.row_factory = sqlite3.Row

    # Verificar si el esquema 'arm' está adjunto; si no, adjuntar en memoria
    bases = [fila[1] for fila in conexion.execute("PRAGMA database_list").fetchall()]
    if "arm" not in bases:
        conexion.execute("ATTACH DATABASE ':memory:' AS arm")

    conexion.execute("PRAGMA arm.foreign_keys = ON;")

    # Tabla arm.vendedores
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS arm.vendedores (
            vendedor_id TEXT PRIMARY KEY,
            telefono_token TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            activo BOOLEAN NOT NULL DEFAULT 1,
            regla_comision_default_id TEXT
        );
        """
    )

    # Tabla arm.secuencia_tickets
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS arm.secuencia_tickets (
            anio INTEGER PRIMARY KEY,
            ultimo INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    # Tabla arm.ventas
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS arm.ventas (
            venta_id TEXT PRIMARY KEY,
            ticket TEXT NOT NULL UNIQUE,
            vendedor_id TEXT NOT NULL REFERENCES vendedores(vendedor_id),
            cliente_token TEXT,
            telefono_cliente_token TEXT,
            producto TEXT NOT NULL,
            propiedad_id TEXT,
            noches INTEGER,
            monto TEXT NOT NULL,
            moneda TEXT NOT NULL DEFAULT 'USD',
            fecha_venta TEXT NOT NULL,
            fecha_llegada TEXT,
            texto_original_token TEXT NOT NULL,
            mensaje_id TEXT NOT NULL,
            indice_en_mensaje INTEGER NOT NULL DEFAULT 0,
            confianza REAL NOT NULL,
            confianza_campos TEXT NOT NULL DEFAULT '{}',
            huella_duplicado TEXT NOT NULL,
            posible_duplicado_de TEXT REFERENCES ventas(venta_id),
            estado TEXT NOT NULL DEFAULT 'por_validar',
            comision_estimada TEXT,
            comision_fijada TEXT,
            reserva_ref TEXT,
            creada TEXT NOT NULL,
            validada_en TEXT,
            actualizada TEXT NOT NULL,
            UNIQUE (mensaje_id, indice_en_mensaje)
        );
        """
    )

    # Tabla arm.transiciones
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS arm.transiciones (
            transicion_id TEXT PRIMARY KEY,
            venta_id TEXT NOT NULL REFERENCES ventas(venta_id),
            de TEXT NOT NULL,
            a TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            rol TEXT NOT NULL,
            motivo TEXT,
            instante TEXT NOT NULL
        );
        """
    )

    # Tabla arm.configuracion
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS arm.configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            cambiado_por TEXT NOT NULL,
            cambiado_en TEXT NOT NULL
        );
        """
    )
    conexion.commit()


# ¤arm-jarvis
# ¤arm-jarvis
def _sincronizado(metodo):
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return metodo(self, *args, **kwargs)
    wrapper.__name__ = metodo.__name__
    wrapper.__doc__ = metodo.__doc__
    return wrapper


# ¤arm-jarvis
def _con_cerrojo(cls):
    for attr_name, attr_val in list(cls.__dict__.items()):
        if callable(attr_val) and not attr_name.startswith("__") and not isinstance(attr_val, property):
            setattr(cls, attr_name, _sincronizado(attr_val))
    return cls


# ¤arm-jarvis
@_con_cerrojo
class RepositorioArm:
    """Manejo de consultas y transacciones sobre las tablas de arm."""

    def __init__(self, conexion: Any = None) -> None:
        self._lock = threading.RLock()
        with self._lock:
            # None: DATABASE_URL (PostgreSQL) o SQLite en memoria. Transacciones explícitas con commit/rollback.
            self._con = envolver(conexion, esquemas=("arm",))
            inicializar_esquema_arm(self._con)

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    # ¤arm-jarvis
    @property
    def conexion(self) -> sqlite3.Connection:
        return self._con

    # ¤arm-jarvis
    def registrar_vendedor(self, vendedor: Vendedor) -> None:
        """Registra o actualiza un vendedor."""
        with self._con:
            self._con.execute(
                """
                INSERT INTO arm.vendedores (vendedor_id, telefono_token, nombre, activo, regla_comision_default_id)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(vendedor_id) DO UPDATE SET
                    telefono_token = excluded.telefono_token,
                    nombre = excluded.nombre,
                    activo = excluded.activo,
                    regla_comision_default_id = excluded.regla_comision_default_id;
                """,
                (
                    vendedor.vendedor_id,
                    vendedor.telefono_token,
                    vendedor.nombre,
                    bool(vendedor.activo),
                    vendedor.regla_comision_default_id,
                ),
            )

    # ¤arm-jarvis
    def obtener_vendedor_por_telefono(self, telefono_token: str) -> Vendedor | None:
        """Busca vendedor activo por su token de teléfono."""
        cur = self._con.execute(
            "SELECT vendedor_id, telefono_token, nombre, activo, regla_comision_default_id FROM arm.vendedores WHERE telefono_token = ? AND activo = TRUE;",
            (telefono_token,),
        )
        fila = cur.fetchone()
        if not fila:
            return None
        return Vendedor(
            vendedor_id=fila["vendedor_id"],
            telefono_token=fila["telefono_token"],
            nombre=fila["nombre"],
            activo=bool(fila["activo"]),
            regla_comision_default_id=fila["regla_comision_default_id"],
        )

    # ¤arm-jarvis
    def obtener_vendedor_por_id(self, vendedor_id: str) -> Vendedor | None:
        """Busca vendedor por su identificador único."""
        cur = self._con.execute(
            "SELECT vendedor_id, telefono_token, nombre, activo, regla_comision_default_id FROM arm.vendedores WHERE vendedor_id = ?;",
            (vendedor_id,),
        )
        fila = cur.fetchone()
        if not fila:
            return None
        return Vendedor(
            vendedor_id=fila["vendedor_id"],
            telefono_token=fila["telefono_token"],
            nombre=fila["nombre"],
            activo=bool(fila["activo"]),
            regla_comision_default_id=fila["regla_comision_default_id"],
        )

    # ¤arm-jarvis
    def listar_vendedores_activos(self) -> tuple[Vendedor, ...]:
        cur = self._con.execute(
            "SELECT vendedor_id, telefono_token, nombre, activo, regla_comision_default_id FROM arm.vendedores WHERE activo = TRUE ORDER BY nombre ASC;"
        )
        return tuple(
            Vendedor(
                vendedor_id=f["vendedor_id"],
                telefono_token=f["telefono_token"],
                nombre=f["nombre"],
                activo=bool(f["activo"]),
                regla_comision_default_id=f["regla_comision_default_id"],
            )
            for f in cur.fetchall()
        )

    # ¤arm-jarvis
    def buscar_por_mensaje_e_indice(self, mensaje_id: str, indice: int) -> Venta | None:
        """Busca una venta ya existente por el par único (mensaje_id, indice_en_mensaje)."""
        cur = self._con.execute(
            "SELECT * FROM arm.ventas WHERE mensaje_id = ? AND indice_en_mensaje = ?;",
            (mensaje_id, indice),
        )
        fila = cur.fetchone()
        if not fila:
            return None
        return self._fila_a_venta(fila)

    # ¤arm-jarvis
    def calcular_huella_duplicado(
        self,
        cliente_token: str | None,
        producto: str,
        monto: Decimal,
        fecha_venta: date,
    ) -> str:
        """Calcula hash normalizado para detectar posibles duplicados en ventana de 7 días."""
        cadena = f"{(cliente_token or '').strip().lower()}|{producto.strip().lower()}|{monto:.2f}|{fecha_venta.isoformat()}"
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest()

    # ¤arm-jarvis
    def buscar_posible_duplicado(
        self,
        cliente_token: str | None,
        producto: str,
        monto: Decimal,
        fecha_venta: date,
    ) -> str | None:
        """Busca si existe otra venta con mismo cliente, producto, monto dentro de 7 días."""
        limite_inferior = (fecha_venta - timedelta(days=7)).isoformat()
        limite_superior = (fecha_venta + timedelta(days=7)).isoformat()
        monto_str = str(monto)

        cur = self._con.execute(
            """
            SELECT venta_id FROM arm.ventas
            WHERE producto = ?
              AND monto = ?
              AND (cliente_token = ? OR (CAST(? AS TEXT) IS NULL AND cliente_token IS NULL))
              AND fecha_venta BETWEEN ? AND ?
              AND estado NOT IN ('rechazada', 'anulada')
            ORDER BY creada ASC
            LIMIT 1;
            """,
            (
                producto,
                monto_str,
                cliente_token,
                cliente_token,
                limite_inferior,
                limite_superior,
            ),
        )
        fila = cur.fetchone()
        return fila["venta_id"] if fila else None

    # ¤arm-jarvis
    def insertar_venta(self, venta: Venta) -> None:
        """Inserta una venta de forma transaccional."""
        f_llegada_str = venta.extraida.fecha_llegada.isoformat() if venta.extraida.fecha_llegada else None
        f_venta_str = venta.extraida.fecha_venta.isoformat() if venta.extraida.fecha_venta else date.today().isoformat()
        monto_str = str(venta.extraida.monto) if venta.extraida.monto is not None else "0.00"
        com_est_str = str(venta.comision_estimada) if venta.comision_estimada is not None else None
        com_fij_str = str(venta.comision_fijada) if venta.comision_fijada is not None else None
        conf_campos_str = json.dumps(dict(venta.extraida.confianza_campos), ensure_ascii=False)
        huella = self.calcular_huella_duplicado(
            venta.extraida.cliente_token,
            venta.extraida.producto or "",
            venta.extraida.monto or Decimal("0"),
            venta.extraida.fecha_venta or date.today(),
        )

        self._con.execute(
            """
            INSERT INTO arm.ventas (
                venta_id, ticket, vendedor_id, cliente_token, telefono_cliente_token,
                producto, propiedad_id, noches, monto, moneda,
                fecha_venta, fecha_llegada, texto_original_token, mensaje_id, indice_en_mensaje,
                confianza, confianza_campos, huella_duplicado, posible_duplicado_de,
                estado, comision_estimada, comision_fijada, reserva_ref,
                creada, actualizada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                venta.venta_id,
                venta.ticket,
                venta.vendedor_id,
                venta.extraida.cliente_token,
                venta.extraida.telefono_cliente_token,
                venta.extraida.producto or "desconocido",
                venta.extraida.propiedad_id,
                venta.extraida.noches,
                monto_str,
                venta.extraida.moneda,
                f_venta_str,
                f_llegada_str,
                venta.texto_original_token,
                venta.mensaje_id,
                venta.indice_en_mensaje,
                venta.extraida.confianza,
                conf_campos_str,
                huella,
                venta.posible_duplicado_de,
                venta.estado.value,
                com_est_str,
                com_fij_str,
                venta.reserva_ref,
                venta.creada.isoformat(),
                venta.actualizada.isoformat(),
            ),
        )

    # ¤arm-jarvis
    def obtener_venta(self, venta_id: str) -> Venta:
        cur = self._con.execute("SELECT * FROM arm.ventas WHERE venta_id = ?;", (venta_id,))
        fila = cur.fetchone()
        if not fila:
            raise VentaNoEncontrada(venta_id)
        return self._fila_a_venta(fila)

    # ¤arm-jarvis
    def obtener_venta_por_ticket(self, ticket: str) -> Venta | None:
        cur = self._con.execute("SELECT * FROM arm.ventas WHERE ticket = ?;", (ticket,))
        fila = cur.fetchone()
        return self._fila_a_venta(fila) if fila else None

    # ¤arm-jarvis
    def actualizar_estado(
        self,
        venta_id: str,
        nuevo_estado: EstadoVenta,
        estado_esperado: EstadoVenta,
        actor_id: str,
        rol: str,
        motivo: str | None = None,
        comision_fijada: Decimal | None = None,
        reserva_ref: str | None = None,
    ) -> Venta:
        """Actualiza el estado de forma atómica y audita la transición en arm.transiciones."""
        ahora = datetime.now(timezone.utc)
        ahora_str = ahora.isoformat()
        com_str = str(comision_fijada) if comision_fijada is not None else None

        with self._con:
            # 1. Comprobar estado esperado
            cur = self._con.execute(
                """
                UPDATE arm.ventas
                SET estado = ?,
                    actualizada = ?,
                    comision_fijada = COALESCE(?, comision_fijada),
                    reserva_ref = COALESCE(?, reserva_ref),
                    validada_en = CASE WHEN ? = 'validada' THEN ? ELSE validada_en END
                WHERE venta_id = ? AND estado = ?;
                """,
                (
                    nuevo_estado.value,
                    ahora_str,
                    com_str,
                    reserva_ref,
                    nuevo_estado.value,
                    ahora_str,
                    venta_id,
                    estado_esperado.value,
                ),
            )
            if cur.rowcount == 0:
                raise VentaNoEncontrada(f"Venta {venta_id} en estado inesperado o no encontrada")

            # 2. Registrar en arm.transiciones
            transicion_id = str(uuid.uuid4())
            self._con.execute(
                """
                INSERT INTO arm.transiciones (
                    transicion_id, venta_id, de, a, actor_id, rol, motivo, instante
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    transicion_id,
                    venta_id,
                    estado_esperado.value,
                    nuevo_estado.value,
                    actor_id,
                    rol,
                    motivo,
                    ahora_str,
                ),
            )

        return self.obtener_venta(venta_id)

    # ¤arm-jarvis
    def listar_transiciones(self, venta_id: str) -> tuple[Transicion, ...]:
        cur = self._con.execute(
            "SELECT * FROM arm.transiciones WHERE venta_id = ? ORDER BY instante ASC;",
            (venta_id,),
        )
        return tuple(
            Transicion(
                venta_id=f["venta_id"],
                de=EstadoVenta(f["de"]),
                a=EstadoVenta(f["a"]),
                actor_id=f["actor_id"],
                rol=f["rol"],
                motivo=f["motivo"],
                timestamp=datetime.fromisoformat(f["instante"]),
            )
            for f in cur.fetchall()
        )

    # ¤arm-jarvis
    def listar_ventas(
        self,
        estado: EstadoVenta | None = None,
        vendedor_id: str | None = None,
        periodo: str | None = None,
        pagina: int = 1,
        tamano_pagina: int = 50,
    ) -> tuple[Venta, ...]:
        clausulas = []
        parametros: list[Any] = []

        if estado is not None:
            clausulas.append("estado = ?")
            parametros.append(estado.value)

        if vendedor_id is not None:
            clausulas.append("vendedor_id = ?")
            parametros.append(vendedor_id)

        if periodo is not None:
            clausulas.append("(substr(CAST(fecha_venta AS TEXT), 1, 7) = ? OR substr(CAST(fecha_llegada AS TEXT), 1, 7) = ?)")
            parametros.extend([periodo, periodo])

        where = ("WHERE " + " AND ".join(clausulas)) if clausulas else ""
        offset = max(0, (pagina - 1) * tamano_pagina)
        query = f"SELECT * FROM arm.ventas {where} ORDER BY creada DESC LIMIT ? OFFSET ?;"
        parametros.extend([tamano_pagina, offset])

        cur = self._con.execute(query, tuple(parametros))
        return tuple(self._fila_a_venta(f) for f in cur.fetchall())

    # ¤arm-jarvis
    def obtener_resumen_comisiones(
        self,
        vendedor_id: str,
        periodo: str | None = None,
    ) -> tuple[Decimal, Decimal, int]:
        """Calcula comisiones validadas, pendientes y conteo de ventas para un vendedor en un período."""
        params: list[Any] = [vendedor_id]
        filtro_periodo = ""
        if periodo:
            filtro_periodo = "AND substr(CAST(fecha_venta AS TEXT), 1, 7) = ?"
            params.append(periodo)

        # 1. Validadas / Publicadas
        cur_val = self._con.execute(
            f"""
            SELECT SUM(CAST(comision_fijada AS NUMERIC)) as total_val, COUNT(*) as cnt
            FROM arm.ventas
            WHERE vendedor_id = ?
              AND estado IN ('validada', 'publicada', 'no_publicada')
              {filtro_periodo};
            """,
            tuple(params),
        )
        r_val = cur_val.fetchone()
        validada = Decimal(str(r_val["total_val"] or "0.00")).quantize(Decimal("0.01"))
        ventas_cnt = int(r_val["cnt"] or 0)

        # 2. Pendientes (por_validar)
        cur_pend = self._con.execute(
            f"""
            SELECT SUM(CAST(comision_estimada AS NUMERIC)) as total_pend, COUNT(*) as cnt
            FROM arm.ventas
            WHERE vendedor_id = ?
              AND estado = 'por_validar'
              {filtro_periodo};
            """,
            tuple(params),
        )
        r_pend = cur_pend.fetchone()
        pendiente = Decimal(str(r_pend["total_pend"] or "0.00")).quantize(Decimal("0.01"))
        ventas_cnt += int(r_pend["cnt"] or 0)

        return validada, pendiente, ventas_cnt

    # ¤arm-jarvis
    def obtener_tablero(self, periodo: str) -> Tablero:
        """Construye las estadísticas consolidadas del tablero para el período dado."""
        # 1. Total comisiones validadas y pendientes
        cur_totales = self._con.execute(
            """
            SELECT
                SUM(CASE WHEN estado IN ('validada', 'publicada', 'no_publicada') THEN CAST(comision_fijada AS NUMERIC) ELSE 0 END) as com_val,
                SUM(CASE WHEN estado = 'por_validar' THEN CAST(comision_estimada AS NUMERIC) ELSE 0 END) as com_pend,
                SUM(CASE WHEN estado = 'por_validar' THEN 1 ELSE 0 END) as cnt_por_validar
            FROM arm.ventas
            WHERE substr(CAST(fecha_venta AS TEXT), 1, 7) = ?;
            """,
            (periodo,),
        )
        r_tot = cur_totales.fetchone()
        com_val = Decimal(str(r_tot["com_val"] or "0.00")).quantize(Decimal("0.01"))
        com_pend = Decimal(str(r_tot["com_pend"] or "0.00")).quantize(Decimal("0.01"))
        cnt_pv = int(r_tot["cnt_por_validar"] or 0)

        # 2. Ventas por mes (en el año del período)
        anio = periodo.split("-")[0]
        cur_mes = self._con.execute(
            """
            SELECT substr(CAST(fecha_venta AS TEXT), 1, 7) as mes, SUM(CAST(monto AS NUMERIC)) as total
            FROM arm.ventas
            WHERE substr(CAST(fecha_venta AS TEXT), 1, 4) = ? AND estado IN ('validada', 'publicada', 'no_publicada')
            GROUP BY mes ORDER BY mes ASC;
            """,
            (anio,),
        )
        ventas_mes = tuple(
            (row["mes"], Decimal(str(row["total"] or "0.00")).quantize(Decimal("0.01")))
            for row in cur_mes.fetchall()
        )

        # 3. Ventas por vendedor en el período
        cur_vend = self._con.execute(
            """
            SELECT v.nombre, SUM(CAST(vt.monto AS NUMERIC)) as total, COUNT(*) as cnt
            FROM arm.ventas vt
            JOIN arm.vendedores v ON vt.vendedor_id = v.vendedor_id
            WHERE substr(CAST(vt.fecha_venta AS TEXT), 1, 7) = ? AND vt.estado IN ('validada', 'publicada', 'no_publicada')
            GROUP BY v.nombre ORDER BY total DESC;
            """,
            (periodo,),
        )
        ventas_vend = tuple(
            (row["nombre"], Decimal(str(row["total"] or "0.00")).quantize(Decimal("0.01")), int(row["cnt"]))
            for row in cur_vend.fetchall()
        )

        # 4. Ventas por propiedad
        cur_prop = self._con.execute(
            """
            SELECT COALESCE(propiedad_id, 'sin_propiedad') as prop, SUM(CAST(monto AS NUMERIC)) as total
            FROM arm.ventas
            WHERE substr(CAST(fecha_venta AS TEXT), 1, 7) = ? AND estado IN ('validada', 'publicada', 'no_publicada')
            GROUP BY prop ORDER BY total DESC;
            """,
            (periodo,),
        )
        ventas_prop = tuple(
            (row["prop"], Decimal(str(row["total"] or "0.00")).quantize(Decimal("0.01")))
            for row in cur_prop.fetchall()
        )

        return Tablero(
            periodo=periodo,
            ventas_por_mes=ventas_mes,
            ventas_por_vendedor=ventas_vend,
            ventas_por_propiedad=ventas_prop,
            comisiones_validadas=com_val,
            comisiones_pendientes=com_pend,
            por_validar=cnt_pv,
        )

    # ¤arm-jarvis
    def guardar_configuracion(self, clave: str, valor: Any, autor: str) -> None:
        ahora_str = datetime.now(timezone.utc).isoformat()
        valor_json = json.dumps(valor)
        with self._con:
            self._con.execute(
                """
                INSERT INTO arm.configuracion (clave, valor, cambiado_por, cambiado_en)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(clave) DO UPDATE SET
                    valor = excluded.valor,
                    cambiado_por = excluded.cambiado_por,
                    cambiado_en = excluded.cambiado_en;
                """,
                (clave, valor_json, autor, ahora_str),
            )

    # ¤arm-jarvis
    def obtener_configuracion(self, clave: str) -> Any | None:
        cur = self._con.execute("SELECT valor FROM arm.configuracion WHERE clave = ?;", (clave,))
        fila = cur.fetchone()
        if not fila:
            return None
        return json.loads(fila["valor"])

    # ¤arm-jarvis
    def _fila_a_venta(self, fila: Any) -> Venta:
        conf_campos = json.loads(fila["confianza_campos"]) if fila["confianza_campos"] else {}
        extraida = VentaExtraida(
            cliente_token=fila["cliente_token"],
            telefono_cliente_token=fila["telefono_cliente_token"],
            producto=fila["producto"],
            propiedad_id=fila["propiedad_id"],
            monto=Decimal(fila["monto"]) if fila["monto"] is not None else None,
            moneda=fila["moneda"],
            fecha_venta=date.fromisoformat(fila["fecha_venta"]) if fila["fecha_venta"] else None,
            confianza=float(fila["confianza"]),
            noches=fila["noches"],
            fecha_llegada=date.fromisoformat(fila["fecha_llegada"]) if fila["fecha_llegada"] else None,
            confianza_campos=conf_campos,
        )
        return Venta(
            venta_id=fila["venta_id"],
            ticket=fila["ticket"],
            vendedor_id=fila["vendedor_id"],
            extraida=extraida,
            texto_original_token=fila["texto_original_token"],
            estado=EstadoVenta(fila["estado"]),
            comision_estimada=Decimal(fila["comision_estimada"]) if fila["comision_estimada"] is not None else None,
            comision_fijada=Decimal(fila["comision_fijada"]) if fila["comision_fijada"] is not None else None,
            reserva_ref=fila["reserva_ref"],
            posible_duplicado=bool(fila["posible_duplicado_de"]),
            posible_duplicado_de=fila["posible_duplicado_de"],
            mensaje_id=fila["mensaje_id"],
            indice_en_mensaje=fila["indice_en_mensaje"],
            creada=datetime.fromisoformat(fila["creada"]),
            actualizada=datetime.fromisoformat(fila["actualizada"]),
        )
