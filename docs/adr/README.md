# Registro de decisiones de arquitectura (ADR)
`¤adr-glamping`

Cada decisión duradera se registra aquí. Un ADR nace en estado **Propuesto**; pasa a **Aceptado** cuando el propietario lo aprueba; **Reemplazado** cuando otro ADR lo sustituye. Las decisiones que el informe maestro (§14) deja abiertas tienen su ADR en estado Propuesto con las opciones, el criterio y lo que bloquean: **la IA no las resuelve por iniciativa propia**.

## Índice

| ADR | Título | Estado | Rastro | Bloquea |
| :--- | :--- | :--- | :--- | :--- |
| [ADR-0001](ADR-0001-construir-vs-adoptar.md) | Construir el núcleo diferencial, adoptar la capa commodity detrás de interfaces abstractas | Aceptado | `¤adr-construir-adoptar` | — |
| [ADR-0002](ADR-0002-pgvector-sobre-postgres-gestionado.md) | pgvector sobre PostgreSQL gestionado como base vectorial | Aceptado (proveedor: Neon) | `¤conocimiento-rag` | — |
| [ADR-0003](ADR-0003-api-oficial-whatsapp-cloud.md) | API oficial de WhatsApp Cloud; prohibición de librerías no oficiales | Aceptado | `¤canal-whatsapp` | — |
| [ADR-0004](ADR-0004-infraestructura-hibrida-aislada.md) | Infraestructura híbrida y aislamiento del flujo contable | Aceptado | `¤infra-hibrida` | — |
| [ADR-0005](ADR-0005-arm-construido-en-casa.md) | Construir el ARM «Jarvis» en casa | Aceptado (reevaluable) | `¤arm-jarvis` | — |
| [ADR-0006](ADR-0006-metodologia-zerag-adpa-huellas.md) | Metodología ZERAG: salas ADPA, compuertas, rastros y arnés | Aceptado | `¤adr-zerag` | — |
| [ADR-0007](ADR-0007-pms-definitivo.md) | Calendario propio en lugar de un PMS externo | Aceptado (2026-10-31) | `¤pms-conector` | — |
| [ADR-0008](ADR-0008-proveedor-capa-commodity.md) | Proveedor de la capa commodity (GoHighLevel vs Chatwoot + Attio/HubSpot + n8n) | **Propuesto** `[DECISIÓN PENDIENTE]` | `¤crm-conector` | Fase 7 |
| [ADR-0009](ADR-0009-registro-comisiones.md) | Sistema de registro de comisiones (propio vs CRM) | **Propuesto** `[DECISIÓN PENDIENTE]` | `¤comisiones` | Tablero (fase 7) |
| [ADR-0010](ADR-0010-inbox-proveedor.md) | ¿Inbox del proveedor o inbox completo de huéspedes en el panel operativo? (reformulado por ADR-0013) | **Propuesto** `[DECISIÓN PENDIENTE]` | `¤panel-operativo` | Fase 8 |
| [ADR-0011](ADR-0011-mcp-comunidad.md) | Verificación de MCP de comunidad antes de usarlos | **Propuesto** `[DECISIÓN PENDIENTE]` | `¤pms-conector` `¤crm-conector` | Implementaciones internas |
| [ADR-0012](ADR-0012-residencia-datos.md) | Residencia de datos en Ecuador | **Propuesto** `[DECISIÓN PENDIENTE]` | `¤infra-hibrida` | Fase 2 (datos reales) |
| [ADR-0013](ADR-0013-panel-operativo-propio.md) | Panel operativo propio: frontend del equipo (ventas, comisiones, Jarvis, handoff, administración) | Aceptado (2026-10-30) | `¤panel-operativo` | — (habilita RF-PAN en fases 4–7) |
| [ADR-0014](ADR-0014-decisiones-especificacion-sdd.md) | Decisiones de la especificación 0.2 para Spec-Driven Development | **Propuesto** | `¤spec-glamping` | Congelar la especificación 1.0 |

| [ADR-0018](ADR-0018-plataforma-local-de-hospedajes.md) | Plataforma local de hospedajes | Aceptado en lo funcional, con puntos abiertos | `¤spec-glamping` `¤anfitriones` | Publicar hospedajes reales |

## Plantilla

```markdown
# ADR-NNNN — Título
`¤rastro`

| Campo | Valor |
| :--- | :--- |
| Estado | Propuesto / Aceptado / Reemplazado por ADR-MMMM |
| Fecha | AAAA-MM-DD |
| Decisores | |
| Fuente | PROJECT_CONTEXT.md §N |
| Bloquea | fases / requisitos |

## Contexto
## Opciones consideradas
## Decisión
## Consecuencias
## Criterios de verificación (árbitro)
```

`¤adr-glamping/`
