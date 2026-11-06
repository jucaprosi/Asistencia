# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Árbitro de RF-AG-03: Exposición selectiva de herramientas e INV_ALLOWLIST_POR_ACCION."""
from __future__ import annotations

from typing import Any

import pytest

from features.agente.agente_service import AgenteService, cargar_config
from features.agente.cliente_modelo_internal import DobleClienteModelo
from features.agente.tipos import DefinicionHerramienta, RespuestaModelo
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
class DobleHerramientasFiltradas:
    def __init__(self, agente_service: AgenteService) -> None:
        self.agente_service = agente_service
        self.llamadas_listar: list[dict[str, Any]] = []

    def listar(self, rol: str, propiedad_id: str | None) -> tuple[DefinicionHerramienta, ...]:
        nombres_permitidos = self.agente_service.herramientas_para(rol, propiedad_id)
        self.llamadas_listar.append({"rol": rol, "propiedad_id": propiedad_id, "nombres": nombres_permitidos})
        return tuple(
            DefinicionHerramienta(
                nombre=n,
                descripcion=f"Herramienta {n}",
                esquema_entrada={"type": "object"},
            )
            for n in nombres_permitidos
        )

    def ejecutar(self, nombre: str, entrada: Any, identidad: Any, conversacion_id: str) -> Any:
        return {}


# ¤agente-enrutador
def test_huesped_potencial_no_ve_herramientas_de_ventas() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    herramientas = servicio.herramientas_para("huesped_potencial")

    assert "registrar_venta" not in herramientas
    assert "consultar_comision_propia" not in herramientas
    assert "validar_venta" not in herramientas
    assert "consultar_disponibilidad" in herramientas
    assert "cotizar" in herramientas


# ¤agente-enrutador
def test_vendedor_no_ve_herramientas_de_reservas() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    herramientas = servicio.herramientas_para("vendedor")

    assert "consultar_disponibilidad" not in herramientas
    assert "cotizar" not in herramientas
    assert "crear_reserva_preliminar" not in herramientas
    assert "registrar_venta" in herramientas
    assert "consultar_comision_propia" in herramientas


# ¤agente-enrutador
def test_huesped_activo_incluye_checkin_e_incidencias() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    herramientas = servicio.herramientas_para("huesped_activo")

    assert "obtener_instrucciones_checkin" in herramientas
    assert "reportar_incidencia" in herramientas
    assert "registrar_venta" not in herramientas


# ¤agente-enrutador
def test_lider_incluye_validacion_y_reportes() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    herramientas = servicio.herramientas_para("lider")

    assert "validar_venta" in herramientas
    assert "rechazar_venta" in herramientas
    assert "ver_comisiones_todas" in herramientas
    assert "consultar_disponibilidad" not in herramientas


# ¤agente-enrutador
def test_anfitrion_incluye_herramientas_de_anfitrion() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    herramientas = servicio.herramientas_para("anfitrion")

    assert "responder_solicitud" in herramientas
    assert "reportar_resultado_estadia" in herramientas
    assert "actualizar_calendario" in herramientas
    assert "registrar_venta" not in herramientas


# ¤agente-enrutador
def test_rol_desconocido_retorna_vacio() -> None:
    config = cargar_config()
    servicio = AgenteService(config)
    herramientas = servicio.herramientas_para("desconocido")
    assert herramientas == ()


# ¤agente-enrutador
def test_traza_registra_conjunto_de_herramientas_expuestas() -> None:
    config = cargar_config()
    obs = DobleObservabilidad()
    modelo = DobleClienteModelo([RespuestaModelo(texto="Bienvenido")])

    servicio = AgenteService(
        config=config,
        observabilidad=obs,
        cliente_modelo=modelo,
    )
    herramientas_spy = DobleHerramientasFiltradas(servicio)
    servicio._herramientas = herramientas_spy

    mensaje = MensajeLimpio(
        identidad=Identidad(remitente_token="usr_vendedor", rol=Rol.VENDEDOR),
        texto_tokenizado="Hola, deseo registrar una venta",
        marcas=(),
        conversacion_id="conv_expuesta_1",
    )

    servicio.atender(mensaje)

    logs_expuestas = [log for log in obs.logs if log.get("evento") == "herramientas_expuestas"]
    assert len(logs_expuestas) >= 1
    log_exp = logs_expuestas[0]
    assert log_exp["rol"] == "vendedor"
    assert "registrar_venta" in log_exp["herramientas"]
    assert "consultar_disponibilidad" not in log_exp["herramientas"]
