# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Contratos de la compuerta de inferencia (ADR-0021): bloqueantes 3 a 6, falla cerrada y tope concurrente.

El cliente de ``google-genai`` se sustituye por un doble con la misma forma (``models.generate_content``);
el contrato mira lo que la compuerta le envía, sin importar el SDK.
"""
from __future__ import annotations

import ast
import json
import threading
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from features.inferencia.inferencia_service import InferenciaService
from features.inferencia.tipos import (
    EsquemaHerramienta,
    InferenciaNoDisponible,
    MensajeNeutro,
    PeticionInferencia,
    ResultadoNeutro,
    TiempoAgotado,
)

RAIZ = Path(__file__).resolve().parents[2]
ENTORNO = {"GOOGLE_CLOUD_PROJECT": "proyecto-de-prueba", "VERTEX_LOCATION": "us"}
HERRAMIENTA = EsquemaHerramienta("consultar_disponibilidad", "Disponibilidad", {"type": "object", "properties": {}})


# ¤inferencia
def _campo(objeto: Any, nombre: str) -> Any:
    return objeto.get(nombre) if isinstance(objeto, dict) else getattr(objeto, nombre, None)


# ¤inferencia
def _parte(texto: str | None = None, llamada: tuple[str, str, dict] | None = None, firma: bytes | None = None) -> Any:
    funcion = SimpleNamespace(id=llamada[0], name=llamada[1], args=llamada[2]) if llamada else None
    return SimpleNamespace(text=texto, function_call=funcion, thought_signature=firma)


# ¤inferencia
def _respuesta(*partes: Any) -> Any:
    candidato = SimpleNamespace(content=SimpleNamespace(role="model", parts=list(partes)), finish_reason="STOP")
    uso = SimpleNamespace(prompt_token_count=10, candidates_token_count=5, thoughts_token_count=0)
    return SimpleNamespace(candidates=[candidato], usage_metadata=uso, text=None)


# ¤inferencia
class DobleGenai:
    """Mismo contrato que ``genai.Client``: registra cada llamada y honra ``http_options.timeout`` (ms)."""

    def __init__(self, *respuestas: Any, demora_s: float = 0.0) -> None:
        self._respuestas = list(respuestas)
        self.demora_s = demora_s
        self.llamadas: list[dict[str, Any]] = []
        self.models = SimpleNamespace(generate_content=self._generar)

    def _generar(self, *, model: str, contents: Any, config: Any = None) -> Any:
        self.llamadas.append({"model": model, "contents": list(contents), "config": config})
        opciones = _campo(config, "http_options")
        limite_ms = _campo(opciones, "timeout") if opciones is not None else None
        if limite_ms is not None and self.demora_s * 1000 > limite_ms:
            time.sleep(limite_ms / 1000)
            raise TimeoutError("deadline exceeded")
        time.sleep(self.demora_s)
        return self._respuestas.pop(0) if self._respuestas else _respuesta(_parte(texto="ok"))


# ¤inferencia
def _peticion(*mensajes: MensajeNeutro, modelo: str = "gemini-3.8-flash", plazo_s: float = 10.0) -> PeticionInferencia:
    return PeticionInferencia(
        system="Eres el asistente.", mensajes=mensajes or (MensajeNeutro("usuario", "hola"),),
        modelo=modelo, plazo_s=plazo_s, herramientas=(HERRAMIENTA,),
    )


# ¤inferencia
def test_b3_el_plazo_corta_la_llamada() -> None:
    """Bloqueante 3: el timeout por llamada viaja en http_options y la llamada se corta dentro del plazo."""
    doble = DobleGenai(demora_s=3.0)
    servicio = InferenciaService(ENTORNO, cliente=doble)
    inicio = time.monotonic()
    with pytest.raises(TiempoAgotado):
        servicio.generar(_peticion(plazo_s=0.3))
    assert time.monotonic() - inicio < 1.5
    assert 0 < _campo(_campo(doble.llamadas[0]["config"], "http_options"), "timeout") <= 300


# ¤inferencia
def test_b4_function_call_y_thought_signature_sobreviven_al_turno() -> None:
    """Bloqueante 4: el contexto opaco y serializable reinyecta function_call y thought_signature intactos."""
    doble = DobleGenai(_respuesta(_parte(llamada=("c1", "consultar_disponibilidad", {"fecha": "2026-12-01"}), firma=b"sig")))
    servicio = InferenciaService(ENTORNO, cliente=doble)
    primera = servicio.generar(_peticion())
    assert [(l.id, l.nombre) for l in primera.llamadas] == [("c1", "consultar_disponibilidad")]
    json.dumps(primera.contexto_turno)  # serializable

    servicio.generar(_peticion(
        MensajeNeutro("usuario", "hola"),
        MensajeNeutro("modelo", contexto_turno=primera.contexto_turno),
        MensajeNeutro("resultados", resultados=(ResultadoNeutro("c1", "consultar_disponibilidad", {"libre": True}),)),
    ))
    turno_modelo = doble.llamadas[1]["contents"][1]
    assert _campo(turno_modelo, "role") == "model"
    parte = _campo(turno_modelo, "parts")[0]
    assert _campo(_campo(parte, "function_call"), "name") == "consultar_disponibilidad"
    assert _campo(parte, "thought_signature") == b"sig"


# ¤inferencia
def test_b5_resultados_en_un_solo_turno_user_en_orden_y_con_id() -> None:
    """Bloqueante 5: sin rol 'tool'; las function_response de una iteración van en un único turno user."""
    doble = DobleGenai()
    servicio = InferenciaService(ENTORNO, cliente=doble)
    servicio.generar(_peticion(
        MensajeNeutro("usuario", "hola"),
        MensajeNeutro("resultados", resultados=(
            ResultadoNeutro("c1", "consultar_disponibilidad", {"libre": True}),
            ResultadoNeutro("c2", "consultar_tarifa", {"usd": 90}),
        )),
    ))
    contenidos = doble.llamadas[0]["contents"]
    assert all(_campo(c, "role") in {"user", "model"} for c in contenidos)
    ultimo = contenidos[-1]
    assert _campo(ultimo, "role") == "user"
    respuestas = [_campo(p, "function_response") for p in _campo(ultimo, "parts")]
    assert [(_campo(r, "id"), _campo(r, "name")) for r in respuestas] == [
        ("c1", "consultar_disponibilidad"), ("c2", "consultar_tarifa"),
    ]


# ¤inferencia
def test_b6_el_modelo_enrutado_llega_al_proveedor() -> None:
    """Bloqueante 6: el modelo pedido es el que recibe Vertex."""
    doble = DobleGenai()
    InferenciaService(ENTORNO, cliente=doble).generar(_peticion(modelo="gemini-3.5-flash-lite"))
    assert doble.llamadas[0]["model"] == "gemini-3.5-flash-lite"


# ¤inferencia
@pytest.mark.parametrize(
    ("entorno", "modelo"),
    [
        ({}, "gemini-3.8-flash"),
        ({"GOOGLE_CLOUD_PROJECT": "p"}, "gemini-3.8-flash"),
        ({"GOOGLE_CLOUD_PROJECT": "p", "VERTEX_LOCATION": "us-central1"}, "gemini-3.8-flash"),
        ({"GOOGLE_CLOUD_PROJECT": "p", "VERTEX_LOCATION": "global"}, "gemini-3.8-flash"),
        (ENTORNO, "gemini-1.5-flash"),
        ({**ENTORNO, "GEMINI_API_KEY": "x"}, "gemini-3.8-flash"),
    ],
)
def test_falla_cerrada_sin_llamar_al_proveedor(entorno: dict[str, str], modelo: str) -> None:
    """INV_MODELO_FALLA_CERRADA e INV_MODELO_EN_LISTA_BLANCA: config incompleta, región fuera del mapa o modelo ajeno."""
    doble = DobleGenai()
    servicio = InferenciaService(entorno, cliente=doble)
    with pytest.raises(InferenciaNoDisponible):
        servicio.generar(_peticion(modelo=modelo))
    assert doble.llamadas == []


# ¤inferencia
def test_estado_informa_pais_y_region_para_el_aviso_lopdp() -> None:
    estado = InferenciaService(ENTORNO, cliente=DobleGenai()).estado()
    assert estado.disponible is True
    assert estado.region == "us"
    assert InferenciaService({}, cliente=DobleGenai()).estado().disponible is False


# ¤inferencia
def test_tope_diario_concurrente_solo_pasa_una() -> None:
    """Tope diario único: dos llamadas concurrentes en el límite, solo una llega al proveedor."""

    class CuotaAtomica:
        def __init__(self, tope: Decimal) -> None:
            self.restante, self._candado = tope, threading.Lock()

        def reservar(self, costo: Decimal) -> bool:
            with self._candado:
                if costo > self.restante:
                    return False
                self.restante -= costo
                return True

    doble = DobleGenai(demora_s=0.2)
    servicio = InferenciaService(ENTORNO, cliente=doble, cuota=CuotaAtomica(Decimal("0.0001")))
    errores: list[BaseException] = []

    def llamar() -> None:
        try:
            servicio.generar(_peticion())
        except InferenciaNoDisponible as exc:
            errores.append(exc)

    hilos = [threading.Thread(target=llamar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(doble.llamadas) == 1
    assert len(errores) == 1


# ¤inferencia
def test_seguridad_no_importa_inferencia() -> None:
    """ADR-0021, Decisión 12: app_core pasa país y región; seguridad no conoce a inferencia."""
    infractores = []
    for ruta in sorted((RAIZ / "features" / "seguridad").rglob("*.py")):
        for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
            modulos = [a.name for a in nodo.names] if isinstance(nodo, ast.Import) else (
                [nodo.module or ""] if isinstance(nodo, ast.ImportFrom) else []
            )
            if any(m.startswith("features.inferencia") for m in modulos):
                infractores.append(str(ruta.relative_to(RAIZ)))
    assert infractores == []
