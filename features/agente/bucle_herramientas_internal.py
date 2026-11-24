# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Orquestación del bucle de tool use, control de iteraciones y degradación (RF-AG-04, RF-AG-05)."""
from __future__ import annotations

import json
import threading
import time
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from features.agente.cliente_modelo_internal import ClienteModelo
from features.agente.tipos import (
    DefinicionHerramienta,
    HerramientaFallida,
    PropiedadRequeridaNoResuelta,
    Respuesta,
    RespuestaModelo,
    TimeoutModelo,
    TopeIteraciones,
)

__all__ = ["BucleHerramientas", "HERRAMIENTAS_CON_PROPIEDAD_OBLIGATORIA"]

HERRAMIENTAS_CON_PROPIEDAD_OBLIGATORIA = {
    "consultar_disponibilidad",
    "cotizar",
    "crear_reserva_preliminar",
    "reportar_incidencia",
}


# ¤agente-enrutador
class BucleHerramientas:
    """Ejecuta el ciclo de llamadas al modelo y ejecución de herramientas con tope y degradación."""

    def __init__(
        self,
        config: Mapping[str, Any],
        cliente_modelo: ClienteModelo,
        herramientas_service: Any,
        observabilidad: Any,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._config = config
        self._reloj = reloj
        # ADR-0021, C1: un solo presupuesto de tiempo para todo el turno, no uno por vuelta.
        self._plazo_turno_s = float(config.get("timeout_modelo_s", 45))
        self._cliente_modelo = cliente_modelo
        self._herramientas_service = herramientas_service
        self._observabilidad = observabilidad
        self._tope_iteraciones = int(config.get("tope_iteraciones", 6))
        self._acuse_si_tarda_s = float(config.get("acuse_si_tarda_s", 3.0))

    # ¤agente-enrutador
    def ejecutar(
        self,
        system_prompt: str,
        mensajes_historial: Sequence[Mapping[str, str]],
        mensaje_actual_token: str,
        identidad: Any,
        conversacion_id: str,
        propiedad_id: str | None,
        herramientas_disponibles: Sequence[DefinicionHerramienta],
        traza_id: str,
        modelo: str | None = None,
        canal: Any = None,
    ) -> Respuesta:
        """Bucle de tool use con control de iteraciones, invariantes e informe honesto de caídas."""
        mensajes: list[dict[str, Any]] = [
            {"role": m["role"], "content": m["content"]} for m in mensajes_historial
        ]
        mensajes.append({"role": "user", "content": mensaje_actual_token})

        iteracion = 0
        herramientas_usadas: list[str] = []
        total_tokens_in = 0
        total_tokens_out = 0
        costo_total = Decimal("0")
        ultimo_modelo = modelo or ""
        hubo_acuse = [False]
        fin_turno = self._reloj() + self._plazo_turno_s

        while iteracion < self._tope_iteraciones:
            iteracion += 1

            # Invocación al modelo de lenguaje con lo que queda del plazo del turno
            try:
                restante = fin_turno - self._reloj()
                if restante <= 0:
                    raise TimeoutModelo(self._plazo_turno_s, detalle_tecnico="plazo_del_turno_agotado")
                resp_modelo = self._cliente_modelo.generar(
                    mensajes=mensajes,
                    system_prompt=system_prompt,
                    herramientas=herramientas_disponibles,
                    modelo=modelo,
                    plazo_s=restante,
                )
            except TimeoutModelo as exc:
                self._observabilidad.log(
                    "ERROR",
                    "modelo_timeout",
                    motivo=f"Timeout de modelo: {exc}",
                    traza_id=traza_id,
                    conversacion_id=conversacion_id,
                )
                return self._generar_degradacion(
                    motivo="timeout_modelo",
                    detalle="El modelo superó el tiempo máximo de respuesta.",
                    propiedad_id=propiedad_id,
                    herramientas_usadas=herramientas_usadas,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    costo=costo_total,
                    modelo=ultimo_modelo,
                    acuse_emitido=hubo_acuse[0],
                )
            except Exception as exc:
                causa = exc.__cause__ or exc
                self._observabilidad.log(
                    "ERROR",
                    "modelo_no_disponible",
                    motivo=getattr(exc, "detalle_tecnico", None) or str(exc),
                    tipo_error=type(causa).__name__,
                    traza_id=traza_id,
                    conversacion_id=conversacion_id,
                )
                return self._generar_degradacion(
                    motivo="modelo_no_disponible",
                    detalle=str(exc),
                    propiedad_id=propiedad_id,
                    herramientas_usadas=herramientas_usadas,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    costo=costo_total,
                    modelo=ultimo_modelo,
                    acuse_emitido=hubo_acuse[0],
                )

            total_tokens_in += resp_modelo.tokens_in
            total_tokens_out += resp_modelo.tokens_out
            costo_total += resp_modelo.costo_usd
            ultimo_modelo = resp_modelo.modelo

            # Si el modelo no solicitó herramientas, culmina exitosamente
            if not resp_modelo.llamadas_herramientas:
                return Respuesta(
                    texto=resp_modelo.texto,
                    herramientas_usadas=tuple(herramientas_usadas),
                    modelo=ultimo_modelo,
                    tokens_in=total_tokens_in,
                    tokens_out=total_tokens_out,
                    costo_usd=costo_total,
                    degradada=False,
                    acuse_emitido=hubo_acuse[0],
                )

            # Agregar respuesta del asistente a la conversación antes de los resultados de herramientas
            mensajes.append({
                "role": "assistant", "content": resp_modelo.texto, "contexto_turno": resp_modelo.contexto_turno,
            })

            # Ejecución de herramientas invocadas
            for llamada in resp_modelo.llamadas_herramientas:
                nombre_h = llamada.nombre
                args_h = dict(llamada.argumentos)
                herramientas_usadas.append(nombre_h)

                # INV_PROPIEDAD_RESUELTA: requerida por contrato de la herramienta
                requiere_propiedad = (
                    nombre_h in HERRAMIENTAS_CON_PROPIEDAD_OBLIGATORIA
                    or "propiedad_id" in args_h
                )
                if requiere_propiedad and not propiedad_id:
                    self._observabilidad.log(
                        "ERROR",
                        "inv_propiedad_resuelta_violada",
                        herramienta=nombre_h,
                        motivo="Invocación de herramienta sin propiedad resuelta",
                        traza_id=traza_id,
                    )
                    raise PropiedadRequeridaNoResuelta(nombre_h)

                if propiedad_id and "propiedad_id" not in args_h:
                    args_h["propiedad_id"] = propiedad_id

                # Configurar acuse «un momento…» si tarda más de 3s (T-403)
                timer_disparado = [False]

                def _emitir_acuse_espera() -> None:
                    if timer_disparado[0]:
                        return
                    timer_disparado[0] = True
                    hubo_acuse[0] = True
                    self._observabilidad.log(
                        "INFO",
                        "acuse_espera_herramienta",
                        herramienta=nombre_h,
                        conversacion_id=conversacion_id,
                        traza_id=traza_id,
                        mensaje="Un momento, por favor. Estamos procesando tu consulta...",
                    )
                    if canal is not None and hasattr(canal, "enviar_texto"):
                        try:
                            remitente = getattr(identidad, "remitente_token", "") if identidad else ""
                            canal.enviar_texto(
                                destinatario=remitente or conversacion_id,
                                texto="Un momento, por favor. Estamos procesando tu consulta...",
                            )
                        except Exception:
                            pass

                timer_acuse = threading.Timer(self._acuse_si_tarda_s, _emitir_acuse_espera)
                timer_acuse.daemon = True
                timer_acuse.start()
                t_inicio = time.monotonic()

                # Ejecutar compuerta de herramientas
                try:
                    resultado_h = self._herramientas_service.ejecutar(
                        nombre_h,
                        args_h,
                        identidad,
                        conversacion_id,
                    )
                except Exception as exc:
                    self._observabilidad.log(
                        "ERROR",
                        "excepcion_herramienta",
                        herramienta=nombre_h,
                        error=str(exc),
                        traza_id=traza_id,
                    )
                    return self._generar_degradacion(
                        motivo="herramienta_caida",
                        detalle=f"Fallo crítico al invocar {nombre_h}: {exc}",
                        propiedad_id=propiedad_id,
                        herramientas_usadas=herramientas_usadas,
                        tokens_in=total_tokens_in,
                        tokens_out=total_tokens_out,
                        costo=costo_total,
                        modelo=ultimo_modelo,
                        acuse_emitido=hubo_acuse[0],
                    )
                finally:
                    t_fin = time.monotonic()
                    timer_acuse.cancel()
                    duracion_s = t_fin - t_inicio
                    # Si tardó más de acuse_si_tarda_s o si el resultado reporta >= 3000ms
                    duracion_ms = getattr(resultado_h, "duracion_ms", 0) if "resultado_h" in locals() and resultado_h else 0
                    if (duracion_s >= self._acuse_si_tarda_s or duracion_ms >= 3000) and not timer_disparado[0]:
                        _emitir_acuse_espera()

                # Si la herramienta reportó error (ej. PMS caído o RAG inaccesible)
                if resultado_h.error:
                    self._observabilidad.log(
                        "WARNING",
                        "herramienta_fallida",
                        herramienta=nombre_h,
                        motivo=resultado_h.error,
                        traza_id=traza_id,
                    )
                    # "un fallo de herramienta no inventa resultado y ofrece pasar con una persona"
                    return self._generar_degradacion(
                        motivo="herramienta_fallida",
                        detalle=resultado_h.error,
                        propiedad_id=propiedad_id,
                        herramientas_usadas=herramientas_usadas,
                        tokens_in=total_tokens_in,
                        tokens_out=total_tokens_out,
                        costo=costo_total,
                        modelo=ultimo_modelo,
                        acuse_emitido=hubo_acuse[0],
                    )

                # Inyectar resultado de herramienta al historial para la siguiente iteración
                mensajes.append({
                    "role": "tool",
                    "id": llamada.id,
                    "name": nombre_h,
                    "content": json.dumps(dict(resultado_h.salida)),
                })

        # Superó el tope de 6 iteraciones
        self._observabilidad.log(
            "ERROR",
            "limite_iteraciones",
            motivo="limite_iteraciones",
            traza_id=traza_id,
            conversacion_id=conversacion_id,
        )
        return self._generar_degradacion(
            motivo="limite_iteraciones",
            detalle="El bucle de herramientas superó el tope de iteraciones permitidas.",
            propiedad_id=propiedad_id,
            herramientas_usadas=herramientas_usadas,
            tokens_in=total_tokens_in,
            tokens_out=total_tokens_out,
            costo=costo_total,
            modelo=ultimo_modelo,
            acuse_emitido=hubo_acuse[0],
        )

    # ¤agente-enrutador
    def _generar_degradacion(
        self,
        motivo: str,
        detalle: str,
        propiedad_id: str | None,
        herramientas_usadas: list[str],
        tokens_in: int,
        tokens_out: int,
        costo: Decimal,
        modelo: str,
        acuse_emitido: bool = False,
    ) -> Respuesta:
        """Entrega el contacto humano configurado y registra motivo en traza (RF-AG-05, RF-MCP-06)."""
        propiedades = self._config.get("propiedades", {})
        prop_cfg = propiedades.get(propiedad_id or "glamping", {})
        contacto = prop_cfg.get("contacto_humano") or self._config.get("escalamiento", {}).get("contacto_humano_defecto", "+593991234567")
        gestor = prop_cfg.get("nombre_gestor") or self._config.get("escalamiento", {}).get("nombre_gestor_defecto", "Gestor de Servicio")

        if motivo == "limite_iteraciones":
            texto = (
                f"Hemos detectado dificultad procesando tu consulta tras varios intentos automáticos. "
                f"Para brindarte atención inmediata sin errores, te comunicamos con nuestro gestor humano: {gestor} al {contacto}."
            )
        elif motivo in ("herramienta_fallida", "herramienta_caida"):
            texto = (
                f"En este momento el servicio del sistema presenta una intermitencia y no puedo consultar la información en tiempo real. "
                f"No quiero entregarte datos incorrectos o desactualizados. Te ofrezco comunicarte directamente con {gestor} al {contacto} para ayudarte con gusto."
            )
        else:
            texto = (
                f"Nuestro asistente está experimentando lentitud o dificultades temporales de conexión. "
                f"Para garantizar una respuesta oportuna, por favor comunícate con {gestor} al {contacto}."
            )

        return Respuesta(
            texto=texto,
            herramientas_usadas=tuple(herramientas_usadas),
            modelo=modelo,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            costo_usd=costo,
            degradada=True,
            acuse_emitido=acuse_emitido,
        )
