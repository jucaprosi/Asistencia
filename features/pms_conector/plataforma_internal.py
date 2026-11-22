# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Implementación de plataforma propia para calendario, tarifas y reservas (RF-PMS-02, RF-PMS-07, RF-PMS-08)."""
from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Mapping

from features.pms_conector.base_internal import PMSConnector
from features.pms_conector.persistencia_internal import inicializar_base_datos
from features.pms_conector.tipos import (
    AislamientoAnfitrionError,
    CapacidadExcedida,
    Cotizacion,
    Disponibilidad,
    EstadoReserva,
    FechasInvalidas,
    Incidencia,
    InstruccionesCheckin,
    Propiedad,
    PropiedadInexistente,
    Reserva,
    ReservaInexistente,
    SinDisponibilidad,
    TipoPropiedad,
    Unidad,
    UnidadInexistente,
)


# ¤pms-conector
class PlataformaPMS(PMSConnector):
    """Conector PMS nativo respaldado por tablas relacionales del esquema pms."""

    def __init__(
        self,
        conexion: sqlite3.Connection | None = None,
        anfitriones_unidades: Mapping[str, str] | None = None,
    ) -> None:
        self._conn = conexion or inicializar_base_datos()
        self._lock = threading.RLock()
        self._secuencia_reservas: int = 1
        self._secuencia_hk: int = 1

        # Mapeo anfitriones a unidades (INV_AISLAMIENTO_ANFITRION)
        self._anfitriones_unidades: dict[str, str] = {
            "domo_lago": "anf_imbabura_01",
            "domo_bosque": "anf_imbabura_01",
            "suite_101": "anf_ibarra_01",
            "fam_201": "anf_ibarra_01",
        }
        if anfitriones_unidades:
            self._anfitriones_unidades.update(anfitriones_unidades)

        self._sembrar_datos_iniciales()

    def registrar_anfitrion_unidad(self, unidad_id: str, anfitrion_id: str) -> None:
        """Registra o actualiza la propiedad de una unidad para un anfitrión."""
        with self._lock:
            self._anfitriones_unidades[unidad_id] = anfitrion_id

    def _sembrar_datos_iniciales(self) -> None:
        with self._lock:
            # 1. Propiedades canónicas
            self._conn.execute(
                """
                INSERT INTO pms.propiedades (
                    propiedad_id, tipo, nombre, zona_id, direccion, pms_ref, prompt_variante, activa
                ) VALUES
                ('glamping_imbabura', 'glamping', 'Glamping Imbabura', 'imbabura_norte', 'Sector San Pablo del Lago, Otavalo', 'pms_glamping_01', 'glamping', TRUE),
                ('dep_ibarra_centro', 'departamento', 'Departamentos Ibarra Centro', 'ibarra_centro', 'Calle Bolívar y Flores, Ibarra', 'pms_dep_02', 'departamentos', TRUE)
                ON CONFLICT DO NOTHING
                """
            )

            # 2. Unidades canónicas
            self._conn.execute(
                """
                INSERT INTO pms.unidades (
                    unidad_id, propiedad_id, nombre, capacidad, edificio, piso, acceso_ref, wifi_ref
                ) VALUES
                ('domo_lago', 'glamping_imbabura', 'Domo Lago', 2, NULL, NULL, 'Cerradura digital', 'WIFI_DOMO_LAGO'),
                ('domo_bosque', 'glamping_imbabura', 'Domo Bosque', 4, NULL, NULL, 'Cerradura digital', 'WIFI_DOMO_BOSQUE'),
                ('suite_101', 'dep_ibarra_centro', 'Suite 101', 2, 'Torre Central', '1', 'Tarjeta magnética', 'WIFI_SUITE_101'),
                ('fam_201', 'dep_ibarra_centro', 'Departamento Familiar 201', 5, 'Torre Central', '2', 'Tarjeta magnética', 'WIFI_FAM_201')
                ON CONFLICT DO NOTHING
                """
            )

            # 3. Tarifas iniciales por 365 días si la tabla está vacía
            cursor = self._conn.execute("SELECT COUNT(*) FROM pms.tarifas_noche")
            if cursor.fetchone()[0] == 0:
                hoy = date.today()
                tarifas_defecto = [
                    ("domo_lago", Decimal("120.00"), 1),
                    ("domo_bosque", Decimal("180.00"), 2),
                    ("suite_101", Decimal("65.00"), 1),
                    ("fam_201", Decimal("110.00"), 1),
                ]
                filas_tarifas = []
                for dia_offset in range(365):
                    noche_dt = hoy + timedelta(days=dia_offset)
                    noche_iso = noche_dt.isoformat()
                    for uid, precio, min_n in tarifas_defecto:
                        filas_tarifas.append((uid, noche_iso, str(precio), min_n))

                self._conn.executemany(
                    """
                    INSERT INTO pms.tarifas_noche (unidad_id, noche, precio, minimo_noches)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT DO NOTHING
                    """,
                    filas_tarifas,
                )
            self._conn.commit()

    def listar_propiedades(self) -> tuple[Propiedad, ...]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT propiedad_id, tipo, nombre, zona_id, direccion, activa, pms_ref, prompt_variante
                FROM pms.propiedades
                WHERE activa = TRUE
                ORDER BY propiedad_id
                """
            )
            propiedades = []
            for f in cursor.fetchall():
                propiedades.append(
                    Propiedad(
                        propiedad_id=f["propiedad_id"],
                        tipo=TipoPropiedad(f["tipo"]),
                        nombre=f["nombre"],
                        zona_id=f["zona_id"],
                        direccion=f["direccion"],
                        activa=bool(f["activa"]),
                        pms_ref=f["pms_ref"] or "",
                        prompt_variante=f["prompt_variante"] or "glamping",
                    )
                )
            return tuple(propiedades)

    def consultar_disponibilidad(
        self, propiedad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Disponibilidad:
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido (hasta <= desde)")

        with self._lock:
            # Validar existencia de propiedad
            cursor_prop = self._conn.execute(
                "SELECT propiedad_id FROM pms.propiedades WHERE propiedad_id = ? AND activa = TRUE",
                (propiedad_id,),
            )
            if not cursor_prop.fetchone():
                raise PropiedadInexistente(f"Propiedad '{propiedad_id}' inexistente o inactiva")

            # Buscar unidades con capacidad suficiente
            cursor_u = self._conn.execute(
                """
                SELECT unidad_id, propiedad_id, nombre, capacidad, edificio, piso, acceso_ref, wifi_ref
                FROM pms.unidades
                WHERE propiedad_id = ? AND capacidad >= ?
                ORDER BY unidad_id
                """,
                (propiedad_id, huespedes),
            )
            unidades_candidatas = cursor_u.fetchall()

            duracion_estancia = (hasta - desde).days
            disponibles: list[Unidad] = []

            for u in unidades_candidatas:
                uid = u["unidad_id"]
                unidad_apta = True

                # RF-PMS-07 (a) y (c): tarifa y mínimo de noches para cada noche del rango
                cur = desde
                while cur < hasta:
                    noche_iso = cur.isoformat()
                    cur_tarifa = self._conn.execute(
                        "SELECT precio, minimo_noches FROM pms.tarifas_noche WHERE unidad_id = ? AND noche = ?",
                        (uid, noche_iso),
                    )
                    fila_tarifa = cur_tarifa.fetchone()
                    if not fila_tarifa:
                        # Noche sin tarifa no se ofrece
                        unidad_apta = False
                        break

                    minimo_noches = fila_tarifa["minimo_noches"]
                    if duracion_estancia < minimo_noches:
                        # Estancia no cumple estancia mínima
                        unidad_apta = False
                        break
                    cur += timedelta(days=1)

                if not unidad_apta:
                    continue

                # RF-PMS-07 (b): disponibilidad sale de pms.noches_ocupadas
                cur_oc = self._conn.execute(
                    """
                    SELECT COUNT(*) FROM pms.noches_ocupadas
                    WHERE unidad_id = ? AND noche >= ? AND noche < ?
                    """,
                    (uid, desde.isoformat(), hasta.isoformat()),
                )
                if cur_oc.fetchone()[0] > 0:
                    continue

                disponibles.append(
                    Unidad(
                        unidad_id=u["unidad_id"],
                        propiedad_id=u["propiedad_id"],
                        nombre=u["nombre"],
                        capacidad=u["capacidad"],
                        edificio=u["edificio"],
                        piso=u["piso"],
                        acceso_ref=u["acceso_ref"],
                        wifi_ref=u["wifi_ref"],
                    )
                )

            return Disponibilidad(
                disponible=len(disponibles) > 0,
                unidades=tuple(disponibles),
                motivo=None if disponibles else "Sin disponibilidad para las fechas o requisitos solicitados",
            )

    def cotizar(
        self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Cotizacion:
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido (hasta <= desde)")

        with self._lock:
            # Validar propiedad y unidad
            cur_u = self._conn.execute(
                "SELECT propiedad_id, capacidad FROM pms.unidades WHERE unidad_id = ?",
                (unidad_id,),
            )
            fila_u = cur_u.fetchone()
            if not fila_u or fila_u["propiedad_id"] != propiedad_id:
                raise UnidadInexistente(f"Unidad '{unidad_id}' inexistente en la propiedad '{propiedad_id}'")

            if huespedes > fila_u["capacidad"]:
                raise CapacidadExcedida(f"Huéspedes ({huespedes}) excede capacidad ({fila_u['capacidad']})")

            duracion_estancia = (hasta - desde).days
            desglose: list[tuple[str, Decimal]] = []
            total = Decimal("0.00")

            cur = desde
            while cur < hasta:
                noche_iso = cur.isoformat()
                cur_t = self._conn.execute(
                    "SELECT precio, minimo_noches FROM pms.tarifas_noche WHERE unidad_id = ? AND noche = ?",
                    (unidad_id, noche_iso),
                )
                fila_t = cur_t.fetchone()
                if not fila_t:
                    raise SinDisponibilidad(f"La noche {noche_iso} no tiene tarifa configurada")

                min_noches = fila_t["minimo_noches"]
                if duracion_estancia < min_noches:
                    raise SinDisponibilidad(f"Estancia de {duracion_estancia} noches no cumple mínimo de {min_noches}")

                precio_noche = Decimal(str(fila_t["precio"]))
                desglose.append((f"Noche {noche_iso}", precio_noche))
                total += precio_noche
                cur += timedelta(days=1)

            return Cotizacion(
                total=total,
                moneda="USD",
                desglose=tuple(desglose),
                politica_cancelacion_id="POL_ESTANDAR_24H",
            )

    def crear_reserva_preliminar(
        self,
        propiedad_id: str,
        unidad_id: str,
        desde: date,
        hasta: date,
        huespedes: int,
        huesped_token: str,
        clave_idempotencia: str,
    ) -> Reserva:
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido (hasta <= desde)")

        with self._lock:
            # 1. Purgar reservas expiradas antes de evaluar
            self._purgar_expiradas_locked()

            # 2. Cotizar para validar tarifas, noches mínimas y capacidad
            cotizacion = self.cotizar(propiedad_id, unidad_id, desde, hasta, huespedes)

            # 3. Verificar si alguna noche está ocupada
            cur_oc = self._conn.execute(
                """
                SELECT noche FROM pms.noches_ocupadas
                WHERE unidad_id = ? AND noche >= ? AND noche < ?
                """,
                (unidad_id, desde.isoformat(), hasta.isoformat()),
            )
            ocupadas = cur_oc.fetchall()
            if ocupadas:
                raise SinDisponibilidad(f"La unidad '{unidad_id}' ya está ocupada en las fechas solicitadas")

            # 4. Generar código único de reserva RES-YYYY-NNNN
            anio = desde.year
            self._secuencia_reservas += 1
            codigo = f"RES-{anio}-{self._secuencia_reservas:04d}"
            expira_en = datetime.now(timezone.utc) + timedelta(hours=24)

            # 5. Insertar en reservas_ref
            self._conn.execute(
                """
                INSERT INTO pms.reservas_ref (
                    codigo_reserva, propiedad_id, unidad_id, huesped_token, desde, hasta,
                    huespedes, total, estado, expira_en, pms_ref, actualizada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    codigo,
                    propiedad_id,
                    unidad_id,
                    huesped_token,
                    desde.isoformat(),
                    hasta.isoformat(),
                    huespedes,
                    str(cotizacion.total),
                    EstadoReserva.PRELIMINAR.value,
                    expira_en.isoformat(),
                    f"plat_ref_{codigo}",
                ),
            )

            # 6. Insertar en noches_ocupadas (INV_SIN_DOBLE_RESERVA: PK por unidad y noche)
            cur = desde
            try:
                while cur < hasta:
                    self._conn.execute(
                        """
                        INSERT INTO pms.noches_ocupadas (unidad_id, noche, origen, codigo_reserva)
                        VALUES (?, ?, 'reserva', ?)
                        """,
                        (unidad_id, cur.isoformat(), codigo),
                    )
                    cur += timedelta(days=1)
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                self._conn.rollback()
                raise SinDisponibilidad(f"Conflicto de ocupación al reservar: {exc}") from exc

            return Reserva(
                codigo=codigo,
                propiedad_id=propiedad_id,
                unidad_id=unidad_id,
                huesped_token=huesped_token,
                desde=desde,
                hasta=hasta,
                huespedes=huespedes,
                estado=EstadoReserva.PRELIMINAR,
                total=cotizacion.total,
                expira_en=expira_en,
                pms_ref=f"plat_ref_{codigo}",
            )

    def confirmar_reserva(self, codigo: str, clave_idempotencia: str) -> Reserva:
        with self._lock:
            self._purgar_expiradas_locked()
            cur = self._conn.execute(
                "SELECT * FROM pms.reservas_ref WHERE codigo_reserva = ?",
                (codigo,),
            )
            fila = cur.fetchone()
            if not fila:
                raise ReservaInexistente(f"Reserva con código '{codigo}' no encontrada")

            if fila["estado"] == EstadoReserva.EXPIRADA.value:
                raise SinDisponibilidad(f"La reserva {codigo} ha expirado y no puede confirmarse")
            if fila["estado"] == EstadoReserva.CANCELADA.value:
                raise SinDisponibilidad(f"La reserva {codigo} fue cancelada")

            # Actualizar estado a confirmada
            self._conn.execute(
                """
                UPDATE pms.reservas_ref
                SET estado = ?, expira_en = NULL, actualizada = CURRENT_TIMESTAMP
                WHERE codigo_reserva = ?
                """,
                (EstadoReserva.CONFIRMADA.value, codigo),
            )
            self._conn.commit()

            return Reserva(
                codigo=fila["codigo_reserva"],
                propiedad_id=fila["propiedad_id"],
                unidad_id=fila["unidad_id"],
                huesped_token=fila["huesped_token"],
                desde=date.fromisoformat(fila["desde"]),
                hasta=date.fromisoformat(fila["hasta"]),
                huespedes=fila["huespedes"],
                estado=EstadoReserva.CONFIRMADA,
                total=Decimal(str(fila["total"])),
                expira_en=None,
                pms_ref=fila["pms_ref"],
            )

    def obtener_reserva(self, codigo: str) -> Reserva:
        with self._lock:
            self._purgar_expiradas_locked()
            cur = self._conn.execute(
                "SELECT * FROM pms.reservas_ref WHERE codigo_reserva = ?",
                (codigo,),
            )
            fila = cur.fetchone()
            if not fila:
                raise ReservaInexistente(f"Reserva con código '{codigo}' no encontrada")

            expira_dt = datetime.fromisoformat(fila["expira_en"]) if fila["expira_en"] else None
            return Reserva(
                codigo=fila["codigo_reserva"],
                propiedad_id=fila["propiedad_id"],
                unidad_id=fila["unidad_id"],
                huesped_token=fila["huesped_token"],
                desde=date.fromisoformat(fila["desde"]),
                hasta=date.fromisoformat(fila["hasta"]),
                huespedes=fila["huespedes"],
                estado=EstadoReserva(fila["estado"]),
                total=Decimal(str(fila["total"])),
                expira_en=expira_dt,
                pms_ref=fila["pms_ref"],
            )

    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]:
        with self._lock:
            self._purgar_expiradas_locked()
            cur = self._conn.execute(
                """
                SELECT * FROM pms.reservas_ref
                WHERE desde = ? AND estado IN ('confirmada', 'preliminar')
                ORDER BY codigo_reserva
                """,
                (fecha.isoformat(),),
            )
            reservas = []
            for f in cur.fetchall():
                expira_dt = datetime.fromisoformat(f["expira_en"]) if f["expira_en"] else None
                reservas.append(
                    Reserva(
                        codigo=f["codigo_reserva"],
                        propiedad_id=f["propiedad_id"],
                        unidad_id=f["unidad_id"],
                        huesped_token=f["huesped_token"],
                        desde=date.fromisoformat(f["desde"]),
                        hasta=date.fromisoformat(f["hasta"]),
                        huespedes=f["huespedes"],
                        estado=EstadoReserva(f["estado"]),
                        total=Decimal(str(f["total"])),
                        expira_en=expira_dt,
                        pms_ref=f["pms_ref"],
                    )
                )
            return tuple(reservas)

    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM pms.reservas_ref WHERE codigo_reserva = ?",
                (codigo,),
            )
            fila = cur.fetchone()
            if not fila:
                raise ReservaInexistente(f"Reserva con código '{codigo}' no encontrada")

            # Liberar noches en noches_ocupadas
            self._conn.execute(
                "DELETE FROM pms.noches_ocupadas WHERE codigo_reserva = ?",
                (codigo,),
            )

            # Actualizar estado a cancelada
            self._conn.execute(
                "UPDATE pms.reservas_ref SET estado = ?, actualizada = CURRENT_TIMESTAMP WHERE codigo_reserva = ?",
                (EstadoReserva.CANCELADA.value, codigo),
            )
            self._conn.commit()

            return Reserva(
                codigo=fila["codigo_reserva"],
                propiedad_id=fila["propiedad_id"],
                unidad_id=fila["unidad_id"],
                huesped_token=fila["huesped_token"],
                desde=date.fromisoformat(fila["desde"]),
                hasta=date.fromisoformat(fila["hasta"]),
                huespedes=fila["huespedes"],
                estado=EstadoReserva.CANCELADA,
                total=Decimal(str(fila["total"])),
                expira_en=None,
                pms_ref=fila["pms_ref"],
            )

    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT r.codigo_reserva, r.unidad_id, r.estado, p.nombre as prop_nombre, p.direccion as prop_direccion, u.wifi_ref, u.acceso_ref
                FROM pms.reservas_ref r
                JOIN pms.propiedades p ON r.propiedad_id = p.propiedad_id
                JOIN pms.unidades u ON r.unidad_id = u.unidad_id
                WHERE r.codigo_reserva = ?
                """,
                (codigo_reserva,),
            )
            fila = cur.fetchone()
            if not fila:
                raise ReservaInexistente(f"Reserva '{codigo_reserva}' no encontrada")

            uid = fila["unidad_id"]
            return InstruccionesCheckin(
                propiedad=fila["prop_nombre"],
                direccion=fila["prop_direccion"],
                hora_checkin="15:00",
                acceso=("Acceso digital por cerradura inteligente", "Código remitido por mensaje privado"),
                wifi_red=fila["wifi_ref"] or f"WIFI_{uid.upper()}",
                wifi_clave_token=f"[[SECRETO:wifi_{uid}]]",
                normas=(
                    "Prohibido fumar en domos y áreas cerradas",
                    "Horario de silencio: 22:00 a 08:00",
                    "Mascotas permitidas con previo registro",
                ),
                contacto_emergencia="+593994445566",
            )

    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia:
        with self._lock:
            cur_p = self._conn.execute(
                "SELECT propiedad_id FROM pms.propiedades WHERE propiedad_id = ?",
                (incidencia.propiedad_id,),
            )
            if not cur_p.fetchone():
                raise PropiedadInexistente(f"Propiedad '{incidencia.propiedad_id}' inexistente")

            if incidencia.unidad_id:
                cur_u = self._conn.execute(
                    "SELECT unidad_id FROM pms.unidades WHERE unidad_id = ?",
                    (incidencia.unidad_id,),
                )
                if not cur_u.fetchone():
                    raise UnidadInexistente(f"Unidad '{incidencia.unidad_id}' inexistente")

            anio = date.today().year
            # INV_TICKET_UNICO mediante secuencia atómica
            cur_seq = self._conn.execute(
                """
                INSERT INTO pms.secuencia_incidencias (anio, ultimo)
                VALUES (?, 1)
                ON CONFLICT(anio) DO UPDATE SET ultimo = secuencia_incidencias.ultimo + 1
                RETURNING ultimo
                """,
                (anio,),
            )
            ultimo_ticket = cur_seq.fetchone()[0]
            ticket_id = f"I-{anio}-{ultimo_ticket:04d}"

            # Regla de integridad de categoría y prioridad
            prioridad_efectiva = incidencia.prioridad
            if incidencia.categoria in ("acceso", "seguridad") and prioridad_efectiva != "critica":
                prioridad_efectiva = "critica"

            self._conn.execute(
                """
                INSERT INTO pms.incidencias (
                    incidencia_id, propiedad_id, unidad_id, codigo_reserva,
                    categoria, prioridad, estado, descripcion_token, gestor_id
                ) VALUES (?, ?, ?, ?, ?, ?, 'abierta', ?, ?)
                """,
                (
                    ticket_id,
                    incidencia.propiedad_id,
                    incidencia.unidad_id,
                    incidencia.reserva_codigo,
                    incidencia.categoria,
                    prioridad_efectiva,
                    incidencia.descripcion_token,
                    incidencia.gestor_id or "gestor_zona_norte",
                ),
            )
            self._conn.commit()

            return Incidencia(
                incidencia_id=ticket_id,
                propiedad_id=incidencia.propiedad_id,
                unidad_id=incidencia.unidad_id,
                reserva_codigo=incidencia.reserva_codigo,
                categoria=incidencia.categoria,
                prioridad=prioridad_efectiva,
                descripcion_token=incidencia.descripcion_token,
                estado="abierta",
                gestor_id=incidencia.gestor_id or "gestor_zona_norte",
            )

    def registrar_tarea_housekeeping(
        self,
        propiedad_id: str,
        unidad_id: str,
        fecha: date,
        nota: str,
        clave_idempotencia: str,
    ) -> str:
        with self._lock:
            cur_u = self._conn.execute(
                "SELECT propiedad_id FROM pms.unidades WHERE unidad_id = ?",
                (unidad_id,),
            )
            if not cur_u.fetchone():
                raise UnidadInexistente(f"Unidad '{unidad_id}' inexistente")

            self._secuencia_hk += 1
            return f"HK-2026-{self._secuencia_hk:04d}"

    def guardar_tarifas(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        precio: Decimal,
        minimo_noches: int,
        actor_id: str,
    ) -> int:
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido (hasta <= desde)")

        with self._lock:
            cur_u = self._conn.execute(
                "SELECT unidad_id FROM pms.unidades WHERE unidad_id = ?",
                (unidad_id,),
            )
            if not cur_u.fetchone():
                raise UnidadInexistente(f"Unidad '{unidad_id}' no encontrada")

            noches_actualizadas = 0
            cur = desde
            while cur < hasta:
                self._conn.execute(
                    """
                    INSERT INTO pms.tarifas_noche (unidad_id, noche, precio, minimo_noches)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(unidad_id, noche) DO UPDATE SET
                        precio = excluded.precio,
                        minimo_noches = excluded.minimo_noches
                    """,
                    (unidad_id, cur.isoformat(), str(precio), minimo_noches),
                )
                noches_actualizadas += 1
                cur += timedelta(days=1)

            self._conn.commit()
            return noches_actualizadas

    def actualizar_calendario(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        accion: str,
        actor_id: str,
    ) -> tuple[int, int]:
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido (hasta <= desde)")

        with self._lock:
            cur_u = self._conn.execute(
                "SELECT unidad_id FROM pms.unidades WHERE unidad_id = ?",
                (unidad_id,),
            )
            if not cur_u.fetchone():
                raise UnidadInexistente(f"Unidad '{unidad_id}' no encontrada")

            # INV_AISLAMIENTO_ANFITRION: el anfitrión solo puede modificar sus propias unidades
            if actor_id and (actor_id.startswith("anf_") or "anfitrion" in actor_id):
                dueno = self._anfitriones_unidades.get(unidad_id)
                if dueno and dueno != actor_id:
                    raise AislamientoAnfitrionError(
                        f"El anfitrión '{actor_id}' no tiene permisos sobre la unidad '{unidad_id}'"
                    )

            noches_afectadas = 0
            omitidas = 0

            cur = desde
            while cur < hasta:
                noche_iso = cur.isoformat()
                cur_oc = self._conn.execute(
                    "SELECT origen, codigo_reserva FROM pms.noches_ocupadas WHERE unidad_id = ? AND noche = ?",
                    (unidad_id, noche_iso),
                )
                fila_oc = cur_oc.fetchone()

                if accion == "bloquear":
                    if fila_oc:
                        omitidas += 1
                    else:
                        self._conn.execute(
                            """
                            INSERT INTO pms.noches_ocupadas (unidad_id, noche, origen, codigo_reserva)
                            VALUES (?, ?, 'bloqueo', NULL)
                            """,
                            (unidad_id, noche_iso),
                        )
                        noches_afectadas += 1
                elif accion == "liberar":
                    if fila_oc:
                        if fila_oc["origen"] == "bloqueo":
                            self._conn.execute(
                                "DELETE FROM pms.noches_ocupadas WHERE unidad_id = ? AND noche = ? AND origen = 'bloqueo'",
                                (unidad_id, noche_iso),
                            )
                            noches_afectadas += 1
                        else:
                            # RF-PMS-08 (b): liberar nunca toca una noche reservada
                            omitidas += 1
                    else:
                        omitidas += 1
                cur += timedelta(days=1)

            self._conn.commit()
            return noches_afectadas, omitidas

    def _purgar_expiradas_locked(self) -> None:
        """Purga reservas preliminares que superaron su ventana de 24 horas y libera sus noches."""
        ahora_iso = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """
            SELECT codigo_reserva FROM pms.reservas_ref
            WHERE estado = ? AND expira_en IS NOT NULL AND expira_en < ?
            """,
            (EstadoReserva.PRELIMINAR.value, ahora_iso),
        )
        codigos_expirados = [f["codigo_reserva"] for f in cursor.fetchall()]

        for cod in codigos_expirados:
            self._conn.execute(
                "DELETE FROM pms.noches_ocupadas WHERE codigo_reserva = ?",
                (cod,),
            )
            self._conn.execute(
                "UPDATE pms.reservas_ref SET estado = ?, actualizada = CURRENT_TIMESTAMP WHERE codigo_reserva = ?",
                (EstadoReserva.EXPIRADA.value, cod),
            )
        if codigos_expirados:
            self._conn.commit()
