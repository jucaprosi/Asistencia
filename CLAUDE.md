# `¤reglas` Zero-Regression AI Governance BIAS — Glamping Imbabura

> **HEAD DE ATENCIÓN MÁXIMA — ADUANA COERCITIVA (`¤¦triaje`):**
> Antes de emitir cualquier respuesta conversacional, diagnóstico o acción técnica en el workspace, invoca como **PRIMERA acción** la herramienta `mcp_orchestrate_triage` del servidor MCP `zero_regression_bios`, con estos argumentos:
> ```json
> {
>   "project_root": "<ruta_absoluta_del_workspace>",
>   "user_request": "<solicitud_del_usuario>"
> }
> ```
> Acata las directivas de ejecución y los roles especializados (`¤¤`) devueltos por el triaje. Si la herramienta no está disponible, informa que falta la conexión MCP; no declares un triaje ejecutado.

<!-- Justificación: el triaje entrega la gobernanza vigente; el cliente conserva solo su activador. -->

---

## Fuente de verdad del proyecto

**Lee [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) antes de cualquier tarea de arquitectura, implementación o generación de PRD.** Es el informe maestro: contexto de negocio, decisiones tomadas, decisiones abiertas y referencias. Si una propuesta contradice una decisión documentada allí, no la implementes: escribe un ADR en [`docs/adr/`](docs/adr/README.md) y detente hasta que el propietario lo acepte.

| Documento | Qué resuelve |
| :--- | :--- |
| [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) | Informe maestro y anexos (madurez del agente, proyección ZERAG). |
| [`docs/PRD.md`](docs/PRD.md) | Requisitos funcionales y no funcionales, user stories, flujos, modelo de datos, roadmap 0–8. |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Salas ADPA, compuertas, pasillo central, topología Docker, seguridad por capa. |
| [`docs/modulos/`](docs/modulos/README.md) | Diseño detallado por sala: compuerta con firmas tipadas, tipos, configuración, errores, persistencia, tests. Leer el de la sala antes de tocarla. |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | Diseño del panel operativo (pantallas, componentes, tokens, contrato del BFF). |
| [`docs/adr/`](docs/adr/README.md) | Decisiones aceptadas (ADR-0001 a 0006) y pendientes (ADR-0007 a 0012). |
| [`governance/artefactos/`](governance/artefactos/PRD.md) | Nido de artefactos vivos: catálogo de salas, invariantes, fuentes, índice de rastros, problemas. |
| [`governance/tareas/TASKS.md`](governance/tareas/TASKS.md) | Tareas ejecutables por sala (T-101…T-701) en olas paralelas sin colisión: propiedad exclusiva de rutas, compuertas que consume, árbitro. Toma una tarea de aquí, nunca una fase entera. |
| [`governance/tareas/`](governance/tareas/README.md) | Hitos de fase (TASK-000 a TASK-008) que sellan las tareas de integración. |

## Proceso (único, idéntico para cualquier solicitud)

1. **Reestructuración.** Si la solicitud no es informativa, se reestructura en una directiva técnica (sala, rastro `¤`, test) con `mcp_orchestrate_triage` y se valida el alcance si hay ambigüedad.
2. **Boceto → arnés → sellado.** Boceto libre dentro de la sala (huellas `¦`), arnés físico con todos los requerimientos de la tarea, resolución uno por uno, sellado: interfaz en la compuerta `_service.py`, cero imports laterales, huellas consolidadas a `¤`, Exit Code 0.

## Normas con árbitro exógeno

> **ENFORCE: Confinamiento ADPA.** Todo código vive en `features/<sala>/`; las dependencias cruzadas transitan solo por `<sala>_service.py` (`server.py` del servidor MCP es un ejecutable, no una compuerta); `app_core/` orquesta compuertas y no importa nada privado. Árbitro: `adpa_linter` (hook PostToolUse del servidor ZERAG) y la suite del arnés.

> **ENFORCE: Escritura conforme.** UTF-8 sin BOM, huellas `¦` consolidadas a `¤` antes de sellar, sin reclamos de IP ajena. Árbitro: hooks PostToolUse (`utf8_linter`, `huellas_linter`, `ip_safety_linter`).

> **ENFORCE: Nido de artefactos vivos antes del código.** No se escribe `.py` si falta alguno de `governance/artefactos/{PRD.md, INVARIANTS.md, FUENTES_Y_BIBLIOGRAFIA.md, VPA_INDEX.md, PROBLEMS.json}`. Árbitro: `living_artifacts_linter` en el triaje y el cierre.

> **ENFORCE: Sellado.** Una fase se da por completada solo con `ejecutar_arnes_glamping.bat` (o `.sh`) en Exit Code 0 y su certificado `.test_verdict.json` en `governance/artefactos/data/`. El arnés nace en la fase 0 (TASK-000). Hasta entonces el cierre de sesión se registra como `fallo_honesto`, nunca como éxito autodeclarado.

> **ENFORCE: Canal oficial.** Ninguna dependencia de `baileys`, `whatsapp-web.js` ni `whatsmeow` entra al repositorio. Árbitro: test `tests/test_canal_oficial.py` (fase 0) que recorre los manifiestos de dependencias.

> **ENFORCE: Interfaz purificada.** Ningún texto de cara a huésped, vendedor o equipo (mensajes de WhatsApp, etiquetas del CRM, plantillas) contiene `¤`, `¦`, `¤¬` ni `¤¤`. Árbitro: `ui_sanitizer_linter` y `tests/test_interfaz_purificada.py` (fase 1).

## Método (guía, sin árbitro)

- **Búsqueda por rastro.** Antes de buscar en lenguaje natural, busca el rastro: `git grep --untracked "¤arm-jarvis"` devuelve PRD, invariantes, tarea, ADR y código de esa capacidad en una sola pasada. El índice de rastros está en `governance/artefactos/VPA_INDEX.md`.
- **Decisiones pendientes.** Las marcas `[DECISIÓN PENDIENTE]` del PRD no se resuelven por iniciativa de la IA: se proponen al propietario con un ADR en estado *Propuesto*.
- **Secretos.** Tokens de Meta, claves de Anthropic, credenciales del PMS y del CRM no se escriben en el repositorio ni se repiten en el chat; viven en variables de entorno o en el gestor de secretos del servidor.
- **Conducta.** Investigar la causa raíz antes de proponer alternativas; no parchear; no pedir input interactivo si hay vía no interactiva; ante un comando que exige privilegios, parar y reportar el comando exacto.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
Contacto: juancarlosproanios@gmail.com
