# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del árbitro para caché semántico y enrutamiento de modelos (RF-AG-07, INV_CACHE_SIN_PRECIOS, RNF-16)."""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Any, Mapping

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.cache_internal import (
    CacheSemantico,
    contiene_precio_o_disponibilidad,
    seleccionar_modelo,
)
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.tipos import (
    DefinicionHerramienta,
    LlamadaHerramienta,
    RespuestaModelo,
    ResultadoHerramienta,
)
from features.seguridad.seguridad_service import Identidad, Rol


# ¤agente-enrutador
class MensajePrueba:
    def __init__(
        self,
        texto_tokenizado: str,
        conversacion_id: str = "conv_test_enrutamiento",
        rol: Rol = Rol.HUESPED_POTENCIAL,
    ) -> None:
        self.identidad = Identidad(remitente_token="usr_test_enrutador", rol=rol)
        self.texto_tokenizado = texto_tokenizado
        self.conversacion_id = conversacion_id
        self.marcas = ()


# ¤agente-enrutador
class DobleObservabilidadSpy:
    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []
        self.trazas_iniciadas: list[str] = []
        self.trazas_cerradas: list[dict[str, Any]] = []

    def iniciar_traza(self, *args: Any, **kwargs: Any) -> str:
        tid = f"traza-{len(self.trazas_iniciadas) + 1}"
        self.trazas_iniciadas.append(tid)
        return tid

    def cerrar_traza(self, traza_id: str, resultado: str = "") -> None:
        self.trazas_cerradas.append({"traza_id": traza_id, "resultado": resultado})

    def log(self, nivel: str, evento: str, **kwargs: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **kwargs})

    def tiene_evento(self, evento: str) -> bool:
        return any(log["evento"] == evento for log in self.logs)

    def obtener_evento(self, evento: str) -> dict[str, Any] | None:
        for log in self.logs:
            if log["evento"] == evento:
                return log
        return None


# ¤agente-enrutador
class DobleHerramientasLentas:
    def __init__(self, retardo_s: float = 0.0, duracion_ms: int = 0) -> None:
        self.retardo_s = retardo_s
        self.duracion_ms = duracion_ms
        self.ejecutadas: list[str] = []

    def listar(self, rol: str = "", propiedad_id: str | None = None) -> tuple[DefinicionHerramienta, ...]:
        return (
            DefinicionHerramienta(
                nombre="consultar_disponibilidad",
                descripcion="Consulta cupos y unidades",
                esquema_entrada={"type": "object", "properties": {"propiedad_id": {"type": "string"}}},
            ),
        )

    def ejecutar(self, nombre: str, args: Mapping[str, Any], identidad: Any, conversacion_id: str) -> ResultadoHerramienta:
        self.ejecutadas.append(nombre)
        if self.retardo_s > 0:
            time.sleep(self.retardo_s)
        return ResultadoHerramienta(
            nombre=nombre,
            salida={"disponible": True, "unidades": ["domo_1"]},
            error=None,
            duracion_ms=self.duracion_ms or int(self.retardo_s * 1000),
        )


# ¤agente-enrutador
class DobleCanalSpy:
    def __init__(self) -> None:
        self.mensajes_enviados: list[dict[str, str]] = []

    def enviar_texto(self, destinatario: str, texto: str) -> None:
        self.mensajes_enviados.append({"destinatario": destinatario, "texto": texto})


# ¤agente-enrutador
def test_invariante_inv_cache_sin_precios_no_guarda_respuestas_con_precios_ni_disponibilidad() -> None:
    """Escenario: Invariante INV_CACHE_SIN_PRECIOS rechaza almacenamiento (@RF-AG-07, @INV_CACHE_SIN_PRECIOS).

    Dado un intento de almacenar una respuesta generada
    Cuando la respuesta o la consulta contiene términos de precios, costos, tarifas o disponibilidad
    Entonces el caché semántico rechaza el guardado y no se persiste.
    """
    cache = CacheSemantico()

    # Intentos con precios, cotizaciones y monedas
    assert not cache.guardar("¿Tienen clave de wifi?", "El domo cuesta 120 USD por noche")
    assert not cache.guardar("¿Tienen clave de wifi?", "La tarifa es de $85 por pareja")
    assert not cache.guardar("¿Tienen clave de wifi?", "El costo total con impuestos es 95 dólares")
    assert not cache.guardar("¿Cuál es el precio del glamping?", "El wifi es gratis")
    assert not cache.guardar("¿Hay disponibilidad para este fin de semana?", "Sí, contamos con cupos")
    assert not cache.guardar("Consulta", "Políticas de cancelación con reembolso del 50%")

    assert cache.tamano() == 0


# ¤agente-enrutador
def test_invariante_inv_cache_sin_precios_no_sirve_desde_cache() -> None:
    """Escenario: Invariante INV_CACHE_SIN_PRECIOS no sirve consultas de precios desde caché (@RF-AG-07).

    Dado un caché semántico en memoria
    Cuando un huésped consulta por precios o disponibilidad
    Entonces el caché semántico devuelve None y obliga a enrutar al modelo principal.
    """
    cache = CacheSemantico()
    cache.guardar("horario de ingreso", "El check-in es a las 15:00 y el check-out a las 11:00")
    assert cache.tamano() == 1

    # Si la consulta contiene términos monetarios o de cupos, nunca debe servir del caché
    resp, sim = cache.buscar("¿cuál es el precio del check-in?")
    assert resp is None

    resp, sim = cache.buscar("¿tienen disponibilidad para hoy?")
    assert resp is None


# ¤agente-enrutador
def test_cache_semantico_hit_sirve_faq_con_costo_cero_y_registra_traza() -> None:
    """Escenario: FAQ de bajo riesgo servida desde caché con costo 0 USD (@RF-AG-07, @RNF-16).

    Dado un caché semántico que contiene una FAQ de bajo riesgo sobre wifi
    Cuando un usuario realiza una consulta con similitud semántica >= 0.92
    Entonces el servicio responde desde el caché sin invocar al modelo, con costo 0 USD y registra en la traza.
    """
    config = cargar_config()
    obs = DobleObservabilidadSpy()
    modelo = DobleClienteModelo([])

    servicio = AgenteService(
        config=config,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    # Pre-cargar FAQ en el caché
    servicio._cache.guardar(
        consulta="¿cuál es la clave del wifi?",
        respuesta="La clave de la red Wifi Glamping es GlampingSanPablo2026.",
        propiedad_id="glamping",
    )

    mensaje = MensajePrueba(texto_tokenizado="¿me pueden dar la clave de internet wifi?")
    respuesta = servicio.atender(mensaje)

    assert "GlampingSanPablo2026" in respuesta.texto
    assert respuesta.modelo == "cache_semantico"
    assert respuesta.costo_usd == Decimal("0")
    assert not respuesta.degradada
    assert len(modelo.llamadas) == 0

    # Comprobar log en observabilidad
    log_hit = obs.obtener_evento("cache_semantico_hit")
    assert log_hit is not None
    assert log_hit["similitud"] >= 0.90


# ¤agente-enrutador
def test_enrutamiento_pregunta_frecuente_bajo_riesgo_usa_modelo_economico() -> None:
    """Escenario: Preguntas frecuentes de bajo riesgo usan modelo económico (@RF-AG-07).

    Dado un mensaje que consulta por horario, ubicación, wifi o clima
    Cuando el enrutador evalúa el riesgo
    Entonces selecciona el modelo económico (gemini-3.5-flash-lite) y la decisión queda registrada en la traza.
    """
    config = cargar_config()
    obs = DobleObservabilidadSpy()
    modelo = DobleClienteModelo([
        RespuestaModelo(texto="El horario de check-in es desde las 15:00.", modelo="gemini-3.5-flash-lite"),
    ])

    servicio = AgenteService(
        config=config,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajePrueba(texto_tokenizado="¿A qué hora es el horario de llegada y check-in?")
    respuesta = servicio.atender(mensaje)

    assert respuesta.modelo == "gemini-3.5-flash-lite"
    assert len(modelo.llamadas) == 1
    assert modelo.llamadas[0]["modelo"] == "economico"  # perfil; inferencia resuelve el nombre

    log_decision = obs.obtener_evento("decision_enrutamiento_modelo")
    assert log_decision is not None
    assert log_decision["modelo_elegido"] == "economico"
    assert log_decision["razon"] == "pregunta_frecuente_bajo_riesgo"


# ¤agente-enrutador
def test_enrutamiento_precios_y_politicas_usa_modelo_principal() -> None:
    """Escenario: Consultas de precios y disponibilidad usan modelo principal y no se cachean (@RF-AG-07, @INV_CACHE_SIN_PRECIOS).

    Dado un mensaje que pregunta por precios o tarifas
    Cuando el agente procesa la consulta
    Entonces se enruta al modelo principal (gemini-3.8-flash) y no se persiste en caché.
    """
    config = cargar_config()
    obs = DobleObservabilidadSpy()
    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="La tarifa del domo es de 110 USD por noche e incluye desayuno.",
            modelo="gemini-3.8-flash",
        ),
    ])

    servicio = AgenteService(
        config=config,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajePrueba(texto_tokenizado="¿Cuánto cuesta una noche en el domo?")
    respuesta = servicio.atender(mensaje)

    assert respuesta.modelo == "gemini-3.8-flash"
    assert len(modelo.llamadas) == 1
    assert modelo.llamadas[0]["modelo"] == "principal"  # perfil; inferencia resuelve el nombre

    # Verificar que la decisión quedó en la traza
    log_decision = obs.obtener_evento("decision_enrutamiento_modelo")
    assert log_decision is not None
    assert log_decision["modelo_elegido"] == "principal"
    assert log_decision["razon"] == "pregunta_critica_precio_o_disponibilidad"

    # Verificar que se rechazó el guardado en caché por la invariante
    log_rechazo = obs.obtener_evento("cache_semantico_rechazado_por_precio_o_disponibilidad")
    assert log_rechazo is not None
    assert log_rechazo["invariante"] == "INV_CACHE_SIN_PRECIOS"
    assert servicio._cache.tamano() == 0


# ¤agente-enrutador
def test_enrutamiento_acciones_con_herramientas_usa_modelo_principal() -> None:
    """Escenario: Consultas que invocan herramientas van siempre al modelo principal (@RF-AG-07)."""
    config = cargar_config()
    obs = DobleObservabilidadSpy()
    herramientas = DobleHerramientasLentas()
    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="",
            llamadas_herramientas=(
                LlamadaHerramienta(
                    id="call_1",
                    nombre="consultar_disponibilidad",
                    argumentos={"propiedad_id": "glamping"},
                ),
            ),
            modelo="gemini-3.8-flash",
        ),
        RespuestaModelo(
            texto="Tenemos el domo_1 disponible.",
            modelo="gemini-3.8-flash",
        ),
    ])

    servicio = AgenteService(
        config=config,
        herramientas=herramientas,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajePrueba(texto_tokenizado="Deseo ver si hay cupo para reservar")
    respuesta = servicio.atender(mensaje)

    assert "consultar_disponibilidad" in respuesta.herramientas_usadas
    assert respuesta.modelo == "gemini-3.8-flash"


# ¤agente-enrutador
def test_acuse_un_momento_si_herramienta_tarda_mas_de_3_segundos() -> None:
    """Escenario: Acuse «un momento…» si una herramienta tarda más de 3 segundos (@T-403).

    Dado un bucle de herramientas que ejecuta una herramienta con duración >= 3 s
    Cuando la herramienta se demora
    Entonces el agente emite el acuse «un momento…», lo registra en observabilidad y entrega la respuesta final.
    """
    config = dict(cargar_config())
    config["acuse_si_tarda_s"] = 0.05  # Umbral bajo para prueba rápida sin frenar el arnés

    obs = DobleObservabilidadSpy()
    canal = DobleCanalSpy()
    herramientas = DobleHerramientasLentas(retardo_s=0.08)  # Supera el umbral configurado de 0.05s

    modelo = DobleClienteModelo([
        RespuestaModelo(
            texto="",
            llamadas_herramientas=(
                LlamadaHerramienta(
                    id="call_lenta",
                    nombre="consultar_disponibilidad",
                    argumentos={"propiedad_id": "glamping"},
                ),
            ),
            modelo="gemini-3.8-flash",
        ),
        RespuestaModelo(
            texto="Información confirmada: el domo está disponible.",
            modelo="gemini-3.8-flash",
        ),
    ])

    servicio = AgenteService(
        config=config,
        herramientas=herramientas,
        canal=canal,
        observabilidad=obs,
        cliente_modelo=modelo,
    )

    mensaje = MensajePrueba(texto_tokenizado="Revisa la disponibilidad por favor")
    respuesta = servicio.atender(mensaje)

    assert "consultar_disponibilidad" in respuesta.herramientas_usadas
    assert respuesta.acuse_emitido is True
    assert "Información confirmada" in respuesta.texto

    # Verificar que se registró el evento de acuse en observabilidad
    log_acuse = obs.obtener_evento("acuse_espera_herramienta")
    assert log_acuse is not None
    assert log_acuse["herramienta"] == "consultar_disponibilidad"

    # Verificar que se envió el acuse al canal
    assert len(canal.mensajes_enviados) >= 1
    assert "Un momento" in canal.mensajes_enviados[0]["texto"]
