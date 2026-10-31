# Módulo `conocimiento` — RAG sobre pgvector
`¤conocimiento-rag`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/conocimiento/` (+ `docs/negocio/` como datos, `scripts/seed_knowledge.py` como CLI de la sala) |
| Compuerta | `conocimiento_service.py` → `ConocimientoService` |
| Privados | `chunker_internal.py`, `indexador_internal.py`, `recuperador_internal.py`, `evaluador_internal.py`, `embeddings_internal.py`, `tipos.py` |
| Config | `config_conocimiento.yaml` |
| Rol | `¤¤data-engineer` |
| Requisitos | RF-RAG-01..06 · RNF-04 · INV_SIN_FUGA_ENTRE_PROPIEDADES, INV_NO_LO_SE |
| Tarea | TASK-002 |
| Decisión | Construir; pgvector gestionado (ADR-0002); proveedor Neon/Render pendiente |

## Propósito
Indexar el corpus del negocio y recuperar fragmentos con filtro obligatorio por propiedad, devolviendo puntuación y fuente para que el agente cite en la traza y se abstenga sin soporte.

## Tipos del dominio

```python
@dataclass(frozen=True)
class Documento: documento_id: str; ruta: str; propiedad_id: str; tipo: str; dueno: str; revisado: date; version_hash: str
@dataclass(frozen=True)
class Fragmento: chunk_id: str; documento_id: str; propiedad_id: str; encabezado: str; texto: str; puntuacion: float; orden: int
@dataclass(frozen=True)
class ResultadoRecuperacion: fragmentos: tuple[Fragmento, ...]; mejor_puntuacion: float; suficiente: bool   # suficiente = sobre umbral
@dataclass(frozen=True)
class ResumenIndexacion: documentos: int; chunks_nuevos: int; chunks_reemplazados: int; duracion_ms: int
```

## Compuerta

```python
class ConocimientoService:
    def indexar(self, raiz: Path = Path("docs/negocio")) -> ResumenIndexacion: ...             # idempotente (RF-RAG-01)
    def recuperar(self, consulta: str, propiedad_id: str | None, k: int | None = None) -> ResultadoRecuperacion: ...  # híbrida (RF-RAG-03)
    def documentos(self, propiedad_id: str | None = None) -> tuple[Documento, ...]: ...
    def evaluar(self, set_dorado: Path) -> dict[str, float]: ...                               # fidelidad, abstención, alucinaciones
```

## Configuración (`config_conocimiento.yaml`)
`db_url: ${CONOCIMIENTO_DB_URL}`, `embeddings {proveedor, modelo, dimension}`, `chunking {tokens_min: 400, tokens_max: 600, solapamiento: 0.10}`, `recuperacion {k: 6, peso_vectorial: 0.6, peso_bm25: 0.4, umbral_suficiente: 0.55, indice: hnsw {m: 16, ef_construction: 64}}`, `set_dorado: evals/set_dorado.jsonl`, `umbrales {fidelidad: 0.95, abstencion: 0.90, alucinaciones_precio_politica: 0}`.

## Compuertas que consume
`observabilidad` (span de recuperación). El modelo de embeddings es dependencia externa propia de la sala.

## Errores
`CorpusVacio`, `DocumentoSinCabecera` (falta `propiedad`/`dueno`/`revisado`), `IndiceNoDisponible`, `ConsultaSinPropiedad` (si la política exige filtro y no llega).

## Persistencia (`esquema conocimiento`)
`documentos(documento_id PK, ruta, propiedad_id, tipo, dueno, revisado, version_hash, indexado_en)`; `chunks(chunk_id PK, documento_id FK, propiedad_id, encabezado, texto, embedding vector(d), tsv tsvector, orden)` con índices HNSW (coseno) y GIN; RLS por `propiedad_id`.

## Tests (árbitro)
`tests/conocimiento/test_indexacion.py`, `test_chunking.py`, `test_recuperacion.py` (incluye benchmark P95), `test_citacion.py`; `scripts/run_evals.py --suite rag`.

`¤conocimiento-rag/`
