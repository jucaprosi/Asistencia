# ¤conocimiento-rag
# ¤¤qa-engineer
"""Pruebas de recuperación híbrida, aislamiento RLS y rendimiento P95 <= 150 ms (RF-RAG-03, RNF-04, INV_SIN_FUGA_ENTRE_PROPIEDADES)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from features.conocimiento.conocimiento_service import ConocimientoService, cargar_config
from features.conocimiento.tipos import ConsultaSinPropiedad


# ¤conocimiento-rag
@pytest.fixture
def servicio_con_datos(tmp_path: Path) -> ConocimientoService:
    """Instancia un servicio de conocimiento con documentos para múltiples propiedades."""
    doc_glamping = tmp_path / "glamping.md"
    doc_glamping.write_text(
        """---
propiedad: glamping
dueno: Admin
revisado: 2026-11-01
tipo: politicas
---
# Experiencia Glamping
## Domos Geodésicos
Los domos cuentan con jacuzzi privado y vista al volcán Imbabura. Cama king-size y calefacción ecológica.
""",
        encoding="utf-8",
    )

    doc_depto = tmp_path / "departamentos.md"
    doc_depto.write_text(
        """---
propiedad: depto-centro-01
dueno: Gestor
revisado: 2026-11-01
tipo: politicas
---
# Departamento Centro
## Edificio Los Ceibos
Departamento de dos dormitorios en el piso 4 con parqueadero subterráneo asignado espacio #12.
""",
        encoding="utf-8",
    )

    doc_global = tmp_path / "politicas.md"
    doc_global.write_text(
        """---
propiedad: global
dueno: Admin
revisado: 2026-11-01
tipo: politicas
---
# Políticas Generales
## Cancelaciones
Reembolso total notificando con al menos 7 días de anticipación.
""",
        encoding="utf-8",
    )

    servicio = ConocimientoService(cargar_config())
    servicio.indexar(tmp_path)
    return servicio


# ¤conocimiento-rag
def test_aislamiento_rls_sin_fuga_entre_propiedades(servicio_con_datos: ConocimientoService) -> None:
    """Verifica que una consulta sobre 'glamping' jamás devuelve fragmentos de 'depto-centro-01' (INV_SIN_FUGA_ENTRE_PROPIEDADES)."""
    # Consulta sobre glamping
    res_glamping = servicio_con_datos.recuperar("¿Tienen jacuzzi?", propiedad_id="glamping")
    assert res_glamping.suficiente
    propiedades_recuperadas = {f.propiedad_id for f in res_glamping.fragmentos}
    assert "depto-centro-01" not in propiedades_recuperadas
    assert propiedades_recuperadas <= {"glamping", "global"}

    # Consulta que menciona términos del departamento, pero filtrada por glamping
    res_intento_fuga = servicio_con_datos.recuperar("parqueadero subterráneo edificio Los Ceibos", propiedad_id="glamping")
    propiedades_fuga = {f.propiedad_id for f in res_intento_fuga.fragmentos}
    assert "depto-centro-01" not in propiedades_fuga


# ¤conocimiento-rag
def test_consulta_sin_propiedad_falla_coercitivamente(servicio_con_datos: ConocimientoService) -> None:
    """Consultar con propiedad_id=None debe lanzar ConsultaSinPropiedad para evitar fuga involuntaria."""
    with pytest.raises(ConsultaSinPropiedad):
        servicio_con_datos.recuperar("consulta general", propiedad_id=None)


# ¤conocimiento-rag
def test_recuperacion_hibrida_y_umbral_suficiente(servicio_con_datos: ConocimientoService) -> None:
    """Verifica ranking híbrido y que preguntas no soportadas marcan suficiente=False."""
    # Pregunta con soporte pleno
    res_ok = servicio_con_datos.recuperar("¿Cuál es la política de cancelación con reembolso total?", propiedad_id="glamping")
    assert res_ok.suficiente
    assert res_ok.mejor_puntuacion >= 0.55
    assert len(res_ok.fragmentos) > 0

    # Pregunta sobre tema inexistente (debe abstenerse)
    res_inexistente = servicio_con_datos.recuperar("¿Tienen helipuerto y casino con mesas de poker?", propiedad_id="glamping")
    assert not res_inexistente.suficiente


# ¤conocimiento-rag
def test_benchmark_rendimiento_p95_menor_a_150ms(servicio_con_datos: ConocimientoService) -> None:
    """Evalúa que la latencia P95 sea estrictamente menor o igual a 150 ms (RNF-04)."""
    consultas = [
        "¿Cuáles son los domos geodésicos?",
        "¿Hay jacuzzi privado disponible?",
        "¿Cuál es la vista al volcán Imbabura?",
        "¿Qué incluye la cama king-size?",
        "¿Tienen calefacción ecológica?",
        "¿Cuál es el plazo de cancelación para reembolso?",
        "¿Cómo funciona la política de 7 días?",
        "¿Hay opciones para hospedaje familiar?",
        "¿Se admiten cancelaciones?",
        "¿Cuáles son las políticas generales?",
    ] * 10  # 100 consultas para calcular percentil 95 realista

    latencias_ms: list[float] = []
    for q in consultas:
        t0 = time.time()
        servicio_con_datos.recuperar(q, propiedad_id="glamping")
        latencia = (time.time() - t0) * 1000.0
        latencias_ms.append(latencia)

    latencias_ms.sort()
    idx_p95 = int(len(latencias_ms) * 0.95)
    p95 = latencias_ms[idx_p95]

    assert p95 <= 150.0, f"Latencia P95 excedió el límite: {p95:.2f} ms > 150 ms"
