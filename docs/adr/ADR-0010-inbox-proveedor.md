# ADR-0010 — ¿Inbox del proveedor o inbox completo de huéspedes en el panel operativo?
`¤panel-operativo`

> **Reformulado por [ADR-0013](ADR-0013-panel-operativo-propio.md) (2026-10-30):** la bandeja de handoff por zona existe en el panel operativo propio desde la fase 4 en cualquier caso. Lo que queda por decidir es si las conversaciones de huéspedes **fuera** de handoff (historial completo, búsqueda, etiquetas) se consultan en el inbox del proveedor de CRM o si el panel incorpora un inbox completo en la fase 8. El texto original se conserva abajo como contexto.

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado** (decisión del propietario, 2026-11-03) |
| Fecha | 2026-11-03 |
| Decisores | Propietario del proyecto; gestores de propiedad |
| Fuente | Solicitud formal de Glamping Imbabura (alineada al PMV); [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §5.6, §12 (fase 8), §14.4 |
| Bloquea | — (desbloquea la fase 8 / T-701) |

## Contexto
El handoff a humano por zona (CU-08) necesita una bandeja donde el gestor vea la conversación, la propiedad y el resumen, y pueda devolver el control al agente. El inbox del proveedor (ADR-0008) lo cubre; con volumen bajo, un panel propio mínimo podría evitar la licencia.

## Opciones consideradas
1. Inbox del proveedor (sin fase 8).
2. **Inbox completo de huéspedes en el panel operativo propio** (fase 8 / T-701): bandeja por zona, historial completo de conversaciones, búsqueda global, etiquetas y notas internas; 100% soberanía de datos y 0 costo de licencias externas.
3. Híbrido: inbox del proveedor para huéspedes, panel propio solo para incidencias críticas.

## Criterio de decisión propuesto
Medir en las fases 4–7: handoffs por semana, tiempo de atención, número de gestores concurrentes. Si el costo a 12 meses del inbox supera el costo de construir y mantener el panel, o si el negocio requiere soberanía y privacidad total sin intermediarios, se aprueba la fase 8.

## Decisión
**Opción 2 Aceptada.** Se aprueba la construcción del Inbox completo de huéspedes en el panel operativo (`T-701` / `TASK-008`). Glamping Imbabura prescinde del inbox de mensajería del proveedor CRM externo para centralizar toda la experiencia de atención y supervisión de huéspedes en su propio servidor y panel operativo.

## Consecuencias previstas
- Opción 1: `crm_conector` implementa `asignar_conversacion` contra el inbox; no hay UI propia.
- Opción 2: nace la sala `panel_handoff` con su compuerta; `crm_conector.asignar_conversacion` la invoca en lugar del proveedor; las US-09 y US-10 deben pasar sin el inbox.

## Criterios de verificación (árbitro)
- US-09 y US-10 en verde con la opción elegida.
- Métrica de handoffs/semana disponible en trazas desde la fase 4 (PRD §15.4, punto 3).

`¤panel-handoff/`
