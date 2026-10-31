# PRD vivo — Catálogo de salas ADPA y asignación de requisitos
`¤prd-glamping`

> **Relación con `docs/PRD.md`.** Este archivo es el PRD *vivo* que exige la metodología ZERAG: declara las salas estancas, su compuerta y qué requisitos responde cada una. Los requisitos completos (criterios de aceptación, user stories, flujos, modelo de datos, roadmap) viven en [`../../docs/PRD.md`](../../docs/PRD.md) y no se duplican aquí. Si ambos difieren, manda `docs/PRD.md` y este catálogo se corrige.

## 1. Producto y propuesta de valor
`¤prd-vision`

Asistente de WhatsApp con Claude para huéspedes de Glamping Imbabura y sus departamentos urbanos, con acciones reales sobre el PMS vía MCP, RAG sobre el conocimiento del negocio, y un ARM («Jarvis») que convierte las ventas escritas por los vendedores en WhatsApp en registros validables con comisión calculada, visibles en un CRM adoptado. Núcleo propio; capa commodity adoptada tras interfaces abstractas. Visión completa: [`docs/PRD.md` §1](../../docs/PRD.md#1-visión-del-producto).

## 2. Salas ADPA
`¤arquitectura-salas`

Una **sala** es la unidad autónoma de trabajo y de contención de fallos: tiene dueño de sus archivos, una compuerta pública y requisitos propios. Un agente escribe solo en los archivos de su sala; lo que necesite de otra lo obtiene por la compuerta de esa sala o lo pide al pasillo central.

| Sala | Ubicación | Compuerta | Rastro | Rol | Requisitos |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `canal_whatsapp` | `features/canal_whatsapp` | `canal_whatsapp_service.py` (por crear, TASK-001) | `¤canal-whatsapp` | `¤¤integration-engineer` | RF-GW-01..06 |
| `seguridad` | `features/seguridad` | `seguridad_service.py` (por crear, TASK-001) | `¤seguridad-canal` | `¤¤security-engineer` | RF-SEC-01..07 |
| `agente` | `features/agente` | `agente_service.py` (por crear, TASK-001) | `¤agente-enrutador` | `¤¤machine-learning-engineer` | RF-AG-01..07 |
| `conocimiento` | `features/conocimiento`, `docs/negocio` (datos), `scripts/seed_knowledge.py` | `conocimiento_service.py` (por crear, TASK-002) | `¤conocimiento-rag` | `¤¤data-engineer` | RF-RAG-01..06 |
| `pms_conector` | `features/pms_conector` | `pms_conector_service.py` (por crear, TASK-003) | `¤pms-conector` | `¤¤integration-engineer` | RF-PMS-01..04 |
| `herramientas_glamping` | `features/herramientas_glamping` | `herramientas_glamping_service.py` (TASK-000); `server.py` es el ejecutable MCP (TASK-003) | `¤herramientas-mcp` | `¤¤backend-developer` | RF-MCP-01..09 |
| `operaciones` (condicional, ADR-0007) | `features/operaciones` | `operaciones_service.py` (por definir) | `¤operaciones-incidencias` | `¤¤backend-developer` | RF-MCP-05 (registro de Incidencia) |
| `crm_conector` | `features/crm_conector` | `crm_conector_service.py` (por crear, TASK-004 mínimo; TASK-007 completo) | `¤crm-conector` | `¤¤integration-engineer` | RF-CRM-01..05 |
| `arm_jarvis` | `features/arm_jarvis` | `arm_jarvis_service.py` (por crear, TASK-006) | `¤arm-jarvis` | `¤¤backend-developer` | RF-ARM-01..09 |
| `comisiones` | `features/comisiones` | `comisiones_service.py` (por crear, TASK-006) | `¤comisiones` | `¤¤backend-developer` | RF-COM-01..03 |
| `observabilidad` | `features/observabilidad`, `scripts/run_evals.py`, `evals/` | `observabilidad_service.py` (por crear, TASK-001) | `¤observabilidad` | `¤¤devops-engineer` | RF-OBS-01..04 |
| `panel_operativo` (ADR-0013) | `features/panel_operativo` (BFF, `ui/`, `estaticos/`) | `panel_operativo_service.py` (por crear, TASK-004) | `¤panel-operativo` | `¤¤frontend-developer` | RF-PAN-01..10 |
| *pasillo central* | `app_core/` | `main.py`, `contenedor.py` (por crear, TASK-000) | `¤pasillo-central` | `¤¤solutions-architect` | orquestación; sin requisitos propios |
| *infraestructura* | `compose.yaml`, `compose.production.yaml`, `ejecutar_arnes_glamping.*`, `.env.example` | — | `¤infra-hibrida` | `¤¤devops-engineer` | RNF-10, RNF-14, RNF-15 |

**Reglas de las salas**

1. **Solo por compuerta.** Una sala importa a otra únicamente por su compuerta. Las compuertas «por crear» o «por definir» son deuda declarada de su sala y nacen con su tarea.
2. **Una sola fuente de asignación.** Este catálogo declara qué sala responde de cada requisito; cada tarea en `governance/tareas/` declara la sala que la ejecuta y los archivos de su propiedad exclusiva.
3. **Puntos de contención.** `app_core/`, `compose*.yaml`, el arnés, `INVARIANTS.md`, `FUENTES_Y_BIBLIOGRAFIA.md` y `VPA_INDEX.md` los edita solo el coordinador de la sesión; cada sala entrega sus herramientas MCP a través de `herramientas_glamping/server.py` por su compuerta.
4. **Árbitro de salida.** Una entrega se acepta con el arnés en Exit Code 0, `adpa_linter` y `huellas_linter` sin errores en sus archivos y las evaluaciones de la fase sobre umbral.
5. **Reservado al propietario.** Cuenta de Meta, claves de Anthropic, credenciales del PMS y del CRM, despliegue en el servidor contable: no los cambia ningún agente.

## 3. Requisitos por sala
`¤prd-requisitos`

Detalle, criterios de aceptación y árbitros en [`docs/PRD.md` §5](../../docs/PRD.md#5-requisitos-funcionales-por-módulo). Resumen de asignación:

| Prefijo | Sala | Construir / Adoptar |
| :--- | :--- | :--- |
| RF-GW | `canal_whatsapp` | Construir |
| RF-AG | `agente` | Construir |
| RF-RAG | `conocimiento` | Construir |
| RF-PMS | `pms_conector` | Construir sobre MCP; proveedor `[DECISIÓN PENDIENTE]` ADR-0007 |
| RF-CRM | `crm_conector` | Interfaz propia; CRM adoptado `[DECISIÓN PENDIENTE]` ADR-0008 |
| RF-ARM | `arm_jarvis` | Construir (ADR-0005) |
| RF-COM | `comisiones` | Construir; registro `[DECISIÓN PENDIENTE]` ADR-0009 |
| RF-SEC | `seguridad` | Construir |
| RF-OBS | `observabilidad` | Construir |
| RF-MCP | `herramientas_glamping` | Construir |
| RF-PAN | `panel_operativo` | Construir (ADR-0013); diseño en `docs/FRONTEND.md` |

## 4. Matriz de invariantes y leyes de negocio
`¤invariantes-glamping`

Catálogo en [`INVARIANTS.md`](INVARIANTS.md).

## 5. Fuera de alcance
`¤prd-fuera-alcance`

[`docs/PRD.md` §11](../../docs/PRD.md#11-fuera-de-alcance-versión-01).

`¤prd-glamping/`
