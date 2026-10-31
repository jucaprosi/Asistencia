```toml
id = "TASK-005"
titulo = "Seguridad completa, evaluaciones en CI, alertas, prueba de carga y aislamiento de red (salida de beta)"
fase = 5
estado = "pendiente"
sala = ["seguridad", "observabilidad", "agente"]
rastro = ["¤seguridad-canal", "¤observabilidad", "¤agente-enrutador", "¤infra-hibrida"]
rol = "¤¤security-engineer"
depende_de = ["TASK-004"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "features/observabilidad/**", "features/agente/cache_internal.py", "features/agente/config_agente.yaml", "evals/inyecciones.jsonl", "scripts/run_evals.py", "tests/seguridad/**", "tests/observabilidad/**", "tests/agente/test_enrutamiento_modelos.py"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); run_evals --suite inyecciones = 0 éxitos; RNF-06 carga; RNF-10 conexión negativa; alertas disparadas con datos sintéticos"
```

# TASK-005 — Seguridad y observabilidad
`¤seguridad-canal` `¤observabilidad`

## Objetivo
Cerrar la beta con todas las capas de seguridad del informe §10 verificadas por evaluación, observabilidad completa y aislamiento de red probado.

## Requisitos cubiertos
RF-SEC-02, 04, 06, 07; RF-OBS-03, 04; RF-AG-07; RNF-05, 06, 10, 13. Invariantes: `INV_ALLOWLIST_POR_ACCION`, `INV_INYECCION_CERO`, `INV_AUDIT_APPEND_ONLY`, `INV_CACHE_SIN_PRECIOS`, `INV_RED_AISLADA`.

## Entregables
1. Allowlist rol → herramienta en `config_seguridad.yaml` con test por rol.
2. Filtro de inyección (≥ 40 patrones, 4 idiomas) y `evals/inyecciones.jsonl`; escalamiento al tercer intento.
3. Audit log append-only con rol `INSERT`-only; informe semanal.
4. Caché semántico y enrutamiento de modelos con exclusión de precios/disponibilidad.
5. `scripts/run_evals.py` con las cuatro suites y umbrales en `config_observabilidad.yaml`; alertas de silencio, errores, cola y costo.
6. Prueba de carga (50 conversaciones concurrentes, 200 mensajes/min) y prueba de conexión negativa desde `agent-net`.

## Criterios de fase completada
- OP-10 = 0; falsos positivos ≤ 2 %.
- RNF-06 y RNF-10 medidos y anotados.
- **Hito:** salida de beta aprobada por el propietario con los datos de esta tarea.

## Pantallas del panel operativo en esta tarea (ADR-0013)
`¤panel-operativo` · Sala adicional: `panel_operativo`. Entregables: P-11 Whitelist y roles, Auditoría, Salud del sistema (RF-PAN-09 parcial) y RF-PAN-10 (accesibilidad AA, presupuesto de rendimiento LCP ≤ 2,5 s medido en CI, interfaz purificada sobre el build). Criterio: `tests/panel_operativo/test_bff_admin.py` con cada rol; `tests/e2e/test_calidad_ui.py`.
