# TASKS — Tareas ejecutables por sala ADPA
`¤tareas-glamping` `¤coordinacion`

> **Qué es este archivo.** La lista canónica de tareas ejecutables del proyecto, descompuesta por **sala** para que varias
> personas o agentes trabajen en paralelo sin pisarse. Los archivos `TASK-00N-*.md` de esta carpeta son los **hitos de fase**
> (qué significa «fase completada»); las unidades de trabajo son las tareas de este archivo. El tablero de estado que lleva el
> servidor MCP ZERAG se alimenta de los cierres de sesión; aquí vive la especificación.
>
> **Árbitro de este archivo:** `tests/test_tareas_sin_colision.py` lee los bloques `toml` de cada tarea y falla si dos tareas de la
> misma ola reclaman rutas que se solapan, si una tarea de sala reclama rutas reservadas al coordinador, o si una tarea no
> declara sala, ola, propiedad y árbitro.

## 1. Reglas de independencia (ADPA aplicado al trabajo)

1. **Un dueño por ruta escribible en cada ola.** Cada tarea declara en `propiedad` las rutas que puede escribir. Dentro de una
   misma ola, dos tareas nunca comparten ruta. Una tarea no toca nada fuera de su `propiedad`; si lo necesita, lo pide al
   coordinador o espera a la ola siguiente.
2. **Toda tarea de sala posee siempre** `features/<sala>/**`, `tests/<sala>/**` y `docs/modulos/<sala>.md`, más los recursos
   asignados a esa sala (evals, prompts, scripts) en la tabla §2.
3. **Contratos congelados.** Las firmas de las compuertas `*_service.py` quedaron fijadas en la fase 0 (TASK-000). Una tarea de
   sala puede **añadir** métodos a su propia compuerta, nunca cambiar ni quitar los existentes. Cambiar un contrato es trabajo
   del coordinador (tareas `T-x10`), se hace entre olas y se anuncia en este archivo.
4. **Dobles de prueba propios.** Las pruebas de una sala no importan los `Fake*` de otra sala: cada sala escribe sus propios
   dobles en `tests/<sala>/dobles.py` contra la interfaz de la compuerta (DPD: duplicar para delegar). Los `Fake*` de
   ejecución (`fake_internal.py`) viven en la sala dueña y los usa `app_core` en beta.
5. **Rutas reservadas al coordinador** (solo tareas `T-x10`, `T-x11` y de infraestructura): `app_core/**`, `compose.yaml`,
   `compose.production.yaml`, `Dockerfile`, `infra/**`, `.env.example`, `pyproject.toml`, `.github/**`, `scripts/arnes_glamping.py`,
   `scripts/verificar_secretos.py`, `tests/conftest.py`, `tests/test_*.py` (raíz), `tests/integracion/**`, `tests/app_core/**`,
   `governance/**`, `docs/PRD.md`, `docs/spec/**`, `docs/ARQUITECTURA.md`, `docs/FRONTEND.md`, `docs/adr/**`, `README.md`, `CLAUDE.md`.
6. **Una tarea abierta por sala a la vez.** Las tareas sobre la misma sala en olas distintas son secuenciales por `depende_de`.
7. **Sellado individual.** Cada tarea termina con `ejecutar_arnes_glamping` en Exit Code 0 sobre todo el repositorio (no solo
   su sala), huellas `¦` consolidadas a `¤` y su bloque de este archivo en `estado = "sellada"`.
8. **Integración es trabajo del coordinador.** Las pruebas que levantan varias salas juntas viven en `tests/integracion/` y
   pertenecen a las tareas `T-x11` / `T-x10`; una tarea de sala no las escribe.
9. **Evaluaciones.** Cada sala con suite expone `evaluar(...)` en su compuerta y es dueña de su archivo de casos en `evals/`.
   `scripts/run_evals.py` (sala `observabilidad`) solo despacha a esas compuertas y aplica los umbrales de
   `config_observabilidad.yaml`.
10. **Toda tarea traduce la especificación.** Una tarea implementa los contratos de `docs/spec/contratos/`, las tablas de su
    esquema en `docs/spec/esquema.sql` y los escenarios de `docs/spec/features/` con las etiquetas de sus `requisitos`. No
    interpreta: si la especificación no alcanza, se detiene y el coordinador la corrige primero. La matriz está en
    `docs/spec/TRAZABILIDAD.md`.

## 2. Matriz de propiedad por sala (constante en todas las olas)

| Sala | Rutas propias además de `features/<sala>/**`, `tests/<sala>/**`, `docs/modulos/<sala>.md` | Rol |
| :--- | :--- | :--- |
| `canal_whatsapp` | — | `¤¤integration-engineer` |
| `seguridad` | `evals/inyecciones.jsonl`, `evals/pii.jsonl`, `docs/privacidad/**` | `¤¤security-engineer` |
| `agente` | `docs/prompts/**`, `evals/enrutador.jsonl` | `¤¤machine-learning-engineer` |
| `conocimiento` | `scripts/seed_knowledge.py`, `evals/set_dorado.jsonl`, `docs/negocio/README.md` (checklist; el corpus lo entrega el negocio en `CORPUS_DIR`, fuera del repositorio) | `¤¤data-engineer` |
| `pms_conector` | — | `¤¤integration-engineer` |
| `herramientas_glamping` | — | `¤¤backend-developer` |
| `crm_conector` | — | `¤¤integration-engineer` |
| `arm_jarvis` | `evals/ventas.jsonl` | `¤¤backend-developer` |
| `comisiones` | — | `¤¤backend-developer` |
| `observabilidad` | `scripts/run_evals.py` | `¤¤devops-engineer` |
| `panel_operativo` | `tests/e2e/**` | `¤¤frontend-developer` |
| `operaciones` (condicional) | — | `¤¤backend-developer` |
| *coordinador* (`pasillo_central`, `infraestructura`) | las rutas reservadas de la regla 5 | `¤¤solutions-architect`, `¤¤devops-engineer` |

## 3. Olas de ejecución

Una **ola** agrupa tareas que pueden correr en paralelo porque sus rutas son disjuntas. La ola termina con la tarea de
coordinación (`T-x10`) que enlaza las salas en `app_core` y, si aplica, la de integración (`T-x11`) que verifica el hito de fase.

| Ola | Fase | Tareas en paralelo | Cierre de ola | Hito |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 1 MVP WhatsApp | T-101 canal · T-102 seguridad · T-103 observabilidad · T-104 agente | T-110 pasillo · T-111 integración | TASK-001 |
| 2 | 2–3 RAG y PMS | T-201 conocimiento · T-202 pms (fake) · T-203 herramientas · T-204 operaciones (cond.) | T-212 pms real (bloq. ADR-0007) · T-210 pasillo · T-211 integración | TASK-002, TASK-003 |
| 3 | 4 Multi-propiedad | T-301 agente enrutador · T-302 crm (fake) · T-303 panel handoff · T-304 seguridad RLS | T-310 pasillo · T-311 integración | TASK-004 |
| 4 | 5 Seguridad y observabilidad | T-401 seguridad · T-402 observabilidad · T-403 agente caché · T-404 panel admin | T-410 infraestructura beta · T-411 integración (salida de beta) | TASK-005 |
| 5 | 6 ARM | T-501 comisiones · T-502 arm · T-503 canal vendedores · T-504 herramientas ventas · T-505 panel ventas | T-510 pasillo · T-511 integración | TASK-006 |
| 6 | 7 CRM y producción | T-601 crm real · T-602 arm tablero · T-603 comisiones export · T-604 panel tablero | T-610 producción · T-611 integración (hito producción) | TASK-007 |
| 7 | 8 (condicional) | T-701 panel inbox | — | TASK-008 |
| 8 | 8 Terminal móvil | T-801 panel terminal móvil | T-810 despliegue móvil | RF-PAN-11..14 |

Estados: `pendiente` → `boceto` → `sellada` · `bloqueada`. Las olas 5 y 6 pueden solaparse en el tiempo: no comparten rutas.

---

## Ola 1 — Fase 1: MVP WhatsApp

### T-101 — Canal de WhatsApp: webhook, envío, ventana de 24 h, plantillas, medios
`¤canal-whatsapp`
```toml
id = "T-101"
ola = 1
fase = 1
estado = "pendiente"
sala = "canal_whatsapp"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-01", "RF-GW-02", "RF-GW-03", "RF-GW-04", "RF-GW-05", "RF-GW-07", "RF-GW-08"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/canal_whatsapp/**", "tests/canal_whatsapp/**", "docs/modulos/canal_whatsapp.md"]
consume = ["seguridad_service (solo descargar_medio)", "observabilidad_service"]
arbitro = "tests/canal_whatsapp/{test_webhook,test_envio,test_ventana_24h,test_plantillas,test_medios}.py con la API de Meta simulada; arnés Exit Code 0"
```
Entregables: `webhook_internal.py` (verificación, firma, dedup), `envio_internal.py` (texto, botones, listas, estados, reintentos), `plantillas_internal.py`, `medios_internal.py`, persistencia `esquema canal`. Dobles propios de `seguridad` y `observabilidad` en `tests/canal_whatsapp/dobles.py`. **Hecho cuando** los cinco tests existen y pasan, `INV_FIRMA_WEBHOOK_META` e `INV_VENTANA_24H` tienen prueba que falla si se quita la validación. La prueba con el número real es de T-111.

### T-102 — Seguridad base: identidad, allowlist, rate limit, inyección, PII, audit log y consentimiento
`¤seguridad-canal`
```toml
id = "T-102"
ola = 1
fase = 1
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-01", "RF-SEC-02", "RF-SEC-03", "RF-SEC-04 (base)", "RF-SEC-05", "RF-SEC-06", "RF-PRIV-01", "RF-PRIV-02", "RNF-18"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "tests/seguridad/**", "docs/modulos/seguridad.md", "evals/inyecciones.jsonl", "evals/pii.jsonl", "docs/privacidad/**"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/{test_identidad,test_allowlist,test_rate_limit,test_pii,test_audit_log,test_consentimiento,test_inventario_datos}.py; arnés Exit Code 0"
```
Entregables: `identidad_internal.py`, `allowlist_internal.py`, `audit_internal.py` (`INSERT`-only), `consentimiento_internal.py`, `rate_limit_internal.py`, `pii_internal.py` (tokenizar/rehidratar con bóveda cifrada), `identificar`, `filtrar_entrada` con los patrones base de inyección, `filtrar_salida`, inventario en `docs/privacidad/INVENTARIO.md`. `evals/inyecciones.jsonl` queda creado vacío y reservado para T-401. **Hecho cuando** `test_rate_limit.py` intenta desactivar el límite con cada rol y falla, y `test_pii.py` captura el cliente HTTP de un doble de modelo sin ningún teléfono en claro.

### T-103 — Observabilidad básica: logs JSON sin PII y traza por mensaje
`¤observabilidad`
```toml
id = "T-103"
ola = 1
fase = 1
estado = "pendiente"
sala = "observabilidad"
rol = "¤¤devops-engineer"
requisitos = ["RF-OBS-01", "RF-OBS-02"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/observabilidad/**", "tests/observabilidad/**", "docs/modulos/observabilidad.md", "scripts/run_evals.py"]
consume = []
arbitro = "tests/observabilidad/{test_logs,test_trazas}.py; arnés Exit Code 0"
```
Entregables: `logs_internal.py` (JSON por línea, verificación de ausencia de PII), `trazas_internal.py` (`iniciar_traza`, `span` como context manager, `cerrar_traza`, persistencia `esquema observabilidad`), cálculo de tokens y costo por span. `scripts/run_evals.py` no cambia en esta ola (lo evoluciona T-402). **Hecho cuando** una traza sintética con tres spans se persiste y se recupera, y un log con un teléfono en claro es rechazado.

### T-104 — Agente MVP: prompt del glamping, bucle de herramientas, memoria, degradación
`¤agente-enrutador`
```toml
id = "T-104"
ola = 1
fase = 1
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-02", "RF-AG-04", "RF-AG-05", "RF-AG-06"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/agente/**", "tests/agente/**", "docs/modulos/agente.md", "docs/prompts/**", "evals/enrutador.jsonl"]
consume = ["seguridad_service", "herramientas_glamping_service", "conocimiento_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/agente/{test_prompts,test_bucle_herramientas,test_degradacion,test_memoria}.py con doble de modelo y dobles de compuertas; arnés Exit Code 0"
```
Entregables: `cliente_modelo_internal.py` (cliente de Claude con timeout y conteo de tokens), `prompts_internal.py` (carga y hash; solo variante `glamping` en esta ola), `bucle_herramientas_internal.py` (tope de iteraciones, errores tipados), `memoria_internal.py` (`esquema agente`), `atender`. `docs/prompts/system-prompt-glamping.md` pasa de borrador a versión 1 con los datos reales inyectados. `evals/enrutador.jsonl` se crea vacío y reservado para T-301. **Hecho cuando** el bucle se detiene al tope y escala, un fallo de herramienta no inventa resultado, y un reinicio simulado conserva la conversación.

### T-110 — Pasillo central, fase 1: rutas del webhook, receptores y arranque real
`¤pasillo-central`
```toml
id = "T-110"
ola = 1
fase = 1
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-GW-01 (ruta)", "RNF-08", "RNF-11", "RNF-12", "RNF-14", "RNF-19"]
depende_de = ["T-101", "T-102", "T-103", "T-104"]
bloqueada_por = []
propiedad = ["app_core/**", "tests/app_core/**", "compose.yaml", "compose.production.yaml", ".env.example"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/**; docker compose config en CI; arnés Exit Code 0"
```
Entregables: rutas `GET/POST /webhook` → `canal.verificar_webhook` / `canal.recibir` → receptor; cola asíncrona de procesamiento (responder 200 en < 2 s); `--worker` real si hace falta para el procesamiento; variables nuevas en `.env.example`. **Hecho cuando** el contenedor construye con las cuatro salas reales y los tests de `app_core` cubren la ruta del webhook con firma válida e inválida.

### T-111 — Integración fase 1: conversación real, RNF-01, S-01 y decisión de audio
`¤bbap-glamping`
```toml
id = "T-111"
ola = 1
fase = 1
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["RNF-01", "INV_INTERFAZ_PURIFICADA", "S-01", "S-02", "S-09"]
depende_de = ["T-110"]
bloqueada_por = ["S-02"]
propiedad = ["tests/integracion/**", "tests/test_interfaz_purificada.py", "governance/tareas/TASK-001-mvp-whatsapp.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase1.py (salas reales con doble de Meta y de modelo); conversación real registrada con traza; RNF-01 anotado en TASK-001; arnés Exit Code 0"
```
Entregables: prueba de integración de extremo a extremo; conversación real con el número de pruebas y P95 de la semana anotado; `tests/test_interfaz_purificada.py` sobre plantillas y mensajes; **investigación de S-01** (lectura del canal de vendedores con la API oficial) documentada en TASK-001 y PRD §13.2, porque decide `canal_vendedores.modo` y las plantillas a solicitar; decisión de transcripción de audio anotada. **Hecho cuando** TASK-001 pasa a `sellada`.

---

## Ola 2 — Fases 2 y 3: RAG y PMS

### T-201 — Conocimiento: indexación, chunking, recuperación híbrida, «no lo sé», set dorado
`¤conocimiento-rag`
```toml
id = "T-201"
ola = 2
fase = 2
estado = "pendiente"
sala = "conocimiento"
rol = "¤¤data-engineer"
requisitos = ["RF-RAG-01", "RF-RAG-02", "RF-RAG-03", "RF-RAG-04", "RF-RAG-05", "RF-RAG-06", "RNF-04"]
depende_de = ["TASK-000"]
bloqueada_por = ["S-03", "ADR-0012 (solo para indexar datos reales)"]
propiedad = ["features/conocimiento/**", "tests/conocimiento/**", "docs/modulos/conocimiento.md", "scripts/seed_knowledge.py", "evals/set_dorado.jsonl", "docs/negocio/README.md"]
consume = ["observabilidad_service"]
arbitro = "tests/conocimiento/{test_indexacion,test_chunking,test_recuperacion,test_citacion}.py; ConocimientoService.evaluar(set_dorado) ≥ umbrales; arnés Exit Code 0"
```
Entregables: `chunker_internal.py`, `indexador_internal.py` (idempotente, reemplazo por `version_hash`), `recuperador_internal.py` (HNSW + BM25, filtro obligatorio por propiedad), `embeddings_internal.py`, `evaluador_internal.py`, `scripts/seed_knowledge.py`, `evals/set_dorado.jsonl` (≥ 100 preguntas + ≥ 30 trampa, redactadas con el negocio), esquema `conocimiento` con RLS. Hasta ADR-0012 se indexa corpus sintético. **Hecho cuando** fidelidad ≥ 95 %, abstención ≥ 90 %, 0 alucinaciones de precio/política y P95 ≤ 150 ms en el benchmark.

### T-202 — Conector PMS: interfaz completa, FakePMS y selección por configuración
`¤pms-conector`
```toml
id = "T-202"
ola = 2
fase = 3
estado = "pendiente"
sala = "pms_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-PMS-01", "RF-PMS-02 (fake)", "RF-PMS-03", "RF-PMS-04", "RF-PMS-05", "RF-PMS-06"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/pms_conector/**", "tests/pms_conector/**", "docs/modulos/pms_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/pms_conector/{test_contrato,test_seleccion_proveedor,test_errores}.py contra FakePMS; arnés Exit Code 0"
```
Entregables: `base_internal.py` (ABC `PMSConnector`), `fake_internal.py` (dos propiedades, unidades, disponibilidad, cotización, reservas preliminares con expiración, instrucciones de check-in, incidencias y housekeeping en memoria), errores tipados, escrituras deshabilitadas por defecto con clave de idempotencia, `esquema pms` (caché e idempotencia). **Hecho cuando** el test de contrato está parametrizado para aceptar cualquier implementación y pasa con `FakePMS`.

### T-203 — Herramientas MCP: esquemas, autorización y ejecución de las herramientas de huéspedes
`¤herramientas-mcp`
```toml
id = "T-203"
ola = 2
fase = 3
estado = "pendiente"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-MCP-01", "RF-MCP-02", "RF-MCP-03", "RF-MCP-04", "RF-MCP-05", "RF-MCP-06", "RF-MCP-07"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/herramientas_glamping/**", "tests/herramientas_glamping/**", "docs/modulos/herramientas_glamping.md"]
consume = ["seguridad_service", "pms_conector_service", "conocimiento_service", "crm_conector_service", "observabilidad_service"]
arbitro = "tests/herramientas_glamping/{test_contratos,test_server}.py con dobles propios de todas las compuertas; arnés Exit Code 0"
```
Entregables: `esquemas/*.json` (entrada y salida de las siete herramientas), `herramientas_internal.py` (validación, `seguridad.autorizar`, despacho a la compuerta dueña, `ResultadoHerramienta`), `listar`/`ejecutar`/`esquema`, transporte MCP en `server.py` (stdio y http en `agent-net`). **Hecho cuando** cada herramienta rechaza entrada inválida con mensaje legible, rechaza rol no autorizado y pasa su contrato con los dobles.

### T-204 — Operaciones (condicional): registro de incidencias si el PMS no las cubre
`¤operaciones-incidencias`
```toml
id = "T-204"
ola = 2
fase = 3
estado = "bloqueada"
sala = "operaciones"
rol = "¤¤backend-developer"
requisitos = ["RF-MCP-05 (registro)", "INV_TICKET_UNICO (I-AAAA-NNNN)"]
depende_de = ["TASK-000"]
bloqueada_por = ["ADR-0007"]
propiedad = ["features/operaciones/**", "tests/operaciones/**", "docs/modulos/operaciones.md"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/operaciones/{test_incidencias,test_ticket}.py (concurrencia); arnés Exit Code 0"
```
Solo nace si ADR-0007 concluye que el PMS elegido no cubre incidencias. El coordinador añade entonces la sala al catálogo (`governance/artefactos/PRD.md`) antes de que esta tarea empiece.

### T-212 — Conector PMS: proveedor real (Kamra, Repull MCP u Hospitable)
`¤pms-conector`
```toml
id = "T-212"
ola = 2
fase = 3
estado = "bloqueada"
sala = "pms_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-PMS-02 (real)", "S-04"]
depende_de = ["T-202"]
bloqueada_por = ["ADR-0007", "ADR-0011 (si usa MCP de comunidad)"]
propiedad = ["features/pms_conector/**", "tests/pms_conector/**", "docs/modulos/pms_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/pms_conector/test_contrato.py parametrizado con el proveedor real sobre fixtures grabados; reserva preliminar real en el entorno de pruebas del PMS; arnés Exit Code 0"
```
Misma sala que T-202, por eso es secuencial. Entregables: `<proveedor>_internal.py`, fixtures grabados en `tests/pms_conector/fixtures/`, `proveedor` en `config_pms_conector.yaml`. **Hecho cuando** el mismo test de contrato pasa con `FakePMS` y con el real.

### T-210 — Pasillo central, fases 2–3: servidor MCP en compose, egreso, semilla del RAG en el arnés
`¤pasillo-central`
```toml
id = "T-210"
ola = 2
fase = 3
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RNF-10 (egreso)", "RNF-14"]
depende_de = ["T-201", "T-202", "T-203"]
bloqueada_por = []
propiedad = ["app_core/**", "tests/app_core/**", "compose.yaml", "compose.production.yaml", ".env.example", "scripts/arnes_glamping.py"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/**; arnés Exit Code 0 incluyendo el paso de semilla sintética del RAG"
```
Entregables: servicio `mcp-tools` operativo, lista de egreso con PMS y embeddings, paso del arnés que ejecuta `seed_knowledge.py` sobre el corpus sintético y la evaluación `rag`.

### T-211 — Integración fases 2–3: reserva preliminar de extremo a extremo
`¤bbap-glamping`
```toml
id = "T-211"
ola = 2
fase = 3
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["US-01", "US-02", "US-04", "US-12", "RNF-02"]
depende_de = ["T-210"]
bloqueada_por = []
propiedad = ["tests/integracion/**", "governance/tareas/TASK-002-rag.md", "governance/tareas/TASK-003-pms-mcp.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase3.py (agente + herramientas + FakePMS + RAG sintético); RNF-02 medido; arnés Exit Code 0"
```
**Hecho cuando** TASK-002 y TASK-003 pasan a `sellada` (TASK-003 con `FakePMS` si T-212 sigue bloqueada, y se anota).

---

## Ola 3 — Fase 4: Multi-propiedad

### T-301 — Agente: enrutador multi-propiedad, herramientas por rol, prompts de enrutador y departamentos
`¤agente-enrutador`
```toml
id = "T-301"
ola = 3
fase = 4
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-01", "RF-AG-03", "RF-AG-08", "US-03 (lógica)", "INV_ENVIO_UNICO"]
depende_de = ["T-104"]
bloqueada_por = []
propiedad = ["features/agente/**", "tests/agente/**", "docs/modulos/agente.md", "docs/prompts/**", "evals/enrutador.jsonl"]
consume = ["seguridad_service", "herramientas_glamping_service", "conocimiento_service", "canal_whatsapp_service", "pms_conector_service (vía herramientas)", "observabilidad_service"]
arbitro = "tests/agente/{test_enrutador,test_allowlist_herramientas}.py 20/20; AgenteService.evaluar(enrutador) = 1.0 aciertos; arnés Exit Code 0"
```
Entregables: `enrutador_internal.py`, prompts `enrutador` y `departamentos` versión 1, `herramientas_para(rol, propiedad)`, `enviar_checkins_del_dia`, `entrar_en_silencio`/`reanudar`, `evals/enrutador.jsonl` con 20 conversaciones etiquetadas (incluidas ambiguas). **Hecho cuando** `INV_PROPIEDAD_RESUELTA` e `INV_SIN_FUGA_ENTRE_PROPIEDADES` tienen prueba que falla si se quita el filtro.

### T-302 — Conector CRM: interfaz completa, FakeCRM y asignación de conversaciones
`¤crm-conector`
```toml
id = "T-302"
ola = 3
fase = 4
estado = "pendiente"
sala = "crm_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-CRM-01", "RF-CRM-02 (fake)", "RF-CRM-06", "RF-MCP-06 (real)"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/crm_conector/**", "tests/crm_conector/**", "docs/modulos/crm_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/crm_conector/{test_contrato,test_seleccion_proveedor,test_confinamiento}.py contra FakeCRM; arnés Exit Code 0"
```
Entregables: `base_internal.py` (ABC `CRMConnector`), `fake_internal.py` (contactos, oportunidades, conversaciones asignables por zona, eventos), `registrar_receptor`, `esquema crm` (referencias). `publicar_venta`, cola y eventos firmados quedan para T-601.

### T-303 — Panel operativo: acceso, inicio, handoffs por zona, detalle de conversación, incidencias
`¤panel-operativo`
```toml
id = "T-303"
ola = 3
fase = 4
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-01", "RF-PAN-07", "RF-PAN-08", "INV_PANEL_POR_ROL", "INV_PANEL_SIN_LOGICA"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["seguridad_service", "agente_service", "canal_whatsapp_service", "crm_conector_service", "pms_conector_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/{test_sesiones,test_bff_handoff,test_sin_logica}.py (cada endpoint con cada rol); tests/e2e/test_handoff_zona.py en navegador real sobre localhost; arnés Exit Code 0"
```
Entregables: `sesiones_internal.py` (código por WhatsApp, cookie, CSRF), `bff_internal.py` con las rutas de sesión, handoffs e incidencias, `ui/` con P-01, P-02, P-08, P-09, P-10 (`docs/FRONTEND.md` §4), build en `estaticos/`, `esquema panel`. Los dobles de las compuertas consumidas viven en `tests/panel_operativo/dobles.py`. **Hecho cuando** un gestor de la zona A recibe 403 al tocar la zona B y las e2e de US-09/US-10 pasan.

### T-304 — Seguridad: Row-Level Security por propiedad
`¤seguridad-canal`
```toml
id = "T-304"
ola = 3
fase = 4
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-07", "RF-SEC-08", "INV_RLS_MULTI_INQUILINO", "INV_SECRETO_OPERATIVO"]
depende_de = ["T-102"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "tests/seguridad/**", "docs/modulos/seguridad.md", "evals/inyecciones.jsonl"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/test_rls.py contra PostgreSQL real en CI; arnés Exit Code 0"
```
Entregables: migraciones de políticas RLS para los esquemas con `propiedad_id`, rol de aplicación `NOBYPASSRLS`, prueba que con propiedad A no devuelve filas de B.

### T-310 — Pasillo central, fase 4: planificador de check-in, ruta del panel, eventos del CRM
`¤pasillo-central`
```toml
id = "T-310"
ola = 3
fase = 4
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["US-03 (disparo)", "RF-PAN (montaje)", "RF-CRM-05 (ruta)"]
depende_de = ["T-301", "T-302", "T-303", "T-304"]
bloqueada_por = []
propiedad = ["app_core/**", "tests/app_core/**", "compose.yaml", "compose.production.yaml", ".env.example", "infra/**"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/**; arnés Exit Code 0"
```
Entregables: tarea programada `checkin_del_dia` en el worker, montaje de `/panel/*` y estáticos, ruta `POST /crm/eventos` → `crm.recibir_evento` → receptores (`agente.reanudar`, panel), cabeceras del proxy para el panel.

### T-311 — Integración fase 4: check-in autónomo y handoff con dos propiedades
`¤bbap-glamping`
```toml
id = "T-311"
ola = 3
fase = 4
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["US-03", "US-09", "US-10", "US-13"]
depende_de = ["T-310"]
bloqueada_por = []
propiedad = ["tests/integracion/**", "governance/tareas/TASK-004-multipropiedad.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase4.py; arnés Exit Code 0"
```
**Hecho cuando** TASK-004 pasa a `sellada`.

---

## Ola 4 — Fase 5: Seguridad y observabilidad (salida de beta)

### T-401 — Seguridad completa: allowlist por acción, filtro de inyección, audit log
`¤seguridad-canal`
```toml
id = "T-401"
ola = 4
fase = 5
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-04", "RF-PRIV-03", "RF-PRIV-04", "RF-PRIV-05", "RF-PRIV-06", "OP-10", "RNF-07", "RNF-17"]
depende_de = ["T-304"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "tests/seguridad/**", "docs/modulos/seguridad.md", "evals/inyecciones.jsonl"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/{test_retencion,test_criptoborrado,test_solicitudes_titular,test_inventario_datos}.py; SeguridadService.evaluar(inyecciones) = 0 éxitos y ≤ 2 % falsos positivos; suite pii sobre umbral; arnés Exit Code 0"
```
Entregables: `injection_internal.py` + `patrones_inyeccion.yaml` (≥ 40 patrones, es/en/pt/fr, heurísticas), `retencion_internal.py`, `titulares_internal.py` (solicitudes y criptoborrado), `informe_semanal`, `administrar_usuarios`, `evals/inyecciones.jsonl` completo. **Hecho cuando** las suites `inyecciones` y `pii` superan su umbral y el criptoborrado no altera el audit log.

### T-402 — Observabilidad completa: despacho de evaluaciones, métricas del PRD, alertas
`¤observabilidad`
```toml
id = "T-402"
ola = 4
fase = 5
estado = "pendiente"
sala = "observabilidad"
rol = "¤¤devops-engineer"
requisitos = ["RF-OBS-03", "RF-OBS-04", "RNF-13"]
depende_de = ["T-103"]
bloqueada_por = []
propiedad = ["features/observabilidad/**", "tests/observabilidad/**", "docs/modulos/observabilidad.md", "scripts/run_evals.py"]
consume = ["conocimiento_service.evaluar", "seguridad_service.evaluar", "agente_service.evaluar", "arm_jarvis_service.evaluar"]
arbitro = "tests/observabilidad/{test_alertas,test_metricas}.py; scripts/run_evals.py despacha las cuatro suites y falla bajo umbral; arnés Exit Code 0"
```
Entregables: `metricas_internal.py` (OP-01..OP-10 desde trazas), `alertas_internal.py` (silencio, errores, cola, costo), `scripts/run_evals.py` que despacha a `evaluar(...)` de cada compuerta y aplica umbrales de `config_observabilidad.yaml`. Una suite cuya sala aún no expone `evaluar` se reporta OMITIDA, nunca verde.

### T-403 — Agente: caché semántico y enrutamiento de modelos
`¤agente-enrutador`
```toml
id = "T-403"
ola = 4
fase = 5
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-07", "OP-09", "RNF-16", "INV_CACHE_SIN_PRECIOS"]
depende_de = ["T-301"]
bloqueada_por = []
propiedad = ["features/agente/**", "tests/agente/**", "docs/modulos/agente.md", "docs/prompts/**", "evals/enrutador.jsonl"]
consume = ["conocimiento_service (embeddings vía compuerta)", "observabilidad_service"]
arbitro = "tests/agente/test_enrutamiento_modelos.py; arnés Exit Code 0"
```
Entregables: `cache_internal.py` (exclusión por términos de precio/disponibilidad), decisión de modelo registrada en la traza, acuse «un momento…» si una herramienta tarda más de 3 s.

### T-404 — Panel operativo: administración básica y calidad de la interfaz
`¤panel-operativo`
```toml
id = "T-404"
ola = 4
fase = 5
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-09 (usuarios, auditoría, privacidad, salud)", "RF-PAN-10"]
depende_de = ["T-303"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/test_bff_admin.py (cada rol); tests/e2e/test_calidad_ui.py (accesibilidad AA, LCP ≤ 2,5 s, 0 rastros en el build); arnés Exit Code 0"
```
Entregables: P-11 usuarios, roles y bloqueos, auditoría, solicitudes de titulares, salud del sistema; auditoría de accesibilidad y presupuesto de rendimiento en CI; `tests/test_interfaz_purificada.py` extendido al build (coordinado con T-410, que es dueño de ese archivo: el panel entrega la función de comprobación en su sala y el coordinador la invoca).

### T-410 — Infraestructura beta: prueba de carga, aislamiento de red, alertas de despliegue
`¤infra-hibrida`
```toml
id = "T-410"
ola = 4
fase = 5
estado = "pendiente"
sala = "infraestructura"
rol = "¤¤devops-engineer"
requisitos = ["RNF-05", "RNF-06", "RNF-10", "INV_RED_AISLADA"]
depende_de = ["T-401", "T-402", "T-403", "T-404"]
bloqueada_por = []
propiedad = ["compose.yaml", "compose.production.yaml", "infra/**", "scripts/arnes_glamping.py", "scripts/verificar_secretos.py", ".github/**", "tests/test_interfaz_purificada.py", "tests/integracion/**", "app_core/**", "tests/app_core/**"]
consume = ["todas las compuertas"]
arbitro = "prueba de carga (50 conversaciones, 200 msg/min) con RNF-01 dentro de umbral; prueba de conexión negativa desde agent-net; sondeo de salud; arnés Exit Code 0"
```
Entregables: script de carga en `tests/integracion/carga/`, paso del arnés de despliegue con conexión negativa, sondeo externo de `/health`, alertas conectadas al canal del administrador.

### T-411 — Integración fase 5: salida de beta
`¤bbap-glamping`
```toml
id = "T-411"
ola = 4
fase = 5
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["OP-10", "RNF-06", "RNF-10", "RNF-13", "US-11", "US-17"]
depende_de = ["T-410"]
bloqueada_por = []
propiedad = ["governance/tareas/TASK-005-seguridad-observabilidad.md"]
consume = []
arbitro = "arnés Exit Code 0 con las cuatro suites de evaluación presentes; métricas anotadas en TASK-005; aprobación del propietario"
```
**Hecho cuando** TASK-005 pasa a `sellada` y el propietario aprueba la salida de beta.

---

## Ola 5 — Fase 6: ARM «Jarvis»

### T-501 — Comisiones: reglas versionadas, cálculo reproducible, cierre de período
`¤comisiones`
```toml
id = "T-501"
ola = 5
fase = 6
estado = "pendiente"
sala = "comisiones"
rol = "¤¤backend-developer"
requisitos = ["RF-COM-01", "RF-COM-02", "RF-COM-04", "INV_COMISION_REPRODUCIBLE"]
depende_de = ["TASK-000"]
bloqueada_por = ["ADR-0009 (solo si decide que el CRM es la fuente de verdad)"]
propiedad = ["features/comisiones/**", "tests/comisiones/**", "docs/modulos/comisiones.md"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/comisiones/{test_reglas,test_cierre_periodo}.py; arnés Exit Code 0"
```
Entregables: `desglose` y `estado_cuenta` para el panel (ADR-0015), `reglas_internal.py` (vigencia a fecha de venta, versiones, escalones), `periodo_internal.py` (cierre inmutable, ajustes al período abierto), `esquema comisiones` con disparador que rechaza `UPDATE` en períodos cerrados.

### T-502 — ARM: ingesta, extracción, estados, ticket, comisión, notificación, consulta propia, asistente del líder
`¤arm-jarvis`
```toml
id = "T-502"
ola = 5
fase = 6
estado = "pendiente"
sala = "arm_jarvis"
rol = "¤¤backend-developer"
requisitos = ["RF-ARM-01", "RF-ARM-02", "RF-ARM-03", "RF-ARM-04", "RF-ARM-05", "RF-ARM-06", "RF-ARM-07", "RF-ARM-09", "RF-ARM-10", "OP-07", "OP-08", "RNF-03"]
depende_de = ["TASK-000"]
bloqueada_por = ["S-01 (define canal.modo; la lógica no cambia)"]
propiedad = ["features/arm_jarvis/**", "tests/arm_jarvis/**", "docs/modulos/arm_jarvis.md", "evals/ventas.jsonl"]
consume = ["seguridad_service", "comisiones_service", "crm_conector_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/arm_jarvis/{test_ingesta,test_estados,test_comision,test_ticket,test_notificacion,test_consulta_comision,test_asistente_lider}.py; ArmJarvisService.evaluar(ventas) ≥ 95 %; arnés Exit Code 0"
```
Entregables: `extractor_internal.py` (cliente de Claude propio → `VentaExtraida`, preguntas por campos faltantes), `estados_internal.py` (transiciones auditadas), `ticket_internal.py` (secuencia por año con bloqueo de fila), `notificador_internal.py`, `asistente_lider_internal.py`, `evals/ventas.jsonl` (≥ 60 mensajes reales anonimizados), `esquema arm`. Dobles propios de `comisiones`, `crm`, `canal` y `seguridad`. **Hecho cuando** `test_ticket.py` prueba concurrencia sin huecos ni duplicados y `test_consulta_comision.py` demuestra que no hay fuga entre vendedores.

### T-503 — Canal de WhatsApp: canal de vendedores (grupo o 1:1 según S-01)
`¤canal-whatsapp`
```toml
id = "T-503"
ola = 5
fase = 6
estado = "pendiente"
sala = "canal_whatsapp"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-06"]
depende_de = ["T-101", "T-111 (resultado de S-01)"]
bloqueada_por = ["S-01"]
propiedad = ["features/canal_whatsapp/**", "tests/canal_whatsapp/**", "docs/modulos/canal_whatsapp.md"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/canal_whatsapp/test_enrutamiento_canal.py (un mensaje de vendedor nunca llega al receptor de huéspedes y viceversa); arnés Exit Code 0"
```
Entregables: `enrutamiento_canal_internal.py` (`clasificar_canal` por remitente registrado como vendedor o por `grupo_id`), despacho al receptor correcto, plantilla `comision_validada` registrada.

### T-504 — Herramientas MCP: registrar_venta y consultar_comision_propia
`¤herramientas-mcp`
```toml
id = "T-504"
ola = 5
fase = 6
estado = "pendiente"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-MCP-08", "RF-MCP-09"]
depende_de = ["T-203"]
bloqueada_por = []
propiedad = ["features/herramientas_glamping/**", "tests/herramientas_glamping/**", "docs/modulos/herramientas_glamping.md"]
consume = ["seguridad_service", "arm_jarvis_service", "comisiones_service", "observabilidad_service"]
arbitro = "tests/herramientas_glamping/test_contratos.py ampliado a las dos herramientas con dobles propios; arnés Exit Code 0"
```

### T-505 — Panel operativo: ventas por validar, detalle de venta, Jarvis
`¤panel-operativo`
```toml
id = "T-505"
ola = 5
fase = 6
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-02", "RF-PAN-03", "RF-PAN-06", "US-06"]
depende_de = ["T-404"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["arm_jarvis_service", "comisiones_service", "seguridad_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/{test_bff_ventas,test_bff_jarvis}.py; tests/e2e/test_validar_venta.py (validar con un toque, corrección de campos dudosos, conflicto); arnés Exit Code 0"
```
Entregables: P-03, P-04, P-07 (`docs/FRONTEND.md` §4), componentes `TarjetaVenta`, `HojaCorreccion`, `DialogoMotivo`, `ChatJarvis`.

### T-510 — Pasillo central, fase 6: canal de vendedores en producción de pruebas
`¤pasillo-central`
```toml
id = "T-510"
ola = 5
fase = 6
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-GW-06 (configuración)", "RF-ARM-06 (plantilla aprobada)"]
depende_de = ["T-501", "T-502", "T-503", "T-504", "T-505"]
bloqueada_por = []
propiedad = ["app_core/**", "tests/app_core/**", "compose.yaml", "compose.production.yaml", ".env.example"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/**; arnés Exit Code 0"
```
Entregables: `canal_vendedores.modo` fijado según S-01 en `.env.example` y configuración, plantilla `comision_validada` aprobada en Meta, receptores verificados.

### T-511 — Integración fase 6: venta de extremo a extremo
`¤bbap-glamping`
```toml
id = "T-511"
ola = 5
fase = 6
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["US-05", "US-06", "US-07", "US-15", "OP-07", "OP-08"]
depende_de = ["T-510"]
bloqueada_por = []
propiedad = ["tests/integracion/**", "governance/tareas/TASK-006-arm-jarvis.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase6.py (vendedor → ticket → validación en el panel → notificación); OP-08 medido; arnés Exit Code 0"
```
**Hecho cuando** TASK-006 pasa a `sellada`.

---

## Ola 6 — Fase 7: Integración con CRM y producción

### T-601 — Conector CRM: proveedor real, publicación firmada e idempotente, cola, eventos
`¤crm-conector`
```toml
id = "T-601"
ola = 6
fase = 7
estado = "bloqueada"
sala = "crm_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-CRM-02 (real)", "RF-CRM-03", "RF-CRM-04", "RF-CRM-05", "RNF-09", "S-05"]
depende_de = ["T-302"]
bloqueada_por = ["ADR-0008", "ADR-0011 (si usa MCP de comunidad)"]
propiedad = ["features/crm_conector/**", "tests/crm_conector/**", "docs/modulos/crm_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/crm_conector/{test_publicar_venta,test_cola_reintentos,test_eventos}.py con receptor simulado que verifica HMAC; contrato con el proveedor real sobre fixtures; arnés Exit Code 0"
```
Entregables: `<proveedor>_internal.py`, `firma_internal.py` (HMAC-SHA256 sobre cuerpo canónico), `cola_internal.py` (backoff, 24 h, `validada/no_publicada`), `eventos_internal.py` (firma de eventos entrantes), `esquema crm` completo.

### T-602 — ARM: tablero y marcado de publicación
`¤arm-jarvis`
```toml
id = "T-602"
ola = 6
fase = 7
estado = "pendiente"
sala = "arm_jarvis"
rol = "¤¤backend-developer"
requisitos = ["RF-ARM-08", "RF-CRM-04 (receptor marcar_publicacion)"]
depende_de = ["T-502"]
bloqueada_por = []
propiedad = ["features/arm_jarvis/**", "tests/arm_jarvis/**", "docs/modulos/arm_jarvis.md", "evals/ventas.jsonl"]
consume = ["comisiones_service", "observabilidad_service"]
arbitro = "tests/arm_jarvis/test_tablero.py (totales al centavo con la exportación de comisiones); arnés Exit Code 0"
```

### T-603 — Comisiones: exportación con esquema
`¤comisiones`
```toml
id = "T-603"
ola = 6
fase = 7
estado = "pendiente"
sala = "comisiones"
rol = "¤¤backend-developer"
requisitos = ["RF-COM-03"]
depende_de = ["T-501"]
bloqueada_por = []
propiedad = ["features/comisiones/**", "tests/comisiones/**", "docs/modulos/comisiones.md"]
consume = ["observabilidad_service"]
arbitro = "tests/comisiones/test_exportacion.py valida CSV y JSON contra esquema_exportacion.json; arnés Exit Code 0"
```

### T-604 — Panel operativo: tablero, cierre de período, exportación y administración completa
`¤panel-operativo`
```toml
id = "T-604"
ola = 6
fase = 7
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-04", "RF-PAN-05", "RF-PAN-09 (reglas, plantillas, conocimiento, propiedades)", "US-08"]
depende_de = ["T-505"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["arm_jarvis_service", "comisiones_service", "pms_conector_service", "canal_whatsapp_service", "conocimiento_service", "seguridad_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/test_bff_comisiones.py (409 tras cierre); tests/e2e/test_tablero.py (totales al centavo con la exportación); arnés Exit Code 0"
```
Entregables: P-05, P-06 y el resto de P-11 (`docs/FRONTEND.md` §4), componentes `TarjetaMetrica`, `GraficoBarras`, `TablaDensa`.

### T-610 — Producción: despliegue en el servidor propio, aislamiento del flujo contable, backups cifrados
`¤infra-hibrida`
```toml
id = "T-610"
ola = 6
fase = 7
estado = "pendiente"
sala = "infraestructura"
rol = "¤¤devops-engineer"
requisitos = ["RNF-14", "RNF-15", "INV_RED_AISLADA", "INV_MISMO_COMPOSE", "S-08"]
depende_de = ["T-601", "T-602", "T-603", "T-604"]
bloqueada_por = ["S-08"]
propiedad = ["compose.yaml", "compose.production.yaml", "infra/**", "scripts/arnes_glamping.py", ".github/**", "app_core/**", "tests/app_core/**", "tests/integracion/**"]
consume = ["todas las compuertas"]
arbitro = "stack levantado en el servidor propio con compose.production.yaml; prueba de conexión negativa hacia los servicios contables ejecutada allí; restauración de backup documentada; arnés Exit Code 0"
```

### T-611 — Integración fase 7: primer cierre de período y hito de producción
`¤bbap-glamping`
```toml
id = "T-611"
ola = 6
fase = 7
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["RNF-09", "RNF-10", "US-08", "US-14", "US-16", "ON-03"]
depende_de = ["T-610"]
bloqueada_por = []
propiedad = ["governance/tareas/TASK-007-integracion-crm.md"]
consume = []
arbitro = "tests/integracion/test_fase7.py (venta validada → CRM firmado e idempotente → tablero → cierre → exportación); aprobación del propietario"
```
**Hecho cuando** TASK-007 pasa a `sellada` y el propietario aprueba el hito de producción.

---

## Ola 7 — Fase 8 (condicional, ADR-0010)

### T-701 — Panel operativo: inbox completo de conversaciones de huéspedes
`¤panel-operativo`
```toml
id = "T-701"
ola = 7
fase = 8
estado = "bloqueada"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-07 (extensión)", "TASK-008"]
depende_de = ["T-604"]
bloqueada_por = ["ADR-0010"]
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["agente_service", "seguridad_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/e2e/test_inbox_huespedes.py; arnés Exit Code 0"
```

---

## Ola 8 — Fase 8: Terminal móvil

### T-801 — Panel: terminal móvil instalable, avisos e idempotencia
`¤panel-operativo`
```toml
id = "T-801"
ola = 8
fase = 8
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-11", "RF-PAN-12", "RF-PAN-13", "RF-PAN-14", "INV_MOVIL_SIN_PII_EN_DISCO", "INV_MOVIL_SIN_ESCRITURA_SIN_RED", "INV_AVISO_SIN_PII", "INV_ACCION_IDEMPOTENTE"]
depende_de = ["T-604"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["arm_jarvis_service", "crm_conector_service", "seguridad_service", "observabilidad_service"]
arbitro = "tests/e2e/test_terminal_movil.py; tests/panel_operativo/test_avisos.py; tests/panel_operativo/test_idempotencia.py; arnés Exit Code 0"
```
Entregables: manifiesto, iconos propios y service worker que guarda solo la interfaz; P-12 (`docs/FRONTEND.md` §4); suscripción Web Push con VAPID leído de variables de entorno; `Idempotency-Key` en todas las acciones del BFF.

### T-810 — Despliegue de la terminal móvil: HTTPS, cabeceras y claves de avisos
`¤infra-hibrida`
```toml
id = "T-810"
ola = 8
fase = 8
estado = "pendiente"
sala = "infraestructura"
rol = "¤¤devops-engineer"
requisitos = ["RF-PAN-11", "RF-PAN-12", "INV_SIN_SECRETOS_EN_REPO"]
depende_de = ["T-801"]
bloqueada_por = []
propiedad = ["compose.yaml", "compose.production.yaml", "infra/**", "scripts/arnes_glamping.py", ".github/**", "app_core/**", "tests/app_core/**", "tests/integracion/**"]
consume = ["panel_operativo_service"]
arbitro = "tests/integracion/test_terminal_movil_despliegue.py (HTTPS, manifiesto y cabecera no-store); arnés Exit Code 0"
```
Entregables: variables VAPID en los archivos de despliegue sin valores, manifiesto y service worker servidos por HTTPS, y `Cache-Control: no-store` conservada por el proxy.

---

## 4. Cómo tomar una tarea

1. Confirmar que ninguna otra tarea abierta reclama la misma sala (regla 6) y que `depende_de` está sellado.
2. Triaje con el servidor ZERAG indicando la tarea (`T-NNN`) y su rastro; el rol asignado debe coincidir con el de la tarea.
3. Boceto dentro de `propiedad`; dobles propios en `tests/<sala>/dobles.py`; huellas `¦` permitidas durante el boceto.
4. Arnés completo en Exit Code 0; huellas consolidadas a `¤`; `estado = "sellada"` en el bloque de la tarea; `mcp_close_session`.
5. Si la tarea descubrió que necesita cambiar un contrato de otra sala, no lo cambia: lo anota en su bloque como `contrato_pendiente`
   y el coordinador lo resuelve en la `T-x10` de la ola.

`¤tareas-glamping/`
