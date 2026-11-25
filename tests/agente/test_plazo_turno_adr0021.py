# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Paso 4 del ADR-0021, lado agente: C1 (un solo plazo por turno) y m3 (MAX_TOKENS queda registrado)."""
from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from features.agente.bucle_herramientas_internal import BucleHerramientas
from features.agente.cliente_modelo_internal import ClienteModelo, DobleClienteModelo
from features.agente.tipos import DefinicionHerramienta, LlamadaHerramienta, ResultadoHerramienta, RespuestaModelo
from features.inferencia.tipos import RespuestaNoUtilizable

HERRAMIENTA = DefinicionHerramienta(
    nombre="buscar_politica", descripcion="Política", esquema_entrada={"type": "object"},
    esquema_salida={"type": "object"}, roles=("huesped_potencial",), sala_destino="conocimiento",
)


# ¤inferencia
class _Obs:
    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **campos})

    def span(self, *a: Any, **k: Any) -> Any:
        return nullcontext()


# ¤inferencia
class _Herramientas:
    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> ResultadoHerramienta:
        return ResultadoHerramienta(nombre=nombre, salida={"ok": True})


# ¤inferencia
class _DobleConPlazo(DobleClienteModelo):
    def __init__(self, *respuestas: Any) -> None:
        super().__init__(list(respuestas))
        self.plazos: list[float | None] = []

    def generar(self, mensajes, system_prompt, herramientas=(), modelo=None, plazo_s=None):  # type: ignore[override]
        self.plazos.append(plazo_s)
        return super().generar(mensajes, system_prompt, herramientas, modelo, plazo_s)


# ¤inferencia
def _reloj(*instantes: float):
    valores = list(instantes)

    def leer() -> float:
        return valores.pop(0) if len(valores) > 1 else valores[0]

    return leer


# ¤inferencia
def _con_herramienta(i: int) -> RespuestaModelo:
    return RespuestaModelo(texto="", llamadas_herramientas=(LlamadaHerramienta(id=f"l{i}", nombre="buscar_politica", argumentos={}),))


# ¤inferencia
def _ejecutar(bucle: BucleHerramientas) -> Any:
    return bucle.ejecutar(
        system_prompt="s", mensajes_historial=[], mensaje_actual_token="hola", identidad=None,
        conversacion_id="c1", propiedad_id="glamping", herramientas_disponibles=(HERRAMIENTA,), traza_id="t1",
    )


# ¤inferencia
def test_c1_el_plazo_es_del_turno_y_no_de_cada_vuelta() -> None:
    """C1: 45 s valen para todo el turno; cada vuelta recibe solo lo que queda."""
    modelo = _DobleConPlazo(_con_herramienta(1), _con_herramienta(2), RespuestaModelo(texto="listo"))
    bucle = BucleHerramientas(
        {"timeout_modelo_s": 45, "tope_iteraciones": 6}, modelo, _Herramientas(), _Obs(), reloj=_reloj(0, 0, 20, 50),
    )
    respuesta = _ejecutar(bucle)
    assert modelo.plazos == [45, 25]
    assert respuesta.degradada


# ¤inferencia
def test_c1_el_adaptador_no_repone_el_plazo() -> None:
    """C1: sin plazo explícito el adaptador no inventa 45 s nuevos; el plazo viene del bucle."""
    vistos: list[float] = []

    class _Inferencia:
        def generar(self, peticion: Any) -> Any:
            vistos.append(peticion.plazo_s)
            raise RespuestaNoUtilizable("max_tokens")

    cliente = ClienteModelo({"timeout_modelo_s": 45}, inferencia=_Inferencia())
    try:
        cliente.generar([{"role": "user", "content": "hola"}], system_prompt="s", plazo_s=12.5)
    except Exception:
        pass
    assert vistos == [12.5]


# ¤inferencia
def test_m3_max_tokens_queda_registrado_en_el_log() -> None:
    """m3: un corte por largo se degrada y deja el motivo concreto en observabilidad."""

    class _Inferencia:
        def generar(self, peticion: Any) -> Any:
            raise RespuestaNoUtilizable("max_tokens")

    obs = _Obs()
    cliente = ClienteModelo({"timeout_modelo_s": 45}, inferencia=_Inferencia())
    bucle = BucleHerramientas({"timeout_modelo_s": 45}, cliente, _Herramientas(), obs)
    respuesta = _ejecutar(bucle)
    assert respuesta.degradada
    registro = [l for l in obs.logs if l["evento"] == "modelo_no_disponible"]
    assert registro and "max_tokens" in registro[0]["motivo"]
    assert registro[0].get("tipo_error") == "RespuestaNoUtilizable"
