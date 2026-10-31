```toml
id = "TASK-008"
titulo = "Inbox completo de conversaciones de huéspedes dentro del panel operativo (solo si ADR-0010 prescinde del inbox del proveedor)"
fase = 8
estado = "bloqueada"
sala = ["panel_operativo"]
rastro = ["¤panel-operativo"]
rol = "¤¤frontend-developer"
depende_de = ["TASK-007"]
bloqueada_por = ["ADR-0010"]
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/test_inbox_huespedes.py"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); conversaciones de huéspedes consultables y atendibles sin el inbox del proveedor (e2e)"
```

# TASK-008 — Inbox completo de huéspedes en el panel (condicional)
`¤panel-operativo`

## Objetivo
Si el análisis de costo a 12 meses y el volumen medido en las fases 4–7 (ADR-0010) favorecen prescindir del inbox del proveedor de CRM, ampliar la sección Conversaciones del panel operativo: hoy cubre handoffs e incidencias por zona (TASK-004); esta tarea añade el historial completo de conversaciones de huéspedes, búsqueda por propiedad, reserva y fecha, etiquetas y notas internas.

## Requisitos cubiertos
Extensión de RF-PAN-07 (conversaciones fuera de handoff); US-09 y US-10 siguen en verde; `crm_conector.asignar_conversacion` deja de depender del proveedor (`inbox.usar_proveedor: false`).

## Entregables
1. Pantallas: lista de conversaciones por propiedad y estado, detalle con historial completo redactado de PII (rehidratación solo del huésped de la reserva), búsqueda, etiquetas, notas internas.
2. BFF: `GET /conversaciones`, `GET /conversaciones/{id}`, `POST /conversaciones/{id}/etiquetas`, `POST /conversaciones/{id}/notas` → `agente.contexto`, `seguridad`.
3. Prueba e2e `tests/e2e/test_inbox_huespedes.py`.

## Criterios de fase completada
- Un gestor encuentra y atiende cualquier conversación de su zona sin el inbox del proveedor.
- Métrica de handoffs/semana y tiempo de atención visibles en Salud del sistema.

## Estado
Bloqueada hasta ADR-0010. No se inicia por iniciativa de la IA. Reformulada el 2026-10-30 por ADR-0013 (antes: «panel de handoff propio», que ahora existe desde la fase 4).
