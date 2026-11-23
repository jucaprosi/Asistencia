# ¤conocimiento-rag
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de fragmentación de Markdown por secciones, encabezados y segregación (RF-RAG-02)."""
from __future__ import annotations

from features.conocimiento.chunker_internal import extraer_metadatos_cabecera, fragmentar_documento


# ¤conocimiento-rag
def test_fragmentacion_preserva_encabezados_y_propiedad() -> None:
    """Verifica que cada fragmento conserva su encabezado Markdown y metadatos de propiedad."""
    documento = """---
propiedad: glamping
dueno: Gestor
revisado: 2026-11-01
tipo: checkin
---
# Protocolo de Check-in y Check-out

## Horarios Oficiales
Hora de Check-in: a partir de las 15:00 horas.
Hora de Check-out: hasta las 11:00 horas.

## Procedimiento de Llegada
El anfitrión recibe al huésped en recepción principal.
Se verifica identidad y se entrega la llave del domo.
"""
    fragmentos = fragmentar_documento(documento, ruta="checkin.md")
    assert len(fragmentos) >= 2

    encabezados = [f["encabezado"] for f in fragmentos]
    assert "Horarios Oficiales" in encabezados
    assert "Procedimiento de Llegada" in encabezados

    for f in fragmentos:
        assert f["propiedad_id"] == "glamping"
        assert f["texto"].strip()


# ¤conocimiento-rag
def test_fragmentacion_con_solapamiento_en_secciones_largas() -> None:
    """Secciones largas se dividen respetando límites y solapamiento del 10%."""
    parrafos_largos = "\n\n".join(
        f"Párrafo de prueba {i}: Información detallada sobre las normas y procedimientos del glamping "
        f"para asegurar el descanso y disfrute en la naturaleza."
        for i in range(40)
    )
    documento = f"""---
propiedad: depto-centro-01
dueno: Administrador
revisado: 2026-11-01
tipo: politicas
---
# Normas Generales

## Sección Extensa
{parrafos_largos}
"""
    # Con tokens_max=100 para forzar múltiples chunks en la misma sección
    fragmentos = fragmentar_documento(
        documento,
        ruta="normas.md",
        tokens_min=50,
        tokens_max=100,
        solapamiento=0.10,
    )
    assert len(fragmentos) > 1

    # Todos los fragmentos de la sección conservan el mismo encabezado
    for f in fragmentos:
        assert f["encabezado"] == "Sección Extensa"
        assert f["propiedad_id"] == "depto-centro-01"

    # Verificar solapamiento: texto del final del primer chunk aparece en el inicio del segundo
    texto_1 = fragmentos[0]["texto"]
    texto_2 = fragmentos[1]["texto"]
    palabras_1 = set(texto_1.split()[-10:])
    palabras_2 = set(texto_2.split()[:20])
    assert len(palabras_1 & palabras_2) > 0


# ¤conocimiento-rag
def test_segregacion_estricta_sin_mezcla_de_propiedades() -> None:
    """Los fragmentos nunca mezclan propiedades distintas en un mismo chunk."""
    doc_a = """---
propiedad: glamping
dueno: Admin
revisado: 2026-11-01
tipo: politicas
---
## Domos
Información exclusiva de glamping.
"""
    doc_b = """---
propiedad: depto-centro-01
dueno: Admin
revisado: 2026-11-01
tipo: politicas
---
## Edificio
Información exclusiva de departamento urbano.
"""
    chunks_a = fragmentar_documento(doc_a, "glamping.md")
    chunks_b = fragmentar_documento(doc_b, "depto.md")

    assert all(c["propiedad_id"] == "glamping" for c in chunks_a)
    assert all(c["propiedad_id"] == "depto-centro-01" for c in chunks_b)
