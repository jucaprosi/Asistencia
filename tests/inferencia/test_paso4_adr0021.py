# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Paso 4 del ADR-0021, lado inferencia: C1 (reintento único), C2 (sin tope no hay servicio), C3 (reserva y
conciliación), C4 (SDK declarado y detectado), D6-D9 y menores m1-m2."""
from __future__ import annotations

import re
import tomllib
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from features.inferencia import inferencia_service as modulo
from features.inferencia.inferencia_service import InferenciaService
from features.inferencia.tipos import (
    InferenciaNoDisponible,
    MensajeNeutro,
    PeticionInferencia,
    RespuestaNoUtilizable,
    TiempoAgotado,
)

RAIZ = Path(__file__).resolve().parents[2]
ENTORNO = {"GOOGLE_CLOUD_PROJECT": "proyecto-de-prueba", "VERTEX_LOCATION": "us"}


@pytest.fixture(autouse=True)
def _sin_claves(monkeypatch: pytest.MonkeyPatch) -> None:
    for clave in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(clave, raising=False)


# ¤inferencia
class ErrorProveedor(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"error {code}")
        self.code = code


# ¤inferencia
def _respuesta(final: str = "STOP", texto: str | None = "ok", entrada: int = 10, salida: int = 5, pensamiento: int = 0) -> Any:
    parte = SimpleNamespace(text=texto, function_call=None, thought_signature=None)
    candidato = SimpleNamespace(content=SimpleNamespace(role="model", parts=[parte] if texto else []), finish_reason=final)
    uso = SimpleNamespace(prompt_token_count=entrada, candidates_token_count=salida, thoughts_token_count=pensamiento)
    return SimpleNamespace(candidates=[candidato], usage_metadata=uso)


# ¤inferencia
class Guion:
    """Doble de ``genai.Client``: cada llamada consume el siguiente elemento (respuesta o excepción)."""

    def __init__(self, *pasos: Any) -> None:
        self.pasos = list(pasos)
        self.llamadas: list[dict[str, Any]] = []
        self.models = SimpleNamespace(generate_content=self._generar)

    def _generar(self, *, model: str, contents: Any, config: Any = None) -> Any:
        self.llamadas.append({"model": model, "config": config})
        paso = self.pasos.pop(0) if self.pasos else _respuesta()
        if isinstance(paso, BaseException):
            raise paso
        return paso


# ¤inferencia
class Cuota:
    def __init__(self, permitir: bool = True) -> None:
        self.permitir = permitir
        self.reservas: list[Decimal] = []
        self.conciliaciones: list[tuple[Decimal, Decimal]] = []

    def reservar(self, costo: Decimal) -> bool:
        self.reservas.append(costo)
        return self.permitir

    def conciliar(self, reservado: Decimal, real: Decimal) -> None:
        self.conciliaciones.append((reservado, real))


# ¤inferencia
def _peticion(plazo_s: float = 10.0) -> PeticionInferencia:
    return PeticionInferencia(system="s" * 40, mensajes=(MensajeNeutro("usuario", "h" * 40),), perfil="principal", plazo_s=plazo_s)


# ¤inferencia
@pytest.mark.parametrize("codigo", [500, 503, 429])
def test_c1_d6_un_reintento_ante_5xx_o_429(codigo: int) -> None:
    guion = Guion(ErrorProveedor(codigo), _respuesta(texto="segunda"))
    cuota = Cuota()
    respuesta = InferenciaService(ENTORNO, cliente=guion, cuota=cuota).generar(_peticion())
    assert respuesta.texto == "segunda"
    assert len(guion.llamadas) == 2
    assert len(cuota.reservas) == 2, "D9: el reintento también reserva cuota"


# ¤inferencia
@pytest.mark.parametrize("codigo", [400, 403, 404])
def test_c1_d6_ningun_reintento_ante_4xx(codigo: int) -> None:
    guion = Guion(ErrorProveedor(codigo), _respuesta())
    with pytest.raises(InferenciaNoDisponible):
        InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())
    assert len(guion.llamadas) == 1


# ¤inferencia
def test_c1_solo_un_reintento() -> None:
    guion = Guion(ErrorProveedor(503), ErrorProveedor(503), _respuesta())
    with pytest.raises(InferenciaNoDisponible):
        InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())
    assert len(guion.llamadas) == 2


# ¤inferencia
def test_c1_el_reintento_usa_el_mismo_plazo() -> None:
    """El reintento no repone el plazo: su timeout es menor o igual que el de la primera llamada."""
    guion = Guion(ErrorProveedor(503), _respuesta())
    InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion(plazo_s=5.0))
    primero, segundo = (l["config"]["http_options"]["timeout"] for l in guion.llamadas)
    assert segundo <= primero <= 5000


# ¤inferencia
def test_c2_sin_cuota_la_sala_no_esta_disponible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo, "_sdk_instalado", lambda: True, raising=False)
    servicio = InferenciaService(ENTORNO)
    assert servicio.estado().disponible is False
    assert servicio.estado().motivo == "sin_tope_diario"
    with pytest.raises(InferenciaNoDisponible, match="sin_tope_diario"):
        servicio.generar(_peticion())


# ¤inferencia
def test_c3_reserva_entrada_mas_salida_maxima_y_concilia_con_el_real() -> None:
    cuota = Cuota()
    servicio = InferenciaService(ENTORNO, cliente=Guion(_respuesta(entrada=10, salida=5)), cuota=cuota)
    servicio.generar(_peticion())
    maximo = int(modulo.cargar_config()["max_output_tokens"])
    entrada_estimada = (40 + 40) // 4
    assert cuota.reservas == [servicio._costo("gemini-3.8-flash", entrada_estimada, maximo)]
    assert cuota.conciliaciones == [(cuota.reservas[0], servicio._costo("gemini-3.8-flash", 10, 5))]


# ¤inferencia
def test_c3_max_output_tokens_viaja_al_proveedor() -> None:
    guion = Guion(_respuesta())
    InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())
    assert guion.llamadas[0]["config"]["max_output_tokens"] == int(modulo.cargar_config()["max_output_tokens"])


# ¤inferencia
def test_c4_google_genai_declarado_y_fijado_con_hash() -> None:
    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    declaradas = proyecto["project"]["dependencies"]
    fijada = [d for d in declaradas if re.fullmatch(r"google-genai==\d+\.\d+\.\d+", d.replace(" ", ""))]
    assert fijada, "google-genai debe estar en dependencies con versión exacta"
    candado = (RAIZ / "requirements.lock").read_text(encoding="utf-8")
    assert re.search(rf"^{re.escape(fijada[0].replace(' ', ''))}\s*\\?\s*\n?\s*--hash=sha256:[0-9a-f]{{64}}", candado, re.M)


# ¤inferencia
def test_c4_sin_sdk_la_sala_lo_dice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo.importlib.util, "find_spec", lambda nombre, *a: None)
    estado = InferenciaService(ENTORNO, cuota=Cuota()).estado()
    assert (estado.disponible, estado.motivo) == (False, "sdk_no_instalado")


# ¤inferencia
def test_d7_afc_desactivado_y_system_instruction() -> None:
    guion = Guion(_respuesta())
    InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())
    config = guion.llamadas[0]["config"]
    assert config["automatic_function_calling"] == {"disable": True}
    assert config["system_instruction"] == "s" * 40


# ¤inferencia
@pytest.mark.parametrize("final", ["SAFETY", "MAX_TOKENS", "MALFORMED_FUNCTION_CALL"])
def test_d8_finales_no_utilizables_sin_texto_parcial(final: str) -> None:
    guion = Guion(_respuesta(final=final, texto="parcial"))
    with pytest.raises(RespuestaNoUtilizable, match=final.lower()):
        InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())


# ¤inferencia
def test_d9_costo_exacto_con_pensamiento_como_salida() -> None:
    guion = Guion(_respuesta(entrada=1_000_000, salida=500_000, pensamiento=500_000))
    respuesta = InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())
    assert respuesta.uso.salida == 1_000_000
    assert respuesta.uso.costo_usd == Decimal("9.000000")


# ¤inferencia
def test_m1_el_motivo_lleva_el_tipo_de_error() -> None:
    guion = Guion(ErrorProveedor(403))
    with pytest.raises(InferenciaNoDisponible, match="ErrorProveedor"):
        InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())


# ¤inferencia
def test_m2_el_tiempo_agotado_se_detecta_por_tipo_y_no_por_texto() -> None:
    guion = Guion(ValueError("deadline en el texto, pero no es un timeout"))
    with pytest.raises(InferenciaNoDisponible) as info:
        InferenciaService(ENTORNO, cliente=guion, cuota=Cuota()).generar(_peticion())
    assert not isinstance(info.value, TiempoAgotado)


# ¤inferencia
def test_m2_timeout_de_httpx_por_tipo() -> None:
    class TimeoutException(Exception):
        pass

    class ReadTimeout(TimeoutException):
        pass

    with pytest.raises(TiempoAgotado):
        InferenciaService(ENTORNO, cliente=Guion(ReadTimeout("x")), cuota=Cuota()).generar(_peticion())
