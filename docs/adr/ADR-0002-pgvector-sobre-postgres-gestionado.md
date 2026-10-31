# ADR-0002 — pgvector sobre PostgreSQL gestionado como base vectorial
`¤conocimiento-rag`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado. Proveedor concreto (Neon vs Render) **pendiente**, se fija en la fase 0 y queda sujeto a [ADR-0012](ADR-0012-residencia-datos.md) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §5.1, §9.1 |
| Bloquea | Fase 0 (elección del proveedor) |

## Contexto
El RAG indexa documentos del negocio (políticas, precios, check-in, atractivos) con filtro por propiedad. El volumen esperado es de miles a decenas de miles de chunks, no millones. El sistema ya necesita PostgreSQL para historial, ARM, comisiones y auditoría.

## Opciones consideradas
1. Base vectorial dedicada (Qdrant, Weaviate, Pinecone).
2. **pgvector sobre el PostgreSQL gestionado que ya se necesita.**
3. Índice en memoria (FAISS) dentro del contenedor.

## Decisión
Opción 2. El informe cita latencias P95 de 10–50 ms bajo 10 M de vectores y < 10 ms con HNSW a 50 k vectores; el corpus de este proyecto está muy por debajo. Se hereda seguridad, backups, PITR y RLS de PostgreSQL, sin un servicio adicional que operar desde un PC con disco único.

## Consecuencias
- Recuperación híbrida (HNSW + BM25 con `tsvector`) en la misma base.
- El filtro por `propiedad_id` y la RLS viven en la base, no en el código.
- Si el corpus superara ~1 M de chunks o se exigiera latencia < 5 ms, se reabre este ADR.

## Criterios de verificación (árbitro)
- `tests/conocimiento/test_recuperacion.py`: P95 ≤ 150 ms con ≤ 50 000 chunks (RNF-04).
- `tests/seguridad/test_rls.py`: ninguna consulta con `propiedad_id` A devuelve filas de B.
- Proveedor fijado en la fase 0 con PITR ≥ 7 días documentado en `INVARIANTS.md`.

`¤conocimiento-rag/`
