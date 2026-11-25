# ¤herramientas-mcp
# ¤seguridad-canal
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-408: anotaciones ``x-pii`` y ``x-pii-exento`` en los esquemas de ``salida`` (decisión A1, H-1).

Recorre los 14 esquemas de ``features/herramientas_glamping/esquemas/`` con un recorrido propio
(``properties`` e ``items``) que arma rutas ``a.b`` y ``lista[]``; leer ``x-pii`` en producción es de T-407.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Iterator

import pytest

from features.seguridad.seguridad_service import SeguridadService
from tests.conftest import RAIZ

ESQUEMAS = RAIZ / "features" / "herramientas_glamping" / "esquemas"

# Copia de TIPOS_PII (features/seguridad/pii_internal.py): una prueba de otra sala no importa un _internal ajeno.
TIPOS_PII = ("nombre", "telefono", "correo", "documento", "tarjeta", "direccion")

# R1: ruta de salida -> anotación exacta.
R1 = {
    ("obtener_instrucciones_checkin", "contacto_emergencia"): {"x-pii": "telefono"},
    ("obtener_instrucciones_checkin", "direccion"): {"x-pii": "direccion"},
    ("obtener_instrucciones_checkin", "wifi.clave_ref"): {"x-pii-exento": True},
    ("solicitar_humano", "asignado_a"): {"x-pii": "nombre"},
    ("reportar_incidencia", "gestor_asignado"): {"x-pii": "nombre"},
    ("crear_reserva_preliminar", "codigo_reserva"): {"x-pii-exento": True},
}

# A8: nodos de salida con pattern en main (14) más codigo_reserva.
PATTERNS_MEDIDOS = {
    ("consultar_comision_propia", "validada"),
    ("consultar_comision_propia", "pendiente"),
    ("consultar_comision_propia", "periodo"),
    ("consultar_disponibilidad", "alternativas[].desde"),
    ("consultar_disponibilidad", "alternativas[].hasta"),
    ("cotizar", "total"),
    ("cotizar", "desglose[].monto"),
    ("obtener_instrucciones_checkin", "wifi.clave_ref"),
    ("registrar_venta", "ticket"),
    ("registrar_venta", "comision_estimada"),
    ("reportar_incidencia", "incidencia_id"),
    ("reportar_resultado_estadia", "solicitud"),
    ("responder_solicitud", "solicitud"),
    ("solicitar_reserva", "solicitud"),
}
PATTERNS_ESPERADOS = PATTERNS_MEDIDOS | {("crear_reserva_preliminar", "codigo_reserva")}


def _esquemas() -> dict[str, dict[str, Any]]:
    return {
        ruta.stem: json.loads(ruta.read_text(encoding="utf-8"))
        for ruta in sorted(ESQUEMAS.glob("*.json"))
    }


def _nodos(nodo: dict[str, Any], ruta: str = "") -> Iterator[tuple[str, dict[str, Any]]]:
    """Recorre ``properties`` e ``items``; cada hijo se emite con su ruta ``a.b`` o ``lista[]``."""
    for clave, hijo in (nodo.get("properties") or {}).items():
        sub = f"{ruta}.{clave}" if ruta else clave
        yield sub, hijo
        yield from _nodos(hijo, sub)
    items = nodo.get("items")
    if isinstance(items, dict):
        sub = f"{ruta}[]"
        yield sub, items
        yield from _nodos(items, sub)


def _salida(herramienta: str, ruta: str) -> dict[str, Any]:
    return dict(_nodos(_esquemas()[herramienta]["salida"]))[ruta]


def _pattern_codigo_reserva() -> str:
    nodo = _salida("crear_reserva_preliminar", "codigo_reserva")
    assert "pattern" in nodo, "codigo_reserva debe declarar un pattern (R7)"
    return nodo["pattern"]


def test_hay_14_esquemas() -> None:
    assert len(_esquemas()) == 14


def test_r1_anotaciones_obligatorias() -> None:
    for (herramienta, ruta), esperado in R1.items():
        nodo = _salida(herramienta, ruta)
        anotaciones = {k: v for k, v in nodo.items() if k in ("x-pii", "x-pii-exento")}
        assert anotaciones == esperado, f"{herramienta}.{ruta}: {anotaciones} != {esperado}"
    # Solo esas rutas llevan anotación.
    anotadas = {
        (h, ruta)
        for h, esquema in _esquemas().items()
        for ruta, nodo in _nodos(esquema["salida"])
        if "x-pii" in nodo or "x-pii-exento" in nodo
    }
    assert anotadas == set(R1)


def test_r1_incidencia_id_sin_exencion_fugitiva() -> None:
    nodo = _salida("reportar_incidencia", "incidencia_id")
    assert "x-pii" not in nodo
    if nodo.get("x-pii-exento"):
        patron = re.compile(nodo["pattern"])
        for valor in ("I-2026-123456", "I-2026-12345678", "I-2026-1234567890"):
            assert not patron.fullmatch(valor), valor


def test_r2_exento_exige_pattern() -> None:
    for herramienta, esquema in _esquemas().items():
        for ruta, nodo in _nodos(esquema["salida"]):
            if "x-pii-exento" in nodo:
                assert nodo["x-pii-exento"] is True, f"{herramienta}.{ruta}"
                assert isinstance(nodo.get("pattern"), str), f"{herramienta}.{ruta} sin pattern"
                re.compile(nodo["pattern"])


def test_r3_tipo_valido() -> None:
    for herramienta, esquema in _esquemas().items():
        for ruta, nodo in _nodos(esquema["salida"]):
            if "x-pii" in nodo:
                assert nodo["x-pii"] in TIPOS_PII, f"{herramienta}.{ruta}: {nodo['x-pii']!r}"


def test_r4_solo_en_salida() -> None:
    for herramienta, esquema in _esquemas().items():
        for ruta, nodo in _nodos(esquema["entrada"]):
            assert "x-pii" not in nodo and "x-pii-exento" not in nodo, f"{herramienta}.{ruta}"


def test_r5_sin_contradiccion() -> None:
    for herramienta, esquema in _esquemas().items():
        for lado in ("entrada", "salida"):
            for ruta, nodo in _nodos(esquema[lado]):
                assert not ("x-pii" in nodo and "x-pii-exento" in nodo), f"{herramienta}.{lado}.{ruta}"


def test_r6_sin_patterns_nuevos_salvo_codigo_reserva() -> None:
    con_pattern = {
        (h, ruta)
        for h, esquema in _esquemas().items()
        for ruta, nodo in _nodos(esquema["salida"])
        if "pattern" in nodo
    }
    assert con_pattern == PATTERNS_ESPERADOS


def test_r7_patterns_aceptan_formatos_medidos() -> None:
    patron = re.compile(_pattern_codigo_reserva())
    for valor in ("RES-2026-0001", "RES-PREL-999"):
        assert patron.fullmatch(valor), valor
    for valor in (
        "0991234567",
        "Juan Pérez",
        "RES-1712345678",
        "RES-0991234567",
        "RES-593-99111-2233",
        "RES-12345678-12345678",
        "RES-0991-112233",
    ):
        assert not patron.fullmatch(valor), valor


@pytest.fixture(scope="module")
def seguridad() -> SeguridadService:
    return SeguridadService({"pii": {"clave_boveda": "clave-de-prueba-t408"}})


def _digitos(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789") for _ in range(n))


def test_r8_exento_por_forma_intacto_ante_el_detector(seguridad: SeguridadService) -> None:
    patron = re.compile(_pattern_codigo_reserva())
    rng = random.Random(408)
    corpus = [
        "0991234567",
        "Juan Pérez",
        "RES-1712345678",
        "RES-0991234567",
        "RES-593-99111-2233",
        "RES-12345678-12345678",
        "RES-0991-112233",
    ]
    for _ in range(200):
        corpus.append(f"RES-{_digitos(rng, 4)}-{_digitos(rng, 4)}")
    for _ in range(200):
        corpus.append(f"RES-{_digitos(rng, 4)}-{_digitos(rng, 5)}")
    for _ in range(200):
        corpus.append(f"RES-PREL-{_digitos(rng, rng.randint(1, 6))}")
    for _ in range(200):
        corpus.append(f"RES-{_digitos(rng, 4)}-{_digitos(rng, 6)}")
    for _ in range(200):
        corpus.append(f"RES-{_digitos(rng, 3)}-{_digitos(rng, 5)}-{_digitos(rng, 4)}")
    for _ in range(200):
        corpus.append(f"RES-{_digitos(rng, 8)}-{_digitos(rng, 8)}")
    aceptados = [v for v in corpus if patron.fullmatch(v)]
    assert aceptados, "el pattern no acepta ningún valor del corpus"
    for valor in aceptados:
        assert seguridad.tokenizar(valor, "conv-408-r8") == valor, valor


def _reglas_desde_esquema(herramienta: str) -> tuple[list[str], dict[str, str]]:
    campos_pii: list[str] = []
    exentos: dict[str, str] = {}
    for ruta, nodo in _nodos(_esquemas()[herramienta]["salida"]):
        if "x-pii" in nodo:
            campos_pii.append(ruta)
        if nodo.get("x-pii-exento"):
            exentos[ruta] = nodo["pattern"]
    return campos_pii, exentos


def test_integracion_con_tokenizar_estructura(seguridad: SeguridadService) -> None:
    telefono = "099 111 2233"
    direccion = "Hacienda La Merced, Angochagua"
    checkin = {
        "propiedad": "Glamping Imbabura",
        "direccion": direccion,
        "hora_checkin": "15:00",
        "acceso": ["Portón norte"],
        "wifi": {"red": "GI-Guest", "clave_ref": "[[SECRETO:wifi_abc123]]"},
        "normas": ["Silencio desde las 22:00"],
        "contacto_emergencia": telefono,
    }
    pii, exentos = _reglas_desde_esquema("obtener_instrucciones_checkin")
    salida = seguridad.tokenizar_estructura(checkin, "conv-408-a7", campos_pii=pii, campos_exentos=exentos)
    assert telefono not in json.dumps(salida, ensure_ascii=False)
    assert direccion not in json.dumps(salida, ensure_ascii=False)
    assert salida["contacto_emergencia"] != telefono
    assert salida["direccion"] != direccion
    assert salida["wifi"]["clave_ref"] == "[[SECRETO:wifi_abc123]]"

    pii, exentos = _reglas_desde_esquema("crear_reserva_preliminar")
    base = {"estado": "preliminar", "expira_en": "2026-11-26T10:00:00+00:00"}
    ok = seguridad.tokenizar_estructura(
        {"codigo_reserva": "RES-2026-0001", **base}, "conv-408-a7", campos_pii=pii, campos_exentos=exentos
    )
    assert ok["codigo_reserva"] == "RES-2026-0001"
    fuera = seguridad.tokenizar_estructura(
        {"codigo_reserva": "RES-593-99111-2233", **base}, "conv-408-a7", campos_pii=pii, campos_exentos=exentos
    )
    assert re.fullmatch(r"RES-\[TELEFONO_\d+\]", fuera["codigo_reserva"]), fuera["codigo_reserva"]
