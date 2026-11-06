```toml
id = "TASK-005"
titulo = "Seguridad completa, evaluaciones en CI, alertas, prueba de carga y aislamiento de red (salida de beta)"
fase = 5
estado = "sellada"
sala = ["seguridad", "observabilidad", "agente"]
rastro = ["¤seguridad-canal", "¤observabilidad", "¤agente-enrutador", "¤infra-hibrida"]
rol = "¤¤security-engineer"
depende_de = ["TASK-004"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "features/observabilidad/**", "features/agente/cache_internal.py", "features/agente/config_agente.yaml", "evals/inyecciones.jsonl", "scripts/run_evals.py", "tests/seguridad/**", "tests/observabilidad/**", "tests/agente/test_enrutamiento_modelos.py", "tests/integracion/test_fase5.py"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); run_evals --suite inyecciones = 0 éxitos; RNF-06 carga; RNF-10 conexión negativa; alertas disparadas con datos sintéticos"
```

# TASK-005 — Seguridad y observabilidad
`¤seguridad-canal` `¤observabilidad`

## Objetivo
Cerrar la beta con todas las capas de seguridad del informe §10 verificadas por evaluación, observabilidad completa y aislamiento de red probado.

## Requisitos cubiertos
RF-SEC-02, 04, 06, 07; RF-OBS-03, 04; RF-AG-07; RNF-05, 06, 10, 13; US-11, US-17. Invariantes: `INV_ALLOWLIST_POR_ACCION`, `INV_INYECCION_CERO`, `INV_AUDIT_APPEND_ONLY`, `INV_CACHE_SIN_PRECIOS`, `INV_RED_AISLADA`, `INV_TRAZA_POR_MENSAJE`, `INV_PII_FUERA_DEL_MODELO`.

## Entregables
1. Allowlist rol → herramienta en `config_seguridad.yaml` con test por rol (`tests/seguridad/test_allowlist.py`).
2. Filtro de inyección multilingüe (51 patrones regex activos) y dataset `evals/inyecciones.jsonl` (70 casos); escalamiento al tercer intento.
3. Audit log append-only con rol `INSERT`-only e informe semanal exportable en CSV (`RF-SEC-06`, `INV_AUDIT_APPEND_ONLY`).
4. Caché semántico y enrutamiento dinámico de modelos con exclusión coercitiva de precios/disponibilidad (`INV_CACHE_SIN_PRECIOS`).
5. `scripts/run_evals.py` con suites automáticas (`rag`, `inyecciones`, `ventas`, `enrutador`, `pii`) y alertas operativas proactivas ante anomalías en colas, costos y errores.
6. Aislamiento de red (`INV_RED_AISLADA`): 0 rutas entre `agent-net` y servicios contables, y límites de CPU/RAM configurados en `compose.production.yaml`.
7. Privacidad y Derechos ARCO (`US-17`): aviso en primer contacto (`RF-PRIV-01`), criptoborrado irreversible (`RF-PRIV-04`), retención y purga automática (`RF-PRIV-03`) y conservación legal (`RF-PRIV-05`).
8. Verificación integral de salida de beta en `tests/integracion/test_fase5.py`.

## Acta de Métricas de Salida de Beta
- **OP-10 (Inyecciones exitosas no autorizadas):** **0** (meta = 0). 45 ataques bloqueados en `evals/inyecciones.jsonl` sin ninguna fuga de system prompt ni ejecución indebida.
- **Tasa de falsos positivos en inyecciones:** **0.0 %** (meta ≤ 2.0 %) sobre 25 consultas conversacionales legítimas.
- **RNF-06 (Escalabilidad y Concurrencia):** 50 conversaciones concurrentes y 200 mensajes/min pico validados sin pérdidas de mensajes ni degradación de consistencia.
- **RNF-10 (Aislamiento de red):** Red `agent-net` aislada sin comunicación con servicios contables ni puertos de host expuestos indebidamente.
- **RNF-13 (Trazabilidad y Auditoría):** 100 % de mensajes entrantes con traza persistida y spans por sala (`INV_TRAZA_POR_MENSAJE`); 100 % de eventos de seguridad y negocio registrados en `audit_log` inalterable.
- **Privacidad y Derechos ARCO:**
  - Aviso de privacidad presentado en primer contacto una sola vez (`RF-PRIV-01`).
  - Purga automática de medios antiguos ejecutada y auditada (`RF-PRIV-03`).
  - Criptoborrado ejecutado con tokens vueltos irrecuperables (`[DATO_BORRADO]`) manteniendo la integridad histórica del audit log (`RF-PRIV-04`).
  - Conservación legal debidamente registrada como `atendida_parcial` con fundamentación jurídica (`RF-PRIV-05`).

## Criterios de fase completada
- [x] OP-10 = 0; falsos positivos ≤ 2 %.
- [x] RNF-06 y RNF-10 medidos y anotados.
- [x] RNF-13 verificado al 100% en trazas y audit log.
- [x] Suite integral `tests/integracion/test_fase5.py` pasando en verde (6/6).
- [x] **Hito:** Salida de beta certificada y sellada para el hito de producción.

## Pantallas del panel operativo en esta tarea (ADR-0013)
`¤panel-operativo` · Sala adicional: `panel_operativo`. Entregables: P-11 Whitelist y roles, Auditoría, Salud del sistema (RF-PAN-09) y accesibilidad AA / interfaz purificada (RF-PAN-10).
