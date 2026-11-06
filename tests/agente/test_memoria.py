# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Árbitro de RF-AG-06: Memoria de conversación, límite de 30 mensajes / 24h e INV_PII_FUERA_DEL_MODELO tras reinicio."""
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.memoria_internal import MemoriaConversacion
from features.agente.tipos import ContextoConversacion, ModoAgente, RespuestaModelo
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
class DobleSeguridadConTokenizacion:
    def tokenizar(self, texto: str, conversacion_id: str) -> str:
        # Reemplazar números de teléfono y correos por tokens
        import re
        limpio = re.sub(r"\b09\d{8}\b|\b\+593\d{9}\b", "[[TOKEN_TEL_1]]", texto)
        limpio = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[[TOKEN_EMAIL_1]]", limpio)
        return limpio

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        return texto.replace("[[TOKEN_TEL_1]]", "0991234567").replace("[[TOKEN_EMAIL_1]]", "cliente@ejemplo.com")

    def filtrar_salida(self, texto: str, conversacion_id: str) -> str:
        return self.rehidratar(texto, conversacion_id)


# ¤agente-enrutador
class DobleHerramientas:
    def listar(self, rol: str, propiedad_id: str | None) -> tuple[Any, ...]:
        return ()

    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> Any:
        return None


# ¤agente-enrutador
def test_memoria_tras_un_reinicio() -> None:
    """Escenario: Memoria tras un reinicio (@RF-AG-06 @INV_PII_FUERA_DEL_MODELO).

    Dado una conversación abierta
    Cuando el contenedor se reinicia
    Entonces el contexto sigue disponible y el historial solo contiene tokens
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_file = Path(temp_dir) / "agente_test.db"
        config = dict(cargar_config())
        config["db_path"] = str(db_file)

        obs1 = DobleObservabilidad()
        seg1 = DobleSeguridadConTokenizacion()
        modelo1 = DobleClienteModelo([
            RespuestaModelo(texto="Respuesta para el usuario con token [[TOKEN_TEL_1]]"),
        ])

        # 1. Instancia inicial del servicio
        servicio1 = AgenteService(
            config=config,
            seguridad=seg1,
            herramientas=DobleHerramientas(),
            conocimiento=None,
            canal=None,
            observabilidad=obs1,
            cliente_modelo=modelo1,
        )

        cid = "conv_persistente_1"
        # Mensaje entrante con PII que seguridad tokeniza
        texto_con_pii = "Mi teléfono es 0991234567 y mi correo es cliente@ejemplo.com"
        texto_tokenizado = seg1.tokenizar(texto_con_pii, cid)
        assert "0991234567" not in texto_tokenizado
        assert "cliente@ejemplo.com" not in texto_tokenizado

        msg = MensajeLimpio(
            identidad=Identidad(remitente_token="tk_pers", rol=Rol.HUESPED_POTENCIAL),
            texto_tokenizado=texto_tokenizado,
            marcas=(),
            conversacion_id=cid,
        )

        resp1 = servicio1.atender(msg)
        assert resp1.texto  # Salida rehidratada entregada al usuario

        # 2. Simulación de reinicio del contenedor (destruir servicio1 e instanciar servicio2 con la misma BD)
        del servicio1

        obs2 = DobleObservabilidad()
        seg2 = DobleSeguridadConTokenizacion()
        servicio2 = AgenteService(
            config=config,
            seguridad=seg2,
            herramientas=DobleHerramientas(),
            conocimiento=None,
            canal=None,
            observabilidad=obs2,
        )

        # Verificar que el contexto sigue disponible
        ctx_recuperado = servicio2.contexto(cid)
        assert ctx_recuperado.conversacion_id == cid
        assert ctx_recuperado.identidad_token == "tk_pers"
        assert ctx_recuperado.propiedad_id == "glamping"
        assert ctx_recuperado.modo == ModoAgente.ACTIVO

        # Verificar que el historial recuperado solo contiene tokens y nada de PII en claro
        memoria2 = MemoriaConversacion(db_path=db_file)
        historial = memoria2.obtener_historial(cid)
        assert len(historial) >= 2  # Mensaje entrante y mensaje saliente

        for m in historial:
            # INV_PII_FUERA_DEL_MODELO: ∀ v ∈ PII(m) : v ∉ historial
            assert "0991234567" not in m.contenido_token, f"Fuga de PII en mensaje {m.mensaje_id}"
            assert "cliente@ejemplo.com" not in m.contenido_token, f"Fuga de PII en mensaje {m.mensaje_id}"
            assert "[[TOKEN_" in m.contenido_token


# ¤agente-enrutador
def test_historial_limite_30_mensajes() -> None:
    """Verifica que el historial devuelve como máximo los últimos 30 mensajes."""
    memoria = MemoriaConversacion(":memory:")
    cid = "conv_limite_30"
    ctx = ContextoConversacion(
        conversacion_id=cid,
        identidad_token="usr_test",
        rol="huesped_potencial",
        propiedad_id="glamping",
        modo=ModoAgente.ACTIVO,
        ventana_24h_hasta=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    memoria.guardar_conversacion(ctx)

    # Insertar 35 mensajes secuenciales
    ahora = datetime.now(timezone.utc)
    for i in range(35):
        memoria.guardar_mensaje(
            mensaje_id=f"msg_{i}",
            conversacion_id=cid,
            direccion="in" if i % 2 == 0 else "out",
            tipo="texto",
            contenido_token=f"Token_mensaje_{i}",
            instante=ahora + timedelta(seconds=i),
        )

    historial = memoria.obtener_historial(cid, limite=30)
    assert len(historial) == 30
    # Los más viejos (0 a 4) deben haber sido excluidos
    assert historial[0].contenido_token == "Token_mensaje_5"
    assert historial[-1].contenido_token == "Token_mensaje_34"


# ¤agente-enrutador
def test_historial_filtra_mensajes_mayores_a_24_horas() -> None:
    """Verifica que mensajes de más de 24 horas no ingresan al contexto reciente."""
    memoria = MemoriaConversacion(":memory:")
    cid = "conv_24h"
    ctx = ContextoConversacion(
        conversacion_id=cid,
        identidad_token="usr_24h",
        rol="huesped_potencial",
        propiedad_id="glamping",
        modo=ModoAgente.ACTIVO,
        ventana_24h_hasta=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    memoria.guardar_conversacion(ctx)

    ahora = datetime.now(timezone.utc)
    # Mensaje de hace 26 horas
    memoria.guardar_mensaje(
        mensaje_id="msg_antiguo",
        conversacion_id=cid,
        direccion="in",
        tipo="texto",
        contenido_token="Mensaje_antiguo",
        instante=ahora - timedelta(hours=26),
    )
    # Mensaje de hace 2 horas
    memoria.guardar_mensaje(
        mensaje_id="msg_reciente",
        conversacion_id=cid,
        direccion="in",
        tipo="texto",
        contenido_token="Mensaje_reciente",
        instante=ahora - timedelta(hours=2),
    )

    historial = memoria.obtener_historial(cid, horas=24)
    assert len(historial) == 1
    assert historial[0].mensaje_id == "msg_reciente"


# ¤agente-enrutador
def test_cambio_de_modo_silencio_y_reanudacion() -> None:
    """Verifica la persistencia de los modos ACTIVO y SILENCIO."""
    memoria = MemoriaConversacion(":memory:")
    cid = "conv_modo"
    ctx = ContextoConversacion(
        conversacion_id=cid,
        identidad_token="usr_modo",
        rol="huesped_potencial",
        propiedad_id="glamping",
        modo=ModoAgente.ACTIVO,
        ventana_24h_hasta=None,
    )
    memoria.guardar_conversacion(ctx)

    assert memoria.obtener_conversacion(cid).modo == ModoAgente.ACTIVO

    memoria.actualizar_modo(cid, ModoAgente.SILENCIO)
    assert memoria.obtener_conversacion(cid).modo == ModoAgente.SILENCIO

    memoria.actualizar_modo(cid, ModoAgente.ACTIVO)
    assert memoria.obtener_conversacion(cid).modo == ModoAgente.ACTIVO
