"""Pruebas de RF-GW-04: Catálogo de plantillas, validación de variables y estado de aprobación."""
from __future__ import annotations

import pytest

from features.canal_whatsapp.canal_whatsapp_service import CanalWhatsappService, cargar_config
from features.canal_whatsapp.tipos import (
    Plantilla, PlantillaNoAprobada, VariablesPlantillaInvalidas,
)
from tests.canal_whatsapp.dobles import (
    ApiMetaSimulada, DobleObservabilidadService, DobleSeguridadService,
)


@pytest.fixture
def api_simulada() -> ApiMetaSimulada:
    return ApiMetaSimulada()


@pytest.fixture
def servicio(api_simulada: ApiMetaSimulada) -> CanalWhatsappService:
    config = dict(cargar_config())
    return CanalWhatsappService(
        config,
        seguridad=DobleSeguridadService(),
        observabilidad=DobleObservabilidadService(),
        cliente_http=api_simulada,
        sleep_fn=lambda _: None,
    )


def test_catalogo_plantillas_cargado_desde_config(servicio: CanalWhatsappService) -> None:
    """RF-GW-04: El catálogo de plantillas se siembra en la persistencia con su configuración."""
    plantillas = servicio.repositorio.listar_plantillas()
    nombres = {p.nombre for p in plantillas}

    assert "instrucciones_checkin" in nombres
    assert "recordatorio_llegada" in nombres
    assert "comision_validada" in nombres
    assert "venta_rechazada" in nombres
    assert "incidencia_actualizada" in nombres
    assert "handoff_asignado" in nombres
    assert "seguimiento_atencion" in nombres
    assert "solicitud_reserva_anfitrion" in nombres
    assert "reserva_confirmada" in nombres
    assert "estado_cuenta_anfitrion" in nombres
    assert "codigo_acceso_panel" in nombres


def test_envio_plantilla_no_aprobada_falla_sin_llamar_a_meta(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-04 (b): Una plantilla no aprobada no se envía y se rechaza con PlantillaNoAprobada."""
    plantilla = Plantilla(
        nombre="recordatorio_llegada",
        idioma="es",
        variables=("Juan", "Domo Bosque", "2026-11-01"),
    )

    with pytest.raises(PlantillaNoAprobada) as exc_info:
        servicio.enviar_plantilla("593991234567", plantilla)

    assert exc_info.value.codigo == "PLANTILLA_NO_APROBADA"
    assert len(api_simulada.mensajes_enviados) == 0


def test_envio_plantilla_con_variables_insuficientes_falla(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-04 (a): Rechaza si la cantidad de variables no coincide con la definición."""
    servicio.aprobar_plantilla("instrucciones_checkin", True)

    plantilla_incompleta = Plantilla(
        nombre="instrucciones_checkin",
        idioma="es",
        variables=("Juan", "Domo"),  # Requiere 3: nombre, propiedad, hora
    )

    with pytest.raises(VariablesPlantillaInvalidas) as exc_info:
        servicio.enviar_plantilla("593991234567", plantilla_incompleta)

    assert exc_info.value.codigo == "VARIABLES_PLANTILLA_INVALIDAS"
    assert len(api_simulada.mensajes_enviados) == 0


def test_envio_plantilla_con_variables_tipo_invalido_falla(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-04 (a): Rechaza si alguna variable no es de tipo texto."""
    servicio.aprobar_plantilla("instrucciones_checkin", True)

    plantilla_tipo_malo = Plantilla(
        nombre="instrucciones_checkin",
        idioma="es",
        variables=("Juan", "Domo", 12345),  # type: ignore[arg-type]
    )

    with pytest.raises(VariablesPlantillaInvalidas):
        servicio.enviar_plantilla("593991234567", plantilla_tipo_malo)
    assert len(api_simulada.mensajes_enviados) == 0


def test_envio_plantilla_inexistente_falla(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-04: Rechaza plantillas desconocidas."""
    plantilla_fantasma = Plantilla(
        nombre="plantilla_inexistente_xyz",
        idioma="es",
        variables=("a", "b"),
    )

    with pytest.raises(PlantillaNoAprobada):
        servicio.enviar_plantilla("593991234567", plantilla_fantasma)
    assert len(api_simulada.mensajes_enviados) == 0


def test_envio_plantilla_aprobada_exitoso(
    servicio: CanalWhatsappService, api_simulada: ApiMetaSimulada,
) -> None:
    """RF-GW-04: Envía la plantilla aprobada correctamente y registra en canal.mensajes_meta."""
    servicio.aprobar_plantilla("instrucciones_checkin", True)

    plantilla = Plantilla(
        nombre="instrucciones_checkin",
        idioma="es",
        variables=("Elena", "Cabaña Vista Sol", "14:00"),
    )
    res = servicio.enviar_plantilla("593991234567", plantilla)

    assert res.estado == "sent"
    assert len(api_simulada.mensajes_enviados) == 1

    enviado = api_simulada.mensajes_enviados[0]["payload"]
    assert enviado["type"] == "template"
    assert enviado["template"]["name"] == "instrucciones_checkin"
    params = enviado["template"]["components"][0]["parameters"]
    assert [p["text"] for p in params] == ["Elena", "Cabaña Vista Sol", "14:00"]

    meta = servicio.repositorio.obtener_mensaje_meta(res.mensaje_id)
    assert meta is not None
    assert meta.tipo == "plantilla"
    assert meta.plantilla == "instrucciones_checkin"
    assert meta.estado == "sent"
