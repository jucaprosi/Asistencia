```toml
id = "TASK-004"
titulo = "Enrutador multi-propiedad, prompt de departamentos, check-in autónomo y handoff por zona"
fase = 4
estado = "pendiente"
sala = ["agente", "crm_conector (inbox mínimo con FakeCRM)"]
rastro = ["¤agente-enrutador", "¤crm-conector"]
rol = "¤¤machine-learning-engineer"
depende_de = ["TASK-002", "TASK-003"]
bloqueada_por = []
propiedad = ["features/agente/**", "features/crm_conector/**", "docs/prompts/system-prompt-enrutador.md", "docs/prompts/system-prompt-departamentos.md", "docs/prompts/system-prompt-hospedaje.md", "evals/enrutador.jsonl", "tests/agente/**", "tests/crm_conector/**"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); tests/agente/test_enrutador.py 20/20; scripts/run_evals.py --suite enrutador con 0 fugas entre propiedades; US-03, US-09, US-10 en verde con FakeCRM"
```

# TASK-004 — Multi-propiedad
`¤agente-enrutador`

## Objetivo
Un solo número atiende el glamping y los departamentos: el agente identifica la propiedad antes de actuar, carga el prompt correcto, expone solo las herramientas del rol, envía el check-in del día por propiedad y escala al gestor de la zona.

## Requisitos cubiertos
RF-AG-01, RF-AG-03, RF-MCP-04 (completo), RF-MCP-06, RF-CRM-01 (interfaz) y `asignar_conversacion` con `FakeCRM`. Invariantes: `INV_PROPIEDAD_RESUELTA`, `INV_SIN_FUGA_ENTRE_PROPIEDADES`, `INV_RLS_MULTI_INQUILINO` (entra en vigor).

## Entregables
1. `enrutador_internal.py` con resolución por código de reserva, nombre, dirección, contexto o pregunta con lista de opciones.
2. `docs/prompts/system-prompt-enrutador.md` y `system-prompt-departamentos.md` y `system-prompt-hospedaje.md` con datos inyectados por propiedad.
3. Planificador de check-in del día en `app_core` invocando `agente_service`.
4. `evals/enrutador.jsonl` con 20 conversaciones etiquetadas (incluidas ambiguas).
5. RLS por `propiedad_id` activa en PostgreSQL con rol `NOBYPASSRLS`.

## Criterios de fase completada
- 20/20 en el enrutador; 0 fugas entre propiedades.
- Check-in autónomo probado con dos propiedades en el PMS de pruebas (US-03).
- Handoff por zona con `FakeCRM` (US-09, US-10).

## Pantallas del panel operativo en esta tarea (ADR-0013)
`¤panel-operativo` · Sala adicional: `panel_operativo` (propiedad: `features/panel_operativo/**`, `tests/panel_operativo/**`, `tests/e2e/test_handoff_zona.py`). Entregables: P-01 Acceso, P-02 Inicio, P-08 Handoffs de mi zona, P-09 Detalle de conversación, P-10 Incidencias (RF-PAN-01, 07, 08). La bandeja del panel sustituye a `FakeCRM` como inbox de esta fase. Criterio: US-09 y US-10 en e2e sobre `localhost`. Diseño: `docs/FRONTEND.md` §4.
