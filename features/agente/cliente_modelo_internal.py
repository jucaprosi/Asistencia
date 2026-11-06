# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Cliente de modelo con timeout configurable, conteo de tokens y estimación de costos (RF-AG-05)."""
from __future__ import annotations

import concurrent.futures
import json
import os
import time
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from features.agente.tipos import (
    DefinicionHerramienta,
    LlamadaHerramienta,
    ModeloNoDisponible,
    RespuestaModelo,
    TimeoutModelo,
)

__all__ = ["ClienteModelo", "DobleClienteModelo", "estimar_tokens"]


# ¤agente-enrutador
def _resolver_valor_config(valor: Any, defecto: str = "") -> str:
    if not isinstance(valor, str):
        return defecto
    if valor.startswith("${") and ":-" in valor and valor.endswith("}"):
        var_name, default_val = valor[2:-1].split(":-", 1)
        return os.environ.get(var_name, default_val)
    return valor

# Costos por 1M tokens en USD (entrada, salida). Gemini: tarifa estándar de pago de
# ai.google.dev/gemini-api/docs/pricing (consulta 2026-11-04); para gemini-3.8-flash se usa la
# tarifa vigente desde 2027-01-01, más alta que la promocional, para no subestimar RNF-16.
PRECIOS_POR_MILLON = {
    "gemini-3.8-flash": (Decimal("1.50"), Decimal("7.50")),
    "gemini-3.5-flash-lite": (Decimal("0.30"), Decimal("2.50")),
    "claude-opus-5-5": (Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-5-5": (Decimal("0.80"), Decimal("4.00")),
}
PRECIO_DEFECTO = (Decimal("3.00"), Decimal("15.00"))


# ¤agente-enrutador
def estimar_tokens(texto: str) -> int:
    """Estimación heurística de tokens (~4 caracteres por token, mínimo 1 si hay texto)."""
    if not texto:
        return 0
    return max(1, (len(texto) + 3) // 4)


# ¤agente-enrutador
class ClienteModelo:
    """Cliente para interactuar con el modelo de lenguaje con timeout y telemetría de tokens."""

    def __init__(
        self,
        config: Mapping[str, Any],
        observabilidad: Any = None,
        llamador: Callable[..., RespuestaModelo] | None = None,
    ) -> None:
        self._config = config
        self._observabilidad = observabilidad
        self._timeout_s = float(config.get("timeout_modelo_s", 30))
        self._modelo = _resolver_valor_config(config.get("modelos", {}).get("principal"), "claude-opus-5-5")
        self._llamador = llamador

    # ¤agente-enrutador
    def calcular_costo(self, tokens_in: int, tokens_out: int, modelo: str) -> Decimal:
        precio_in, precio_out = PRECIOS_POR_MILLON.get(modelo, PRECIO_DEFECTO)
        costo_in = (Decimal(tokens_in) / Decimal("1000000")) * precio_in
        costo_out = (Decimal(tokens_out) / Decimal("1000000")) * precio_out
        return (costo_in + costo_out).quantize(Decimal("0.000001"))

    # ¤agente-enrutador
    def generar(
        self,
        mensajes: Sequence[Mapping[str, Any]],
        system_prompt: str,
        herramientas: Sequence[DefinicionHerramienta] = (),
        modelo: str | None = None,
    ) -> RespuestaModelo:
        """Invoca al modelo asegurando timeout de 30s y telemetría de tokens."""
        modelo_activo = modelo or self._modelo
        tokens_in = estimar_tokens(system_prompt)
        for m in mensajes:
            tokens_in += estimar_tokens(str(m.get("content", "")))
        for h in herramientas:
            tokens_in += estimar_tokens(h.nombre + h.descripcion + json.dumps(dict(h.esquema_entrada)))

        def _invocacion() -> RespuestaModelo:
            if self._llamador is not None:
                return self._llamador(mensajes, system_prompt, herramientas)
            # Simulación por defecto si no hay backend activo en Clean-Room
            texto_default = "Entendido, soy el asistente virtual del glamping. ¿En qué puedo ayudarte?"
            return RespuestaModelo(
                texto=texto_default,
                llamadas_herramientas=(),
                tokens_in=tokens_in,
                tokens_out=estimar_tokens(texto_default),
                costo_usd=self.calcular_costo(tokens_in, estimar_tokens(texto_default), modelo_activo),
                modelo=modelo_activo,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            futuro = executor.submit(_invocacion)
            try:
                respuesta = futuro.result(timeout=self._timeout_s)
                # Asegurar tokens y costo si el llamador no los calculó
                t_in = respuesta.tokens_in or tokens_in
                t_out = respuesta.tokens_out or estimar_tokens(respuesta.texto)
                mod_resp = respuesta.modelo or modelo_activo
                costo = respuesta.costo_usd or self.calcular_costo(t_in, t_out, mod_resp)
                return RespuestaModelo(
                    texto=respuesta.texto,
                    llamadas_herramientas=respuesta.llamadas_herramientas,
                    tokens_in=t_in,
                    tokens_out=t_out,
                    costo_usd=costo,
                    modelo=mod_resp,
                )
            except concurrent.futures.TimeoutError as exc:
                raise TimeoutModelo(self._timeout_s, detalle_tecnico=f"Llamada al modelo superó {self._timeout_s}s") from exc
            except TimeoutModelo:
                raise
            except Exception as exc:
                raise ModeloNoDisponible(detalle_tecnico=str(exc)) from exc


# ¤agente-enrutador
class DobleClienteModelo(ClienteModelo):
    """Doble de pruebas programable para simular respuestas, herramientas, caídas y timeouts."""

    def __init__(
        self,
        respuestas_programadas: Sequence[RespuestaModelo | Exception] | None = None,
        timeout_s: float = 30.0,
        modelo: str = "claude-opus-5-5",
    ) -> None:
        super().__init__(config={"timeout_modelo_s": timeout_s, "modelos": {"principal": modelo}})
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
            t_in = estimar_tokens(system_prompt)
            t_out = estimar_tokens(texto)
            return RespuestaModelo(
                texto=texto,
                llamadas_herramientas=(),
                tokens_in=t_in,
                tokens_out=t_out,
                costo_usd=self.calcular_costo(t_in, t_out, modelo_activo),
                modelo=modelo_activo,
            )
        siguiente = self._cola.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente
