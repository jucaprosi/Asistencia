# ¤anfitriones
# ¤¤backend-developer
"""Gestión interna de estados de cuenta, liquidación de comisión, registro de pagos y pausa por mora (RF-ANF-07, RF-ANF-08)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping
import uuid

from features.anfitriones.persistencia_internal import PersistenciaAnfitriones
from features.anfitriones.tipos import (
    EstadoCuenta,
    EstadoDeCuenta,
    EstadoHospedaje,
    EstadoSolicitud,
    LineaCuenta,
    Solicitud,
)

__all__ = ["GestorEstadoCuenta"]


# ¤anfitriones
class GestorEstadoCuenta:
    """Dueña del cierre mensual, cobro, ajustes y morosidad de comisiones de plataforma."""

    def __init__(
        self,
        persistencia: PersistenciaAnfitriones,
        config: Mapping[str, Any],
        seguridad: Any = None,
        canal: Any = None,
        observabilidad: Any = None,
    ) -> None:
        self._persistencia = persistencia
        self._config = config
        self._seguridad = seguridad
        self._canal = canal
        self._observabilidad = observabilidad

    def cerrar_periodo(self, periodo: str, ahora: datetime | None = None) -> tuple[EstadoDeCuenta, ...]:
        """RF-ANF-07: El día 5 cierra el mes de salida anterior por anfitrión con comisiones únicas."""
        ahora_dt = ahora or datetime.now(timezone.utc)
        fecha_emision = ahora_dt.date() if isinstance(ahora_dt, datetime) else ahora_dt
        plazo_dias = int(self._config.get("pago_plazo_dias", 14))
        fecha_vence = fecha_emision + timedelta(days=plazo_dias)

        # 1. Obtener estadías completadas con fecha de salida (hasta) en el período
        estadias = self._persistencia.listar_estadias_completadas_por_periodo(periodo)

        # 2. Agrupar estadías completadas no cobradas por anfitrión
        estadias_por_anfitrion: dict[str, list[Solicitud]] = {}
        for est in estadias:
            # INV_COMISION_PLATAFORMA_UNICA: cada estadía se cobra a lo sumo una vez
            if self._persistencia.solicitud_tiene_cargo(est.solicitud):
                continue
            estadias_por_anfitrion.setdefault(est.anfitrion_id, []).append(est)

        # 3. Identificar anfitriones relevantes (aquellos con estadías nuevas o activos)
        anfitriones_activos = {a.anfitrion_id: a for a in self._persistencia.listar_anfitriones_activos()}
        anfitriones_a_cerrar = set(estadias_por_anfitrion.keys())

        estados_creados: list[EstadoDeCuenta] = []

        for anf_id in anfitriones_a_cerrar:
            # Comprobar si ya existe estado de cuenta para este período (idempotencia)
            ec_existente = self._persistencia.obtener_estado_cuenta(anf_id, periodo)
            solicitudes_anf = estadias_por_anfitrion.get(anf_id, [])

            lineas_nuevas: list[LineaCuenta] = []
            for sol in solicitudes_anf:
                base = sol.total
                porcentaje = sol.comision_porcentaje
                comision = (base * porcentaje / Decimal("100")).quantize(Decimal("0.01"))
                lineas_nuevas.append(
                    LineaCuenta(
                        solicitud=sol.solicitud,
                        base=base,
                        porcentaje=porcentaje,
                        comision=comision,
                        tipo="cargo",
                    )
                )

            if ec_existente is None:
                total_inicial = sum(l.comision for l in lineas_nuevas)
                nuevo_ec = EstadoDeCuenta(
                    estado_cuenta_id=str(uuid.uuid4()),
                    anfitrion_id=anf_id,
                    periodo=periodo,
                    total=total_inicial,
                    estado=EstadoCuenta.EMITIDO,
                    vence_en=fecha_vence,
                    lineas=tuple(lineas_nuevas),
                    emitido_en=ahora_dt,
                )
                self._persistencia.guardar_estado_cuenta(nuevo_ec)
                estados_creados.append(nuevo_ec)

                # Notificación al anfitrión por WhatsApp
                self._notificar_estado_cuenta(anf_id, periodo, total_inicial, fecha_vence)
            else:
                # Agregar líneas pendientes si no estaban registradas
                for l in lineas_nuevas:
                    try:
                        self._persistencia.guardar_linea_cuenta(ec_existente.estado_cuenta_id, l)
                    except Exception:
                        pass
                ec_actualizado = self._persistencia.obtener_estado_cuenta(anf_id, periodo)
                if ec_actualizado:
                    estados_creados.append(ec_actualizado)

        if hasattr(self._observabilidad, "log"):
            try:
                self._observabilidad.log(
                    "INFO",
                    "cierre_periodo_anfitriones",
                    periodo=periodo,
                    estados_generados=len(estados_creados),
                )
            except Exception:
                pass

        return tuple(estados_creados)

    def _notificar_estado_cuenta(self, anfitrion_id: str, periodo: str, total: Decimal, vence_en: date) -> None:
        """Envía plantilla oficial de WhatsApp al anfitrión notificando el cierre mensual."""
        if self._canal is None or not hasattr(self._canal, "enviar_plantilla"):
            return

        anf = self._persistencia.obtener_anfitrion(anfitrion_id)
        if anf is None or not anf.telefono_token:
            return

        try:
            from features.canal_whatsapp.canal_whatsapp_service import Plantilla
            plantilla = Plantilla(
                nombre="estado_cuenta_anfitrion",
                idioma="es",
                variables=(
                    anf.nombre_comercial,
                    periodo,
                    f"{total:.2f}",
                    vence_en.isoformat(),
                ),
            )
            self._canal.enviar_plantilla(anf.telefono_token, plantilla)
        except Exception as exc:
            if hasattr(self._observabilidad, "log"):
                try:
                    self._observabilidad.log(
                        "WARNING",
                        "fallo_notificacion_whatsapp_estado_cuenta",
                        anfitrion_id=anfitrion_id,
                        periodo=periodo,
                        error=str(exc),
                    )
                except Exception:
                    pass

    def estado_de_cuenta(self, anfitrion_id: str, periodo: str, actor_id: str | None = None) -> EstadoDeCuenta:
        """RF-ANF-07: Consulta el estado de cuenta mensual con aislamiento entre anfitriones (INV_AISLAMIENTO_ANFITRION)."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        # INV_AISLAMIENTO_ANFITRION: el anfitrión solo puede consultar sus propias cuentas
        if actor_id is not None and actor_id != anfitrion_id:
            if hasattr(self._seguridad, "auditar"):
                try:
                    from features.seguridad.seguridad_service import EventoAuditoria, Rol
                    rol_actor = Rol.ANFITRION if hasattr(Rol, "ANFITRION") else "anfitrion"
                    self._seguridad.auditar(
                        EventoAuditoria(
                            actor_token=actor_id,
                            rol=rol_actor,
                            accion="consultar_estado_cuenta",
                            herramienta="consultar_estado_cuenta",
                            propiedad_id=anfitrion_id,
                            resultado="denegado_aislamiento_anfitrion",
                        )
                    )
                except Exception:
                    pass
            raise ErrorAnfitriones(
                "ACCESO_DENEGADO",
                "No tienes autorización para consultar el estado de cuenta de otro anfitrión.",
            )

        ec = self._persistencia.obtener_estado_cuenta(anfitrion_id, periodo)
        if ec is None:
            raise ErrorAnfitriones(
                "ESTADO_CUENTA_NO_ENCONTRADO",
                f"No existe estado de cuenta para el período {periodo}.",
            )
        return ec

    def registrar_pago(self, estado_cuenta_id: str, actor_id: str, ahora: datetime | None = None) -> EstadoDeCuenta:
        """RF-ANF-08: El administrador registra el pago guardando actor y fecha."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        ec = self._persistencia.obtener_estado_cuenta_por_id(estado_cuenta_id)
        if ec is None:
            raise ErrorAnfitriones(
                "ESTADO_CUENTA_NO_ENCONTRADO",
                f"No existe el estado de cuenta {estado_cuenta_id}.",
            )

        if ec.estado == EstadoCuenta.PAGADO:
            return ec

        ahora_dt = ahora or datetime.now(timezone.utc)
        self._persistencia.actualizar_estado_cuenta(
            estado_cuenta_id=estado_cuenta_id,
            estado=EstadoCuenta.PAGADO,
            pagado_en=ahora_dt,
            pago_registrado_por=actor_id,
        )

        if hasattr(self._seguridad, "auditar"):
            try:
                from features.seguridad.seguridad_service import EventoAuditoria, Rol
                self._seguridad.auditar(
                    EventoAuditoria(
                        actor_token=actor_id,
                        rol=Rol.ADMINISTRADOR if hasattr(Rol, "ADMINISTRADOR") else "administrador",
                        accion="registrar_pago",
                        herramienta="registrar_pago",
                        propiedad_id=ec.anfitrion_id,
                        resultado="ok",
                    )
                )
            except Exception:
                pass

        if hasattr(self._observabilidad, "log"):
            try:
                self._observabilidad.log(
                    "INFO",
                    "pago_estado_cuenta_registrado",
                    estado_cuenta_id=estado_cuenta_id,
                    anfitrion_id=ec.anfitrion_id,
                    periodo=ec.periodo,
                    total=str(ec.total),
                    actor_id=actor_id,
                )
            except Exception:
                pass

        ec_actualizado = self._persistencia.obtener_estado_cuenta_por_id(estado_cuenta_id)
        assert ec_actualizado is not None
        return ec_actualizado

    def agregar_ajuste(
        self,
        anfitrion_id: str,
        periodo: str,
        solicitud: str,
        comision: Decimal,
        base: Decimal = Decimal("0.00"),
        porcentaje: Decimal = Decimal("0.00"),
        actor_id: str = "admin",
    ) -> LineaCuenta:
        """RF-ANF-07 (c): Registra una línea de corrección posterior tipo 'ajuste' en el período abierto."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        ec = self._persistencia.obtener_estado_cuenta(anfitrion_id, periodo)
        if ec is None:
            # Crear estado de cuenta en emitido para el período
            plazo_dias = int(self._config.get("pago_plazo_dias", 14))
            vence_d = date.today() + timedelta(days=plazo_dias)
            ec = EstadoDeCuenta(
                estado_cuenta_id=str(uuid.uuid4()),
                anfitrion_id=anfitrion_id,
                periodo=periodo,
                total=Decimal("0.00"),
                estado=EstadoCuenta.EMITIDO,
                vence_en=vence_d,
                lineas=(),
                emitido_en=datetime.now(timezone.utc),
            )
            self._persistencia.guardar_estado_cuenta(ec)

        if ec.estado == EstadoCuenta.PAGADO:
            raise ErrorAnfitriones(
                "PERIODO_CERRADO_Y_PAGADO",
                f"El estado de cuenta del período {periodo} ya está pagado; los ajustes deben registrarse en un período abierto.",
            )

        linea_ajuste = LineaCuenta(
            solicitud=solicitud,
            base=base,
            porcentaje=porcentaje,
            comision=comision,
            tipo="ajuste",
        )
        self._persistencia.guardar_linea_cuenta(ec.estado_cuenta_id, linea_ajuste)

        if hasattr(self._observabilidad, "log"):
            try:
                self._observabilidad.log(
                    "INFO",
                    "ajuste_estado_cuenta_registrado",
                    anfitrion_id=anfitrion_id,
                    periodo=periodo,
                    solicitud=solicitud,
                    comision=str(comision),
                    actor_id=actor_id,
                )
            except Exception:
                pass

        return linea_ajuste

    def procesar_cuentas_vencidas(self, ahora_fecha: date | None = None) -> tuple[str, ...]:
        """RF-ANF-08: A los 15 días de vencido el estado de cuenta, los hospedajes del anfitrión pasan a pausado."""
        fecha_actual = ahora_fecha or date.today()
        dias_gracia = int(self._config.get("pausa_tras_vencimiento_dias", 15))

        cuentas_pendientes = self._persistencia.listar_estados_cuenta_morosos()
        propiedades_pausadas: list[str] = []

        for ec in cuentas_pendientes:
            if ec.estado == EstadoCuenta.PAGADO:
                continue

            # Marcar vencido si venció la fecha de pago
            if fecha_actual > ec.vence_en and ec.estado == EstadoCuenta.EMITIDO:
                self._persistencia.actualizar_estado_cuenta(
                    estado_cuenta_id=ec.estado_cuenta_id,
                    estado=EstadoCuenta.VENCIDO,
                )

            # Criterio (b): a los 15 días de vencido, sus hospedajes pasan a pausado
            fecha_pausa = ec.vence_en + timedelta(days=dias_gracia)
            if fecha_actual >= fecha_pausa:
                pids = self._persistencia.pausar_hospedajes_de_anfitrion(ec.anfitrion_id)
                propiedades_pausadas.extend(pids)

                if pids and hasattr(self._observabilidad, "log"):
                    try:
                        self._observabilidad.log(
                            "WARNING",
                            "hospedajes_pausados_por_morosidad",
                            anfitrion_id=ec.anfitrion_id,
                            estado_cuenta_id=ec.estado_cuenta_id,
                            propiedades_pausadas=list(pids),
                        )
                    except Exception:
                        pass

        return tuple(propiedades_pausadas)

    def consultar_estado_cuenta(self, anfitrion_id: str, periodo: str, actor_id: str | None = None) -> dict[str, Any]:
        """Atiende la herramienta MCP consultar_estado_cuenta_anfitrion."""
        ec = self.estado_de_cuenta(anfitrion_id, periodo, actor_id=actor_id)
        cargos = [l for l in ec.lineas if l.tipo == "cargo"]
        return {
            "periodo": ec.periodo,
            "total": f"{ec.total:.2f}",
            "estado": ec.estado.value,
            "estadias": len(cargos),
        }
