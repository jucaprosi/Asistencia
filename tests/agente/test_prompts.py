# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-AG-02: Carga de prompts por propiedad, hash en trazas y aislamiento estricto."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.prompts_internal import PromptsManager, calcular_hash_prompt
from features.agente.tipos import ErrorAgente, RespuestaModelo
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
    def listar(self, rol: str, propiedad_id: str | None) -> tuple[Any, ...]:
        return ()

    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> Any:
        return None


# ¤agente-enrutador
def test_prompts_se_precargan_en_arranque() -> None:
    config = cargar_config()
    manager = PromptsManager(config)
    plantilla = manager.obtener_plantilla_cruda("glamping")
    assert plantilla
    assert "System prompt" in plantilla or "glamping" in plantilla.lower()


# ¤agente-enrutador
def test_hash_prompt_es_consistente_y_determinista() -> None:
    texto = "Prompt de prueba determinista 123"
    hash1 = calcular_hash_prompt(texto)
    hash2 = calcular_hash_prompt(texto)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256


# ¤agente-enrutador
def test_prompt_por_propiedad_aislamiento_estricto() -> None:
    """Escenario: Prompt por propiedad (@RF-AG-02 @INV_SIN_FUGA_ENTRE_PROPIEDADES).

    Dado una propiedad resuelta
    Cuando el agente arma el prompt
    Entonces solo contiene datos de esa propiedad y la traza guarda el hash del prompt
    """
    config = cargar_config()
    manager = PromptsManager(config)

    # Propiedad 1: glamping
    prompt_glamping, hash_glamping = manager.armar_prompt("glamping")
    assert "San Pablo" in prompt_glamping
    assert "Domo Lago" in prompt_glamping
    assert "Carlos Alvear" in prompt_glamping
    # Verificación de no fuga: NO debe tener datos de departamento_centro
    assert "Centro Histórico" not in prompt_glamping
    assert "María Elena Morales" not in prompt_glamping
    assert hash_glamping == calcular_hash_prompt(prompt_glamping)

    # Propiedad 2: departamento_centro
    prompt_depto, hash_depto = manager.armar_prompt("departamento_centro")
    assert "Centro Histórico" in prompt_depto
    assert "María Elena Morales" in prompt_depto
    # Verificación de no fuga: NO debe tener datos de glamping
    assert "San Pablo" not in prompt_depto
    assert "Carlos Alvear" not in prompt_depto
    assert hash_depto == calcular_hash_prompt(prompt_depto)

    # Los hashes deben ser distintos al tener datos diferentes
    assert hash_glamping != hash_depto


# ¤agente-enrutador
def test_traza_guarda_hash_del_prompt_al_atender() -> None:
    """Verifica que en la ejecución de atender, el hash del prompt se registra en la traza."""
    config = cargar_config()
    obs = DobleObservabilidad()
    modelo = DobleClienteModelo([RespuestaModelo(texto="Bienvenido al glamping")])
    servicio = AgenteService(
        config=config,
        seguridad=DobleSeguridad(),
        herramientas=DobleHerramientas(),
        conocimiento=None,
        canal=None,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_123", rol=Rol.HUESPED_POTENCIAL),
        texto_tokenizado="Hola, ¿qué servicios tienen?",
        marcas=(),
        conversacion_id="conv_p1",
    )

    respuesta = servicio.atender(mensaje)
    assert not respuesta.degradada

    # Buscar log con hash_prompt
    logs_prompt = [log for log in obs.logs if log.get("evento") == "prompt_cargado"]
    assert len(logs_prompt) >= 1
    log_p = logs_prompt[0]
    assert log_p["propiedad_id"] == "glamping"
    assert "hash_prompt" in log_p
    assert len(log_p["hash_prompt"]) == 64


# ¤agente-enrutador
def test_error_al_solicitar_propiedad_inexistente() -> None:
    config = cargar_config()
    manager = PromptsManager(config)
    with pytest.raises(ErrorAgente) as exc_info:
        manager.armar_prompt("propiedad_fantasma_xyz")
    assert "propiedad_desconocida" in str(exc_info.value)
