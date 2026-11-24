# ¤inferencia
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta de la sala inferencia (ADR-0021): Gemini en Vertex AI, multirregión ``us``, falla cerrada.

Contrato:
- ``InferenciaService(entorno, cliente=None, cuota=None, config=None)``: ``entorno`` trae
  ``GOOGLE_CLOUD_PROJECT`` y ``VERTEX_LOCATION`` sin valores por defecto. En producción ``app_core`` inyecta
  ``os.environ``; el valor vacío por defecto es solo para pruebas. Aunque el entorno inyectado venga limpio,
  ``GOOGLE_API_KEY`` o ``GEMINI_API_KEY`` presentes en ``os.environ`` (que ``google-genai`` lee por su
  cuenta) hacen fallar cerrado. ``config`` sustituye a ``config_inferencia.yaml`` en pruebas;
  ``cliente`` sustituye al de ``google-genai`` en pruebas;
  ``cuota.reservar(costo_estimado) -> bool`` es el tope diario atómico que lleva observabilidad.
- ``generar(peticion) -> RespuestaInferencia``; falla cerrada con ``InferenciaNoDisponible``.
- ``estado() -> EstadoInferencia``.

``MODELOS_PERMITIDOS`` es la lista blanca en código; ``config_inferencia.yaml`` solo selecciona dentro de ella.
Ningún tipo de ``google-genai`` sale de esta compuerta: se le envían dicts y se devuelven tipos propios.
"""
from __future__ import annotations

import base64
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.inferencia.tipos import (
    EsquemaHerramienta,
    EstadoInferencia,
    InferenciaNoDisponible,
    LlamadaNeutra,
    MensajeNeutro,
    PeticionInferencia,
    RespuestaInferencia,
    RespuestaNoUtilizable,
    ResultadoNeutro,
    TiempoAgotado,
    UsoTokens,
)

__all__ = [
    "MODELOS_PERMITIDOS",
    "EsquemaHerramienta",
    "EstadoInferencia",
    "InferenciaNoDisponible",
    "InferenciaService",
    "LlamadaNeutra",
    "MensajeNeutro",
    "PeticionInferencia",
    "RespuestaInferencia",
    "RespuestaNoUtilizable",
    "ResultadoNeutro",
    "TiempoAgotado",
    "UsoTokens",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_inferencia.yaml")
MODELOS_PERMITIDOS = frozenset({"gemini-3.8-flash", "gemini-3.5-flash-lite"})
PERFILES = ("principal", "economico")
CLAVES_PROHIBIDAS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
_FINALES_UTILIZABLES = {"STOP", "FINISH_REASON_UNSPECIFIED", ""}


# ¤inferencia
def cargar_config(ruta: Path = RUTA_CONFIG) -> dict[str, Any]:
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


# ¤inferencia
def _campo(objeto: Any, nombre: str, defecto: Any = None) -> Any:
    if objeto is None:
        return defecto
    if isinstance(objeto, Mapping):
        return objeto.get(nombre, defecto)
    return getattr(objeto, nombre, defecto)


# ¤inferencia
def _validar_config(config: Mapping[str, Any]) -> str | None:
    modelos = config.get("modelos_permitidos") or {}
    if set(modelos) != set(PERFILES):
        return "configuracion_invalida"
    if not set(modelos.values()) <= MODELOS_PERMITIDOS:
        return "modelo_fuera_de_lista_blanca"
    precios = config.get("precios_por_millon") or {}
    if not set(modelos.values()) <= set(precios):
        return "configuracion_invalida"
    return None


# ¤inferencia
class InferenciaService:
    def __init__(
        self,
        entorno: Mapping[str, str] | None = None,
        cliente: Any = None,
        cuota: Any = None,
        config: Mapping[str, Any] | None = None,
    ) -> None:
        self._entorno = dict(entorno or {})
        self._cliente = cliente
        self._cuota = cuota
        self._config = dict(config) if config is not None else cargar_config()
        # Validación al construir: un yaml inválido deja la sala no disponible desde el arranque.
        self._error_config = _validar_config(self._config)

    # ¤inferencia
    def inyectar_cliente_de_prueba(self, cliente: Any) -> None:
        self._cliente = cliente

    # ¤inferencia
    def _motivo_no_disponible(self) -> str | None:
        if self._error_config:
            return self._error_config
        if any(self._entorno.get(c) or os.environ.get(c) for c in CLAVES_PROHIBIDAS):
            return "clave_api_presente"
        if not self._entorno.get("GOOGLE_CLOUD_PROJECT"):
            return "proyecto_no_configurado"
        if self._entorno.get("VERTEX_LOCATION") not in (self._config.get("ubicaciones") or {}):
            return "region_no_permitida"
        return None

    # ¤inferencia
    def estado(self) -> EstadoInferencia:
        motivo = self._motivo_no_disponible()
        region = self._entorno.get("VERTEX_LOCATION", "")
        ubicacion = (self._config.get("ubicaciones") or {}).get(region) or {}
        return EstadoInferencia(
            disponible=motivo is None,
            motivo=motivo or "",
            region=region,
            ubicacion=str(ubicacion.get("endpoint", "")),
            pais=str(ubicacion.get("pais", "")),
        )

    # ¤inferencia
    def _modelo_de(self, perfil: str) -> str:
        modelo = (self._config.get("modelos_permitidos") or {}).get(perfil)
        if perfil not in PERFILES or modelo not in MODELOS_PERMITIDOS:
            raise InferenciaNoDisponible("perfil_no_permitido")
        return str(modelo)

    # ¤inferencia
    def _costo(self, modelo: str, entrada: int, salida: int) -> Decimal:
        precio_in, precio_out = (Decimal(str(p)) for p in self._config["precios_por_millon"][modelo])
        millon = Decimal("1000000")
        return ((Decimal(entrada) / millon) * precio_in + (Decimal(salida) / millon) * precio_out).quantize(
            Decimal("0.000001")
        )

    # ¤inferencia
    def _cliente_real(self) -> Any:
        if self._cliente is None:
            from google import genai  # import perezoso: el SDK solo vive en esta sala

            region = self._entorno["VERTEX_LOCATION"]
            endpoint = self._config["ubicaciones"][region]["endpoint"]
            self._cliente = genai.Client(
                vertexai=True,
                project=self._entorno["GOOGLE_CLOUD_PROJECT"],
                location=region,
                http_options={"base_url": f"https://{endpoint}/"},
            )
        return self._cliente

    # ¤inferencia
    def generar(self, peticion: PeticionInferencia) -> RespuestaInferencia:
        motivo = self._motivo_no_disponible()
        if motivo:
            raise InferenciaNoDisponible(motivo)
        modelo = self._modelo_de(peticion.perfil)
        if peticion.plazo_s <= 0:
            raise TiempoAgotado("plazo_agotado")
        contenidos = [_contenido(m) for m in peticion.mensajes]
        # La cuota se consulta después de la falla cerrada y antes del proveedor: una petición inválida no gasta.
        if self._cuota is not None:
            estimado = self._costo(modelo, _estimar_tokens(peticion), 0)
            if not self._cuota.reservar(estimado):
                raise InferenciaNoDisponible("tope_diario_alcanzado")
        configuracion = {
            "system_instruction": peticion.system,
            "automatic_function_calling": {"disable": True},
            "http_options": {"timeout": max(1, int(peticion.plazo_s * 1000))},
        }
        if peticion.herramientas:
            configuracion["tools"] = [{"function_declarations": [
                {"name": h.nombre, "description": h.descripcion, "parameters_json_schema": dict(h.esquema_json)}
                for h in peticion.herramientas
            ]}]
        try:
            respuesta = self._cliente_real().models.generate_content(
                model=modelo, contents=contenidos, config=configuracion
            )
        except Exception as exc:  # el SDK y httpx tienen varias jerarquías de timeout
            if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower() or "deadline" in str(exc).lower():
                raise TiempoAgotado("tiempo_agotado") from exc
            raise InferenciaNoDisponible("proveedor_no_disponible") from exc
        return _a_respuesta(respuesta, modelo, self._costo)


# ¤inferencia
def _estimar_tokens(peticion: PeticionInferencia) -> int:
    caracteres = len(peticion.system) + sum(len(m.texto) for m in peticion.mensajes)
    return max(1, caracteres // 4)


# ¤inferencia
def _contenido(mensaje: MensajeNeutro) -> dict[str, Any]:
    if mensaje.rol == "resultados":
        return {"role": "user", "parts": [
            {"function_response": {"id": r.id, "name": r.nombre, "response": dict(r.contenido)}}
            for r in mensaje.resultados
        ]}
    if mensaje.rol == "modelo":
        partes = [_parte_desde_contexto(p) for p in (mensaje.contexto_turno or {}).get("partes", [])]
        return {"role": "model", "parts": partes or [{"text": mensaje.texto}]}
    return {"role": "user", "parts": [{"text": mensaje.texto}]}


# ¤inferencia
def _parte_desde_contexto(parte: Mapping[str, Any]) -> dict[str, Any]:
    salida: dict[str, Any] = {}
    if parte.get("texto") is not None:
        salida["text"] = parte["texto"]
    if parte.get("llamada"):
        llamada = parte["llamada"]
        salida["function_call"] = {"id": llamada["id"], "name": llamada["nombre"], "args": llamada["argumentos"]}
    if parte.get("firma"):
        salida["thought_signature"] = base64.b64decode(parte["firma"])
    return salida


# ¤inferencia
def _a_respuesta(respuesta: Any, modelo: str, costo: Any) -> RespuestaInferencia:
    candidatos = _campo(respuesta, "candidates") or []
    if not candidatos:
        raise RespuestaNoUtilizable("respuesta_vacia")
    candidato = candidatos[0]
    final = _campo(candidato, "finish_reason")
    final = str(getattr(final, "name", final) or "")
    if final not in _FINALES_UTILIZABLES:
        raise RespuestaNoUtilizable(final.lower())
    textos: list[str] = []
    llamadas: list[LlamadaNeutra] = []
    partes_contexto: list[dict[str, Any]] = []
    for indice, parte in enumerate(_campo(_campo(candidato, "content"), "parts") or []):
        entrada: dict[str, Any] = {}
        texto = _campo(parte, "text")
        if texto:
            textos.append(texto)
            entrada["texto"] = texto
        funcion = _campo(parte, "function_call")
        if funcion is not None:
            llamada = LlamadaNeutra(
                id=str(_campo(funcion, "id") or f"llamada-{indice}"),
                nombre=str(_campo(funcion, "name")),
                argumentos=dict(_campo(funcion, "args") or {}),
            )
            llamadas.append(llamada)
            entrada["llamada"] = {"id": llamada.id, "nombre": llamada.nombre, "argumentos": dict(llamada.argumentos)}
        firma = _campo(parte, "thought_signature")
        if firma:
            entrada["firma"] = base64.b64encode(firma).decode("ascii")
        if entrada:
            partes_contexto.append(entrada)
    if not textos and not llamadas:
        raise RespuestaNoUtilizable("respuesta_vacia")
    uso = _campo(respuesta, "usage_metadata")
    entrada_tokens = int(_campo(uso, "prompt_token_count") or 0)
    salida_tokens = int(_campo(uso, "candidates_token_count") or 0) + int(_campo(uso, "thoughts_token_count") or 0)
    return RespuestaInferencia(
        texto="".join(textos),
        llamadas=tuple(llamadas),
        uso=UsoTokens(entrada_tokens, salida_tokens, costo(modelo, entrada_tokens, salida_tokens)),
        modelo=modelo,
        contexto_turno={"partes": partes_contexto},
    )
