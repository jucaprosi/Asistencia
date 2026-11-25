# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Adaptador del turno al modelo (RF-AG-05, ADR-0021).

El transporte, la lista blanca, la región, los precios y el tope diario son de la sala ``inferencia``.
Aquí solo se traduce el historial neutro del bucle a la petición de la compuerta, se pasa el plazo y se
mapean errores. Sin compuerta inyectada no hay respuesta (falla cerrada): ``app_core`` es quien la inyecta.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from features.agente.tipos import (
    DefinicionHerramienta,
    LlamadaHerramienta,
    ModeloNoDisponible,
    RespuestaModelo,
    TimeoutModelo,
)
from features.inferencia.inferencia_service import (
    EsquemaHerramienta,
    InferenciaNoDisponible,
    MensajeNeutro,
    PeticionInferencia,
    ResultadoNeutro,
    TiempoAgotado,
)

__all__ = ["ClienteModelo", "DobleClienteModelo", "estimar_tokens"]

PERFIL_DEFECTO = "principal"


# ¤agente-enrutador
def estimar_tokens(texto: str) -> int:
    """Estimación heurística de tokens (~4 caracteres por token, mínimo 1 si hay texto)."""
    if not texto:
        return 0
    return max(1, (len(texto) + 3) // 4)


# ¤agente-enrutador
def _a_neutros(mensajes: Sequence[Mapping[str, Any]]) -> tuple[MensajeNeutro, ...]:
    """Historial del bucle → turnos neutros; los resultados de herramientas consecutivos van juntos."""
    neutros: list[MensajeNeutro] = []
    pendientes: list[ResultadoNeutro] = []

    def volcar() -> None:
        if pendientes:
            neutros.append(MensajeNeutro("resultados", resultados=tuple(pendientes)))
            pendientes.clear()

    for m in mensajes:
        rol = m.get("role")
        if rol == "tool":
            try:
                contenido = json.loads(m.get("content") or "{}")
            except (TypeError, ValueError):
                contenido = {"resultado": m.get("content")}
            if not isinstance(contenido, dict):
                contenido = {"resultado": contenido}
            pendientes.append(ResultadoNeutro(str(m.get("id", "")), str(m.get("name", "")), contenido))
            continue
        volcar()
        if rol == "assistant":
            neutros.append(MensajeNeutro("modelo", str(m.get("content", "")), contexto_turno=m.get("contexto_turno")))
        else:
            neutros.append(MensajeNeutro("usuario", str(m.get("content", ""))))
    volcar()
    return tuple(neutros)


# ¤agente-enrutador
class ClienteModelo:
    """Adaptador de un turno: presupuesto de tiempo y mapeo a ``RespuestaModelo``."""

    def __init__(self, config: Mapping[str, Any], observabilidad: Any = None, inferencia: Any = None) -> None:
        self._observabilidad = observabilidad
        self._timeout_s = float(config.get("timeout_modelo_s", 45))
        self._inferencia = inferencia

    # ¤agente-enrutador
    def generar(
        self,
        mensajes: Sequence[Mapping[str, Any]],
        system_prompt: str,
        herramientas: Sequence[DefinicionHerramienta] = (),
        modelo: str | None = None,
        plazo_s: float | None = None,
    ) -> RespuestaModelo:
        """``modelo`` es el perfil enrutado (``principal`` o ``economico``), nunca un nombre de modelo."""
        if self._inferencia is None:
            raise ModeloNoDisponible(detalle_tecnico="sin compuerta de inferencia inyectada")
        peticion = PeticionInferencia(
            system=system_prompt,
            mensajes=_a_neutros(mensajes),
            perfil=modelo or PERFIL_DEFECTO,  # type: ignore[arg-type]
            plazo_s=self._timeout_s if plazo_s is None else plazo_s,
            herramientas=tuple(
                EsquemaHerramienta(h.nombre, h.descripcion, dict(h.esquema_entrada)) for h in herramientas
            ),
        )
        try:
            respuesta = self._inferencia.generar(peticion)
        except TiempoAgotado as exc:
            raise TimeoutModelo(peticion.plazo_s, detalle_tecnico=str(exc)) from exc
        except InferenciaNoDisponible as exc:
            raise ModeloNoDisponible(detalle_tecnico=str(exc)) from exc
        return RespuestaModelo(
            texto=respuesta.texto,
            llamadas_herramientas=tuple(
                LlamadaHerramienta(id=l.id, nombre=l.nombre, argumentos=dict(l.argumentos)) for l in respuesta.llamadas
            ),
            tokens_in=respuesta.uso.entrada,
            tokens_out=respuesta.uso.salida,
            costo_usd=respuesta.uso.costo_usd,
            modelo=respuesta.modelo,
            contexto_turno=dict(respuesta.contexto_turno),
        )


# ¤agente-enrutador
class DobleClienteModelo(ClienteModelo):
    """Doble de pruebas programable para simular respuestas, herramientas, caídas y timeouts."""

    def __init__(
        self,
        respuestas_programadas: Sequence[RespuestaModelo | Exception] | None = None,
        timeout_s: float = 45.0,
        modelo: str = PERFIL_DEFECTO,
    ) -> None:
        super().__init__(config={"timeout_modelo_s": timeout_s})
        self._modelo = modelo
        self._cola: list[RespuestaModelo | Exception] = list(respuestas_programadas or [])
        self.llamadas: list[dict[str, Any]] = []

    @property
    def llamadas_generar(self) -> list[dict[str, Any]]:
        return self.llamadas

    # ¤agente-enrutador
    def programar(self, *respuestas: RespuestaModelo | Exception) -> None:
        self._cola.extend(respuestas)

    # ¤agente-enrutador
    def generar(
        self,
        mensajes: Sequence[Mapping[str, Any]],
        system_prompt: str,
        herramientas: Sequence[DefinicionHerramienta] = (),
        modelo: str | None = None,
        plazo_s: float | None = None,
    ) -> RespuestaModelo:
        modelo_activo = modelo or self._modelo
        self.llamadas.append({
            "mensajes": list(mensajes),
            "system_prompt": system_prompt,
            "herramientas": tuple(herramientas),
            "modelo": modelo_activo,
        })
        if not self._cola:
            texto = "Respuesta por defecto del doble de pruebas."
            return RespuestaModelo(
                texto=texto,
                tokens_in=estimar_tokens(system_prompt),
                tokens_out=estimar_tokens(texto),
                modelo=modelo_activo,
            )
        siguiente = self._cola.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente
