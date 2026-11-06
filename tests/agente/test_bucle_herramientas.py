# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Árbitro de RF-AG-04: Orquestación del bucle de herramientas, tope de 6 iteraciones e invariantes."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.bucle_herramientas_internal import BucleHerramientas
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.tipos import (
    DefinicionHerramienta,
    LlamadaHerramienta,
    PropiedadRequeridaNoResuelta,
    RespuestaModelo,
    ResultadoHerramienta,
)
from features.seguridad.seguridad_service import Identidad, MensajeLimpio, Rol


# ¤agente-enrutador
class DobleObservabilidad:
    def __init__(self) -> None:
        self.trazas_iniciadas: list[dict[str, Any]] = []
        self.trazas_cerradas: list[dict[str, Any]] = []
        self.logs: list[dict[str, Any]] = []

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str:
        tid = f"traza-{len(self.trazas_iniciadas) + 1}"
        self.trazas_iniciadas.append({"traza_id": tid, "mensaje_id": mensaje_id, "conversacion_id": conversacion_id, "canal": canal})
        return tid

    @contextmanager
    def span(self, traza_id: str, sala: str, nombre: str) -> Iterator[dict[str, Any]]:
        yield {"traza_id": traza_id, "sala": sala, "nombre": nombre}

    def cerrar_traza(self, traza_id: str, resultado: str) -> None:
        self.trazas_cerradas.append({"traza_id": traza_id, "resultado": resultado})

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **campos})


# ¤agente-enrutador
class DobleSeguridad:
    def tokenizar(self, texto: str, conversacion_id: str) -> str:
        return texto

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        return texto

    def filtrar_salida(self, texto: str, conversacion_id: str) -> str:
        return texto


# ¤agente-enrutador
class DobleHerramientas:
    def __init__(self) -> None:
        self.ejecuciones: list[dict[str, Any]] = []
        self.respuestas: dict[str, ResultadoHerramienta] = {}

    def registrar_respuesta(self, nombre: str, resultado: ResultadoHerramienta) -> None:
        self.respuestas[nombre] = resultado

    def listar(self, rol: str, propiedad_id: str | None) -> tuple[DefinicionHerramienta, ...]:
        return (
            DefinicionHerramienta(
                nombre="consultar_disponibilidad",
                descripcion="Consulta disponibilidad de fechas",
                esquema_entrada={"type": "object", "required": ["propiedad_id", "desde", "hasta"]},
                esquema_salida={"type": "object"},
                roles=("huesped_potencial", "huesped_activo"),
                sala_destino="pms_conector",
            ),
        )

    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> ResultadoHerramienta:
        self.ejecuciones.append({"nombre": nombre, "entrada": entrada, "identidad": identidad, "conversacion_id": conversacion_id})
        if nombre in self.respuestas:
            return self.respuestas[nombre]
        return ResultadoHerramienta(nombre=nombre, salida={"disponible": True, "unidades": ["Domo Lago"]})


# ¤agente-enrutador
def test_bucle_ejecuta_herramienta_y_culmina_exitosamente() -> None:
    """Verifica que el modelo puede invocar una herramienta, recibir su resultado y concluir."""
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientas()

    # Iteración 1: el modelo llama a consultar_disponibilidad
    # Iteración 2: con el resultado de la herramienta, el modelo responde al usuario
    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="Voy a consultar la disponibilidad.",
            llamadas_herramientas=(
                LlamadaHerramienta(id="call_1", nombre="consultar_disponibilidad", argumentos={"desde": "2026-12-01", "hasta": "2026-12-03"}),
            ),
        ),
        RespuestaModelo(
            texto="Tenemos disponible el Domo Lago para esas fechas.",
            llamadas_herramientas=(),
        ),
    ])

    servicio = AgenteService(
        config=config,
        seguridad=DobleSeguridad(),
        herramientas=herramientas,
        conocimiento=None,
        canal=None,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_123", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="¿Tienen disponibilidad del 1 al 3 de diciembre?",
        marcas=(),
        conversacion_id="conv_bucle_1",
    )

    respuesta = servicio.atender(mensaje)
    assert not respuesta.degradada
    assert "Tenemos disponible el Domo Lago" in respuesta.texto
    assert "consultar_disponibilidad" in respuesta.herramientas_usadas
    assert len(herramientas.ejecuciones) == 1
    assert herramientas.ejecuciones[0]["entrada"]["propiedad_id"] == "glamping"


# ¤agente-enrutador
def test_tope_de_iteraciones_escala_con_limite_iteraciones() -> None:
    """Escenario: Tope de iteraciones (@RF-AG-04).

    Dado un bucle de herramientas que no termina
    Cuando supera 6 iteraciones
    Entonces el agente abre un handoff con motivo 'limite_iteraciones'
    """
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientas()

    # Programar más de 6 llamadas infinitas a herramientas
    llamadas_infinitas = [
        RespuestaModelo(
            texto=f"Consultando paso {i}",
            llamadas_herramientas=(
                LlamadaHerramienta(id=f"call_{i}", nombre="consultar_disponibilidad", argumentos={"desde": "2026-12-01", "hasta": "2026-12-03"}),
            ),
        )
        for i in range(1, 10)
    ]
    modelo = DobleClienteModelo(llamadas_infinitas)

    servicio = AgenteService(
        config=config,
        seguridad=DobleSeguridad(),
        herramientas=herramientas,
        conocimiento=None,
        canal=None,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_loop", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="Pregunta que genera bucle",
        marcas=(),
        conversacion_id="conv_loop_6",
    )

    respuesta = servicio.atender(mensaje)
    assert respuesta.degradada
    assert len(herramientas.ejecuciones) == 6  # Se detuvo exactamente en el tope de 6

    # Verificar que abrió handoff y registró motivo limite_iteraciones en traza
    logs_escalamiento = [
        log for log in obs.logs
        if log.get("evento") == "limite_iteraciones" or log.get("motivo") == "limite_iteraciones"
    ]
    assert len(logs_escalamiento) >= 1
    assert logs_escalamiento[0]["motivo"] == "limite_iteraciones"
    # Entrega contacto de escalamiento
    assert "Carlos Alvear" in respuesta.texto or "+593991234567" in respuesta.texto


# ¤agente-enrutador
def test_inv_propiedad_resuelta_falla_si_falta_propiedad() -> None:
    """Invariante INV_PROPIEDAD_RESUELTA: requiere_propiedad(h) ∧ invocada(h) ⇒ propiedad_id ≠ ∅."""
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientas()
    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="Llamando sin propiedad",
            llamadas_herramientas=(
                LlamadaHerramienta(id="call_x", nombre="consultar_disponibilidad", argumentos={"desde": "2026-12-01"}),
            ),
        )
    ])

    bucle = BucleHerramientas(
        config=config,
        cliente_modelo=modelo,
        herramientas_service=herramientas,
        observabilidad=obs,
    )

    # Invocación directa con propiedad_id = None
    with pytest.raises(PropiedadRequeridaNoResuelta) as exc_info:
        bucle.ejecutar(
            system_prompt="prompt",
            mensajes_historial=(),
            mensaje_actual_token="consulta",
            identidad=Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL),
            conversacion_id="c_test",
            propiedad_id=None,
            herramientas_disponibles=herramientas.listar("huesped_potencial", None),
            traza_id="t_test",
        )
    assert exc_info.value.herramienta == "consultar_disponibilidad"
    assert len(herramientas.ejecuciones) == 0  # No se ejecutó la herramienta
