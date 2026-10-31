# Asistente de WhatsApp, ARM y CRM — Glamping Imbabura

> **Propósito en una línea:** atender huéspedes del glamping y de los departamentos urbanos por WhatsApp con Claude, actuar sobre el sistema de reservas vía MCP, y convertir las ventas que los vendedores escriben en WhatsApp en registros validados con comisión calculada, visibles en un CRM que el equipo ya sabe usar.

[![Architecture: ZERAG BIAS](https://img.shields.io/badge/Architecture-ZERAG%20BIAS%20ADPA-blue.svg)](docs/adr/ADR-0006-metodologia-zerag-adpa-huellas.md)
[![Zero Regression](https://img.shields.io/badge/Zero--Regression-Arn%C3%A9s%20Exit%20Code%200-green.svg)](CLAUDE.md)
[![Encoding](https://img.shields.io/badge/Encoding-UTF--8%20sin%20BOM-brightgreen.svg)](#)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Cloud%20API%20oficial-25D366.svg)](docs/adr/ADR-0003-api-oficial-whatsapp-cloud.md)

---

## 1. Propósito y propuesta de valor

Glamping Imbabura se expande de una ubicación a departamentos distribuidos por la ciudad. Eso multiplica calendarios, precios, instrucciones de acceso y gestores por zona; atenderlo a mano por WhatsApp no escala. En paralelo, las ventas de los vendedores se transcriben a mano con errores y comisiones tardías.

Este proyecto construye **lo que diferencia al negocio** (motor conversacional con Claude, RAG sobre el conocimiento propio, conectores a PMS y CRM, enrutamiento multi-propiedad, el ARM «Jarvis», comisiones, seguridad, observabilidad y el panel operativo del equipo) y **adopta lo que no** (CRM como sistema de registro de contactos y oportunidades, inbox del proveedor mientras ADR-0010 lo mantenga, constructor de workflows) detrás de interfaces abstractas. Si cambia el proveedor, el núcleo sigue funcionando.

## 2. Estado del proyecto

**Fase 0 sellada (2026-10-30).** Existen el informe maestro, el PRD, la arquitectura, el diseño por módulo y del frontend, los ADR y el nido de gobernanza, más el esqueleto ADPA: once salas con compuerta importable y configuración, pasillo central, compose base y de producción, arnés físico con certificado y CI. Ninguna sala tiene lógica todavía: la fase 1 (TASK-001) empieza por el canal de WhatsApp.

| Documento | Para qué |
| :--- | :--- |
| [`docs/PROJECT_CONTEXT.md`](docs/PROJECT_CONTEXT.md) | Informe maestro: fuente de verdad del negocio, decisiones y referencias. |
| [`docs/PRD.md`](docs/PRD.md) | Requisitos funcionales por módulo, no funcionales con umbral, user stories Given/When/Then, flujos, modelo de datos, roadmap de fases 0–8, riesgos y supuestos. |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Salas ADPA y compuertas, pasillo central, datos, despliegue, seguridad por capa. |
| [`docs/modulos/`](docs/modulos/README.md) | Diseño detallado por sala: compuerta con firmas, tipos, configuración, errores, persistencia, tests. |
| [`docs/FRONTEND.md`](docs/FRONTEND.md) | Diseño del panel operativo: usuarios, navegación, pantallas con wireframes, componentes, tokens, BFF, seguridad, stack. |
| [`docs/adr/`](docs/adr/README.md) | Decisiones aceptadas (0001–0006, 0013) y pendientes (0007–0012). |
| [`docs/prompts/`](docs/prompts/system-prompt-enrutador.md) | Borradores de los system prompts (enrutador, glamping, departamentos). |
| [`docs/negocio/`](docs/negocio/README.md) | Checklist del corpus que el negocio debe entregar para el RAG. |
| [`docs/spec/`](docs/spec/README.md) | Especificación ejecutable: contratos, DDL, escenarios Gherkin y trazabilidad. |
| [`governance/artefactos/`](governance/artefactos/PRD.md) | Catálogo de salas, invariantes con árbitro, fuentes, índice de rastros, problemas. |
| [`governance/tareas/`](governance/tareas/README.md) | Una tarea por fase con sala, archivos propios, dependencias y árbitro. |

## 3. Inicio rápido (a partir de la fase 0)

```bash
# 1. Variables de entorno (sin valores en el repositorio)
cp .env.example .env

# 2. Arnés notarial: linters ADPA/huellas/UTF-8, secretos, tests y evaluaciones
./ejecutar_arnes_glamping.sh        # Windows: ejecutar_arnes_glamping.bat

# 3. Levantar el stack (beta)
docker compose up -d

# 3b. Producción (mismo compose + sobrescritura)
docker compose -f compose.yaml -f compose.production.yaml up -d
```

## 4. Arquitectura modular ADPA

El sistema es un submarino de salas estancas bajo `features/`; cada sala expone una única compuerta `<sala>_service.py` y las salas solo se hablan por compuertas. El pasillo central `app_core/` orquesta.

| Sala | Qué hace | Compuerta |
| :--- | :--- | :--- |
| `canal_whatsapp` | Cloud API oficial de Meta: webhook, envío, ventana de 24 h, plantillas, medios. | `canal_whatsapp_service.py` |
| `seguridad` | Identidad y bloqueos, allowlist por acción, rate limit, filtro de inyección, redacción de PII, audit log. | `seguridad_service.py` |
| `agente` | Claude con tool use, enrutador multi-propiedad, prompts, memoria, caché y enrutamiento de modelos. | `agente_service.py` |
| `conocimiento` | RAG en pgvector sobre el corpus privado de `CORPUS_DIR`, con «no lo sé» explícito. | `conocimiento_service.py` |
| `pms_conector` | Calendario, tarifas y reservas propios (ADR-0007). | `pms_conector_service.py` |
| `herramientas_glamping` | Servidor MCP: disponibilidad, cotización, reserva, check-in, incidencias, handoff, venta, comisión. | `herramientas_glamping_service.py` (ejecutable: `server.py`) |
| `crm_conector` | Interfaz al CRM (proveedor pendiente, ADR-0008), Inbound Webhook firmado y handoff por zona. | `crm_conector_service.py` |
| `arm_jarvis` | Lee las ventas de los vendedores, las estructura, gestiona estados, ticket, notificaciones, tablero. | `arm_jarvis_service.py` |
| `comisiones` | Reglas versionadas, cálculo reproducible, cierre de período, exportación. | `comisiones_service.py` |
| `observabilidad` | Logs sin PII, trazas por mensaje, evaluaciones en CI, alertas. | `observabilidad_service.py` |
| `panel_operativo` | Frontend y BFF del equipo: ventas por validar, tablero y cierre de comisiones, Jarvis, handoff por zona, incidencias, administración ([`docs/FRONTEND.md`](docs/FRONTEND.md)). | `panel_operativo_service.py` |

Detalle y equivalencia con la estructura del informe: [`docs/ARQUITECTURA.md` §3](docs/ARQUITECTURA.md#3-salas-adpa-equivalencia-con-la-estructura-del-informe).

## 5. Decisiones pendientes que bloquean fases

| Decisión | ADR | Bloquea |
| :--- | :--- | :--- |
| Proveedor de CRM/inbox/workflows (GoHighLevel vs Chatwoot + Attio/HubSpot + n8n) | [ADR-0008](docs/adr/ADR-0008-proveedor-capa-commodity.md) | Fase 7 |
| Registro de comisiones (propio vs CRM) | [ADR-0009](docs/adr/ADR-0009-registro-comisiones.md) | Tablero (fase 7) |
| Inbox del proveedor vs panel propio | [ADR-0010](docs/adr/ADR-0010-inbox-proveedor.md) | Fase 8 |
| Verificación de MCP de comunidad | [ADR-0011](docs/adr/ADR-0011-mcp-comunidad.md) | Implementaciones internas |
| Residencia de datos en Ecuador | [ADR-0012](docs/adr/ADR-0012-residencia-datos.md) | Fase 2 |

Supuesto crítico a validar en la fase 1: **S-01**, que la API oficial permita leer y responder el canal de vendedores como grupo; si no, cada vendedor reporta en su chat 1:1 con el número del negocio y el ARM no cambia ([PRD §13](docs/PRD.md#13-riesgos-y-supuestos)).

## 6. Gobernanza y cero regresiones (ZERAG BIAS)

- **Triaje primero:** toda sesión de IA empieza con `mcp_orchestrate_triage` ([`CLAUDE.md`](CLAUDE.md)).
- **Boceto → arnés → sellado:** una fase se da por completada solo con `ejecutar_arnes_glamping` en Exit Code 0 y su certificado en `governance/artefactos/data/`.
- **Rastros `¤`:** `git grep --untracked "¤arm-jarvis"` devuelve PRD, invariantes, tarea, ADR y código de esa capacidad. Índice en [`governance/artefactos/VPA_INDEX.md`](governance/artefactos/VPA_INDEX.md).
- **Interfaz purificada:** ningún texto de cara al huésped, al vendedor o al equipo contiene rastros.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados. Sin licencia de uso: ver [`COPYRIGHT`](COPYRIGHT). Metodología de gobernanza: Zero-Regression AI Governance BIAS.
