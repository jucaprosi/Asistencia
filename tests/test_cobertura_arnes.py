# ¤bbap-glamping
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de verificación de cobertura del arnés y test de mutante muerto (Punto 6)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from scripts.arnes_glamping import (
    RUTA_COBERTURA,
    RUTA_COBERTURA_BASE,
    calcular_cobertura,
    verificar_cobertura_contra_piso,
)


def test_cobertura_base_existe_y_es_valida() -> None:
    """Verifica que el archivo de línea base de cobertura exista y contenga los pisos de las 14 salas."""
    assert RUTA_COBERTURA_BASE.is_file(), f"Falta {RUTA_COBERTURA_BASE}"
    data = json.loads(RUTA_COBERTURA_BASE.read_text(encoding="utf-8"))
    assert "piso_global" in data
    assert data["piso_global"] >= 80.0
    pisos_sala = data.get("pisos_por_sala", {})
    assert len(pisos_sala) == 14
    for sala, piso in pisos_sala.items():
        assert isinstance(piso, (int, float))
        assert piso > 0.0


def test_calcular_cobertura_con_archivo_real() -> None:
    """Verifica que calcular_cobertura extraiga métricas totales y por sala del json de pytest-cov."""
    if not RUTA_COBERTURA.is_file():
        pytest.skip("cobertura.json aún no generado por el arnés")
    medida = calcular_cobertura(RUTA_COBERTURA)
    assert "total" in medida
    assert "salas" in medida
    assert isinstance(medida["total"], float)
    assert len(medida["salas"]) == 14


def test_cobertura_cumple_piso_actual() -> None:
    """Verifica que la cobertura actual satisfaga el piso congelado."""
    if not RUTA_COBERTURA.is_file():
        pytest.skip("cobertura.json aún no generado por el arnés")
    medida = calcular_cobertura(RUTA_COBERTURA)
    codigo, mensaje = verificar_cobertura_contra_piso(medida, RUTA_COBERTURA_BASE)
    assert codigo == 0, f"Fallo de verificación de cobertura: {mensaje}"
    assert "cumplen el piso" in mensaje


def test_mutante_baja_cobertura_falla_verificacion(tmp_path: Path) -> None:
    """Test de mutante muerto: una cobertura inferior al piso debe fallar con exit code 1."""
    base_sintetica = tmp_path / "COBERTURA_BASE_MUTANTE.json"
    base_sintetica.write_text(
        json.dumps(
            {
                "piso_global": 90.0,
                "pisos_por_sala": {
                    "agente": 95.0,
                    "web_huespedes": 85.0,
                },
            }
        ),
        encoding="utf-8",
    )

    medida_baja = {
        "total": 84.5,
        "salas": {
            "agente": 89.0,  # por debajo de 95.0
            "web_huespedes": 80.0,  # por debajo de 85.0
        },
    }

    codigo, mensaje = verificar_cobertura_contra_piso(medida_baja, base_sintetica)
    assert codigo == 1, "El mutante con cobertura baja debió ser rechazado con exit code 1"
    assert "Cobertura global 84.50% por debajo del piso 90.00%" in mensaje
    assert "Sala 'agente' con cobertura 89.00% por debajo del piso 95.00%" in mensaje
    assert "Sala 'web_huespedes' con cobertura 80.00% por debajo del piso 85.00%" in mensaje
