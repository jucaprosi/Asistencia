# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-AG-01, INV_PROPIEDAD_RESUELTA e INV_SIN_FUGA_ENTRE_PROPIEDADES."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.bucle_herramientas_internal import BucleHerramientas
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.enrutador_internal import EnrutadorPropiedad
from features.agente.prompts_internal import PromptsManager
from features.agente.tipos import (
    ContextoConversacion,
    DefinicionHerramienta,
    LlamadaHerramienta,
    ModoAgente,
    PropiedadRequeridaNoResuelta,
    RespuestaModelo,
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

    def cerrar_traza(self, traza_id: str, resultado: str) -> None:
        self.trazas_cerradas.append({"traza_id": traza_id, "resultado": resultado})

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **campos})


# ¤agente-enrutador
class DobleHerramientasSpy:
    def __init__(self) -> None:
        self.ejecuciones: list[dict[str, Any]] = []

    def listar(self, rol: str, propiedad_id: str | None) -> tuple[DefinicionHerramienta, ...]:
        return (
            DefinicionHerramienta(
                nombre="consultar_disponibilidad",
                descripcion="Consulta disponibilidad",
                esquema_entrada={"type": "object", "properties": {"propiedad_id": {"type": "string"}}},
            ),
        )

    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> Any:
        self.ejecuciones.append({"nombre": nombre, "entrada": entrada, "conversacion_id": conversacion_id})
        return {"disponible": True}


# ¤agente-enrutador
def test_resolucion_por_codigo_reserva_glamping() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("Hola, mi código de reserva es RES-GLAMP-101")
    assert res.propiedad_id == "glamping"
    assert res.metodo == "codigo_reserva"


# ¤agente-enrutador
def test_resolucion_por_codigo_reserva_departamento() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("Tengo la reserva RES-DEP-555 confirmada")
    assert res.propiedad_id == "departamento_centro"
    assert res.metodo == "codigo_reserva"


# ¤agente-enrutador
def test_resolucion_por_nombre_glamping() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("¿Cuánto cuesta alojarse en el glamping?")
    assert res.propiedad_id == "glamping"
    assert res.metodo == "nombre"


# ¤agente-enrutador
def test_resolucion_por_nombre_departamento() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("¿Tienen disponibilidad en las suites del centro?")
    assert res.propiedad_id == "departamento_centro"
    assert res.metodo == "nombre"


# ¤agente-enrutador
def test_resolucion_por_direccion_glamping() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("¿Cómo llego al Sector Cajas en la Vía al Lago?")
    assert res.propiedad_id == "glamping"
    assert res.metodo == "direccion"


# ¤agente-enrutador
def test_resolucion_por_direccion_departamento() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("¿El lugar queda en García Moreno y Sucre?")
    assert res.propiedad_id == "departamento_centro"
    assert res.metodo == "direccion"


# ¤agente-enrutador
def test_resolucion_por_contexto_previo() -> None:
    enrutador = EnrutadorPropiedad()
    contexto = ContextoConversacion(
        conversacion_id="conv_ctx",
        identidad_token="usr_1",
        rol="huesped_activo",
        propiedad_id="departamento_centro",
        modo=ModoAgente.ACTIVO,
        ventana_24h_hasta=None,
    )
    res = enrutador.resolver("¿A qué hora debo entregar las llaves?", contexto)
    assert res.propiedad_id == "departamento_centro"
    assert res.metodo == "contexto"


# ¤agente-enrutador
def test_resolucion_ambigua_pregunta_con_lista() -> None:
    enrutador = EnrutadorPropiedad()
    res = enrutador.resolver("¿Qué diferencia hay entre el glamping y el departamento?")
    assert res.propiedad_id is None
    assert res.metodo == "pregunta"
    assert "glamping" in res.candidatas
    assert "departamento_centro" in res.candidatas


# ¤agente-enrutador
def test_atender_mensaje_ambiguo_no_llama_herramientas_y_devuelve_lista() -> None:
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientasSpy()
    modelo = DobleClienteModelo([RespuestaModelo(texto="No debería llamarse")])
    servicio = AgenteService(
        config=config,
        herramientas=herramientas,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_123", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="Quiero comparar el glamping con las suites del centro",
        marcas=(),
        conversacion_id="conv_ambigua_1",
    )

    respuesta = servicio.atender(mensaje)
    assert len(respuesta.lista) >= 2
    assert len(herramientas.ejecuciones) == 0
    assert len(modelo.llamadas) == 0


# ¤agente-enrutador
def test_propiedad_resuelta_se_persiste_en_contexto() -> None:
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientasSpy()
    modelo = DobleClienteModelo([RespuestaModelo(texto="Con gusto le atiendo en Suites Centro.")])
    servicio = AgenteService(
        config=config,
        herramientas=herramientas,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_123", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="Deseo información del departamento centro histórico",
        marcas=(),
        conversacion_id="conv_persistencia_prop",
    )

    servicio.atender(mensaje)
    ctx = servicio.contexto("conv_persistencia_prop")
    assert ctx.propiedad_id == "departamento_centro"


# ¤agente-enrutador
def test_inv_propiedad_resuelta_falla_si_falta_propiedad() -> None:
    """Verifica que INV_PROPIEDAD_RESUELTA rechaza ejecutar herramientas obligatorias con propiedad vacía."""
    config = cargar_config()
    obs = DobleObservabilidad()
    herramientas = DobleHerramientasSpy()
    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="Llamando disponibilidad",
            llamadas_herramientas=(
                LlamadaHerramienta(id="c1", nombre="consultar_disponibilidad", argumentos={"desde": "2026-12-01", "hasta": "2026-12-03"}),
            ),
        ),
    ])

    bucle = BucleHerramientas(
        config=config,
        cliente_modelo=modelo,
        herramientas_service=herramientas,
        observabilidad=obs,
    )

    with pytest.raises(PropiedadRequeridaNoResuelta) as exc_info:
        bucle.ejecutar(
            system_prompt="Prompt base",
            mensajes_historial=(),
            mensaje_actual_token="consulta",
            identidad=None,
            conversacion_id="conv_inv_prop",
            propiedad_id=None,
            herramientas_disponibles=herramientas.listar("huesped_potencial", None),
            traza_id="t1",
        )

    assert "consultar_disponibilidad" in str(exc_info.value)
    assert len(herramientas.ejecuciones) == 0


# ¤agente-enrutador
def test_inv_sin_fuga_entre_propiedades_aislamiento_estricto() -> None:
    """Verifica INV_SIN_FUGA_ENTRE_PROPIEDADES: un prompt de glamping jamás contiene datos de departamentos y viceversa."""
    config = cargar_config()
    prompts_mgr = PromptsManager(config)

    prompt_glamping, _ = prompts_mgr.armar_prompt("glamping")
    prompt_departamento, _ = prompts_mgr.armar_prompt("departamento_centro")

    # Glamping no debe tener referencias a Quito ni Sucre
    assert "García Moreno y Sucre" not in prompt_glamping
    assert "Quito Colonial" not in prompt_glamping
    assert "Suites Centro Histórico" not in prompt_glamping

    # Departamento no debe tener referencias a Lago San Pablo ni Sector Cajas
    assert "Sector Cajas" not in prompt_departamento
    assert "Vía al Lago San Pablo" not in prompt_departamento
    assert "Glamping San Pablo Imbabura" not in prompt_departamento


# ¤agente-enrutador
def test_enrutador_evaluar_archivo_20_casos() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    archivo_eval = Path(__file__).resolve().parent.parent.parent / "evals" / "enrutador.jsonl"
    metricas = servicio.evaluar(archivo_eval)
    assert metricas["total"] == 20.0
    assert metricas["aciertos"] == 1.0
