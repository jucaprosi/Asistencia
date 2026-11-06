# ¤anfitriones
# ¤¤backend-developer
"""Gestión interna de solicitudes de reserva, respuestas y resultados de estadía (RF-ANF-04..06)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

from features.anfitriones.persistencia_internal import PersistenciaAnfitriones
from features.anfitriones.tipos import (
    EstadoAnfitrion,
    EstadoHospedaje,
    EstadoSolicitud,
    Solicitud,
)

__all__ = ["GestorSolicitudes"]


# ¤anfitriones
class GestorSolicitudes:
    """Implementa el ciclo de vida de solicitudes de reserva, confirmación y cierre."""

    def __init__(
        self,
        persistencia: PersistenciaAnfitriones,
        config: Mapping[str, Any],
        pms: Any,
        canal: Any,
        seguridad: Any,
        observabilidad: Any,
    ) -> None:
        self._persistencia = persistencia
        self._config = config
        self._pms = pms
        self._canal = canal
        self._seguridad = seguridad
        self._observabilidad = observabilidad

    def solicitar_reserva(self, codigo_reserva: str) -> Solicitud:
        """RF-ANF-04: Crea una solicitud con código PL- congelando porcentaje y obteniendo datos del PMS."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        # Si ya existe para esta reserva, devolverla de forma idempotente
        existente = self._persistencia.obtener_solicitud_por_reserva(codigo_reserva)
        if existente is not None:
            return existente

        # Criterio (a): Fechas y total salen del PMS, nunca del modelo
        if self._pms is None or not hasattr(self._pms, "obtener_reserva"):
            raise ErrorAnfitriones(
                "PMS_NO_DISPONIBLE",
                "El conector de PMS no se encuentra disponible.",
            )

        reserva = self._pms.obtener_reserva(codigo_reserva)
        if reserva is None:
            raise ErrorAnfitriones(
                "RESERVA_NO_ENCONTRADA",
                f"No se encontró la reserva con código {codigo_reserva}.",
            )

        propiedad_id = str(getattr(reserva, "propiedad_id", ""))
        hospedaje = self._persistencia.obtener_hospedaje(propiedad_id)
        if hospedaje is None or hospedaje.estado != EstadoHospedaje.PUBLICADO:
            raise ErrorAnfitriones(
                "HOSPEDAJE_NO_DISPONIBLE",
                f"El hospedaje {propiedad_id} no se encuentra publicado para recibir reservas.",
            )

        anfitrion = self._persistencia.obtener_anfitrion(hospedaje.anfitrion_id)
        if anfitrion is None or anfitrion.estado != EstadoAnfitrion.ACTIVO:
            raise ErrorAnfitriones(
                "ANFITRION_INACTIVO",
                "El anfitrión de la propiedad no está activo en la plataforma.",
            )

        # Criterio (b): El porcentaje de comisión queda congelado
        comision_congelada = anfitrion.comision_porcentaje

        # Criterio (c): El anfitrión recibe la plantilla con vigencia de 24 horas
        vigencia_h = int(self._config.get("solicitud_vigencia_h", 24))
        ahora = datetime.now(timezone.utc)
        vence_en = ahora + timedelta(hours=vigencia_h)

        codigo_solicitud = self._persistencia.siguiente_codigo_solicitud(ahora.year)
        total_pms = Decimal(str(getattr(reserva, "total", "0.00")))
        desde_pms = getattr(reserva, "desde")
        hasta_pms = getattr(reserva, "hasta")

        solicitud = Solicitud(
            solicitud=codigo_solicitud,
            codigo_reserva=codigo_reserva,
            propiedad_id=propiedad_id,
            anfitrion_id=anfitrion.anfitrion_id,
            desde=desde_pms,
            hasta=hasta_pms,
            total=total_pms,
            comision_porcentaje=comision_congelada,
            estado=EstadoSolicitud.SOLICITADA,
            vence_en=vence_en,
            creado_en=ahora,
        )

        self._persistencia.guardar_solicitud(solicitud)

        # Envío de plantilla de WhatsApp al anfitrión
        if hasattr(self._canal, "enviar_plantilla"):
            try:
                from features.canal_whatsapp.canal_whatsapp_service import Plantilla
                plantilla = Plantilla(
                    nombre="solicitud_reserva_anfitrion",
                    idioma="es",
                    variables=(
                        anfitrion.nombre_comercial,
                        propiedad_id,
                        f"{desde_pms} a {hasta_pms}",
                        codigo_solicitud,
                    ),
                )
                self._canal.enviar_plantilla(anfitrion.telefono_token, plantilla)
            except Exception as exc:
                if hasattr(self._observabilidad, "log"):
                    self._observabilidad.log(
                        "WARNING",
                        "fallo_envio_plantilla_solicitud",
                        solicitud=codigo_solicitud,
                        error=str(exc),
                    )

        if hasattr(self._seguridad, "auditar"):
            try:
                from features.seguridad.seguridad_service import EventoAuditoria, Rol
                self._seguridad.auditar(
                    EventoAuditoria(
                        actor_token="asistente",
                        rol=Rol.AGENTE if hasattr(Rol, "AGENTE") else "agente",
                        accion="solicitar_reserva",
                        herramienta="solicitar_reserva",
                        propiedad_id=propiedad_id,
                        resultado="ok",
                    )
                )
            except Exception:
                pass

        return solicitud

    def responder_solicitud(
        self,
        solicitud: str,
        anfitrion_id: str,
        acepta: bool,
        motivo: str | None = None,
    ) -> Solicitud:
        """RF-ANF-05: Confirma o rechaza. Entrega contacto solo si confirma (INV_CONTACTO_TRAS_CONFIRMAR)."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        sol = self._persistencia.obtener_solicitud(solicitud)
        if sol is None:
            raise ErrorAnfitriones(
                "SOLICITUD_NO_ENCONTRADA",
                f"No existe la solicitud {solicitud}.",
            )

        # Criterio (c): Nadie responde por otro anfitrión (INV_AISLAMIENTO_ANFITRION)
        if sol.anfitrion_id != anfitrion_id:
            if hasattr(self._seguridad, "auditar"):
                try:
                    from features.seguridad.seguridad_service import EventoAuditoria, Rol
                    rol_actor = Rol.ANFITRION if hasattr(Rol, "ANFITRION") else "anfitrion"
                    self._seguridad.auditar(
                        EventoAuditoria(
                            actor_token=anfitrion_id,
                            rol=rol_actor,
                            accion="responder_solicitud",
                            herramienta="responder_solicitud",
                            propiedad_id=sol.propiedad_id,
                            resultado="denegado_aislamiento_anfitrion",
                        )
                    )
                except Exception:
                    pass
            raise ErrorAnfitriones(
                "ACCESO_DENEGADO",
                "No tienes autorización para operar sobre solicitudes de otro anfitrión.",
            )

        ahora = datetime.now(timezone.utc)

        # Comprobar vencimiento
        if sol.estado == EstadoSolicitud.EXPIRADA or (
            sol.estado == EstadoSolicitud.SOLICITADA and ahora > sol.vence_en
        ):
            if sol.estado == EstadoSolicitud.SOLICITADA:
                self._persistencia.actualizar_estado_solicitud(
                    sol.solicitud, EstadoSolicitud.EXPIRADA
                )
            raise ErrorAnfitriones(
                "SOLICITUD_EXPIRADA",
                "La solicitud ha expirado y ya no puede ser respondida.",
            )

        if sol.estado != EstadoSolicitud.SOLICITADA:
            raise ErrorAnfitriones(
                "ESTADO_INVALIDO",
                f"La solicitud ya se encuentra en estado '{sol.estado.value}'.",
            )

        if acepta:
            # Pasa a confirmada
            nuevo_estado = EstadoSolicitud.CONFIRMADA
            self._persistencia.actualizar_estado_solicitud(
                sol.solicitud, nuevo_estado, respondida_en=ahora
            )

            # Criterio (a) e INV_CONTACTO_TRAS_CONFIRMAR:
            # El contacto se entrega solo al confirmar
            reserva = None
            if self._pms is not None and hasattr(self._pms, "obtener_reserva"):
                try:
                    reserva = self._pms.obtener_reserva(sol.codigo_reserva)
                except Exception:
                    pass

            anfitrion = self._persistencia.obtener_anfitrion(sol.anfitrion_id)

            huesped_token = getattr(reserva, "huesped_token", "Huésped") if reserva else "Huésped"
            anfitrion_tel = anfitrion.telefono_token if anfitrion else ""

            if hasattr(self._canal, "enviar_plantilla"):
                try:
                    from features.canal_whatsapp.canal_whatsapp_service import Plantilla
                    # Notificar al huésped con el contacto del anfitrión
                    if reserva and hasattr(reserva, "huesped_token") and reserva.huesped_token:
                        self._canal.enviar_plantilla(
                            reserva.huesped_token,
                            Plantilla(
                                nombre="reserva_confirmada",
                                idioma="es",
                                variables=(huesped_token, sol.propiedad_id, anfitrion_tel),
                            ),
                        )
                    # Notificar al anfitrión con el contacto del huésped
                    if anfitrion and anfitrion.telefono_token:
                        self._canal.enviar_plantilla(
                            anfitrion.telefono_token,
                            Plantilla(
                                nombre="reserva_confirmada",
                                idioma="es",
                                variables=(anfitrion.nombre_comercial, sol.propiedad_id, huesped_token),
                            ),
                        )
                except Exception as exc:
                    if hasattr(self._observabilidad, "log"):
                        self._observabilidad.log(
                            "WARNING",
                            "fallo_entrega_contacto_tras_confirmar",
                            solicitud=sol.solicitud,
                            error=str(exc),
                        )
        else:
            # Pasa a rechazada (el contacto NO se entrega)
            nuevo_estado = EstadoSolicitud.RECHAZADA
            self._persistencia.actualizar_estado_solicitud(
                sol.solicitud, nuevo_estado, respondida_en=ahora
            )

        if hasattr(self._seguridad, "auditar"):
            try:
                from features.seguridad.seguridad_service import EventoAuditoria, Rol
                rol_actor = Rol.ANFITRION if hasattr(Rol, "ANFITRION") else "anfitrion"
                self._seguridad.auditar(
                    EventoAuditoria(
                        actor_token=anfitrion_id,
                        rol=rol_actor,
                        accion=f"responder_{nuevo_estado.value}",
                        herramienta="responder_solicitud",
                        propiedad_id=sol.propiedad_id,
                        resultado="ok",
                    )
                )
            except Exception:
                pass

        return self._persistencia.obtener_solicitud(sol.solicitud)

    def reportar_resultado(
        self,
        solicitud: str,
        anfitrion_id: str,
        resultado: EstadoSolicitud | str,
        ahora_fecha: date | None = None,
    ) -> Solicitud:
        """RF-ANF-06: Reporta cancelada o no_show hasta 3 días tras salida. No generan comisión."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        if isinstance(resultado, str):
            try:
                resultado_enum = EstadoSolicitud(resultado)
            except ValueError:
                raise ErrorAnfitriones(
                    "RESULTADO_INVALIDO",
                    f"El resultado '{resultado}' no es un estado de estadía válido.",
                )
        else:
            resultado_enum = resultado

        if resultado_enum not in (
            EstadoSolicitud.CANCELADA,
            EstadoSolicitud.NO_SHOW,
            EstadoSolicitud.COMPLETADA,
        ):
            raise ErrorAnfitriones(
                "RESULTADO_NO_PERMITIDO",
                f"Solo se puede reportar cancelada, no_show o completada (recibido: {resultado_enum.value}).",
            )

        sol = self._persistencia.obtener_solicitud(solicitud)
        if sol is None:
            raise ErrorAnfitriones(
                "SOLICITUD_NO_ENCONTRADA",
                f"No existe la solicitud {solicitud}.",
            )

        # INV_AISLAMIENTO_ANFITRION
        if sol.anfitrion_id != anfitrion_id:
            if hasattr(self._seguridad, "auditar"):
                try:
                    from features.seguridad.seguridad_service import EventoAuditoria, Rol
                    rol_actor = Rol.ANFITRION if hasattr(Rol, "ANFITRION") else "anfitrion"
                    self._seguridad.auditar(
                        EventoAuditoria(
                            actor_token=anfitrion_id,
                            rol=rol_actor,
                            accion="reportar_resultado",
                            herramienta="reportar_resultado_estadia",
                            propiedad_id=sol.propiedad_id,
                            resultado="denegado_aislamiento_anfitrion",
                        )
                    )
                except Exception:
                    pass
            raise ErrorAnfitriones(
                "ACCESO_DENEGADO",
                "No tienes autorización para reportar resultado sobre solicitudes de otro anfitrión.",
            )

        if sol.estado != EstadoSolicitud.CONFIRMADA:
            raise ErrorAnfitriones(
                "ESTADO_INVALIDO",
                f"Solo se puede reportar resultado sobre estadías confirmadas (estado actual: {sol.estado.value}).",
            )

        dias_reporte = int(self._config.get("reporte_estadia_dias", 3))
        fecha_eval = ahora_fecha or datetime.now(timezone.utc).date()
        fecha_limite = sol.hasta + timedelta(days=dias_reporte)

        if resultado_enum in (EstadoSolicitud.CANCELADA, EstadoSolicitud.NO_SHOW):
            if fecha_eval > fecha_limite:
                raise ErrorAnfitriones(
                    "PLAZO_VENCIDO",
                    f"El plazo de {dias_reporte} días posteriores a la salida para reportar {resultado_enum.value} ha vencido.",
                )

        self._persistencia.actualizar_estado_solicitud(sol.solicitud, resultado_enum)

        if hasattr(self._seguridad, "auditar"):
            try:
                from features.seguridad.seguridad_service import EventoAuditoria, Rol
                rol_actor = Rol.ANFITRION if hasattr(Rol, "ANFITRION") else "anfitrion"
                self._seguridad.auditar(
                    EventoAuditoria(
                        actor_token=anfitrion_id,
                        rol=rol_actor,
                        accion=f"resultado_{resultado_enum.value}",
                        herramienta="reportar_resultado_estadia",
                        propiedad_id=sol.propiedad_id,
                        resultado="ok",
                    )
                )
            except Exception:
                pass

        return self._persistencia.obtener_solicitud(sol.solicitud)

    def expirar_solicitudes_vencidas(self, ahora: datetime | None = None) -> tuple[Solicitud, ...]:
        """Transiciona a expirada las solicitudes sin respuesta al vencer."""
        if ahora is None:
            ahora = datetime.now(timezone.utc)
        expirables = self._persistencia.listar_solicitudes_expirables(ahora)
        actualizadas: list[Solicitud] = []
        for sol in expirables:
            self._persistencia.actualizar_estado_solicitud(sol.solicitud, EstadoSolicitud.EXPIRADA)
            actualizada = self._persistencia.obtener_solicitud(sol.solicitud)
            if actualizada:
                actualizadas.append(actualizada)
        return tuple(actualizadas)

    def procesar_estadias_completadas(self, ahora_fecha: date | None = None) -> tuple[Solicitud, ...]:
        """Sin reporte la estadía se completa tras vencer el plazo de reporte (RF-ANF-06 a)."""
        dias_reporte = int(self._config.get("reporte_estadia_dias", 3))
        if ahora_fecha is None:
            ahora_fecha = datetime.now(timezone.utc).date()
        fecha_limite = ahora_fecha - timedelta(days=dias_reporte + 1)
        a_completar = self._persistencia.listar_estadias_a_completar(fecha_limite)
        completadas: list[Solicitud] = []
        for sol in a_completar:
            self._persistencia.actualizar_estado_solicitud(sol.solicitud, EstadoSolicitud.COMPLETADA)
            actualizada = self._persistencia.obtener_solicitud(sol.solicitud)
            if actualizada:
                completadas.append(actualizada)
        return tuple(completadas)
