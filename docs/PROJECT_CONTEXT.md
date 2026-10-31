# Informe maestro del proyecto: Asistente de WhatsApp, ARM y CRM para Glamping Imbabura
`¤contexto-maestro`

> **Estado documental:** fuente de verdad del proyecto. Este archivo reproduce íntegro el informe maestro entregado el 2026-10-30 y añade dos anexos (A: referencia secundaria del video de @segunrob; B: cómo este informe se proyecta sobre la metodología ZERAG). El PRD derivado vive en [`PRD.md`](PRD.md); la arquitectura en [`ARQUITECTURA.md`](ARQUITECTURA.md); las decisiones en [`adr/`](adr/README.md).
>
> Toda alternativa que contradiga una decisión documentada aquí exige un ADR nuevo antes de implementarse (ver sección 17, punto 4).

**Propósito de este documento:** servir como contexto completo y fuente de verdad para que Claude construya el **PRD (Product Requirements Document)** del proyecto. Incluye contexto de negocio, decisiones de arquitectura, componentes técnicos, el estado del arte del ARM (con la evidencia del video de @santaia.lab), infraestructura, seguridad, riesgos, decisiones pendientes y referencias. La sección final contiene las instrucciones específicas para que Claude genere el PRD con la estructura requerida.

---

## 1. Resumen ejecutivo

Glamping Imbabura opera hoy un alojamiento tipo glamping en la provincia de Imbabura (Ecuador) y planea expandirse hacia **departamentos distribuidos por la ciudad**. El canal principal de atención al huésped es **WhatsApp**, y el motor del asistente es **Claude (Anthropic)**.

La solución distingue dos tipos de capas. Una **columna vertebral construida en casa**, que constituye el activo diferencial del negocio: gateway de WhatsApp sobre la API oficial de Meta, capa de seguridad, agente Claude con enrutamiento multi-propiedad, herramientas MCP para el PMS, RAG sobre PostgreSQL + pgvector, un módulo **ARM ("Jarvis")** que lee las ventas reportadas en un grupo de WhatsApp de vendedores y las estructura automáticamente, y la lógica de comisiones. Y una **capa commodity adoptada**, que cubre lo que no aporta valor construirlo: la interfaz de CRM para el equipo no técnico, la bandeja de entrada con handoff humano y el constructor visual de workflows. Para esta capa se evalúa **GoHighLevel** como opción principal, con **Chatwoot + Attio/HubSpot + n8n** como alternativa open source.

La infraestructura sigue un modelo **híbrido**: los datos críticos (base vectorial y archivos) viven en nube gestionada por sus certificaciones y backups automatizados; la lógica stateless (gateway, agente, ARM, enrutador) corre en el **servidor propio de Glamping Imbabura**, aislada del flujo contable que ya opera allí. La fase beta se ejecuta en un **PC con Ubuntu y disco SATA único**, con backups externos obligatorios y Docker Compose con archivos de sobrescritura que garantizan portabilidad al servidor final.

El video de **@santaia.lab** (28 de octubre de 2026) confirma que el concepto ARM existe, está en operación real y coincide con el flujo descrito para Glamping Imbabura, pero **no es adoptable como dependencia** porque el repositorio está gateado tras una acción de marketing y no documenta API, MCP ni modelo de IA sustituible. Por eso el ARM se construye en casa, usando el video como referencia funcional.

---

## 2. Contexto del negocio

### 2.1. Situación actual

- **Activo principal:** un glamping en Imbabura con una sola ubicación física.
- **Canal dominante:** WhatsApp, tanto para consultas de huéspedes como para la operación comercial de vendedores.
- **Servidor existente:** ejecuta **flujos de datos contables** (no chatbots). Es un activo crítico que no debe verse afectado en rendimiento, seguridad ni cumplimiento.
- **Equipo:** sin perfil de desarrollo dedicado a tiempo completo, lo que exige que la interfaz operativa sea comprensible para personas no técnicas.
- **Entorno de ensayo:** un PC con Ubuntu y un disco SATA único conectado a la placa, que ya ejecuta un MCP en producción interna y sirve como laboratorio para la fase beta.

### 2.2. Requisitos de la expansión a departamentos urbanos

| Frente | Implicación para el asistente |
|---|---|
| Disponibilidad multi-propiedad | Calendarios independientes por departamento, sincronizados con OTAs (Airbnb, Booking). |
| Precios dinámicos | Tarifas por departamento, zona, día de la semana y eventos locales. |
| Check-in autónomo | Instrucciones específicas por edificio (código de portal, wifi, normas del condominio). |
| Housekeeping distribuido | Coordinación de limpieza por zona y franjas entre check-out y check-in. |
| Mantenimiento por barrio | Proveedores distintos según la ubicación del departamento. |
| Enrutamiento de conversación | Identificar de qué propiedad habla el huésped antes de ejecutar cualquier acción. |
| Escalamiento humano por zona | Varios gestores con bandejas de entrada separadas. |
| Comisiones de vendedores | Registro de ventas y cálculo de comisiones por vendedor y por período. |

### 2.3. Usuarios del sistema

| Usuario | Necesidad principal | Canal |
|---|---|---|
| **Huésped potencial** | Consultar disponibilidad, precios, atractivos y reservar. | WhatsApp. |
| **Huésped activo** | Instrucciones de check-in, wifi, normas, reportar incidencias. | WhatsApp. |
| **Vendedor** | Reportar ventas sin fricción, conocer su comisión. | Grupo de WhatsApp. |
| **Líder comercial** | Validar ventas, ver comisiones y tableros. | CRM / inbox / tablero. |
| **Gestor de propiedad** | Coordinar limpieza, mantenimiento y check-in por zona. | CRM / inbox. |
| **Administrador** | Configurar propiedades, precios, políticas y seguridad. | Panel de administración. |

---

## 3. Principios de diseño

Antes de elegir herramientas, el proyecto se rige por una regla única que orienta cada decisión: **construir lo que diferencia al negocio, adoptar lo que no**. La pregunta que se aplica a cada capa es si construirla aporta ventaja competitiva o si, por el contrario, es una pieza estándar que cualquier proveedor ofrece mejor y más rápido.

| Capa | Decisión | Justificación |
|---|---|---|
| Motor conversacional (Claude + MCP) | **Construir** | Diferenciador del negocio; ninguna plataforma cerrada ofrece el control de tools y la calidad de Claude. |
| RAG sobre documentos del negocio (pgvector) | **Construir** | El conocimiento del glamping y de los departamentos es un activo propio. |
| Conector al PMS | **Construir sobre MCP** | Abstrae la dependencia del PMS y permite cambiar de proveedor sin reescribir el agente. |
| Enrutamiento multi-propiedad | **Construir** | Lógica de negocio específica. |
| ARM ("Jarvis") | **Construir** | No existe un producto verificado con ese flujo exacto que sea adoptable como dependencia (ver sección 6). |
| Seguridad (whitelist, injection filter, PII) | **Construir** | La capa de seguridad debe ser propia para adaptarse al dominio y a las amenazas del canal WhatsApp. |
| UI de CRM para equipo no técnico | **Adoptar** | Construir una interfaz decente cuesta semanas; el proveedor la entrega lista. |
| Inbox con handoff humano | **Adoptar** | Unificar canales y asignar conversaciones por zona es una función estándar. |
| Constructor visual de workflows | **Adoptar** | El equipo no técnico necesita crear automatizaciones sin tocar código. |

**Consecuencia práctica:** el sistema **no depende de la capa commodity para funcionar**. Si mañana se cambia de proveedor de CRM o de inbox, el agente, el RAG, el ARM y el PMS siguen operando; solo se sustituye una implementación concreta detrás de una interfaz abstracta.

---

## 4. Arquitectura general

```
Huésped / Vendedor (WhatsApp)
      │
      ▼
[1] Gateway WhatsApp — API oficial de Meta (Cloud API)
      │
      ▼
[2] Seguridad — whitelist / rate-limit / injection filter / PII redaction
      │
      ├────────────────────────────────┐
      ▼                                ▼
[3] Agente Claude (huéspedes)     [4] ARM "Jarvis" (vendedores)
    enrutador multi-propiedad          lee grupo de ventas
      │                                │
      ├── RAG (pgvector, nube)         ├── Extrae venta estructurada
      ├── MCP PMS (Kamra/Repull)       ├── Calcula comisión
      └── MCP CRM (contactos,          └── POST al CRM (Inbound Webhook)
          oportunidades)
      │
      ▼
[5] PMS multi-propiedad + Channel Manager
      │
      ├── Airbnb / Booking
      └── Reservas directas

┌──────────────────────────────────────────────────────┐
│  CAPA COMMODITY (UI para equipo no técnico)          │
│  · CRM: contactos, pipelines, oportunidades          │
│  · Inbox: conversaciones multicanal con handoff      │
│  · Workflow builder visual                           │
└──────────────────────────────────────────────────────┘
      │
      ▼
[6] Tablero de ventas y comisiones
    (lógica propia + visualización en CRM o BI externo)
```

**Principio rector:** el agente no habla directamente con cada OTA ni con cada calendario. Se conecta mediante **servidores MCP** a una capa unificada (PMS o API de channel manager) que abstrae propiedades y canales. Esto permite cambiar de PMS sin reescribir el agente.

---

## 5. Decisiones técnicas por capa

### 5.1. Base de datos vectorial: PostgreSQL + pgvector

**Decisión:** usar **pgvector sobre PostgreSQL gestionado** (Neon o Render), no una base de datos vectorial dedicada.

**Evidencia:** para aproximadamente el **80% de los sistemas RAG en producción en 2026**, pgvector sobre el Postgres que ya se tiene es la opción correcta. Latencia P95 de **~10–50 ms para menos de 10 millones de vectores**; con índice HNSW, **menos de 10 ms y más de 100 consultas por segundo a escala de 50 mil vectores**. En instancia gestionada, **800 mil chunks con P95 de 45–70 ms** incluyendo filtro de inquilino.

**Ventaja operativa:** no añade un servicio extra; hereda seguridad, backups y PITR de PostgreSQL.

### 5.2. Almacenamiento de archivos

- **Autoalojado con MinIO:** S3-compatible, ~512 MiB de RAM. Requiere estrategia **3-2-1** (tres copias, dos medios, una externa), versionado de buckets y replicación con `mc mirror` o `rclone sync`.
- **Gestionado con bucket S3-compatible** (Render, Backblaze B2, Wasabi): elimina carga operativa y garantiza durabilidad. Recomendado para la fase beta por el disco SATA único.

### 5.3. Motor del agente: Claude con tool use

Claude ejecuta acciones concretas: consultar disponibilidad, crear reserva preliminar, enviar instrucciones de check-in, buscar contacto en CRM, crear oportunidad. La referencia pública **SARA** (`Alessandro114/sara`) valida el patrón: RAG con pgvector + BM25, anonimización de PII antes de cada llamada al LLM, guardrails de prompt injection con más de 40 patrones en cuatro idiomas, detección de alucinaciones con puntuación de confianza.

### 5.4. PMS y channel manager vía MCP

| Opción | Tipo | MCP | Multi-propiedad | Nota |
|---|---|---|---|---|
| **Kamra PMS** | Open source (AGPL-3.0) | 116 herramientas MCP gobernadas | ✅ | Front desk, booking engine, housekeeping, POS, WhatsApp. |
| **Repull MCP** | API unificada + MCP | ✅ | ✅ (50+ PMS, Airbnb, Booking, VRBO) | **Read-mostly por defecto**; escrituras con `REPULL_MCP_ENABLE_WRITES`. |
| **Hospitable** | Comercial | Oficial | ✅ | Primer PMS de alquiler vacacional con MCP oficial. |
| **Hostex** | Comercial | No oficial | ✅ | Más de 25 herramientas MCP. |

**Recomendación:** **Kamra** si se busca open source y control total; **Repull MCP** si se prefiere abstraer más de 50 PMS y las principales OTAs con menor riesgo de acciones destructivas por defecto.

### 5.5. Enrutamiento multi-propiedad

Un solo número de WhatsApp con enrutamiento por contexto. El agente debe:

1. Identificar la propiedad (por nombre, dirección, código de reserva o preguntando).
2. Cargar el **system prompt correspondiente** (`glamping` o `departamentos`).
3. Exponer solo las herramientas MCP relevantes para esa propiedad.

La referencia **Una by Polydom** opera multi-propiedad en más de 90 idiomas por WhatsApp, email, voz y bandejas OTA, confirmando la viabilidad del patrón.

### 5.6. Capa commodity: CRM, inbox y workflows

**Ruta comercial — GoHighLevel (GHL).** CRM completo, bandeja de entrada unificada (Conversations) con WhatsApp, SMS, email, Instagram y Facebook, constructor visual de workflows, calendario y reputación online. Usa API oficial de WhatsApp vía LC Phone (Twilio), sin riesgo de baneo. Costo: **$97–$497/mes** según plan.

**Ruta open source — Chatwoot + Attio/HubSpot free + n8n.** Chatwoot cubre inbox multicanal con handoff; Attio o HubSpot free cubren CRM; n8n aporta workflow builder visual. Costo de infraestructura, mayor carga operativa.

**Criterio de elección:** costo a doce meses y comodidad del equipo no técnico. La integración se hace a través de una **interfaz abstracta** en `packages/crm-connector`:

```python
class CRMConnector(ABC):
    def search_contact(self, email=None, phone=None) -> Contact | None: ...
    def create_contact(self, contact: Contact) -> Contact: ...
    def create_opportunity(self, opp: Opportunity) -> Opportunity: ...
    def update_opportunity(self, opp_id: str, data: dict) -> Opportunity: ...
    def send_message(self, conversation_id: str, text: str) -> Message: ...
    def assign_conversation(self, conversation_id: str, agent_id: str) -> None: ...
```

`ghl.py` implementa esta interfaz hoy; `chatwoot.py` o `attio.py` la implementarían mañana sin que `agent-core` ni `arm-jarvis` cambien.

---

## 6. El ARM ("Jarvis")

### 6.1. Definición y estado del arte

El término **ARM (Agent Relationship Manager)** no es un estándar de la industria. Describe una **capa agéntica que automatiza la captura de datos comerciales**, eliminando la entrada manual en el CRM. La parte verificable de la promesa es que el ARM reemplaza la **entrada manual de datos** y cambia la **interfaz** de operación (de formulario a conversación), mientras el sistema de registro —contactos, historial, permisos y auditoría— sigue viviendo en el CRM.

Productos con el nombre "Jarvis" que cubren piezas parciales:

- **JARVIS Suite (RGA Technologies):** suite de 13 módulos con dashboards de ventas y agentes WhatsApp. Cerrado.
- **JARVIS CRM Inteligente (Whoptrends):** SaaS B2B de ventas por WhatsApp con panel CRM. Cerrado.
- **Jarvis + WhatsApp (getjarvis.eu):** asistente de escritorio que lee inbox de WhatsApp. Asistente personal.
- **`kirlts/jarvis` (GitHub):** plataforma multi-tenant de gestión de personal con worker WhatsApp sobre Baileys. No es sistema de ventas.

Ninguno coincide con el flujo exacto para Glamping Imbabura. Sin embargo, el video de **@santaia.lab** confirma que existe una implementación real del concepto ARM con las características descritas.

### 6.2. Funciones que el CRM sigue asumiendo

| Función | Por qué requiere CRM |
|---|---|
| Persistencia | El agente es stateless entre conversaciones; necesita una base de datos donde vivan los contactos, el historial y las oportunidades. |
| Permisos y roles | Quién ve y edita qué se define en el sistema de registro. |
| Audit trail | Cada cambio debe registrar quién lo hizo y cuándo. |
| Fuente de verdad para reporting | Los dashboards de comisiones se calculan sobre datos estructurados y consistentes. |

### 6.3. El video de @santaia.lab: evidencia del concepto

**Datos verificados por transcripción:**
- **Autor:** @santaia.lab
- **Publicado:** 28 de octubre de 2026
- **Duración:** 1 minuto 9 segundos
- **Título:** "Los CRM ya murieron. Un ARM que lee tus ventas directo de WhatsApp, sin digitar nada, con comisión calculada sola."
- **Métricas al momento de la consulta:** 11.400 vistas, 669 me gusta, 80 comentarios, 164 compartidos.

**Flujo que muestra:**
1. La vendedora escribe la venta en un grupo de WhatsApp (ejemplo: vendedora de Pereira con venta de 50.000).
2. La aplicación responde al instante en el grupo confirmando la venta registrada.
3. La venta aparece en la aplicación en estado **"por validar"**. La líder la valida con un toque y la comisión queda calculada automáticamente.
4. Un tablero muestra ventas mes a mes, gastos por categoría y ventas contra gastos.
5. La aplicación incluye un asistente propio al que llama **"Jarvis"**, que conoce todos los datos del ARM y al que se le pueden pedir cambios (ejemplo: que al validar una venta avise a la vendedora por WhatsApp su comisión y lo registre como ticket numerado).

**Qué confirma el video:**
- El concepto ARM existe y está en operación real, no solo en demo.
- El flujo coincide exactamente con el descrito para Glamping Imbabura.
- "Jarvis" es una feature integrada del ARM, no un producto separado.
- El producto se usa en una empresa con ventas en cinco ciudades.

**Qué no confirma (y por qué impide adoptarlo como dependencia):**
- **No hay URL pública del repositorio.** El video pide **comentar "ARM"** para recibir una guía con el repositorio. Es un mecanismo de captura de leads, no una publicación open source.
- **No se identifica una empresa registrada** ni fundadores verificables.
- **No se menciona API, webhooks ni MCP.** Sin eso, no es integrable con el stack de Glamping Imbabura.
- **No se especifica el modelo de IA** ni si es sustituible por Claude.
- **No se detalla el modelo de datos ni la exportación.** Riesgo de lock-in.

**Conclusión:** el video es evidencia de que el concepto es real y está en operación, pero **no es evidencia de que el producto sea adoptable como dependencia**. La recomendación de construir el ARM en casa sigue vigente.

### 6.4. Evaluación build vs buy del ARM

| Criterio | Construir en casa (`apps/arm-jarvis`) | Adoptar el producto del video |
|---|---|---|
| Verificabilidad del código | Total | Nula hasta obtener el repositorio (gateado tras comentar "ARM"). |
| Control del parsing de mensajes no estructurados | Total | Desconocido. |
| Integración con Claude y MCP | Nativa | No documentada. |
| Modelo de IA | Claude (elegido por el negocio) | Desconocido; probablemente cerrado. |
| Exportación de datos y anti-lock-in | Total | No documentada. |
| Costo | Tiempo de desarrollo (1–2 semanas) | Costo del producto + academia + dependencia de proveedor. |
| Riesgo | Bajo (código propio, auditable) | Alto (producto no verificado). |

**Recomendación:** construir el ARM en casa, usando el video como referencia funcional del flujo correcto.

---

## 7. Integración ARM ↔ CRM

### 7.1. Flujo principal: el ARM empuja la venta al CRM

**Mecanismo:** **Inbound Webhook** del proveedor de CRM.

1. Se crea un workflow en el CRM con trigger **"Inbound Webhook"**. URL tipo `https://services.leadconnectorhq.com/hooks/{locationId}/webhook-trigger/{id}`.
2. El ARM hace `POST` con payload estructurado:

   ```json
   {
     "venta_id": "uuid-v4",
     "vendedor": "Juan Pérez",
     "cliente": "María López",
     "telefono_cliente": "+593987654321",
     "monto": 450.00,
     "producto": "Departamento Centro - 3 noches",
     "fecha_venta": "2026-10-30",
     "comision": 45.00,
     "firma": "hmac-sha256-del-payload"
   }
   ```

3. En el workflow del CRM, acciones **"Create/Update Contact"** y **"Create Opportunity"** mapean el JSON a contacto y etapa del pipeline.

**Seguridad:** firma HMAC-SHA256 o token compartido validado en el workflow; endpoint del ARM protegido.

**Idempotencia:** `venta_id` único + upsert (buscar por email/teléfono antes de crear).

### 7.2. Flujo secundario: Claude consulta y actúa sobre el CRM vía MCP

El MCP de comunidad **`ashively101/MCP_GoHighLevel`** expone cerca de **100 herramientas** sobre la API v2: `ghl_search_contacts`, `ghl_create_contact`, `ghl_create_opportunity`, `ghl_update_opportunity`, `ghl_send_message`. Conectado al `agent-core`, permite que Claude consulte o actualice el CRM con cada acción auditada.

### 7.3. Alternativa: el CRM lee el grupo de WhatsApp directamente

**WAGHL** incorpora grupos de WhatsApp al inbox del CRM como "contactos" etiquetados, permitiendo disparar workflows al recibir mensajes. Válido para volumen bajo, pero menos flexible que un script propio para parsear mensajes no estructurados y no cubre el cálculo de comisiones.

### 7.4. Diagrama

```
[Grupo WhatsApp Vendedores]
          │
          ▼
   [ARM "Jarvis"] ──(lee y extrae venta)──┐
          │                                │
          │ (POST a Inbound Webhook)       │
          ▼                                │
   [CRM: Workflow] ──► Crea/Actualiza Contacto + Oportunidad
          │                                │
          │ (API / MCP)                    │
          ▼                                │
   [CRM: Pipeline y Reportes] ◄────────────┘
          │
          ▼
   [Tablero de comisiones] (código propio + visualización en CRM o BI)
```

---

## 8. Plugins y MCP de Claude

### 8.1. Tres tipos de extensión

| Tipo | Qué es | Uso |
|---|---|---|
| Conectores (Claude.ai) | Integraciones oficiales (Google Drive, Calendar, Slack, Notion). | Consultar/actuar desde el chat. |
| MCP servers | Servidores que exponen herramientas a Claude. | Dar al agente capacidad de ejecutar acciones. |
| Claude Code skills / plugins | Archivos `.claude/` que indican a Claude Code cómo construir tareas. | **Construir** el código del stack. |

No existe un plugin oficial de Claude que reemplace de forma integral la capa de CRM, inbox y workflows. Esa capa se **adopta** como producto y se integra mediante `crm-connector`.

### 8.2. Mapeo de capacidades de la capa commodity a MCP

| Capacidad | Cobertura MCP | Brecha |
|---|---|---|
| CRM (contactos, pipelines) | Attio MCP, HubSpot MCP (comunidad), Airtable MCP, Notion MCP | UI de pipeline. |
| Inbox + handoff | Chatwoot (API + MCP comunidad), Intercom conector | UI de inbox; integración con Claude. |
| WhatsApp API oficial | `pywa-mcp-server`, Twilio MCP | Enrutamiento multi-propiedad y RAG propios. |
| Calendario | Google Calendar MCP (oficial), Cal.com MCP | Recordatorios y bloqueo de disponibilidad. |
| Workflows visuales | n8n MCP, Activepieces MCP (comunidad) | Constructor visual no lo reemplaza Claude. |
| Funnels y landings | Sin MCP | Framer, Webflow o Astro. |
| Reputación Google | Google Business Profile MCP (comunidad) | Automatización de solicitudes. |

**Nota de verificación:** confirmar madurez de los MCP de comunidad en `modelcontextprotocol.io`, `smithery.ai` o `mcp.so`.

### 8.3. Lo que Claude Code construye

- ARM "Jarvis" (`apps/arm-jarvis`).
- Puente ARM ↔ CRM (webhook, firma, idempotencia).
- Enrutador multi-propiedad (`router.py`).
- MCP de glamping: disponibilidad, reservas, check-in, incidencias, handoff, creación de ventas.
- Lógica de comisiones (`packages/commissions`).
- Panel de handoff mínimo si se prescinde del inbox del proveedor.

---

## 9. Infraestructura

### 9.1. Modelo híbrido

| Capa | Entorno | Razón |
|---|---|---|
| pgvector | **Nube gestionada** (Neon o Render) | SOC 2 Type II, ISO 27001, PITR de 3 a 30 días, DDoS/WAF. |
| Archivos | **S3 gestionado** o MinIO con backups externos | Estrategia 3-2-1 en MinIO. |
| Gateway, agent-core, ARM | **Servidor propio Glamping** | Stateless, reconstruible desde Git. |
| CRM, inbox, workflows | **SaaS** (GHL) o **autoalojado** (Chatwoot + n8n) | Capa commodity, reemplazable. |
| PMS | On-prem (Kamra) o SaaS (Repull/Hospitable) | Según opción elegida. |

### 9.2. Aislamiento respecto al flujo contable

- Red Docker dedicada (`agent-net`): el asistente no alcanza puertos ni servicios contables.
- Segunda instancia de PostgreSQL en contenedor separado, puerto distinto, solo accesible en `agent-net`.
- Límites de recursos (`deploy.resources.limits`) por contenedor.
- Credenciales de mínimo privilegio por servicio.
- Logs en volúmenes separados.
- Backups contables cifrados (AES-256/GnuPG) si comparten almacenamiento físico.

### 9.3. Fase beta: PC Ubuntu + disco SATA único

1. **Backups externos probados.** Disco único sin RAID = punto de fallo real. Datos críticos en nube gestionada.
2. **Docker Compose con sobrescritura.** `compose.yaml` base + `compose.production.yaml` con `restart: always`, límites más estrictos y volúmenes persistentes. Mismo stack en beta y producción.

**Aislamiento del MCP existente:** red Docker `glamping-beta-net`, sin acceso al MCP que ya corre allí.

### 9.4. WhatsApp: API oficial

Librerías no oficiales (**Baileys, whatsapp-web.js, whatsmeow**) violan los ToS y pueden causar suspensión o baneo permanente. La **API oficial de WhatsApp Business (Cloud API de Meta)** no conlleva riesgo de baneo.

---

## 10. Seguridad

### 10.1. Prompt injection desde WhatsApp

| Capa | Implementación | Referencia |
|---|---|---|
| Whitelist de contactos | Mensajes de desconocidos se registran y descartan. | `rickhallett/wasp` |
| Allowlist por acción | `read` ≠ `send` ≠ `group.add`. | Guías de seguridad WhatsApp |
| Rate limiting no anulable | 2/seg, 30/min, tope diario. | Prácticas documentadas |
| Filtro de injection | Más de 40 patrones, multilenguaje. | SARA |
| PII redaction | Tokenización en tiempo real; rehidratación en respuesta. | Guía IA hospitalidad |
| Audit log | Registro de cada acción con revisión manual periódica. | `guarded-whatsapp-mcp` |

### 10.2. Row-Level Security multi-inquilino

RLS de PostgreSQL si se gestionan datos de varias propiedades o terceros. Rol de aplicación con `NOBYPASSRLS`.

### 10.3. Seguridad del Inbound Webhook del CRM

Firma HMAC-SHA256 o token compartido validado en el workflow + endpoint del ARM protegido + `venta_id` idempotente.

---

## 11. Estructura del repositorio

```
glamping-imbabura-agent/
├── CLAUDE.md
├── compose.yaml
├── compose.production.yaml
├── docs/
│   ├── adr/
│   ├── negocio/                     # glamping.md, departamentos.md,
│   │                                # precios-y-temporadas.md,
│   │                                # politicas-cancelacion.md,
│   │                                # checkin-checkout.md,
│   │                                # atractivos-turisticos.md, faq-*.md
│   └── prompts/
│       ├── system-prompt-enrutador.md
│       ├── system-prompt-glamping.md
│       └── system-prompt-departamentos.md
├── apps/
│   ├── whatsapp-gateway/            # API oficial Meta
│   └── arm-jarvis/                  # lee grupo de vendedores, extrae ventas
├── packages/
│   ├── agent-core/                  # Claude + enrutador multi-propiedad
│   ├── rag/                         # pgvector + chunker + retriever
│   ├── pms-connector/               # base.py + kamra.py / repull.py / hospitable.py
│   ├── crm-connector/               # base.py + ghl.py / chatwoot.py / attio.py
│   ├── commissions/                 # cálculo de comisiones por vendedor y período
│   ├── security/                    # whitelist, rate-limit, injection, PII
│   └── observability/               # logs, trazas, evaluaciones
├── mcp-servers/
│   └── glamping-tools/              # availability, bookings, checkin,
│                                    # incidents, handoff, create_sale
└── scripts/
    ├── seed_knowledge.py
    └── run_evals.py
```

Cada carpeta es un paquete independiente con su `pyproject.toml`. Permite testear el `pms-connector` sin levantar el gateway y cambiar de Kamra a Hospitable o de GHL a Chatwoot sin tocar `agent-core`.

> **Nota ZERAG (Anexo B):** la estructura anterior se conserva como catálogo de *componentes*; su materialización física en el repositorio sigue la disposición ADPA de salas estancas bajo `features/` con compuertas `_service.py`. La equivalencia componente → sala está en [`ARQUITECTURA.md`](ARQUITECTURA.md) y en [`adr/ADR-0006-metodologia-zerag-adpa-huellas.md`](adr/ADR-0006-metodologia-zerag-adpa-huellas.md).

---

## 12. Fases de implementación

| Fase | Entregable | Duración estimada |
|---|---|---|
| 0. Esqueleto | Carpetas, `pyproject.toml`, `Makefile`, `CLAUDE.md`, CI vacío. | 1 día |
| 1. MVP WhatsApp | Gateway con API oficial de Meta y Claude con system prompt detallado. Sin RAG ni PMS. | 3–5 días |
| 2. RAG | Indexación de `docs/negocio/` en pgvector, con respuesta "no lo sé" explícita. | 1 semana |
| 3. PMS vía MCP | `pms-connector` y herramientas de disponibilidad y reservas. | 1–2 semanas |
| 4. Multi-propiedad | `router.py` y `system-prompt-departamentos.md`. | 1 semana |
| 5. Seguridad y observabilidad | `packages/security` y `packages/observability`, con evaluaciones en CI. | 1 semana |
| 6. ARM "Jarvis" | `apps/arm-jarvis` lee el grupo, extrae ventas y calcula comisiones. | 1–2 semanas |
| 7. Integración con CRM | `crm-connector` implementado, Inbound Webhook y tablero de comisiones. | 1 semana |
| 8. Panel de handoff propio | Solo si se decide prescindir del inbox del proveedor. | 2–3 semanas |

Las fases 6 y 7 pueden ejecutarse en paralelo si hay dos builders. La fase 8 solo se aborda si el análisis de costo a doce meses favorece prescindir del inbox gestionado.

---

## 13. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Disco SATA único en beta | Pérdida de datos de prueba. | Backups externos probados; datos críticos en nube gestionada. |
| Baneo del número por Baileys | Pérdida del canal de atención. | API oficial de WhatsApp Cloud (Meta). |
| Prompt injection desde WhatsApp | Revelación de datos o acciones no autorizadas. | Whitelist + allowlist por acción + rate limit + injection filter + PII redaction. |
| Interferencia con flujo contable | Degradación del negocio principal. | Red Docker aislada, segunda instancia PostgreSQL, límites de recursos, credenciales separadas. |
| Alucinaciones en políticas y precios | Daño reputacional. | RAG pgvector + detección de alucinaciones + "no lo sé" explícito. |
| Dependencia de un solo PMS | Dificultad para cambiar. | Interfaz abstracta en `pms-connector` + MCP. |
| Dependencia de un solo CRM | Lock-in de workflows y funnels. | Interfaz abstracta en `crm-connector`; el proveedor solo ocupa la capa commodity. |
| Webhook del CRM sin firma | Inyección de ventas falsas. | HMAC-SHA256 + token compartido + `venta_id` idempotente. |
| "Jarvis ARM" como producto no verificado | Adoptar dependencia inexistente o inmadura. | Construirlo en casa (`apps/arm-jarvis`). |

---

## 14. Decisiones pendientes

Cada una se documenta como ADR en `docs/adr/` cuando se resuelva.

1. **PMS definitivo:** Kamra (open source) vs Repull MCP (abstracción 50+ PMS) vs Hospitable (comercial con MCP oficial).
2. **Proveedor de la capa commodity:** GoHighLevel vs Chatwoot + Attio/HubSpot free + n8n. Criterio: costo a doce meses y comodidad del equipo no técnico.
3. **Sistema de registro de comisiones:** lógica propia en `packages/commissions` (recomendado) vs usar el CRM como fuente de verdad.
4. **¿Es imprescindible el inbox del proveedor?** Con volumen bajo se puede prescindir y usar solo CRM más handoff mínimo propio.
5. **Verificación de MCP de comunidad:** confirmar en `modelcontextprotocol.io`, `smithery.ai` o `mcp.so` la madurez de `MCP_GoHighLevel`, `pywa-mcp-server` y los MCP de Attio/HubSpot/Chatwoot/n8n.
6. **Región de residencia de datos:** confirmar si hay requisitos locales en Ecuador que obliguen a on-prem para algún dato.
7. **Evaluación build vs buy del ARM a la luz del video de @santaia.lab:** el video confirma que el concepto existe y está en operación, pero el repositorio está gateado tras un mecanismo de captura de leads. Antes de considerar la adopción, se debe obtener el repositorio y verificar licencia, calidad, API/MCP, modelo de IA sustituible y exportación de datos. **Mientras no se verifiquen esos puntos, la decisión por defecto es construir en casa.**

---

## 15. Referencias

### Repositorios y herramientas consultadas

- **SARA** — Agente WhatsApp open source multi-vertical con RAG (pgvector + BM25), PII anonymization y guardrails de prompt injection. `github.com/Alessandro114/sara`
- **Repull MCP** — Servidor MCP para la API Repull (50+ PMS, Airbnb, Booking, VRBO). `github.com/ivannikolovbg/repull-mcp`
- **wasp** — Capa de whitelist para sistemas agénticos. `github.com/rickhallett/wasp`
- **Kamra PMS** — PMS open source agéntico con 116 herramientas MCP. `kamrapms.com`
- **Una by Polydom** — Agente IA multi-propiedad para hospitalidad. `github.com/polydom-ai/una-by-polydom`
- **MCP_GoHighLevel** — MCP de comunidad con ~100 herramientas sobre API v2 de GHL. `github.com/ashively101/MCP_GoHighLevel`
- **`kirlts/jarvis`** — Plataforma multi-tenant de gestión de personal con worker WhatsApp (Baileys). `github.com/kirlts/jarvis`
- **`josealfredo79/agenteWhatsapp`** — Agente WhatsApp con Claude + Google Workspace + MCP.
- **`mojtaba-py-code/whatsapp-ai-assistant`** — FastAPI + Claude, RAG BM25, reservas guiadas, multi-idioma.
- **`jayshapiro/whatsapp-claude-bridge`** — Bridge auto-hospedado con tool execution y MCP.
- **`sarrazola/openlivery`** — Plataforma white-label multi-cliente para agentes WhatsApp.
- **`Hainrixz/whatsapp-agentkit`** — Generación de agente vía entrevista con Claude Code.

### Guías, benchmarks y documentación

- **Neon vs Qdrant (2026)** — Base vectorial serverless vs dedicada. `respan.ai`
- **pgvector vs Qdrant (2026)** — Benchmarks de latencia y rendimiento. `toolacademy.ai` / `yourappexpert.com`
- **Conversational AI in Hospitality: Security Guide** — Tokenización PII, controles entrada/salida, audit trails. `witness.ai`
- **Multi-Tenant RAG with PostgreSQL and pgvector** — Row-Level Security. `render.com`
- **Docker Compose in Production** — Archivos de sobrescritura multi-entorno. `docs.docker.com`
- **Registro oficial MCP** — `modelcontextprotocol.io`
- **Índices comunitarios MCP** — `smithery.ai`, `mcp.so`
- **Risk of Ban (OpenWA)** — Confirmación de riesgo de librerías no oficiales de WhatsApp.
- **WhatsApp API for Business: Official vs Open Source** — La API oficial no conlleva riesgo de baneo.

### Productos "Jarvis" y ARM evaluados

- **@santaia.lab — "Los CRM ya murieron. Un ARM que lee tus ventas directo de WhatsApp" (TikTok, 28 de octubre de 2026).** Video promocional de un ARM que lee ventas de un grupo de WhatsApp, las registra automáticamente, permite validación por líder y calcula comisiones. Incluye un asistente llamado "Jarvis" integrado en la app. El repositorio se ofrece a cambio de comentar "ARM" (captura de leads), no como publicación open source verificable. Métricas al momento de la consulta: 11.400 vistas, 669 me gusta, 80 comentarios, 164 compartidos. **Estado: concepto verificado, producto no verificado como dependencia adoptable.**
- **JARVIS Suite (RGA Technologies)** — Suite de 13 módulos IA con dashboards de ventas y agentes WhatsApp.
- **JARVIS CRM Inteligente (Whoptrends)** — SaaS B2B de ventas por WhatsApp con panel CRM.
- **Jarvis + WhatsApp (getjarvis.eu)** — Asistente de escritorio con lectura de inbox WhatsApp.
- **Microsoft JARVIS / HuggingGPT** — Orquestación de modelos con LLM (no relacionado con CRM).

---

## 16. Instrucciones para que Claude construya el PRD

Este informe es el **contexto de entrada**. Claude debe usarlo para generar un **PRD (Product Requirements Document)** completo del proyecto, siguiendo la estructura que se detalla a continuación.

### 16.1. Instrucción inicial para Claude

> "A continuación recibirás el informe maestro del proyecto Glamping Imbabura. Úsalo como fuente de verdad para construir un PRD completo. No inventes decisiones que el informe deje abiertas: márcalas como `[DECISIÓN PENDIENTE]` y referencia la sección 14 del informe. Para cada requisito funcional, incluye criterios de aceptación verificables. Para cada requisito no funcional, incluye una métrica. El PRD debe ser accionable: un equipo de desarrollo debe poder tomar cada user story y estimarla sin necesidad de pedir contexto adicional."

### 16.2. Estructura requerida del PRD

El PRD debe contener, como mínimo, las siguientes secciones:

1. **Visión del producto.** Qué es, para quién, qué problema resuelve y por qué ahora. Una página máximo.
2. **Objetivos y métricas de éxito.** Objetivos de negocio (expansión a departamentos, reducción de fricción en captura de ventas) y objetivos de producto (tiempo de respuesta, tasa de resolución automática, precisión del RAG, tasa de adopción del ARM por vendedores). Cada objetivo con una métrica medible y un plazo.
3. **Personas y roles.** Los seis usuarios de la sección 2.3, con sus necesidades, frustraciones actuales y criterios de éxito.
4. **Casos de uso principales.** Al menos: consulta de disponibilidad y reserva por WhatsApp; check-in autónomo; reporte de incidencia; reporte de venta por vendedor en grupo de WhatsApp; validación de venta por líder; consulta de comisión por vendedor; consulta de tablero por administrador; handoff a humano por zona.
5. **Requisitos funcionales por módulo.** Un bloque por cada componente del repositorio:
   - `whatsapp-gateway`: recepción, envío, ventana de 24 horas, plantillas, manejo de medios.
   - `agent-core`: enrutamiento multi-propiedad, carga de prompts, orquestación de tools, manejo de errores.
   - `rag`: indexación, chunking, recuperación, evaluación, respuesta "no lo sé".
   - `pms-connector`: interfaz abstracta, implementaciones, manejo de errores del PMS.
   - `crm-connector`: interfaz abstracta, implementaciones, manejo de errores del CRM.
   - `arm-jarvis`: lectura del grupo, parsing de ventas, estados (por validar, validada, rechazada), cálculo de comisión, notificación a vendedora, ticket numerado, tablero.
   - `security`: whitelist, rate limit, injection filter, PII redaction, audit log.
   - `observability`: logs, trazas, evaluaciones en CI.
   - `mcp-servers/glamping-tools`: cada tool con su schema de entrada/salida.
6. **Requisitos no funcionales.** Rendimiento (latencia P95 del agente, tiempo de respuesta del ARM), disponibilidad, escalabilidad (número de propiedades y conversaciones concurrentes), seguridad (cumplimiento de las capas de la sección 10), mantenibilidad, observabilidad, portabilidad entre beta y producción.
7. **User stories con criterios de aceptación.** Formato: "Como [rol], quiero [acción] para [beneficio]. Criterios de aceptación: [lista verificable]". Al menos una user story por caso de uso de la sección 4, con sus criterios en formato Given/When/Then.
8. **Flujos de usuario.** Diagramas de secuencia o descripciones paso a paso para: reserva de huésped, check-in, reporte de incidencia, reporte de venta, validación de venta, consulta de comisión, handoff a humano.
9. **Modelo de datos de alto nivel.** Entidades principales (Propiedad, Departamento, Huésped, Reserva, Vendedor, Venta, Comisión, Conversación, Mensaje, Incidencia, Documento de conocimiento), atributos clave y relaciones. Sin llegar a DDL, pero con suficiente detalle para que un equipo de datos pueda diseñar el esquema.
10. **Dependencias técnicas.** PMS elegido, proveedor de CRM, nube gestionada para pgvector, API oficial de Meta, Claude, MCP servers. Cada dependencia con su estado (`[DECISIÓN PENDIENTE]` si aplica).
11. **Fuera de alcance.** Lo que el PRD no cubre en esta versión: por ejemplo, app móvil nativa, integración con OTAs adicionales, multi-idioma, facturación electrónica, etc.
12. **Roadmap por fases.** Mapear las fases 0–8 de la sección 12 a entregables del PRD, con criterios de "fase completada" verificables.
13. **Riesgos y supuestos.** Los riesgos de la sección 13, con su impacto en el PRD, y los supuestos que el PRD asume ciertos (por ejemplo, que el PMS elegido expone MCP).
14. **Glosario.** ARM, MCP, PMS, RAG, pgvector, handoff, prompt injection, PII, OTA, Inbound Webhook, idempotencia.
15. **Anexos.** Referencias de la sección 15, decisiones pendientes de la sección 14, y cualquier ADR que se genere durante la construcción del PRD.

### 16.3. Reglas de calidad para el PRD

- **Cada requisito debe ser verificable.** Si no se puede escribir un test o un criterio de aceptación para él, no es un requisito: es una intención.
- **Cada decisión pendiente debe marcarse explícitamente.** Claude no debe inventar la elección de PMS, CRM o proveedor de nube; debe referenciar la sección 14 y dejar la decisión abierta.
- **Cada user story debe tener criterios de aceptación en formato Given/When/Then.** Sin excepciones.
- **Cada requisito no funcional debe tener una métrica y un umbral.** "Rápido" no es un requisito; "P95 < 3 segundos" sí lo es.
- **El PRD debe ser consistente con el informe.** Si Claude propone algo que contradice una decisión documentada, debe señalarlo explícitamente y proponer un ADR.
- **El PRD debe distinguir núcleo propio de capa commodity.** Cada módulo debe indicar si se construye o se adopta, y en el caso de adopción, qué interfaz abstracta lo aísla.

### 16.4. Entregable esperado

Un documento Markdown (`docs/PRD.md`) con las 15 secciones anteriores, listo para ser revisado por el equipo y usado como base para la planificación de las fases 0–8. Claude debe indicar al final del PRD:

- Qué decisiones pendientes bloquean qué fases.
- Qué supuestos deben validarse antes de empezar la fase 1.
- Qué métricas deben instrumentarse desde el día uno para poder evaluar el éxito del producto.

---

## 17. Cómo usar este informe con Claude

1. **Guardarlo como `docs/PROJECT_CONTEXT.md`** en la raíz del repositorio, junto a `CLAUDE.md`.
2. **En `CLAUDE.md`, referenciarlo:** "Lee `docs/PROJECT_CONTEXT.md` antes de cualquier tarea de arquitectura, implementación o generación de PRD."
3. **Para generar el PRD:** abrir Claude Code en el repositorio y usar la instrucción de la sección 16.1, pidiendo que genere `docs/PRD.md` con la estructura de la sección 16.2.
4. **Usarlo como fuente de verdad:** si Claude propone una alternativa, pedirle que verifique si contradice una decisión documentada o si requiere un nuevo ADR.
5. **Actualizarlo con cada decisión nueva:** cada resolución de la sección 14 genera un ADR en `docs/adr/` y una actualización de este documento y del PRD.
6. **No tratarlo como inmutable:** PMS, proveedor de la capa commodity, verificación de MCP de comunidad y evaluación build vs buy del ARM siguen abiertos.

---

Este informe consolida en un solo documento el contexto del negocio, las decisiones de arquitectura, la distinción entre núcleo propio y capa commodity, la evidencia del ARM a partir del video de @santaia.lab, la integración del ARM con el CRM, la infraestructura híbrida, la seguridad, la estructura del repositorio, las fases de implementación, los riesgos, las decisiones pendientes y las referencias. La sección 16 contiene las instrucciones específicas para que Claude genere el PRD con la estructura, reglas de calidad y entregable esperado.

---

## Anexo A. Referencia secundaria: video de @segunrob (escala de madurez de un agente empresarial)
`¤contexto-madurez`

Fuente: transcripción del video de TikTok de **@segunrob**, publicado el 27 de octubre de 2026 (1 min 42 s; 16.400 vistas, 905 me gusta, 33 comentarios, 345 compartidos al momento de la consulta). Título: *"Todas las empresas quieren su propia IA. Casi ninguna sabe lo que viene después de conectar ChatGPT."*

Es material divulgativo, no una fuente primaria: se usa únicamente como **lista de verificación de madurez** que el PRD convierte en requisitos con métrica. El video narra ocho etapas; cada una nace del problema que deja la anterior:

| Etapa | Qué se añade | Problema que aparece | Dónde lo resuelve este proyecto |
|---|---|---|---|
| 1 | Conectar un LLM por API como "asistente de la empresa". | Se presenta como el proveedor del modelo, no como el negocio. | System prompt con identidad propia (fase 1). |
| 2 | Prompt de sistema con nombre y tono. | Alucina políticas internas. | RAG sobre `docs/negocio/` con "no lo sé" explícito (fase 2). |
| 3 | RAG con los documentos de la empresa. | La gente quiere acciones, no solo respuestas. | Herramientas MCP sobre PMS y CRM (fases 3 y 7). |
| 4 | Servidores MCP hacia sistemas internos: el asistente pasa a ser agente. | Un usuario sin permiso obtiene datos sensibles de otro. | Allowlist por acción, RLS multi-inquilino, el vendedor solo ve su comisión (fases 5 y 6). |
| 5 | Permisos por rol e identidad de usuario. | Un prompt injection ("ignora tus instrucciones…") funciona. | Filtro de injection, whitelist, PII redaction (fase 5). |
| 6 | Barreras, detección de ataques y ocultación de datos sensibles. | En producción la factura de tokens se dispara. | Caché semántico y enrutamiento de modelos (RNF de costo). |
| 7 | Caché semántico y enrutamiento de modelos (simple → barato, difícil → frontera). | Cuando falla, nadie sabe por qué. | Trazas, logs y evaluaciones en CI (fase 5). |
| 8 | Observabilidad: trazas, registros y evaluaciones de cada cambio. | — | Sala `observabilidad`, evaluaciones como árbitro de cada fase. |

Lectura para este proyecto: el roadmap de fases 0–8 del informe ya recorre esta escala, pero lo hace **adelantando** seguridad y observabilidad (fase 5) antes de abrir el ARM y el CRM (fases 6 y 7), para no repetir el patrón "problema primero, remedio después" que el video describe.

`¤contexto-madurez/`

---

## Anexo B. Proyección del informe sobre la metodología ZERAG
`¤contexto-zerag`

El proyecto se desarrolla bajo el **Zero-Regression AI Governance BIAS (ZERAG)**. Esto no altera ninguna decisión de producto del informe; fija *cómo* se construye:

1. **Salas ADPA.** Cada componente de la sección 11 se materializa como una sala estanca bajo `features/<sala>/` con una compuerta pública única `<sala>_service.py` (o `server.py` para el servidor MCP), su `config_<sala>.yaml` y lógica privada. Las dependencias entre salas transitan solo por compuertas; el pasillo central `app_core/` orquesta compuertas y no importa nada privado. La equivalencia exacta está en [`ARQUITECTURA.md`](ARQUITECTURA.md) §3.
2. **Rastros y huellas.** Cada capacidad del PRD lleva un rastro `¤` (definitivo) que aparece en el PRD, en los invariantes, en las tareas, en los ADR y en el código que la ejecuta; durante la edición se usan huellas `¦` que se consolidan a `¤` al sellar. Buscar el rastro en el árbol devuelve toda la historia de la capacidad. El índice vive en [`../governance/artefactos/VPA_INDEX.md`](../governance/artefactos/VPA_INDEX.md).
3. **Boceto → arnés → sellado.** Toda fase se construye en dos pasos: boceto libre dentro de la sala, luego sellado con la interfaz extraída a la compuerta, cero imports laterales y un arnés físico (`ejecutar_arnes_glamping.bat` / `.sh`) con Exit Code 0 como único árbitro de éxito.
4. **Nido de artefactos vivos.** Antes de escribir código ejecutable deben existir y estar anclados `governance/artefactos/PRD.md`, `INVARIANTS.md`, `FUENTES_Y_BIBLIOGRAFIA.md`, `VPA_INDEX.md` y `PROBLEMS.json`. El tablero `TASKS.md` y el `VPA_MAP.md` los sirve el servidor MCP ZERAG; en el repositorio, el trabajo pendiente se especifica como *tasks* en `governance/tareas/`.
5. **Interfaz purificada.** Los rastros son metadatos internos: ningún mensaje de WhatsApp, etiqueta de CRM ni texto de cara al huésped o al vendedor contiene `¤`, `¦`, `¤¬` ni `¤¤`.

`¤contexto-zerag/`

---

## Anexo C. Enmienda 2026-10-30: panel operativo propio (ADR-0013)
`¤contexto-enmiendas`

El propietario revisó el PRD y señaló que no había módulos escritos ni diseño de frontend. Resultado: (1) diseño detallado por sala en [`modulos/`](modulos/README.md); (2) [ADR-0013](adr/ADR-0013-panel-operativo-propio.md), aceptado, que **revisa la decisión de §3** de adoptar la UI del CRM como única interfaz del equipo: se construye un **panel operativo propio** (ventas por validar con validación de un toque, tablero y cierre de comisiones, asistente Jarvis, handoff por zona, incidencias y administración), diseñado en [`FRONTEND.md`](FRONTEND.md). El CRM sigue adoptado como sistema de registro de contactos y oportunidades y, mientras ADR-0010 no decida lo contrario, como inbox de conversaciones de huéspedes fuera de handoff. El cuerpo del informe no se modifica; esta enmienda prevalece sobre §3, §12 (fase 8) y §14.4 en lo que contradigan.

`¤contexto-enmiendas/`

---

`¤contexto-maestro/`
