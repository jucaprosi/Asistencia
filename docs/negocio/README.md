# Corpus del negocio para el RAG — checklist de entrega
`¤negocio-glamping` `¤conocimiento-rag`

El repositorio es público, así que esta carpeta solo guarda esta lista. El corpus real vive en `CORPUS_DIR`, fuera del repositorio, y es la **fuente del conocimiento** que indexa `scripts/seed_knowledge.py` (TASK-002). Cada archivo es Markdown con secciones claras (encabezados `##`), porque el chunking se hace por sección. Cada documento declara en su cabecera la propiedad a la que aplica (`global`, `glamping` o el identificador del departamento), el dueño y la fecha de la última revisión: lo que no esté aquí, el asistente **no lo afirma** (invariante `INV_NO_LO_SE`).

El supuesto S-03 del PRD se considera cumplido cuando toda fila obligatoria está en estado `entregado`.

| Archivo | Propiedad | Contenido mínimo | Dueño | Obligatorio para | Estado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `glamping.md` | `glamping` | Descripción, ubicación y cómo llegar, unidades y capacidad, qué incluye, horarios, normas, clima y qué llevar, contacto humano. | Administrador | Fase 1 (prompt) y 2 | pendiente |
| `departamentos.md` | uno por departamento (o `departamentos/<id>.md`) | Edificio, piso, capacidad, zona, gestor, normas del condominio, parqueo, horarios de limpieza. Sin códigos de acceso (viven cifrados en el PMS/`seguridad`). | Gestor de cada zona | Fase 4 | pendiente |
| `precios-y-temporadas.md` | `global` + secciones por propiedad | Temporadas, reglas de precio por día de semana y eventos, mínimos de noches, descuentos. **Referencia**: la tarifa vigente la da el PMS. | Administrador | Fase 2 | pendiente |
| `politicas-cancelacion.md` | `global` + excepciones por propiedad | Plazos, porcentajes de reembolso, cambios de fecha, no-show. | Administrador | Fase 2 | pendiente |
| `checkin-checkout.md` | por propiedad | Horarios, procedimiento de llegada y salida, llegadas tardías, entrega de llaves, qué revisar al salir. | Gestor | Fase 2 y 4 | pendiente |
| `atractivos-turisticos.md` | `glamping` y por zona | Lugares, distancias, horarios, recomendaciones, transporte. | Administrador | Fase 2 | pendiente |
| `faq-huespedes.md` | `global` | Preguntas frecuentes con respuesta aprobada. | Administrador | Fase 2 | pendiente |
| `faq-vendedores.md` | `global` | Cómo reportar una venta, qué datos incluir, cómo se calcula la comisión, períodos de pago. Lo usa el ARM para responder dudas. | Líder comercial | Fase 6 | pendiente |
| `aviso-privacidad.md` | `global` | Texto que el asistente ofrece en el primer contacto, según ADR-0012. | Propietario / legal | Fase 2 (si ADR-0012 lo exige) | pendiente |

## Formato de cabecera

```markdown
---
propiedad: glamping          # global | glamping | depto-centro-01 | ...
dueno: Nombre Apellido
revisado: 2026-11-15
---
```

## Regla de actualización
Un cambio en cualquier documento exige reindexar (`scripts/seed_knowledge.py`) y pasar el set dorado; el arnés lo hace. Si cambia un precio o una política, se añade o actualiza una pregunta del set dorado que lo cubra.

`¤negocio-glamping/`
