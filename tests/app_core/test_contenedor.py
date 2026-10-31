"""El pasillo central construye las once compuertas con secretos resueltos y enlaza los receptores del canal."""
from __future__ import annotations

import pytest

from app_core.app_core_service import ConfiguracionInvalida, Contenedor, construir, resolver_secretos
from app_core.main import crear_app, main, salud
from features.canal_whatsapp.canal_whatsapp_service import Canal

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "x",
    "META_VERIFY_TOKEN": "x",
    "META_APP_SECRET": "x",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


def test_resolver_secretos_sustituye_y_respeta_defectos() -> None:
    config = {"a": "${UNO}", "b": "${DOS:-por_defecto}", "c": ["${UNO}", 3], "d": {"e": "${TRES:-}"}}
    resuelto = resolver_secretos(config, {"UNO": "valor"})
    assert resuelto == {"a": "valor", "b": "por_defecto", "c": ["valor", 3], "d": {"e": ""}}


def test_resolver_secretos_nombra_la_variable_faltante_sin_exponer_valores() -> None:
    with pytest.raises(ConfiguracionInvalida) as info:
        resolver_secretos({"clave": "${SECRETO_X}"}, {})
    assert "SECRETO_X" in str(info.value)


def test_construir_devuelve_las_once_compuertas_enlazadas() -> None:
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    assert isinstance(contenedor, Contenedor)
    compuertas = ("observabilidad", "seguridad", "conocimiento", "pms", "crm", "comisiones", "canal", "arm",
                  "herramientas", "agente", "panel")
    assert all(getattr(contenedor, nombre) is not None for nombre in compuertas)
    receptores = contenedor.canal.receptores()
    assert receptores[Canal.HUESPEDES] == contenedor.agente.atender
    assert receptores[Canal.VENDEDORES] == contenedor.arm.procesar
    assert contenedor.config_app["aplicacion"]["entorno"] == "prueba"


def test_catalogo_de_herramientas_declaradas_coincide_con_el_prd() -> None:
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    declaradas = set(contenedor.herramientas.catalogo_declarado())
    esperadas = {
        "consultar_disponibilidad", "cotizar", "crear_reserva_preliminar", "obtener_instrucciones_checkin",
        "reportar_incidencia", "solicitar_humano", "buscar_contacto_crm", "crear_oportunidad_crm",
        "registrar_venta", "consultar_comision_propia",
    }
    assert declaradas == esperadas


def test_salud_y_health_http() -> None:
    contenedor = construir(entorno=ENTORNO_PRUEBA)
    assert salud(contenedor) == {"estado": "ok", "version": "0.1.0", "entorno": "prueba"}
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    cliente = fastapi_testclient.TestClient(crear_app(contenedor))
    respuesta = cliente.get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "ok"


def test_main_comprobar_lee_config_app(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--comprobar"]) == 0
    assert "12 salas declaradas" in capsys.readouterr().out
