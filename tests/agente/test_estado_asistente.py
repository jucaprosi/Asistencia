# ¤agente-enrutador
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-417 (docs/spec/tareas/T-417.md): ``AgenteService.estado_asistente()``, el estado del asistente para el panel.

R1: disponible es lo que dice la inferencia inyectada. R2: el motivo es un código (``sin_inferencia``,
``estado_inferencia_ilegible`` o el de ``EstadoInferencia``). R3: ``desde`` marca el inicio de la indisponibilidad
y la transición a disponible es el único punto de reinicio. R4: ``derivadas`` cuenta las respuestas degradadas con
texto mientras el agente está indisponible; ``atender`` consulta la inferencia por sí mismo. R5: sin efectos.
R6: las firmas públicas solo crecen.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any

import pytest

from features.agente import agente_service as modulo
from features.agente import tipos
from features.agente.agente_service import AgenteService, cargar_config
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.memoria_internal import MemoriaConversacion
from features.agente.tipos import LlamadaHerramienta, ModeloNoDisponible, RespuestaModelo
from features.inferencia.inferencia_service import EstadoInferencia
from features.seguridad.seguridad_service import Identidad, MensajeLimpio, Rol
from tests.agente.test_degradacion import DobleHerramientas, DobleObservabilidad, DobleSeguridad

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 11, 25, 12, 5, tzinfo=timezone.utc)
T2 = datetime(2026, 11, 25, 13, 0, tzinfo=timezone.utc)
SIN_INFERENCIA = object()
ARGUMENTOS_INIT = (
    "self", "config", "seguridad", "herramientas", "conocimiento", "canal", "observabilidad", "pms", "memoria",
    "cliente_modelo", "inferencia",
)


# ¤agente-enrutador
class InferenciaFalsa:
    """Doble de la compuerta de inferencia: ``estado()`` configurable, o una excepción."""

    def __init__(self, disponible: bool = True, motivo: str = "", error: BaseException | None = None) -> None:
        self.disponible = disponible
        self.motivo = motivo
        self.error = error

    def estado(self) -> EstadoInferencia:
        if self.error is not None:
            raise self.error
        return EstadoInferencia(
            disponible=self.disponible,
            motivo="" if self.disponible else self.motivo,
            region="us",
            ubicacion="aiplatform.us.rep.googleapis.com",
            pais="Estados Unidos",
            con_tope_diario=True,
        )


# ¤agente-enrutador
class MemoriaEspia(MemoriaConversacion):
    """Memoria real que registra cada escritura (R5)."""

    def __init__(self) -> None:
        super().__init__()
        self.escrituras: list[str] = []

    def guardar_conversacion(self, *args: Any, **kwargs: Any) -> Any:
        self.escrituras.append("guardar_conversacion")
        return super().guardar_conversacion(*args, **kwargs)

    def actualizar_modo(self, *args: Any, **kwargs: Any) -> Any:
        self.escrituras.append("actualizar_modo")
        return super().actualizar_modo(*args, **kwargs)

    def actualizar_propiedad(self, *args: Any, **kwargs: Any) -> Any:
        self.escrituras.append("actualizar_propiedad")
        return super().actualizar_propiedad(*args, **kwargs)

    def guardar_mensaje(self, *args: Any, **kwargs: Any) -> Any:
        self.escrituras.append("guardar_mensaje")
        return super().guardar_mensaje(*args, **kwargs)

    def registrar_envio_programado(self, *args: Any, **kwargs: Any) -> Any:
        self.escrituras.append("registrar_envio_programado")
        return super().registrar_envio_programado(*args, **kwargs)


# ¤agente-enrutador
@pytest.fixture
def reloj(monkeypatch: pytest.MonkeyPatch) -> dict[str, datetime]:
    """Reemplaza ``agente_service._ahora`` (la ficha prohíbe cambiar ``__init__``)."""
    instante = {"t": T0}
    monkeypatch.setattr(modulo, "_ahora", lambda: instante["t"], raising=False)
    return instante


# ¤agente-enrutador
def _servicio(
    inferencia: Any = SIN_INFERENCIA,
    *pasos: Any,
    herramientas: Any = None,
    observabilidad: Any = None,
    memoria: Any = None,
) -> tuple[AgenteService, DobleClienteModelo]:
    modelo = DobleClienteModelo(list(pasos))
    argumentos: dict[str, Any] = {
        "seguridad": DobleSeguridad(),
        "herramientas": herramientas or DobleHerramientas(),
        "conocimiento": None,
        "canal": None,
        "observabilidad": observabilidad or DobleObservabilidad(),
        "memoria": memoria or MemoriaConversacion(),
        "cliente_modelo": modelo,
    }
    if inferencia is not SIN_INFERENCIA:
        argumentos["inferencia"] = inferencia
    return AgenteService(cargar_config(), **argumentos), modelo


# ¤agente-enrutador
def _estado(servicio: AgenteService) -> Any:
    clase = getattr(tipos, "EstadoAsistente", None)
    assert clase is not None, "T-417: falta EstadoAsistente en features/agente/tipos.py"
    metodo = getattr(servicio, "estado_asistente", None)
    assert metodo is not None, "T-417: falta AgenteService.estado_asistente"
    estado = metodo()
    assert isinstance(estado, clase)
    return estado


# ¤agente-enrutador
def _campos(estado: Any) -> tuple[Any, ...]:
    return (estado.disponible, estado.motivo, estado.desde, estado.derivadas)


# ¤agente-enrutador
def _atender(servicio: AgenteService, conversacion_id: str, texto: str = "Quiero reservar") -> Any:
    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token=f"tok_{conversacion_id}", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado=texto,
        marcas=(),
        conversacion_id=conversacion_id,
    )
    return servicio.atender(mensaje)


# ¤agente-enrutador
def _pide_herramienta(sufijo: str) -> RespuestaModelo:
    llamada = LlamadaHerramienta(id=f"call_{sufijo}", nombre="consultar_disponibilidad", argumentos={"desde": "2026-11-20"})
    return RespuestaModelo(texto="Revisando", llamadas_herramientas=(llamada,))


# ¤agente-enrutador
def _derivar(servicio: AgenteService, conversacion_id: str) -> None:
    """Un ``atender`` que degrada con texto y entrega el contacto humano (modelo caído o herramienta caída)."""
    respuesta = _atender(servicio, conversacion_id)
    assert respuesta.degradada is True and respuesta.texto, "premisa: la degradación entrega texto"


# ¤agente-enrutador
def test_r1_disponible_si_la_inferencia_lo_esta(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio(InferenciaFalsa(disponible=True))
    assert _campos(_estado(servicio)) == (True, "", None, 0)


# ¤agente-enrutador
def test_r2_motivo_de_la_inferencia(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio(InferenciaFalsa(disponible=False, motivo="sin_tope_diario"))
    estado = _estado(servicio)
    assert estado.disponible is False
    assert estado.motivo == "sin_tope_diario"


# ¤agente-enrutador
def test_r2_sin_inferencia(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio()
    estado = _estado(servicio)
    assert estado.disponible is False
    assert estado.motivo == "sin_inferencia"


# ¤agente-enrutador
def test_r2_estado_ilegible_no_propaga(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio(InferenciaFalsa(error=RuntimeError("estado roto")))
    estado = _estado(servicio)
    assert estado.disponible is False
    assert estado.motivo == "estado_inferencia_ilegible"


# ¤agente-enrutador
def test_r3_desde_no_se_mueve(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio(InferenciaFalsa(disponible=False, motivo="sin_tope_diario"))
    primero = _estado(servicio)
    reloj["t"] = T1
    segundo = _estado(servicio)
    assert primero.desde == T0
    assert segundo.desde == T0


# ¤agente-enrutador
def test_r3_se_reinicia_al_volver(reloj: dict[str, datetime]) -> None:
    """Las derivadas salen de una herramienta caída y no del modelo: en T-420 una falla del modelo abre una pausa
    que la configuración disponible no cierra, y este caso tiene que seguir siendo cierto después de T-420."""
    inferencia = InferenciaFalsa(disponible=False, motivo="sin_tope_diario")
    herramientas = DobleHerramientas()
    herramientas.error_programado = "PMSConectorTimeout: Conexión con PMS rechazada o caída"
    servicio, _ = _servicio(inferencia, _pide_herramienta("a6_1"), _pide_herramienta("a6_2"), herramientas=herramientas)
    _derivar(servicio, "conv_a6_1")
    _derivar(servicio, "conv_a6_2")
    assert _estado(servicio).derivadas == 2
    inferencia.disponible = True
    assert _campos(_estado(servicio)) == (True, "", None, 0)
    inferencia.disponible = False
    reloj["t"] = T2
    segunda = _estado(servicio)
    assert segunda.desde == T2
    assert segunda.derivadas == 0


# ¤agente-enrutador
def test_r4_cuenta_las_derivadas(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio(
        InferenciaFalsa(disponible=False, motivo="sin_tope_diario"),
        ModeloNoDisponible("caido"), ModeloNoDisponible("caido"), ModeloNoDisponible("caido"),
    )
    for numero in range(3):
        _derivar(servicio, f"conv_a7_{numero}")
    assert _estado(servicio).derivadas == 3


# ¤agente-enrutador
def test_r4_el_silencio_no_cuenta(reloj: dict[str, datetime]) -> None:
    servicio, _ = _servicio(InferenciaFalsa(disponible=False, motivo="sin_tope_diario"), ModeloNoDisponible("caido"))
    _derivar(servicio, "conv_a8")
    servicio.entrar_en_silencio("conv_a8", "handoff")
    antes = _estado(servicio).derivadas
    respuesta = _atender(servicio, "conv_a8")
    assert respuesta.degradada is True and respuesta.texto == "", "premisa: el silencio devuelve texto vacío"
    assert _estado(servicio).derivadas == antes


# ¤agente-enrutador
def test_r4_disponible_no_cuenta(reloj: dict[str, datetime]) -> None:
    """La degradación es de herramienta, no del modelo: sigue siendo cierto después de T-420."""
    inferencia = InferenciaFalsa(disponible=True)
    herramientas = DobleHerramientas()
    herramientas.error_programado = "PMSConectorTimeout: Conexión con PMS rechazada o caída"
    servicio, _ = _servicio(inferencia, _pide_herramienta("a9"), herramientas=herramientas)
    respuesta = _atender(servicio, "conv_a9")
    assert respuesta.degradada is True and respuesta.texto, "premisa: la herramienta caída degrada con texto"
    # Se mide al abrir la ventana siguiente, sin consultar antes con la inferencia disponible: una consulta
    # disponible puede reiniciar el contador y ocultar una suma indebida (m9 sería equivalente).
    inferencia.disponible = False
    assert _estado(servicio).derivadas == 0, "una derivada con el agente disponible no pasa a la ventana siguiente"


# ¤agente-enrutador
def test_r5_sin_efectos(reloj: dict[str, datetime]) -> None:
    observabilidad = DobleObservabilidad()
    memoria = MemoriaEspia()
    servicio, modelo = _servicio(
        InferenciaFalsa(disponible=False, motivo="sin_tope_diario"), observabilidad=observabilidad, memoria=memoria
    )
    _estado(servicio)
    assert observabilidad.trazas_iniciadas == []
    assert modelo.llamadas == []
    assert memoria.escrituras == []


# ¤agente-enrutador
def test_r6_firmas_solo_crecen() -> None:
    assert tuple(inspect.signature(AgenteService.__init__).parameters) == ARGUMENTOS_INIT
    assert tuple(inspect.signature(AgenteService.atender).parameters) == ("self", "mensaje")
    metodo = getattr(AgenteService, "estado_asistente", None)
    assert metodo is not None, "T-417: falta AgenteService.estado_asistente"
    assert tuple(inspect.signature(metodo).parameters) == ("self",)
