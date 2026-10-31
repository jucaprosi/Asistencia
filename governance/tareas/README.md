# Tareas — Glamping Imbabura
`¤tareas-glamping`

Dos niveles:

- **[`TASKS.md`](TASKS.md) — tareas ejecutables por sala.** La unidad de trabajo de una sesión de IA o de una persona. Cada tarea (`T-NNN`) declara sala, rol, requisitos, rutas de propiedad exclusiva, compuertas que consume, dependencias, bloqueos y árbitro, agrupadas en **olas** de ejecución paralela sin colisiones. Árbitro: `tests/test_tareas_sin_colision.py`.
- **`TASK-00N-*.md` — hitos de fase.** Qué significa «fase completada» para las fases 0–8 del roadmap; los sella la tarea de integración (`T-N11`) de cada ola.

El tablero de estado que lleva el servidor MCP ZERAG se alimenta de los cierres de sesión; aquí vive la especificación.

## Estados

`pendiente` → `boceto` (en curso, huellas `¦`) → `sellada` (arnés en Exit Code 0, huellas consolidadas a `¤`, certificado en `governance/artefactos/data/`) · `bloqueada` (por una decisión pendiente o un supuesto no validado).

## Cabecera

```toml
id = "TASK-00N"
titulo = ""
fase = N
estado = "pendiente"
sala = ["..."]
rastro = ["¤..."]
rol = "¤¤..."
depende_de = ["TASK-00M"]
bloqueada_por = ["ADR-00XX", "S-0Y"]      # vacío si no aplica
propiedad = ["features/<sala>/**", "tests/<sala>/**"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0) + tests/evals listados"
```

## Índice de hitos de fase

| Hito | Fase | Título | Sala(s) | Estado | Bloqueada por |
| :--- | :--- | :--- | :--- | :--- | :--- |
| [TASK-000](TASK-000-esqueleto-adpa.md) | 0 | Esqueleto ADPA, compose, arnés, CI, backups | todas (vacías), `app_core`, infraestructura | boceto (faltan 2 pendientes del propietario) | proveedor de PostgreSQL, restauración de backup |
| [TASK-001](TASK-001-mvp-whatsapp.md) | 1 | MVP WhatsApp con Claude y `FakePMS` | `canal_whatsapp`, `agente`, `seguridad`, `observabilidad` | pendiente | S-02 |
| [TASK-002](TASK-002-rag.md) | 2 | RAG sobre `CORPUS_DIR` con set dorado | `conocimiento` | pendiente | S-03, ADR-0012 |
| [TASK-003](TASK-003-pms-mcp.md) | 3 | Conector PMS y herramientas MCP de reservas e incidencias | `pms_conector`, `herramientas_glamping`, (`operaciones`) | pendiente | ADR-0007 |
| [TASK-004](TASK-004-multipropiedad.md) | 4 | Enrutador multi-propiedad, check-in autónomo, handoff por zona en el panel | `agente`, `crm_conector` (mínimo), `panel_operativo` (P-01, P-02, P-08..P-10) | pendiente | — |
| [TASK-005](TASK-005-seguridad-observabilidad.md) | 5 | Seguridad completa, evaluaciones, alertas, carga, aislamiento; administración y salud en el panel | `seguridad`, `observabilidad`, `agente`, `panel_operativo` (P-11 parcial) | pendiente | — |
| [TASK-006](TASK-006-arm-jarvis.md) | 6 | ARM «Jarvis» y comisiones; ventas por validar y Jarvis en el panel | `arm_jarvis`, `comisiones`, `canal_whatsapp`, `panel_operativo` (P-03, P-04, P-07) | pendiente | S-01, ADR-0009 |
| [TASK-007](TASK-007-integracion-crm.md) | 7 | Conector CRM, Inbound Webhook, tablero y cierre en el panel, producción | `crm_conector`, `arm_jarvis`, `comisiones`, `panel_operativo` (P-05, P-06, P-11 completo) | pendiente | ADR-0008, ADR-0011 |
| [TASK-008](TASK-008-panel-handoff.md) | 8 | Inbox completo de huéspedes en el panel (condicional) | `panel_operativo` | bloqueada | ADR-0010 |

Las pantallas del panel por fase están en [`../../docs/FRONTEND.md` §12](../../docs/FRONTEND.md#12-entrega-por-fases); cada tarea de las fases 4–7 incluye las suyas como entregable con sus pruebas e2e.

`¤tareas-glamping/`
