# ¤inferencia
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-409 (ADR-0021, Enmienda 2): espera del único reintento ante 429 y 5xx.

Base de 1,0 s con jitter de 0,5x a 1,5x, ``Retry-After`` hacia arriba, tope de ``espera_maxima_s`` y reintento
solo si tras esperar queda al menos la base para la segunda llamada.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from features.inferencia import inferencia_service as modulo
from features.inferencia.inferencia_service import InferenciaService, cargar_config
from features.inferencia.tipos import InferenciaNoDisponible, MensajeNeutro, PeticionInferencia
from tests.inferencia.test_paso4_adr0021 import ENTORNO, ErrorProveedor, Guion, _respuesta

CONFIG_FIJA = dict(cargar_config(), espera_reintento_s=1.0, espera_maxima_s=5.0)


@pytest.fixture(autouse=True)
def _entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    for clave in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(clave, raising=False)


class Cabeceras:
    """Mapeo sin distinguir mayúsculas, como las cabeceras HTTP del SDK."""

    def __init__(self, **valores: str) -> None:
        self._v = {k.lower().replace("_", "-"): v for k, v in valores.items()}

    def get(self, clave: str, defecto: Any = None) -> Any:
        return self._v.get(clave.lower(), defecto)


def _error(codigo: int, retry_after: str | None = None) -> ErrorProveedor:
    exc = ErrorProveedor(codigo)
    if retry_after is not None:
        exc.response = SimpleNamespace(headers=Cabeceras(retry_after=retry_after))  # type: ignore[attr-defined]
    return exc


def _peticion(plazo_s: float = 10.0) -> PeticionInferencia:
    return PeticionInferencia(
        system="s" * 40, mensajes=(MensajeNeutro("usuario", "h" * 40),), perfil="principal", plazo_s=plazo_s
    )


def _simular(monkeypatch: pytest.MonkeyPatch, error: BaseException, *, plazo_s: float = 10.0, config: Any = None,
             aleatorio: float = 1.0) -> tuple[list[float], Guion, Any]:
    """Ejecuta ``generar`` con un error seguido de una respuesta; devuelve esperas, guion y resultado o excepción."""
    esperas: list[float] = []
    monkeypatch.setattr(modulo.time, "sleep", esperas.append)
    monkeypatch.setattr(modulo.random, "uniform", lambda minimo, maximo: aleatorio)
    guion = Guion(error, _respuesta(texto="segunda"))
    servicio = InferenciaService(ENTORNO, cliente=guion, config=CONFIG_FIJA if config is None else config)
    try:
        resultado: Any = servicio.generar(_peticion(plazo_s))
    except InferenciaNoDisponible as exc:
        resultado = exc
    return esperas, guion, resultado


def _funcion(nombre: str) -> Any:
    funcion = getattr(modulo, nombre, None)
    assert funcion is not None, f"T-409: falta {nombre} en inferencia_service"
    return funcion


# ¤inferencia
def test_r1_base_un_segundo_con_jitter(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas, guion, resultado = _simular(monkeypatch, _error(429), config=cargar_config())
    assert esperas == [1.0]
    assert len(guion.llamadas) == 2 and getattr(resultado, "texto", None) == "segunda"


# ¤inferencia
def test_r1_jitter_entre_medio_y_uno_y_medio() -> None:
    espera = _funcion("_espera_reintento")
    assert espera(_error(429), 1.0, aleatorio=lambda minimo, maximo: minimo) == 0.5
    assert espera(_error(429), 1.0, aleatorio=lambda minimo, maximo: maximo) == 1.5


# ¤inferencia
def test_r2_retry_after_manda_hacia_arriba(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas, guion, _ = _simular(monkeypatch, _error(429, "3"))
    assert esperas == [3.0]
    assert len(guion.llamadas) == 2


# ¤inferencia
def test_r2_retry_after_menor_que_la_base(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas, _, _ = _simular(monkeypatch, _error(429, "0"), aleatorio=0.7)
    assert esperas == [0.7]


# ¤inferencia
@pytest.mark.parametrize("valor", ["Wed, 21 Oct 2026 07:28:00 GMT", "pronto", "-5"])
def test_r2_retry_after_ilegible_se_ignora(monkeypatch: pytest.MonkeyPatch, valor: str) -> None:
    assert _funcion("_retry_after_s")(_error(429, valor)) is None
    esperas, _, _ = _simular(monkeypatch, _error(429, valor))
    assert esperas == [1.0]


# ¤inferencia
def test_r3_tope_de_cinco_segundos(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas, guion, resultado = _simular(monkeypatch, _error(429, "30"), plazo_s=60.0)
    assert esperas == []
    assert len(guion.llamadas) == 1
    assert isinstance(resultado, InferenciaNoDisponible)


# ¤inferencia
def test_r4_solo_si_queda_plazo_para_la_segunda_llamada(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas, guion, resultado = _simular(monkeypatch, _error(429), plazo_s=1.2)
    assert esperas == []
    assert len(guion.llamadas) == 1
    assert isinstance(resultado, InferenciaNoDisponible)


# ¤inferencia
def test_r2_vale_tambien_para_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas, _, _ = _simular(monkeypatch, _error(503, "2"))
    assert esperas == [2.0]


# ¤inferencia
def test_r6_config_invalida() -> None:
    for maxima in (1.0, 0.5):
        config = dict(CONFIG_FIJA, espera_maxima_s=maxima)
        estado = InferenciaService(ENTORNO, cliente=Guion(), config=config).estado()
        assert estado.disponible is False, f"espera_maxima_s={maxima} debe invalidar la config"
