# ¤conocimiento-rag
# ¤¤qa-engineer
"""Pruebas de indexación idempotente del corpus y version_hash (RF-RAG-01, US-12)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from features.conocimiento.conocimiento_service import ConocimientoService, cargar_config
from features.conocimiento.tipos import CorpusVacio, DocumentoSinCabecera


# ¤conocimiento-rag
def test_indexacion_idempotente_y_reemplazo(tmp_path: Path) -> None:
    """Verifica idempotencia y reemplazo exacto de chunks al cambiar el contenido (US-12, RF-RAG-01)."""
    # 1. Crear documento inicial
    doc1 = tmp_path / "politicas-cancelacion.md"
    doc1.write_text(
        """---
propiedad: glamping
dueno: Administrador
revisado: 2026-11-01
tipo: politicas
---
# Políticas de Cancelación
## Reembolso Total
Reembolso del 100% notificando con 7 días de anticipación.
""",
        encoding="utf-8",
    )

    servicio = ConocimientoService(cargar_config())
    resumen1 = servicio.indexar(tmp_path)
    assert resumen1.documentos == 1
    assert resumen1.chunks_nuevos > 0
    assert resumen1.chunks_reemplazados == 0

    docs_iniciales = servicio.documentos("glamping")
    assert len(docs_iniciales) == 1
    hash_original = docs_iniciales[0].version_hash

    # 2. Segunda indexación idéntica (Idempotencia)
    resumen2 = servicio.indexar(tmp_path)
    assert resumen2.documentos == 1
    assert resumen2.chunks_nuevos == 0
    assert resumen2.chunks_reemplazados == 0

    # 3. Cambio de contenido (Escenario US-12: cambio de política)
    doc1.write_text(
        """---
propiedad: glamping
dueno: Administrador
revisado: 2026-11-02
tipo: politicas
---
# Políticas de Cancelación
## Reembolso Total
Reembolso del 100% notificando con 14 días de anticipación en temporada alta.
""",
        encoding="utf-8",
    )

    resumen3 = servicio.indexar(tmp_path)
    assert resumen3.documentos == 1
    assert resumen3.chunks_reemplazados > 0
    assert resumen3.chunks_nuevos == 0

    docs_actualizados = servicio.documentos("glamping")
    assert len(docs_actualizados) == 1
    assert docs_actualizados[0].version_hash != hash_original

    # Verificar que la consulta recupera la versión nueva
    resultado = servicio.recuperar("¿Con cuántos días se reembolsa en temporada alta?", "glamping")
    textos = " ".join(f.texto for f in resultado.fragmentos)
    assert "14 días" in textos


# ¤conocimiento-rag
def test_directorio_vacio_falla_con_corpus_vacio(tmp_path: Path) -> None:
    """Un directorio sin archivos Markdown lanza la excepción tipada CorpusVacio."""
    servicio = ConocimientoService(cargar_config())
    with pytest.raises(CorpusVacio) as exc_info:
        servicio.indexar(tmp_path)
    assert "vacio" in exc_info.value.codigo


# ¤conocimiento-rag
def test_documento_sin_frontmatter_falla(tmp_path: Path) -> None:
    """Documento Markdown sin cabecera YAML obligatoria falla con DocumentoSinCabecera."""
    doc_invalido = tmp_path / "sin_cabecera.md"
    doc_invalido.write_text("# Documento sin cabecera\nTexto sin metadatos.", encoding="utf-8")

    servicio = ConocimientoService(cargar_config())
    with pytest.raises(DocumentoSinCabecera):
        servicio.indexar(tmp_path)


# ¤conocimiento-rag
def test_script_seed_knowledge_exit_code_zero() -> None:
    """El CLI scripts/seed_knowledge.py ejecuta e indexa con Exit Code 0 (RF-RAG-01)."""
    proceso = subprocess.run(
        [sys.executable, "scripts/seed_knowledge.py", "--sintetico"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert proceso.returncode == 0, f"Error en seed_knowledge: {proceso.stderr}"
    assert "Indexación completada" in proceso.stdout
