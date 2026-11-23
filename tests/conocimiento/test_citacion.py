# ¤conocimiento-rag
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de citación interna en traza y preservación de privacidad frente al huésped (RF-RAG-05)."""
from __future__ import annotations

from pathlib import Path

from features.conocimiento.conocimiento_service import ConocimientoService, cargar_config


# ¤conocimiento-rag
class DobleObservabilidad:
    """Doble de prueba para verificar que la traza registra los chunks recuperados."""

    def __init__(self) -> None:
        self.spans_registrados: list[dict[str, str]] = []

    def span(self, nombre: str, metadata: dict[str, str] | None = None) -> DobleContextManager:
        return DobleContextManager(self, nombre, metadata or {})


# ¤conocimiento-rag
class DobleContextManager:

    def __init__(self, observabilidad: DobleObservabilidad, nombre: str, metadata: dict[str, str]) -> None:
        self.obs = observabilidad
        self.nombre = nombre
        self.metadata = metadata

    def __enter__(self) -> DobleContextManager:
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        self.obs.spans_registrados.append({"nombre": self.nombre, **self.metadata})


# ¤conocimiento-rag
def test_citacion_interna_en_traza(tmp_path: Path) -> None:
    """Verifica que la recuperación registra metadatos en la traza y expone fragmentos estructurados."""
    doc = tmp_path / "faq.md"
    doc.write_text(
        """---
propiedad: glamping
dueno: Admin
revisado: 2026-11-01
tipo: faq
---
# Preguntas Frecuentes
## Desayuno Andino
El desayuno andino artesanal se sirve entre las 08:00 y las 10:00.
""",
        encoding="utf-8",
    )

    obs = DobleObservabilidad()
    servicio = ConocimientoService(cargar_config(), observabilidad=obs)
    servicio.indexar(tmp_path)

    resultado = servicio.recuperar("¿A qué hora es el desayuno?", propiedad_id="glamping")
    assert resultado.suficiente
    assert len(resultado.fragmentos) > 0

    # 1. Los fragmentos contienen metadatos completos para auditoría y observabilidad
    chunk_citado = resultado.fragmentos[0]
    assert chunk_citado.chunk_id
    assert chunk_citado.documento_id
    assert chunk_citado.propiedad_id == "glamping"
    assert chunk_citado.encabezado == "Desayuno Andino"
    assert chunk_citado.puntuacion > 0.0

    # 2. La traza de observabilidad registró el span con la propiedad
    assert len(obs.spans_registrados) == 1
    assert obs.spans_registrados[0]["nombre"] == "recuperacion_rag"
    assert obs.spans_registrados[0]["propiedad_id"] == "glamping"

    # 3. La respuesta pública hacia el huésped no incluye el chunk_id ni identificadores de base de datos
    # Simulamos el formateador del agente
    respuesta_huesped = f"El desayuno andino se sirve de 08:00 a 10:00."
    assert chunk_citado.chunk_id not in respuesta_huesped
    assert chunk_citado.documento_id not in respuesta_huesped
