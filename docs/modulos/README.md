# Diseño detallado por módulo (sala ADPA)
`¤modulos-glamping`

Un documento por sala. Cada uno fija lo que un desarrollador necesita para construir la sala sin pedir contexto: propósito, compuerta con firmas tipadas, tipos del dominio, configuración, compuertas que consume, errores, persistencia, tests que la arbitran y tarea que la construye. Los requisitos (RF) y sus criterios de aceptación viven en [`../PRD.md` §5](../PRD.md#5-requisitos-funcionales-por-módulo) y no se repiten aquí; la disposición física está en [`../ARQUITECTURA.md` §3](../ARQUITECTURA.md#3-salas-adpa-equivalencia-con-la-estructura-del-informe).

Convenciones comunes a todos los módulos:

- **Compuerta única** `<sala>_service.py` con una clase `<Sala>Service`; expone solo tipos del dominio definidos en `tipos.py` de la sala (dataclasses inmutables), nunca objetos de SDK ni sesiones de base de datos.
- **Configuración** en `config_<sala>.yaml`; los secretos se referencian como `${VARIABLE}` y los resuelve `app_core` al construir la compuerta.
- **Errores** tipados que heredan de `ErrorSala` (definido en la propia sala; duplicación deliberada, DPD) y llevan `codigo`, `mensaje_usuario` (apto para WhatsApp o pantalla, sin rastros) y `detalle_tecnico`.
- **Persistencia** en un esquema PostgreSQL propio de la sala con rol de base de datos propio; ninguna sala lee tablas de otra.
- **Rastro** `¤` de la sala en la cabecera de cada archivo y encima de cada función o clase de primer nivel; rol `¤¤` en las primeras líneas.
- **Tests** en `tests/<sala>/`; la sala se prueba sola con los `Fake*` de las compuertas que consume.

| Módulo | Documento | Rastro | Construye |
| :--- | :--- | :--- | :--- |
| Pasillo central | [`app_core.md`](app_core.md) | `¤pasillo-central` | TASK-000 |
| Canal de WhatsApp | [`canal_whatsapp.md`](canal_whatsapp.md) | `¤canal-whatsapp` | TASK-001, 006 |
| Seguridad | [`seguridad.md`](seguridad.md) | `¤seguridad-canal` | TASK-001, 005 |
| Agente | [`agente.md`](agente.md) | `¤agente-enrutador` | TASK-001, 004, 005 |
| Conocimiento (RAG) | [`conocimiento.md`](conocimiento.md) | `¤conocimiento-rag` | TASK-002 |
| Conector PMS | [`pms_conector.md`](pms_conector.md) | `¤pms-conector` | TASK-003 |
| Herramientas MCP | [`herramientas_glamping.md`](herramientas_glamping.md) | `¤herramientas-mcp` | TASK-003, 006 |
| Conector CRM | [`crm_conector.md`](crm_conector.md) | `¤crm-conector` | TASK-004, 007 |
| ARM «Jarvis» | [`arm_jarvis.md`](arm_jarvis.md) | `¤arm-jarvis` | TASK-006, 007 |
| Comisiones | [`comisiones.md`](comisiones.md) | `¤comisiones` | TASK-006, 007 |
| Observabilidad | [`observabilidad.md`](observabilidad.md) | `¤observabilidad` | TASK-001, 005 |
| Panel operativo (frontend + BFF) | [`panel_operativo.md`](panel_operativo.md) · diseño de pantallas en [`../FRONTEND.md`](../FRONTEND.md) | `¤panel-operativo` | TASK-004, 005, 006, 007 |
| Anfitriones y comisión de plataforma | [`anfitriones.md`](anfitriones.md) | `¤anfitriones` | TASK-004, 006 |
| Web pública para huéspedes | [`web_huespedes.md`](web_huespedes.md) | `¤web-huespedes` | — |

`¤modulos-glamping/`
