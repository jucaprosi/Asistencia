# Arquitectura — Asistente de WhatsApp, ARM y CRM para Glamping Imbabura
`¤arquitectura-glamping`

| Campo | Valor |
| :--- | :--- |
| Versión | 0.1.0 (2026-10-30) |
| Fuente de verdad | [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) §4, §5, §9, §10, §11 |
| Requisitos | [`PRD.md`](PRD.md) |
| Decisiones | [`adr/README.md`](adr/README.md) |
| Metodología | Zero-Regression AI Governance BIAS: ADPA (salas estancas, compuertas), rastros `¤`/huellas `¦`, Boceto → arnés → Sellado. [ADR-0006](adr/ADR-0006-metodologia-zerag-adpa-huellas.md) |

Este documento fija **cómo se materializa** la arquitectura del informe en un repositorio ADPA. No toma decisiones de producto: cada una remite a su ADR.

---

## 1. Vista de contexto
`¤arquitectura-contexto`

```
                 ┌──────────────────────────────────────────────────────────────┐
                 │                    SISTEMAS EXTERNOS                          │
   Huéspedes ───►│ WhatsApp Cloud API (Meta) ◄── Vendedores (grupo o 1:1, S-01) │
                 │ Claude API (Anthropic)                                        │
                 │ PMS / channel manager  [ADR-0007]  ──► Airbnb · Booking       │
                 │ CRM + inbox + workflows [ADR-0008]                            │
                 │ PostgreSQL + pgvector gestionado [ADR-0002] · S3 gestionado   │
                 └───────────────▲──────────────────────────────▲────────────────┘
                                 │ compuertas                    │
┌────────────────────────────────┴──────────────────────────────┴───────────────────┐
│  SUBMARINO glamping-imbabura-agent (servidor propio · red agent-net · stateless)   │
│                                                                                    │
│  app_core/  ─ pasillo central: arranque, inyección de dependencias, orquestación   │
│                                                                                    │
│  features/                                                                         │
│   canal_whatsapp ─ seguridad ─ agente ─ conocimiento ─ herramientas_glamping        │
│   pms_conector ─ crm_conector ─ arm_jarvis ─ comisiones ─ observabilidad           │
│   panel_operativo · web_huespedes (pública) · anfitriones · operaciones (cond., §3)  │
│                                                                                    │
│  tests/  evals/  scripts/  docs/  governance/  compose.yaml  compose.production.yaml│
└────────────────────────────────────────────────────────────────────────────────────┘
          ▲ aislado por red Docker: no alcanza                    ▲
          │                                                       │
   ┌──────┴────────────────┐                        ┌─────────────┴──────────────┐
   │ Flujo contable (hoy)  │                        │ MCP existente en PC beta   │
   │ servidor propio       │                        │ red glamping-beta-net      │
   └───────────────────────┘                        └────────────────────────────┘
```

Los seis bloques numerados del informe (§4) se corresponden así: [1] gateway → `canal_whatsapp`; [2] seguridad → `seguridad`; [3] agente Claude → `agente` + `conocimiento` + `herramientas_glamping`; [4] ARM → `arm_jarvis` + `comisiones`; [5] PMS → `pms_conector` (externo detrás); [6] tablero → `arm_jarvis` + `comisiones` (cálculo) con visualización en el CRM o BI (ADR-0009).

`¤arquitectura-contexto/`

---

## 2. Principios arquitectónicos
`¤arquitectura-principios`

1. **Construir lo que diferencia, adoptar lo que no** (informe §3). Lo adoptado (CRM, inbox, workflows, PMS) vive **fuera** del submarino y entra solo por una compuerta conectora con tipos propios.
2. **El agente nunca habla con OTAs ni calendarios**: solo con la compuerta del PMS, que delega en el PMS/channel manager (informe §4).
3. **Autonomía de sala sobre DRY** (ADPA/DPD). Cada sala puede duplicar utilidades menores antes de acoplarse a otra. Lo compartido entre salas solo pasa por compuertas; `app_core` no importa nada privado.
4. **Una sola fuente de asignación.** El PRD declara qué sala responde de cada requisito ([`governance/artefactos/PRD.md`](../governance/artefactos/PRD.md) §2); cada tarea declara su sala y los archivos de su propiedad exclusiva.
5. **Stateless en el servidor propio; estado en nube gestionada.** Los contenedores se reconstruyen desde Git; PostgreSQL y archivos viven en servicios gestionados con PITR (ADR-0004). Excepción condicional: datos que ADR-0012 obligue a mantener on-prem.
6. **PII fuera del modelo.** La única sala que ve PII en claro es `seguridad` (bóveda de tokens). Modelo, logs, trazas e historial trabajan con tokens.
7. **Árbitro exógeno.** Ningún requisito se da por cumplido por afirmación: lo da por cumplido un test, una evaluación o un linter dentro del arnés con Exit Code 0.
8. **Interfaz purificada.** Rastros `¤`/`¦` solo en código, configuración y documentación interna; nunca en mensajes de WhatsApp, plantillas, etiquetas del CRM ni exportaciones entregadas al negocio.

`¤arquitectura-principios/`

---

## 3. Salas ADPA: equivalencia con la estructura del informe
`¤arquitectura-salas`

La estructura de §11 del informe (`apps/`, `packages/`, `mcp-servers/`) se conserva como **catálogo de componentes**. Su materialización física es una sala por componente bajo `features/`, con nombre en `snake_case` (requisito de paquete Python) y compuerta única.

| Componente (informe §11) | Sala | Compuerta pública | Config | Rastro | Rol `¤¤` | Decisión |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `apps/whatsapp-gateway` | `features/canal_whatsapp/` | `canal_whatsapp_service.py` | `config_canal_whatsapp.yaml` (plantillas, ventana, reintentos) | `¤canal-whatsapp` | `¤¤integration-engineer` | Construir |
| `packages/security` | `features/seguridad/` | `seguridad_service.py` | `config_seguridad.yaml` (identidad, allowlist, límites, patrones) | `¤seguridad-canal` | `¤¤security-engineer` | Construir |
| `packages/agent-core` | `features/agente/` | `agente_service.py` | `config_agente.yaml` (modelos, tope de iteraciones, ventana de memoria, caché) | `¤agente-enrutador` | `¤¤machine-learning-engineer` | Construir |
| `packages/rag` | `features/conocimiento/` | `conocimiento_service.py` | `config_conocimiento.yaml` (chunking, top-k, umbral «no lo sé») | `¤conocimiento-rag` | `¤¤data-engineer` | Construir |
| `packages/pms-connector` | `features/pms_conector/` | `pms_conector_service.py` | `config_pms_conector.yaml` (proveedor activo, escrituras habilitadas) | `¤pms-conector` | `¤¤integration-engineer` | Construir sobre MCP; proveedor ADR-0007 |
| `packages/crm-connector` | `features/crm_conector/` | `crm_conector_service.py` | `config_crm_conector.yaml` (proveedor activo, URL del webhook, cola) | `¤crm-conector` | `¤¤integration-engineer` | Interfaz propia; CRM adoptado ADR-0008 |
| `apps/arm-jarvis` | `features/arm_jarvis/` | `arm_jarvis_service.py` | `config_arm_jarvis.yaml` (canal, numeración, notificaciones, asistente del líder) | `¤arm-jarvis` | `¤¤backend-developer` | Construir (ADR-0005) |
| `packages/commissions` | `features/comisiones/` | `comisiones_service.py` | `config_comisiones.yaml` (período, moneda, redondeo) | `¤comisiones` | `¤¤backend-developer` | Construir; registro ADR-0009 |
| `packages/observability` | `features/observabilidad/` | `observabilidad_service.py` | `config_observabilidad.yaml` (umbrales de evaluación, alertas) | `¤observabilidad` | `¤¤devops-engineer` | Construir |
| `mcp-servers/glamping-tools` | `features/herramientas_glamping/` | `herramientas_glamping_service.py` (compuerta); `server.py` es el ejecutable del servidor MCP y solo importa su propia compuerta | `config_herramientas_glamping.yaml` (esquemas, herramientas por rol) | `¤herramientas-mcp` | `¤¤backend-developer` | Construir |
| *(implícito)* | `features/operaciones/` — **condicional**: solo si el PMS no cubre incidencias (ADR-0007) | `operaciones_service.py` | `config_operaciones.yaml` | `¤operaciones-incidencias` | `¤¤backend-developer` | Construir si aplica |
| *(nuevo, ADR-0013)* | `features/panel_operativo/` — frontend del equipo y BFF | `panel_operativo_service.py` | `config_panel_operativo.yaml` (sesión, acceso por código, paginación) | `¤panel-operativo` | `¤¤frontend-developer` | Construir; diseño en [`FRONTEND.md`](FRONTEND.md) |
| *(pasillo central)* | `app_core/` | `main.py` (arranque), `contenedor.py` (inyección de dependencias) | `config_app.yaml` + `.env` | `¤pasillo-central` | `¤¤solutions-architect` | — |
| `compose.yaml`, `compose.production.yaml` | zona `infraestructura/` (raíz) | — | archivos compose | `¤infra-hibrida` | `¤¤devops-engineer` | ADR-0004 |
| `CORPUS_DIR` (fuera del repositorio), `docs/prompts/` | zona de conocimiento (datos, no código) | leídos por `conocimiento` y `agente` | — | `¤conocimiento-rag`, `¤agente-enrutador` | — | — |

### 3.1 Estructura física resultante

```
glamping-imbabura-agent/
├── AGENTS.md · CLAUDE.md · README.md
├── compose.yaml · compose.production.yaml · .env.example
├── ejecutar_arnes_glamping.bat · ejecutar_arnes_glamping.sh
├── app_core/
│   ├── app_core_service.py          # compuerta del pasillo: reexporta construir, Contenedor, resolver_secretos
│   ├── contenedor.py                # privado: construye cada compuerta e inyecta dependencias
│   ├── main.py                      # fábrica FastAPI (uvicorn --factory), salud, CLI --comprobar/--worker
│   └── config_app.yaml
├── features/
│   ├── canal_whatsapp/   canal_whatsapp_service.py · config_canal_whatsapp.yaml · webhook_internal.py · envio_internal.py · plantillas_internal.py · medios_internal.py
│   ├── seguridad/        seguridad_service.py · config_seguridad.yaml · identidad_internal.py · allowlist_internal.py · rate_limit_internal.py · injection_internal.py · pii_internal.py · audit_internal.py
│   ├── agente/           agente_service.py · config_agente.yaml · enrutador_internal.py · prompts_internal.py · bucle_herramientas_internal.py · memoria_internal.py · cache_internal.py
│   ├── conocimiento/     conocimiento_service.py · config_conocimiento.yaml · chunker_internal.py · indexador_internal.py · recuperador_internal.py · evaluador_internal.py
│   ├── pms_conector/     pms_conector_service.py · config_pms_conector.yaml · base_internal.py · fake_internal.py · kamra_internal.py | repull_internal.py | hospitable_internal.py
│   ├── crm_conector/     crm_conector_service.py · config_crm_conector.yaml · base_internal.py · fake_internal.py · ghl_internal.py | chatwoot_internal.py | attio_internal.py · cola_internal.py · firma_internal.py
│   ├── arm_jarvis/       arm_jarvis_service.py · config_arm_jarvis.yaml · extractor_internal.py · estados_internal.py · ticket_internal.py · notificador_internal.py · tablero_internal.py · asistente_lider_internal.py
│   ├── comisiones/       comisiones_service.py · config_comisiones.yaml · reglas_internal.py · periodo_internal.py · exportacion_internal.py · esquema_exportacion.json
│   ├── observabilidad/   observabilidad_service.py · config_observabilidad.yaml · logs_internal.py · trazas_internal.py · alertas_internal.py
│   ├── herramientas_glamping/  herramientas_glamping_service.py · server.py (ejecutable MCP) · config_herramientas_glamping.yaml · esquemas/*.json · herramientas_internal.py
│   └── panel_operativo/  panel_operativo_service.py · config_panel_operativo.yaml · bff_internal.py · sesiones_internal.py · ui/ (TypeScript) · estaticos/ (build)
├── docs/            PROJECT_CONTEXT.md · PRD.md · ARQUITECTURA.md · adr/ · negocio/ · prompts/
├── evals/           set_dorado.jsonl · inyecciones.jsonl · ventas.jsonl · enrutador.jsonl
├── scripts/         seed_knowledge.py · run_evals.py
├── tests/           una carpeta por sala + test_canal_oficial.py · test_sin_clientes_ota.py · test_interfaz_purificada.py · test_estructura_adpa.py
└── governance/      artefactos/ (PRD · INVARIANTS · FUENTES · VPA_INDEX · PROBLEMS.json · data/) · tareas/
```

Convenciones: un `pyproject.toml` en la raíz con un paquete por sala (`features.<sala>`), de modo que cada sala se prueba sola (`pytest tests/<sala>`) y se puede extraer a su propio paquete si algún día se despliega aparte, como pedía el informe §11.

### 3.2 Reglas de las salas (árbitro: `adpa_linter`, `tests/test_estructura_adpa.py`)

1. `features/<a>/*` solo importa de `features/<b>/<b>_service.py`, nunca de `*_internal.py` ni de `server.py` de otra sala. Toda compuerta termina en `_service.py`: es lo que reconoce el linter ADPA.
2. `app_core/` importa únicamente compuertas.
3. Una compuerta no expone sesiones de base de datos, clientes HTTP ni objetos de SDK de terceros: solo tipos del dominio definidos en la propia compuerta o en un módulo `tipos.py` de la sala.
4. Los SDK y MCP de terceros (Meta, Anthropic, Kamra/Repull/Hospitable, GHL/Chatwoot/Attio) se importan en una sola sala cada uno: Meta en `canal_whatsapp`; Anthropic en `agente` y en `arm_jarvis` (el ARM tiene su propio extractor: DPD antes que acoplarse al agente de huéspedes); PMS en `pms_conector`; CRM en `crm_conector`.
5. Cada sala tiene su `config_<sala>.yaml`; los secretos van por variables de entorno referenciadas desde el YAML, nunca en claro.

`¤arquitectura-salas/`

---

## 4. Pasillo central y flujo de un mensaje
`¤pasillo-central`

`app_core/contenedor.py` construye las compuertas en este orden y las enlaza por inyección: `observabilidad` → `seguridad` → `conocimiento` → `pms_conector` → `crm_conector` → `comisiones` → `canal_whatsapp` → `anfitriones` → `arm_jarvis` → `herramientas_glamping` → `agente` → `panel_operativo`; al final registra en el canal los receptores (huéspedes → `agente.atender`, vendedores → `arm.procesar`), de modo que el canal no depende de quien lo escucha. Los puntos de entrada HTTP públicos son el webhook de Meta, los eventos firmados del CRM y el panel operativo (`/panel/*`, con sesión); el servidor MCP escucha solo en `agent-net`.

```
Meta ──POST /webhook──► canal_whatsapp_service.recibir()
                            │  verifica firma · dedup · clasifica canal (huéspedes | vendedores)
                            ▼
                       seguridad_service.filtrar_entrada(mensaje, canal)
                            │  bloqueos → rol · rate limit · injection · PII→tokens · audit
                            ├── canal=huéspedes ──► agente_service.atender(mensaje_limpio, rol)
                            │                          │ resuelve propiedad · prompt · herramientas por rol
                            │                          │ bucle Claude ⇄ herramientas_glamping (MCP)
                            │                          │     └─► pms_conector · conocimiento · crm_conector
                            │                          ▼
                            └── canal=vendedores ──► arm_jarvis_service.procesar(mensaje_limpio, vendedor_id)
                                                       │ extrae venta · comisiones_service · estado · ticket
                                                       ▼
                       seguridad_service.filtrar_salida(respuesta)   ← rehidrata PII · verifica interfaz purificada
                            ▼
                       canal_whatsapp_service.enviar(respuesta | plantilla)  → Meta
                            ▼
                       observabilidad_service.cerrar_traza(traza_id)
```

Eventos externos adicionales: `POST /crm/eventos` (firmado) para validaciones de venta, devoluciones de handoff e incidencias resueltas desde el CRM → `crm_conector_service.recibir_evento()` → compuerta destinataria (`arm_jarvis`, `agente`). Tareas programadas (check-in del día, cierre de período, reintentos de cola) las dispara `app_core` invocando compuertas; ninguna sala programa tareas por su cuenta.

`¤pasillo-central/`

---

## 5. Datos y persistencia
`¤arquitectura-datos`

| Almacén | Contenido | Dueño | Ubicación | Notas |
| :--- | :--- | :--- | :--- | :--- |
| PostgreSQL gestionado (`glamping`) | esquemas por sala: `agente`, `conocimiento` (pgvector + tsvector), `arm`, `comisiones`, `seguridad` (bóveda de tokens y audit log), `observabilidad` (trazas) | cada sala su esquema | Neon (ADR-0002, revisable por ADR-0012) | Un rol de base de datos por sala con permisos solo sobre su esquema; `seguridad.audit_log` con rol `INSERT`-only; RLS por `propiedad_id` donde aplique (RF-SEC-07). |
| PostgreSQL local beta (`glamping_beta`) | mismo esquema, datos sintéticos | — | contenedor en `glamping-beta-net`, puerto no estándar | Solo para desarrollo; nunca datos reales. |
| S3-compatible gestionado | medios de WhatsApp, exportaciones CSV/JSON | `canal_whatsapp`, `comisiones` | Backblaze B2 / Wasabi / Render (beta) → MinIO 3-2-1 opcional en producción | Versionado activado; retención configurable. |
| Sistemas de registro externos | reservas y calendarios (PMS); contactos y oportunidades (CRM) | externos | SaaS u on-prem según ADR-0007/0008 | El repositorio guarda `pms_ref` / `crm_ref`; no copia. |
| Disco del contenedor | nada persistente | — | — | Los contenedores son reconstruibles. |

Modelo de entidades y propiedad por sala: [`PRD.md` §9](PRD.md#9-modelo-de-datos-de-alto-nivel).

`¤arquitectura-datos/`

---

## 6. Topología de despliegue
`¤infra-hibrida`

### 6.1 Compose base y sobrescritura

`compose.yaml` define los servicios; `compose.production.yaml` añade `restart: always`, límites más estrictos y volúmenes persistentes de logs. El mismo par levanta beta y producción (RNF-14).

| Servicio | Imagen | Red | Puertos | Límites (beta → producción) |
| :--- | :--- | :--- | :--- | :--- |
| `app` | imagen propia (`app_core` + todas las salas) | `agent-net` + ingreso | 8080 solo tras el proxy TLS | 1 CPU / 1 GiB → 2 CPU / 2 GiB |
| `mcp-tools` | misma imagen, comando `server.py` | `agent-net` | interno | 0,5 CPU / 512 MiB |
| `proxy` | Caddy o Traefik (TLS automático) | ingreso | 443 | 0,25 CPU / 128 MiB |
| `postgres-beta` | `pgvector/pgvector:pg16` | `glamping-beta-net` | 5433 interno | solo beta |
| `worker` | misma imagen, comando de tareas programadas y cola | `agent-net` | — | 0,5 CPU / 512 MiB |

Redes: `agent-net` (interna, sin acceso a los servicios contables: se verifica con una prueba de conexión negativa en el arnés, RNF-10); `glamping-beta-net` en el PC Ubuntu, separada del MCP que ya corre allí.

### 6.2 Secretos y configuración

`.env` (no versionado) con: token de acceso y *verify token* de Meta, secreto de firma del webhook de Meta, clave de Anthropic, URL de PostgreSQL por sala, credenciales S3, credenciales del PMS y del CRM, secreto HMAC del Inbound Webhook, secreto de eventos del CRM. `.env.example` versionado sin valores. En producción se recomienda el gestor de secretos del servidor o archivos `secrets:` de Compose.

### 6.3 Beta en el PC Ubuntu

- Datos reales solo en la nube gestionada; el disco SATA único aloja contenedores y datos sintéticos (R-01).
- Backup externo del repositorio, de `governance/` y de `evals/` probado con una restauración por fase (RNF-15).
- Salida a Internet solo para: Meta, Anthropic, PostgreSQL gestionado, S3, PMS, CRM. Lista de egreso documentada en `config_app.yaml` y verificada en el arnés.

### 6.4 Producción en el servidor propio

Mismo compose con `compose.production.yaml`; el proxy publica solo `443`; `agent-net` no enruta hacia las interfaces del flujo contable; límites de CPU/RAM fijados; logs en volumen separado; backups contables cifrados si comparten almacenamiento (informe §9.2).

`¤infra-hibrida/`

---

## 7. Seguridad por capa
`¤seguridad-canal`

| Capa | Dónde | Mecanismo | Requisito |
| :--- | :--- | :--- | :--- |
| Transporte | `proxy`, `canal_whatsapp` | TLS; verificación `X-Hub-Signature-256`; *verify token* | RF-GW-01 |
| Identidad | `seguridad` | canal de huéspedes abierto con permisos mínimos y lista de bloqueo; usuarios privilegiados registrados; rol por remitente, nunca por texto | RF-SEC-01 |
| Autorización | `seguridad` + `herramientas_glamping` | allowlist rol → herramienta; el servidor MCP pregunta a `seguridad` antes de ejecutar | RF-SEC-02, RF-AG-03 |
| Abuso | `seguridad` | rate limit por remitente y global, no anulable | RF-SEC-03 |
| Contenido | `seguridad` | filtro de inyección ≥ 40 patrones / 4 idiomas; escalamiento al tercer intento | RF-SEC-04 |
| Datos personales | `seguridad` (bóveda) | tokenización antes del modelo, rehidratación en la salida; historial, logs y trazas con tokens | RF-SEC-05, RNF-17 |
| Multi-inquilino | PostgreSQL | RLS por `propiedad_id`, rol `NOBYPASSRLS`; filtro obligatorio en RAG | RF-SEC-07, RF-RAG-03 |
| Integraciones | `crm_conector`, `pms_conector` | HMAC-SHA256 + `venta_id` idempotente hacia el CRM; eventos entrantes del CRM firmados; escrituras al PMS deshabilitadas por defecto | RF-CRM-03, RF-PMS-02 |
| Auditoría | `seguridad` | audit log append-only; informe semanal | RF-SEC-06 |
| Operación | `observabilidad` | alertas de silencio, errores, cola y costo | RF-OBS-04 |
| Cadena de suministro | repositorio | 0 librerías no oficiales de WhatsApp; 0 secretos; escáner en el arnés | ON-05, RNF-08 |

`¤seguridad-canal/`

---

## 8. Observabilidad y evaluación
`¤observabilidad`

- **Traza por mensaje** con *spans* por sala y por llamada al modelo; es la fuente de todas las métricas del PRD §2 (RF-OBS-02).
- **Logs JSON** sin PII, en volumen separado (RF-OBS-01).
- **Evaluaciones** (`scripts/run_evals.py`): `rag` (set dorado), `inyecciones`, `ventas`, `enrutador`. Corren en CI y dentro del arnés; sus umbrales viven en `config_observabilidad.yaml` y coinciden con el PRD. Una caída rompe el sellado (RF-OBS-03).
- **Alertas** (RF-OBS-04) hacia el canal operativo del equipo (correo o WhatsApp del administrador por plantilla).

`¤observabilidad/`

---

## 9. Ciclo de construcción ZERAG aplicado a cada fase
`¤bbap-glamping`

```
Tarea (governance/tareas/TASK-00N.md) ──► triaje ──► rastro ¤ de la sala
      │
      ▼  BOCETO (dentro de la sala, huellas ¦, imports libres dentro de la sala)
      │
      ▼  ARNÉS: ejecutar_arnes_glamping.(bat|sh) con los tests y evals de la tarea
      │     (adpa_linter · huellas_linter · utf8 · secretos · pytest · run_evals)
      │
      ▼  SELLADO: interfaz extraída a <sala>_service.py · 0 imports laterales · ¦ → ¤
      │     Exit Code 0 → certificado .test_verdict.json → tarea = sellada → mcp_close_session
      ▼
Fase completada (PRD §12)
```

ADR obligatorio solo si se fusionan o dividen salas, se altera `app_core`, cambia la propiedad de la persistencia o se excepciona una invariante (ADPA §7). Las decisiones de producto pendientes (§14 del informe) ya tienen su ADR propuesto en [`adr/`](adr/README.md).

`¤bbap-glamping/`

---

`¤arquitectura-glamping/`

© 2026 Juan Carlos Proaño. Todos los derechos reservados. Ver [`COPYRIGHT`](../COPYRIGHT).
