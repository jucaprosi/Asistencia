# ¤canal-whatsapp
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Trabajador asíncrono de ingesta durable, recuperación de caídas, orden y agrupación (RF-GW-07, RF-GW-08)."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from features.canal_whatsapp.persistencia_internal import RepositorioCanal
from features.canal_whatsapp.tipos import Canal, MensajeEntrante
from features.canal_whatsapp.webhook_internal import convertir_mensaje_meta, parsear_payload_webhook

Receptor = Callable[[MensajeEntrante], Any]


# ¤canal-whatsapp
class TrabajadorIngesta:
    """Procesa eventos entrantes fuera del webhook, serializa por remitente y recupera caídas."""

    def __init__(
        self,
        repositorio: RepositorioCanal,
        observabilidad: Any = None,
        max_reintentos: int = 5,
        agrupacion_segundos: int = 3,
        clasificador_canal: Callable[[str, str | None], Canal] | None = None,
        enrutador: Any = None,
    ) -> None:
        self.repositorio = repositorio
        self.observabilidad = observabilidad
        self.max_reintentos = max_reintentos
        self.agrupacion_segundos = agrupacion_segundos
        self.clasificador_canal = clasificador_canal
        self.enrutador = enrutador
        self._locks_remitente: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def _obtener_lock_remitente(self, conversacion_clave: str) -> threading.Lock:
        with self._global_lock:
            if conversacion_clave not in self._locks_remitente:
                self._locks_remitente[conversacion_clave] = threading.Lock()
            return self._locks_remitente[conversacion_clave]

    def recuperar_caidas(self) -> int:
        """RF-GW-07: Recupera eventos en 'procesando' tras caída.

        Incrementa intentos. Si supera max_reintentos pasa a 'muerto' y dispara alerta.
        """
        eventos_caidos = self.repositorio.obtener_eventos_procesando()
        recuperados = 0
        for ev in eventos_caidos:
            nuevos_intentos = ev.intentos + 1
            if nuevos_intentos >= self.max_reintentos:
                self.repositorio.actualizar_estado_evento(ev.evento_id, "muerto", intentos=nuevos_intentos)
                if self.observabilidad:
                    if hasattr(self.observabilidad, "log"):
                        self.observabilidad.log(
                            "CRITICAL",
                            "EVENTO_MUERTO",
                            evento_id=ev.evento_id,
                            mensaje_id=ev.mensaje_id,
                            intentos=nuevos_intentos,
                        )
                    if hasattr(self.observabilidad, "disparar_alerta"):
                        self.observabilidad.disparar_alerta(
                            "EVENTO_MUERTO",
                            "critica",
                            f"Evento {ev.evento_id} superó {self.max_reintentos} intentos y pasó a muerto",
                        )
            else:
                self.repositorio.actualizar_estado_evento(ev.evento_id, "pendiente", intentos=nuevos_intentos)
                recuperados += 1
        return recuperados

    def procesar_pendientes(self, receptores: Mapping[Canal, Receptor]) -> int:
        """RF-GW-08: Procesa mensajes pendientes en orden y agrupa los que caen en ventana de 3 s."""
        pendientes = self.repositorio.obtener_eventos_pendientes()
        if not pendientes:
            return 0

        por_remitente: dict[str, list[Any]] = {}
        for ev in pendientes:
            por_remitente.setdefault(ev.conversacion_clave, []).append(ev)

        procesados_total = 0
        for clave, eventos_clave in por_remitente.items():
            lock = self._obtener_lock_remitente(clave)
            if not lock.acquire(blocking=False):
                continue

            try:
                eventos_clave.sort(key=lambda x: x.recibido_en)
                turnos = self._agrupar_en_turnos(eventos_clave)
                for lote in turnos:
                    for ev in lote:
                        self.repositorio.actualizar_estado_evento(ev.evento_id, "procesando")

                    mensajes_convertidos: list[MensajeEntrante] = []
                    for ev in lote:
                        raw_msgs, _ = parsear_payload_webhook(ev.cuerpo_cifrado)
                        for rm in raw_msgs:
                            if rm.get("id") and rm.get("id") != ev.mensaje_id:
                                continue
                            remitente = rm.get("from", "")
                            grupo_id = rm.get("group_id") or rm.get("chat_id") or rm.get("grupo_id")
                            if self.clasificador_canal:
                                canal = self.clasificador_canal(remitente, grupo_id)
                            else:
                                canal = Canal.HUESPEDES
                            mensajes_convertidos.append(convertir_mensaje_meta(rm, canal))

                    if not mensajes_convertidos:
                        for ev in lote:
                            self.repositorio.actualizar_estado_evento(
                                ev.evento_id, "procesado", procesado_en=datetime.now(timezone.utc)
                            )
                        continue

                    if len(mensajes_convertidos) > 1:
                        primer = mensajes_convertidos[0]
                        textos = [m.texto for m in mensajes_convertidos if m.texto]
                        mensaje_turno = MensajeEntrante(
                            mensaje_id=primer.mensaje_id,
                            remitente=primer.remitente,
                            canal=primer.canal,
                            tipo=primer.tipo,
                            texto="\n".join(textos) if textos else None,
                            medio_ref=primer.medio_ref,
                            ubicacion=primer.ubicacion,
                            recibido_en=primer.recibido_en,
                            contexto_respuesta_a=primer.contexto_respuesta_a,
                            mensajes_agrupados=tuple(mensajes_convertidos),
                        )
                    else:
                        mensaje_turno = mensajes_convertidos[0]

                    if self.enrutador and hasattr(self.enrutador, "despachar"):
                        self.enrutador.despachar(mensaje_turno, receptores)
                    else:
                        canal_destino = mensaje_turno.canal
                        receptor = receptores.get(canal_destino)
                        if receptor:
                            receptor(mensaje_turno)

                    for ev in lote:
                        self.repositorio.actualizar_estado_evento(
                            ev.evento_id, "procesado", procesado_en=datetime.now(timezone.utc)
                        )
                    procesados_total += len(lote)
            finally:
                lock.release()

        return procesados_total

    def _agrupar_en_turnos(self, eventos: list[Any]) -> list[list[Any]]:
        """Agrupa eventos que llegaron con menos de agrupacion_segundos de diferencia respecto al primer mensaje."""
        if not eventos:
            return []
        turnos: list[list[Any]] = []
        lote_actual: list[Any] = [eventos[0]]

        for ev in eventos[1:]:
            delta = (ev.recibido_en - lote_actual[0].recibido_en).total_seconds()
            if delta <= self.agrupacion_segundos:
                lote_actual.append(ev)
            else:
                turnos.append(lote_actual)
                lote_actual = [ev]

        if lote_actual:
            turnos.append(lote_actual)
        return turnos
