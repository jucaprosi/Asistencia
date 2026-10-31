# Fuentes y bibliografía — Glamping Imbabura
`¤fuentes-glamping`

> Catálogo de trazabilidad externa. Cada fuente está anclada al rastro `¤` que fundamenta. Las fuentes del informe maestro (§15) se reproducen con su estado de verificación; las académicas se añaden para fundamentar las decisiones de arquitectura. **Estado:** `verificada` (consultada y vigente al 2026-10-30), `citada por el informe` (no reverificada por este documento), `secundaria` (divulgativa, no se usa como fundamento técnico).

## 1. Fundamentación por rastro

### Construir vs adoptar; salas estancas; compuertas
`¤adr-construir-adoptar` `¤arquitectura-salas` `¤adr-zerag`
- **David L. Parnas (1972).** *«On the Criteria to Be Used in Decomposing Systems into Modules»*, Communications of the ACM 15(12), 1053–1058. Ocultamiento de información: cada sala esconde su proveedor tras una compuerta. — `verificada` (texto clásico).
- **Bertrand Meyer (1992).** *«Applying “Design by Contract”»*, IEEE Computer 25(10), 40–51. Precondiciones y postcondiciones de las compuertas; contrato bilateral de ZERAG. — `verificada` (texto clásico).
- **Michael T. Nygard (2018).** *Release It! Design and Deploy Production-Ready Software*, 2.ª ed., Pragmatic Bookshelf. Patrón *Bulkhead*: fallos del CRM o del PMS no deben tumbar al agente. — `verificada` (texto clásico).
- **Gerard Meszaros (2007).** *xUnit Test Patterns*, Addison-Wesley. Dobles de prueba (`FakePMS`, `FakeCRM`) y arnés de verificación observable. — `verificada` (texto clásico).

### Canal de WhatsApp
`¤canal-whatsapp`
- **Meta — WhatsApp Business Platform, Cloud API.** Documentación oficial: webhooks y firma `X-Hub-Signature-256`, ventana de servicio de 24 h, plantillas de mensaje, medios, precios por conversación. `developers.facebook.com/docs/whatsapp/cloud-api` — `verificada` (fuente primaria del canal; releer para el supuesto S-01 sobre grupos antes de la fase 6).
- **Risk of Ban (OpenWA)** y **WhatsApp API for Business: Official vs Open Source.** Confirman el riesgo de suspensión con librerías no oficiales. — `citada por el informe`.
- **`pywa-mcp-server`.** MCP de comunidad sobre la Cloud API. — `citada por el informe`; verificar según ADR-0011.

### Agente, RAG y evaluación
`¤agente-enrutador` `¤conocimiento-rag`
- **Anthropic — Claude Developer Platform.** Documentación oficial de *tool use*, *prompt caching*, *Model Context Protocol* y buenas prácticas de system prompts. `docs.anthropic.com` — `verificada` (fuente primaria del motor).
- **Model Context Protocol — especificación y registro.** `modelcontextprotocol.io` — `verificada`.
- **Patrick Lewis et al. (2020).** *«Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks»*, NeurIPS 2020. Fundamento del RAG. — `verificada` (artículo original).
- **Yu. A. Malkov, D. A. Yashunin (2018).** *«Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs»*, IEEE TPAMI. Índice HNSW de pgvector. — `verificada` (artículo original).
- **pgvector (repositorio oficial).** `github.com/pgvector/pgvector` — `verificada`.
- **Neon vs Qdrant (2026), pgvector vs Qdrant (2026).** Benchmarks citados en el informe §5.1 (`respan.ai`, `toolacademy.ai`, `yourappexpert.com`). — `citada por el informe`; las cifras del informe se tratan como orden de magnitud, no como garantía: RNF-04 se mide en el arnés.
- **Multi-Tenant RAG with PostgreSQL and pgvector (Render).** RLS por inquilino. — `citada por el informe`.
- **SARA** (`github.com/Alessandro114/sara`). Agente WhatsApp con pgvector + BM25, anonimización de PII, > 40 patrones de inyección en 4 idiomas, detección de alucinaciones. Referencia de diseño, no dependencia. — `citada por el informe`.
- **Una by Polydom** (`github.com/polydom-ai/una-by-polydom`). Agente multi-propiedad en hospitalidad; valida el enrutamiento por propiedad. — `citada por el informe`.
- **`josealfredo79/agenteWhatsapp`, `mojtaba-py-code/whatsapp-ai-assistant`, `jayshapiro/whatsapp-claude-bridge`, `sarrazola/openlivery`, `Hainrixz/whatsapp-agentkit`.** Referencias de patrones (FastAPI + Claude, reservas guiadas, bridge con MCP). — `citadas por el informe`.

### Seguridad
`¤seguridad-canal`
- **OWASP Top 10 for Large Language Model Applications (2025).** LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM06 Excessive Agency. Base de RF-SEC-02/04/05. `owasp.org` — `verificada`.
- **Conversational AI in Hospitality: Security Guide (witness.ai).** Tokenización de PII, controles de entrada/salida, audit trails. — `citada por el informe`.
- **`rickhallett/wasp`.** Whitelist para sistemas agénticos. — `citada por el informe`.
- **`guarded-whatsapp-mcp`.** Audit log de acciones. — `citada por el informe`.
- **RFC 2104 — HMAC: Keyed-Hashing for Message Authentication** (Krawczyk, Bellare, Canetti, 1997). Firma del Inbound Webhook. — `verificada`.
- **PostgreSQL — Row Security Policies.** Documentación oficial. — `verificada`.

### PMS y CRM
`¤pms-conector` `¤crm-conector`
- **Kamra PMS** (`kamrapms.com`, AGPL-3.0; 116 herramientas MCP). — `citada por el informe`; verificar licencia y entorno de pruebas en ADR-0007.
- **Repull MCP** (`github.com/ivannikolovbg/repull-mcp`; *read-mostly*, `REPULL_MCP_ENABLE_WRITES`). — `citada por el informe`.
- **Hospitable** (MCP oficial), **Hostex** (MCP no oficial). — `citadas por el informe`.
- **GoHighLevel — API v2 y workflows (Inbound Webhook).** — `citada por el informe`; verificar validación de firma en ADR-0008.
- **`ashively101/MCP_GoHighLevel`** (~100 herramientas). — `citada por el informe`; verificar en ADR-0011.
- **Chatwoot, Attio, HubSpot, n8n** (documentación y MCP de comunidad). — `citadas por el informe`; verificar en ADR-0011.
- **WAGHL.** Grupos de WhatsApp en el inbox de GHL. Alternativa descartada por no cubrir comisiones (informe §7.3). — `citada por el informe`.

### ARM «Jarvis»
`¤arm-jarvis`
- **@santaia.lab (TikTok, 28-10-2026).** *«Los CRM ya murieron. Un ARM que lee tus ventas directo de WhatsApp, sin digitar nada, con comisión calculada sola.»* 1 min 9 s; 11.400 vistas, 669 me gusta, 80 comentarios, 164 compartidos al momento de la consulta. Transcrito. Referencia **funcional** del flujo; no es dependencia (ADR-0005). — `secundaria`.
- **JARVIS Suite (RGA Technologies), JARVIS CRM Inteligente (Whoptrends), Jarvis + WhatsApp (getjarvis.eu), `kirlts/jarvis`, Microsoft JARVIS/HuggingGPT.** Evaluados y descartados (informe §6.1). — `citadas por el informe`.

### Infraestructura
`¤infra-hibrida`
- **Docker — Compose: use multiple Compose files / production.** `docs.docker.com` — `verificada`.
- **MinIO — replicación y `mc mirror`; rclone.** Estrategia 3-2-1 si se autoaloja. — `citada por el informe`.
- **Peter Krogh (2009).** *The DAM Book*, O'Reilly. Origen de la regla de respaldo 3-2-1. — `verificada` (texto clásico).

### Escala de madurez (referencia secundaria)
`¤contexto-madurez`
- **@segunrob (TikTok, 27-10-2026).** *«Todas las empresas quieren su propia IA. Casi ninguna sabe lo que viene después de conectar ChatGPT.»* 1 min 42 s; 16.400 vistas, 905 me gusta, 33 comentarios, 345 compartidos. Ocho etapas: API → prompt → RAG → MCP → permisos → guardrails → caché/enrutamiento → observabilidad. Usado solo como lista de verificación en [`PROJECT_CONTEXT.md` Anexo A](../../docs/PROJECT_CONTEXT.md). — `secundaria`.

## 2. Pendientes de verificación
Las fuentes marcadas `citada por el informe` sobre PMS, CRM y MCP de comunidad se reverifican en ADR-0007, ADR-0008 y ADR-0011 con fecha, versión y licencia antes de que su código entre en una sala.

`¤fuentes-glamping/`

## Modos de escalón (`¤spec-glamping`)

| Fuente | Función | Nota |
| :--- | :--- | :--- |
| [Stripe: precios por tramos](https://docs.stripe.com/subscriptions/pricing-models/tiered-pricing) | D-10 | Separa graduado y volumen como modos explícitos. |
| [Qobra: comisión escalonada](https://www.qobra.co/glossary/tiered-commission) | D-10 | Marginal y retroactivo. Es fuente de proveedor. |
