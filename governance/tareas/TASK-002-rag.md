```toml
id = "TASK-002"
titulo = "RAG sobre docs/negocio/ en pgvector con set dorado y respuesta «no lo sé»"
fase = 2
estado = "pendiente"
sala = ["conocimiento"]
rastro = ["¤conocimiento-rag"]
rol = "¤¤data-engineer"
depende_de = ["TASK-001"]
bloqueada_por = ["S-03", "ADR-0012"]
propiedad = ["features/conocimiento/**", "scripts/seed_knowledge.py", "evals/set_dorado.jsonl", "tests/conocimiento/**", "docs/negocio/**"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); scripts/run_evals.py --suite rag con fidelidad ≥ 95 %, abstención ≥ 90 %, 0 alucinaciones de precio/política; RNF-04"
```

# TASK-002 — RAG
`¤conocimiento-rag`

## Objetivo
El agente responde preguntas de políticas, precios de referencia, check-in y atractivos con base en `docs/negocio/`, filtrado por propiedad, y dice que no lo sabe cuando no hay soporte.

## Requisitos cubiertos
RF-RAG-01..06. Invariantes: `INV_SIN_FUGA_ENTRE_PROPIEDADES`, `INV_NO_LO_SE`.

## Entregables
1. `scripts/seed_knowledge.py` idempotente con metadatos por documento.
2. Chunking por secciones (400–600 tokens, solapamiento 10 %), encabezado conservado.
3. Recuperación híbrida HNSW + BM25 con filtro obligatorio por `propiedad_id`/`global`.
4. Umbral de «no lo sé» en `config_conocimiento.yaml`; citación de chunks en la traza.
5. `evals/set_dorado.jsonl`: ≥ 100 preguntas con respuesta de referencia y ≥ 30 preguntas trampa fuera del corpus, redactadas con el negocio.
6. Checklist de `docs/negocio/README.md` completa (S-03) con dueño y fecha por documento.

## Criterios de fase completada
- OP-04 ≥ 95 %, OP-05 ≥ 90 %, 0 alucinaciones de precio/política.
- RNF-04: P95 ≤ 150 ms en el benchmark del arnés.
- ADR-0012 aceptado antes de indexar datos reales (hasta entonces, corpus sintético).
