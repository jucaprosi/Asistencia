# Índice de rastros estigmérgicos (VPA) — Glamping Imbabura
`¤vpa-glamping`

> Índice local de capacidades: entidad de negocio → rastro `¤` → rol `¤¤` → sala → significado. Buscar el rastro en el árbol (`git grep --untracked "¤arm-jarvis"`) devuelve su PRD, invariantes, tarea, ADR y código en una pasada. El `VPA_MAP.md` canónico y el tablero `TASKS.md` los sirve el servidor MCP ZERAG; este índice es la copia legible del proyecto y se mantiene en cada sellado.

## 1. Capacidades de producto

| Entidad de negocio | Rastro | Rol | Sala | Significado |
| :--- | :--- | :--- | :--- | :--- |
| Canal de WhatsApp | `¤canal-whatsapp` | `¤¤integration-engineer` | `canal_whatsapp` | Recepción y envío por la Cloud API oficial; ventana de 24 h; plantillas; medios; separación huéspedes/vendedores. |
| Seguridad del canal | `¤seguridad-canal` | `¤¤security-engineer` | `seguridad` | Identidad y bloqueos, allowlist por acción, rate limit, filtro de inyección, redacción de PII, audit log, RLS. |
| Agente y enrutador | `¤agente-enrutador` | `¤¤machine-learning-engineer` | `agente` | Claude con tool use; identificación de propiedad; prompts por propiedad; herramientas por rol; memoria; degradación; caché y enrutamiento de modelos. |
| Conocimiento (RAG) | `¤conocimiento-rag` | `¤¤data-engineer` | `conocimiento` | Indexación de `CORPUS_DIR` en pgvector; chunking; recuperación híbrida con filtro por propiedad; «no lo sé»; set dorado. |
| Conector PMS | `¤pms-conector` | `¤¤integration-engineer` | `pms_conector` | Interfaz `PMSConnector`; `FakePMS`; implementaciones por proveedor; escrituras explícitas; errores tipados. |
| Herramientas MCP | `¤herramientas-mcp` | `¤¤backend-developer` | `herramientas_glamping` | Servidor MCP: disponibilidad, cotización, reserva preliminar, check-in, incidencia, handoff, CRM, venta, comisión. |
| Operaciones e incidencias | `¤operaciones-incidencias` | `¤¤backend-developer` | `operaciones` (condicional) | Registro de incidencias `I-AAAA-NNNN` si el PMS no las cubre (ADR-0007). |
| Conector CRM | `¤crm-conector` | `¤¤integration-engineer` | `crm_conector` | Interfaz `CRMConnector`; `FakeCRM`; publicación de venta firmada e idempotente; cola de reintentos; eventos del CRM; inbox. |
| ARM «Jarvis» | `¤arm-jarvis` | `¤¤backend-developer` | `arm_jarvis` | Lectura del canal de vendedores; extracción de ventas; estados; ticket `V-AAAA-NNNN`; notificación; consulta de comisión propia; tablero; asistente del líder. |
| Comisiones | `¤comisiones` | `¤¤backend-developer` | `comisiones` | Reglas versionadas con vigencia; cálculo reproducible; cierre de período inmutable; exportación. |
| Observabilidad | `¤observabilidad` | `¤¤devops-engineer` | `observabilidad` | Logs JSON sin PII; traza por mensaje con spans; evaluaciones en CI y arnés; alertas. |
| Panel operativo | `¤panel-operativo` | `¤¤frontend-developer` | `panel_operativo` | Frontend y BFF del equipo: ventas por validar, tablero, Jarvis, handoff por zona, incidencias, administración (ADR-0013). |
| Anfitriones | `¤anfitriones` | `¤¤backend-developer` | `anfitriones` | Publicación de hospedajes, solicitudes de reserva y comisión de plataforma. |
| Web pública | `¤web-huespedes` | `¤¤frontend-developer` | `web_huespedes` | Búsqueda y comparación para huéspedes, solo lectura. |
| Pasillo central | `¤pasillo-central` | `¤¤solutions-architect` | `app_core` | Arranque, inyección de dependencias, orquestación de compuertas, tareas programadas. |
| Infraestructura híbrida | `¤infra-hibrida` | `¤¤devops-engineer` | raíz (`compose*`, arnés) | Nube gestionada para datos; servidor propio para lógica; red aislada; mismo compose beta/producción; secretos fuera del repo. |
| Ciclo de construcción | `¤bbap-glamping` | `¤¤qa-engineer` | transversal | Boceto → arnés `ejecutar_arnes_glamping` → sellado por tarea. |
| Privacidad de datos | `¤privacidad-datos` | `¤¤security-engineer` | `seguridad` | Consentimiento, inventario, retención, solicitudes del titular y criptoborrado. |

## 2. Rastros documentales

| Rastro | Documento | Significado |
| :--- | :--- | :--- |
| `¤contexto-maestro` | `docs/PROJECT_CONTEXT.md` | Informe maestro, fuente de verdad. |
| `¤contexto-madurez` | `docs/PROJECT_CONTEXT.md` Anexo A | Escala de madurez de @segunrob (secundaria). |
| `¤contexto-zerag` | `docs/PROJECT_CONTEXT.md` Anexo B | Proyección del informe sobre ZERAG. |
| `¤prd-glamping` | `docs/PRD.md`, `governance/artefactos/PRD.md` | PRD completo y catálogo vivo de salas. |
| `¤spec-glamping` | `docs/spec/`, `docs/adr/ADR-0014-*`, `tests/test_especificacion.py`, `scripts/generar_trazabilidad.py` | Especificación ejecutable para Spec-Driven Development. |
| `¤prd-vision` `¤prd-objetivos` `¤prd-personas` `¤prd-casos-uso` `¤prd-requisitos` `¤prd-rnf` `¤prd-user-stories` `¤prd-flujos` `¤prd-modelo-datos` `¤prd-dependencias` `¤prd-fuera-alcance` `¤prd-roadmap` `¤prd-riesgos` `¤prd-glosario` `¤prd-anexos` | `docs/PRD.md` §1–§15 | Secciones del PRD. |
| `¤arquitectura-glamping` `¤arquitectura-contexto` `¤arquitectura-principios` `¤arquitectura-salas` `¤arquitectura-datos` | `docs/ARQUITECTURA.md` | Arquitectura ADPA. |
| `¤adr-glamping` `¤adr-construir-adoptar` `¤adr-zerag` | `docs/adr/` | Registro de decisiones. |
| `¤invariantes-glamping` | `governance/artefactos/INVARIANTS.md` | Leyes con árbitro. |
| `¤fuentes-glamping` | `governance/artefactos/FUENTES_Y_BIBLIOGRAFIA.md` | Trazabilidad externa. |
| `¤tareas-glamping` `¤coordinacion` | `governance/tareas/TASKS.md`, `governance/tareas/TASK-00N-*.md` | Tareas ejecutables por sala en olas sin colisión (árbitro `tests/test_tareas_sin_colision.py`) e hitos de fase. |
| `¤prompts-glamping` | `docs/prompts/` | System prompts del enrutador, glamping y departamentos. |
| `¤modulos-glamping` | `docs/modulos/` | Diseño detallado por sala: compuerta, tipos, configuración, errores, persistencia, tests. |
| `¤frontend-glamping` (+ `¤frontend-alcance` … `¤frontend-fases`) | `docs/FRONTEND.md` | Diseño del panel operativo: pantallas, navegación, componentes, tokens, BFF, seguridad, stack. |
| `¤negocio-glamping` | `docs/negocio/README.md` | Checklist del corpus del RAG, que vive fuera del repositorio. |

## 3. Roles del proyecto (`¤¤`)

`¤¤solutions-architect`, `¤¤integration-engineer`, `¤¤security-engineer`, `¤¤machine-learning-engineer`, `¤¤data-engineer`, `¤¤backend-developer`, `¤¤frontend-developer`, `¤¤devops-engineer`, `¤¤qa-engineer`. Títulos de industria (ESCO/O*NET); sin roles genéricos.

`¤vpa-glamping/`
