# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Implementación en memoria FakePMS para pruebas y desarrollo (RF-PMS-01, RF-PMS-02)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import time
from typing import Mapping

from features.pms_conector.base_internal import PMSConnector
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
    TareaHousekeeping,
    TipoPropiedad,
    Unidad,
    UnidadInexistente,
)


# ¤pms-conector
class FakePMS(PMSConnector):
    """PMS sintético con dos propiedades preconfiguradas, disponibilidad y ciclo de reservas."""

    def __init__(self, latencia_s: float = 0.0) -> None:
        self.latencia_s = latencia_s
        self.llamadas_realizadas: int = 0

        # Catálogo de dos propiedades canónicas
        self._propiedades: dict[str, Propiedad] = {
            "glamping_imbabura": Propiedad(
                propiedad_id="glamping_imbabura",
                tipo=TipoPropiedad.GLAMPING,
                nombre="Glamping Imbabura",
                zona_id="imbabura_norte",
                direccion="Sector San Pablo del Lago, Otavalo",
                activa=True,
                pms_ref="pms_glamping_01",
                prompt_variante="glamping",
            ),
            "dep_ibarra_centro": Propiedad(
                propiedad_id="dep_ibarra_centro",
                tipo=TipoPropiedad.DEPARTAMENTO,
                nombre="Departamentos Ibarra Centro",
                zona_id="ibarra_centro",
                direccion="Calle Bolívar y Flores, Ibarra",
                activa=True,
                pms_ref="pms_dep_02",
                prompt_variante="departamentos",
            ),
        }

        # Unidades por propiedad
        self._unidades: dict[str, Unidad] = {
            "domo_lago": Unidad(
                unidad_id="domo_lago",
                propiedad_id="glamping_imbabura",
                nombre="Domo Lago",
                capacidad=2,
            ),
            "domo_bosque": Unidad(
                unidad_id="domo_bosque",
                propiedad_id="glamping_imbabura",
                nombre="Domo Bosque",
                capacidad=4,
            ),
            "suite_101": Unidad(
                unidad_id="suite_101",
                propiedad_id="dep_ibarra_centro",
                nombre="Suite 101",
                capacidad=2,
                edificio="Torre Central",
                piso="1",
            ),
            "fam_201": Unidad(
                unidad_id="fam_201",
                propiedad_id="dep_ibarra_centro",
                nombre="Departamento Familiar 201",
                capacidad=5,
                edificio="Torre Central",
                piso="2",
            ),
        }

        # Tarifas por defecto por unidad (noche)
        self._tarifas_base: dict[str, Decimal] = {
            "domo_lago": Decimal("120.00"),
            "domo_bosque": Decimal("180.00"),
            "suite_101": Decimal("65.00"),
            "fam_201": Decimal("110.00"),
        }
        # Tarifas específicas por fecha: (unidad_id, date) -> Decimal
        self._tarifas_fecha: dict[tuple[str, date], Decimal] = {}

        # Noches ocupadas: (unidad_id, date) -> codigo_reserva o "BLOQUEO"
        self._noches_ocupadas: dict[tuple[str, date], str] = {}

        # Reservas activas o históricas: codigo -> Reserva
        self._reservas: dict[str, Reserva] = {}

        # Incidencias: incidencia_id -> Incidencia
        self._incidencias: dict[str, Incidencia] = {}
        self._secuencia_incidencias: int = 100

        # Housekeeping: tarea_id -> TareaHousekeeping
        self._housekeeping: dict[str, TareaHousekeeping] = {}
        self._secuencia_housekeeping: int = 1

        # Mapeo anfitriones a unidades (INV_AISLAMIENTO_ANFITRION)
        self._anfitriones_unidades: dict[str, str] = {
            "domo_lago": "anf_imbabura_01",
            "domo_bosque": "anf_imbabura_01",
            "suite_101": "anf_ibarra_01",
            "fam_201": "anf_ibarra_01",
        }

        # Contador de reservas
        self._contador_reservas: int = 1000

    def _simular_demora(self) -> None:
        self.llamadas_realizadas += 1
        if self.latencia_s > 0:
            time.sleep(self.latencia_s)

    def _purgar_expiradas(self) -> None:
        """Pasa automáticamente reservas preliminares vencidas a estado 'expirada' y libera fechas."""
        ahora = datetime.now(timezone.utc)
        for codigo, res in list(self._reservas.items()):
            if res.estado == EstadoReserva.PRELIMINAR and res.expira_en and ahora > res.expira_en:
                # Actualizar estado a expirada
                res_expirada = Reserva(
                    codigo=res.codigo,
                    propiedad_id=res.propiedad_id,
                    unidad_id=res.unidad_id,
                    huesped_token=res.huesped_token,
                    desde=res.desde,
                    hasta=res.hasta,
                    huespedes=res.huespedes,
                    estado=EstadoReserva.EXPIRADA,
                    total=res.total,
                    expira_en=res.expira_en,
                    pms_ref=res.pms_ref,
                )
                self._reservas[codigo] = res_expirada

                # Liberar noches ocupadas
                cur = res.desde
                while cur < res.hasta:
                    if self._noches_ocupadas.get((res.unidad_id, cur)) == codigo:
                        del self._noches_ocupadas[(res.unidad_id, cur)]
                    cur += timedelta(days=1)

    def listar_propiedades(self) -> tuple[Propiedad, ...]:
        self._simular_demora()
        return tuple(p for p in self._propiedades.values() if p.activa)

    def consultar_disponibilidad(
        self, propiedad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Disponibilidad:
        self._simular_demora()
        self._purgar_expiradas()

        if propiedad_id not in self._propiedades:
            raise PropiedadInexistente(f"Propiedad '{propiedad_id}' no encontrada")
        if hasta <= desde:
            raise FechasInvalidas("La fecha 'hasta' debe ser posterior a 'desde'")

        unidades_propiedad = [
            u for u in self._unidades.values() if u.propiedad_id == propiedad_id and u.capacidad >= huespedes
        ]

        disponibles: list[Unidad] = []
        for u in unidades_propiedad:
            ocupada = False
            cur = desde
            while cur < hasta:
                if (u.unidad_id, cur) in self._noches_ocupadas:
                    ocupada = True
                    break
                cur += timedelta(days=1)
            if not ocupada:
                disponibles.append(u)

        if disponibles:
            return Disponibilidad(disponible=True, unidades=tuple(disponibles))

        return Disponibilidad(
            disponible=False,
            unidades=(),
            motivo="Sin disponibilidad para las fechas y capacidad solicitadas",
            alternativas=(),
        )

    def cotizar(
        self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Cotizacion:
        self._simular_demora()
        if propiedad_id not in self._propiedades:
            raise PropiedadInexistente(f"Propiedad '{propiedad_id}' no encontrada")
        if unidad_id not in self._unidades:
            raise UnidadInexistente(f"Unidad '{unidad_id}' no encontrada")
        unidad = self._unidades[unidad_id]
        if unidad.propiedad_id != propiedad_id:
            raise UnidadInexistente(f"Unidad '{unidad_id}' no pertenece a '{propiedad_id}'")
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido para cotizar")
        if unidad.capacidad < huespedes:
            raise CapacidadExcedida(f"La unidad '{unidad.nombre}' tiene capacidad para {unidad.capacidad} personas")

        noches = (hasta - desde).days
        desglose: list[tuple[str, Decimal]] = []
        total = Decimal("0.00")

        cur = desde
        while cur < hasta:
            precio_noche = self._tarifas_fecha.get((unidad_id, cur), self._tarifas_base.get(unidad_id, Decimal("100.00")))
            desglose.append((f"Noche {cur.isoformat()}", precio_noche))
            total += precio_noche
            cur += timedelta(days=1)

        return Cotizacion(
            total=total,
            moneda="USD",
            desglose=tuple(desglose),
            politica_cancelacion_id="moderada_24h",
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
        self._simular_demora()
        self._purgar_expiradas()

        # Verificar disponibilidad de la unidad
        disp = self.consultar_disponibilidad(propiedad_id, desde, hasta, huespedes)
        if not disp.disponible or unidad_id not in [u.unidad_id for u in disp.unidades]:
            raise SinDisponibilidad(f"La unidad '{unidad_id}' no está libre del {desde} al {hasta}")

        cotizacion = self.cotizar(propiedad_id, unidad_id, desde, hasta, huespedes)
        self._contador_reservas += 1
        codigo = f"RES-2026-{self._contador_reservas:04d}"

        # 24 horas de vigencia para pago y confirmación
        ahora = datetime.now(timezone.utc)
        expira_en = ahora + timedelta(hours=24)

        # Ocupar noches
        cur = desde
        while cur < hasta:
            self._noches_ocupadas[(unidad_id, cur)] = codigo
            cur += timedelta(days=1)

        reserva = Reserva(
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
            pms_ref=f"fake_ref_{codigo}",
        )
        self._reservas[codigo] = reserva
        return reserva

    def confirmar_reserva(self, codigo: str, clave_idempotencia: str) -> Reserva:
        self._simular_demora()
        res = self.obtener_reserva(codigo)

        if res.estado == EstadoReserva.EXPIRADA:
            raise SinDisponibilidad(f"La reserva {codigo} ha expirado y no puede confirmarse")
        if res.estado == EstadoReserva.CANCELADA:
            raise SinDisponibilidad(f"La reserva {codigo} fue cancelada")

        confirmada = Reserva(
            codigo=res.codigo,
            propiedad_id=res.propiedad_id,
            unidad_id=res.unidad_id,
            huesped_token=res.huesped_token,
            desde=res.desde,
            hasta=res.hasta,
            huespedes=res.huespedes,
            estado=EstadoReserva.CONFIRMADA,
            total=res.total,
            expira_en=None,
            pms_ref=res.pms_ref,
        )
        self._reservas[codigo] = confirmada
        return confirmada

    def obtener_reserva(self, codigo: str) -> Reserva:
        self._simular_demora()
        self._purgar_expiradas()
        if codigo not in self._reservas:
            raise ReservaInexistente(f"Reserva con código '{codigo}' no encontrada")
        return self._reservas[codigo]

    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]:
        self._simular_demora()
        self._purgar_expiradas()
        return tuple(
            r for r in self._reservas.values()
            if r.desde == fecha and r.estado in (EstadoReserva.CONFIRMADA, EstadoReserva.PRELIMINAR)
        )

    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva:
        self._simular_demora()
        res = self.obtener_reserva(codigo)

        # Liberar noches
        cur = res.desde
        while cur < res.hasta:
            if self._noches_ocupadas.get((res.unidad_id, cur)) == codigo:
                del self._noches_ocupadas[(res.unidad_id, cur)]
            cur += timedelta(days=1)

        cancelada = Reserva(
            codigo=res.codigo,
            propiedad_id=res.propiedad_id,
            unidad_id=res.unidad_id,
            huesped_token=res.huesped_token,
            desde=res.desde,
            hasta=res.hasta,
            huespedes=res.huespedes,
            estado=EstadoReserva.CANCELADA,
            total=res.total,
            expira_en=None,
            pms_ref=res.pms_ref,
        )
        self._reservas[codigo] = cancelada
        return cancelada

    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin:
        self._simular_demora()
        res = self.obtener_reserva(codigo_reserva)
        prop = self._propiedades.get(res.propiedad_id)

        if res.propiedad_id == "glamping_imbabura":
            return InstruccionesCheckin(
                propiedad=prop.nombre if prop else "Glamping Imbabura",
                direccion="Sector San Pablo del Lago, Otavalo",
                hora_checkin="15:00",
                acceso=("Ingreso por portón automatizado con tarjeta", "Seguir señales luminosas"),
                wifi_red="Glamping_Huespedes",
                wifi_clave_token="[[SECRETO:wifi_glamping_imbabura]]",
                normas=("No fumar dentro del domo", "Silencio desde las 22:00"),
                contacto_emergencia="+593991112233",
            )
        return InstruccionesCheckin(
            propiedad=prop.nombre if prop else "Departamentos Ibarra Centro",
            direccion="Calle Bolívar y Flores, Ibarra",
            hora_checkin="14:00",
            acceso=("Teclado de acceso con código seguro", "Tomar ascensor al piso correspondiente"),
            wifi_red="Departamentos_Ibarra_Fibra",
            wifi_clave_token="[[SECRETO:wifi_ibarra_centro]]",
            normas=("No fiestas ni eventos", "Mascotas bajo petición previa"),
            contacto_emergencia="+593994445566",
        )

    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia:
        self._simular_demora()
        if incidencia.propiedad_id not in self._propiedades:
            raise PropiedadInexistente(f"Propiedad '{incidencia.propiedad_id}' inexistente")

        self._secuencia_incidencias += 1
        ticket_id = f"I-2026-{self._secuencia_incidencias:04d}"

        creada = Incidencia(
            incidencia_id=ticket_id,
            propiedad_id=incidencia.propiedad_id,
            unidad_id=incidencia.unidad_id,
            reserva_codigo=incidencia.reserva_codigo,
            categoria=incidencia.categoria,
            prioridad=incidencia.prioridad,
            descripcion_token=incidencia.descripcion_token,
            estado="abierta",
            gestor_id=incidencia.gestor_id or "gestor_zona_norte",
        )
        self._incidencias[ticket_id] = creada
        return creada

    def registrar_tarea_housekeeping(
        self,
        propiedad_id: str,
        unidad_id: str,
        fecha: date,
        nota: str,
        clave_idempotencia: str,
    ) -> str:
        self._simular_demora()
        if propiedad_id not in self._propiedades:
            raise PropiedadInexistente(f"Propiedad '{propiedad_id}' inexistente")
        if unidad_id not in self._unidades:
            raise UnidadInexistente(f"Unidad '{unidad_id}' inexistente")

        self._secuencia_housekeeping += 1
        tarea_id = f"HK-2026-{self._secuencia_housekeeping:04d}"
        self._housekeeping[tarea_id] = TareaHousekeeping(
            tarea_id=tarea_id,
            propiedad_id=propiedad_id,
            unidad_id=unidad_id,
            fecha=fecha,
            nota=nota,
        )
        return tarea_id

    def guardar_tarifas(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        precio: Decimal,
        minimo_noches: int,
        actor_id: str,
    ) -> int:
        self._simular_demora()
        if unidad_id not in self._unidades:
            raise UnidadInexistente(f"Unidad '{unidad_id}' no encontrada")
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido")

        noches_actualizadas = 0
        cur = desde
        while cur < hasta:
            self._tarifas_fecha[(unidad_id, cur)] = precio
            noches_actualizadas += 1
            cur += timedelta(days=1)

        return noches_actualizadas

    def registrar_anfitrion_unidad(self, unidad_id: str, anfitrion_id: str) -> None:
        """Registra la asignación de propiedad de una unidad a un anfitrión (INV_AISLAMIENTO_ANFITRION)."""
        self._anfitriones_unidades[unidad_id] = anfitrion_id

    def actualizar_calendario(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        accion: str,
        actor_id: str,
    ) -> tuple[int, int]:
        self._simular_demora()
        if unidad_id not in self._unidades:
            raise UnidadInexistente(f"Unidad '{unidad_id}' no encontrada")
        if hasta <= desde:
            raise FechasInvalidas("Rango de fechas inválido")

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
            clave = (unidad_id, cur)
            if accion == "bloquear":
                if clave in self._noches_ocupadas:
                    omitidas += 1
                else:
                    self._noches_ocupadas[clave] = "BLOQUEO_MANUAL"
                    noches_afectadas += 1
            elif accion == "liberar":
                if clave in self._noches_ocupadas:
                    # Si es bloqueo manual se libera, si es reserva confirmada no se libera por aquí
                    if self._noches_ocupadas[clave] == "BLOQUEO_MANUAL":
                        del self._noches_ocupadas[clave]
                        noches_afectadas += 1
                    else:
                        omitidas += 1
                else:
                    omitidas += 1
            cur += timedelta(days=1)

        return noches_afectadas, omitidas
