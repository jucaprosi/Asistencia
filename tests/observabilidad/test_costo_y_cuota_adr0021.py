# ¤inferencia
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Paso 4 del ADR-0021, lado observabilidad: C2 (tope diario atómico) y C5 (una sola tabla de precios)."""
from __future__ import annotations

import threading
from decimal import Decimal
from pathlib import Path

from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config

RAIZ = Path(__file__).resolve().parents[2]


# ¤inferencia
def test_c5_observabilidad_no_tiene_precios_propios() -> None:
    for ruta in RAIZ.joinpath("features", "observabilidad").glob("*.*"):
        if ruta.suffix in (".py", ".yaml"):
            texto = ruta.read_text(encoding="utf-8")
            for prohibido in ("PRECIO_ESTANDAR", "PRECIOS_MILLON", "tabla_precios", "gemini-"):
                assert prohibido not in texto, f"{ruta.name} contiene {prohibido}"


# ¤inferencia
def test_c5_un_span_sin_costo_no_se_inventa_uno() -> None:
    servicio = ObservabilidadService(cargar_config())
    traza = servicio.iniciar_traza("m1", "c1")
    with servicio.span(traza, "agente", "llamada_modelo", modelo="desconocido", tokens_in=1000, tokens_out=1000):
        pass
    span = servicio.cerrar_traza(traza, "resuelta").spans[0]
    assert span.costo_usd is None


# ¤inferencia
def test_c5_el_costo_de_inferencia_se_guarda_tal_cual() -> None:
    servicio = ObservabilidadService(cargar_config())
    traza = servicio.iniciar_traza("m1", "c1")
    with servicio.span(traza, "agente", "llamada_modelo", tokens_in=10, tokens_out=5, costo_usd=Decimal("0.000123")):
        pass
    assert servicio.cerrar_traza(traza, "resuelta").spans[0].costo_usd == Decimal("0.000123")


# ¤inferencia
def test_c2_cuota_diaria_atomica_bajo_concurrencia() -> None:
    cuota = ObservabilidadService(cargar_config()).cuota_inferencia(tope_usd=Decimal("1.00"))
    aceptadas: list[bool] = []
    candado = threading.Lock()

    def reservar() -> None:
        resultado = cuota.reservar(Decimal("0.30"))
        with candado:
            aceptadas.append(resultado)

    hilos = [threading.Thread(target=reservar) for _ in range(10)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert aceptadas.count(True) == 3


# ¤inferencia
def test_c3_conciliar_devuelve_lo_no_gastado() -> None:
    cuota = ObservabilidadService(cargar_config()).cuota_inferencia(tope_usd=Decimal("1.00"))
    assert cuota.reservar(Decimal("0.90"))
    cuota.conciliar(Decimal("0.90"), Decimal("0.10"))
    assert cuota.reservar(Decimal("0.80"))
    assert not cuota.reservar(Decimal("0.20"))


# ¤inferencia
def test_c2_el_tope_por_defecto_sale_de_la_config() -> None:
    config = dict(cargar_config())
    config["umbrales"] = {**config["umbrales"], "costo_diario_usd": "5"}
    tope = Decimal("5")
    cuota = ObservabilidadService(config).cuota_inferencia()
    assert cuota.reservar(tope)
    assert not cuota.reservar(Decimal("0.000001"))
