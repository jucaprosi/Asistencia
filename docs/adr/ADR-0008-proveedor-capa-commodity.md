# ADR-0008 — Proveedor de la capa commodity (GoHighLevel vs Chatwoot + Attio/HubSpot + n8n)
`¤crm-conector`

| Campo | Valor |
| :--- | :--- |
| Estado | **Propuesto** — `[DECISIÓN PENDIENTE]` (informe §14.2) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto; líder comercial (usuario principal de la UI) |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §5.6, §7, §14.2 |
| Bloquea | Fase 7 (RF-CRM-*, tablero, Inbound Webhook); condiciona ADR-0010 |

## Contexto
El equipo no técnico necesita CRM (contactos, pipeline), inbox con handoff por zona y constructor de workflows. Todo entra por `crm_conector_service.py`; la decisión afecta a la UI y al costo, no al núcleo.

## Opciones consideradas

| Criterio | GoHighLevel (SaaS) | Chatwoot + Attio o HubSpot free + n8n (open source / freemium) |
| :--- | :--- | :--- |
| Costo a 12 meses | 97–497 USD/mes según plan (1 164–5 964 USD/año) | Infraestructura propia + horas de operación; licencias gratuitas o bajas |
| Inbox multicanal con asignación | Conversations (WhatsApp vía LC Phone/Twilio, SMS, email, IG, FB) | Chatwoot (WhatsApp Cloud API nativo) |
| Inbound Webhook con firma/token | Sí (workflow trigger) | Chatwoot/n8n webhooks; firma a implementar en n8n |
| MCP de comunidad | `MCP_GoHighLevel` (~100 herramientas) — verificar en ADR-0011 | Chatwoot, Attio, HubSpot, n8n MCP — verificar en ADR-0011 |
| Comodidad del equipo no técnico | Alta, todo en un producto | Media: tres productos |
| Carga operativa | Nula | Alta (tres servicios autoalojados o semigestionados) |
| Lock-in | Workflows y funnels propietarios; mitigado por la interfaz | Bajo |
| WhatsApp | Un segundo número vía LC Phone, o solo CRM sin canal (el canal lo lleva `canal_whatsapp`) | Chatwoot puede compartir el número oficial como inbox |

Nota: en ambas rutas el **canal** de WhatsApp lo opera `canal_whatsapp` con la Cloud API; el CRM recibe copia de las conversaciones para el inbox mediante `crm_conector`, o bien el inbox del proveedor se conecta al mismo número si el proveedor lo permite. Ese detalle se cierra en la prueba de concepto.

## Criterio de decisión propuesto
Costo total a 12 meses (licencias + horas de operación) y prueba de uso de 1 semana del líder comercial y un gestor sobre cada candidato con datos sintéticos. Peso sugerido: 50 % comodidad del equipo, 30 % costo, 20 % riesgo de lock-in.

## Decisión
Pendiente. Fecha límite sugerida: antes de cerrar la fase 5. Hasta entonces `FakeCRM` cubre el inbox mínimo de la fase 4.

## Consecuencias previstas
- Solo cambia `config_crm_conector.yaml` y el `*_internal.py` activo.
- El Inbound Webhook se firma con HMAC-SHA256 en cualquier ruta (RF-CRM-03); si el proveedor no valida firmas, el workflow valida un token compartido y el ARM registra la limitación en `INVARIANTS.md`.

## Criterios de verificación (árbitro)
- `tests/crm_conector/test_contrato.py` y `test_publicar_venta.py` en verde contra el proveedor elegido.
- Handoff por zona (US-09, US-10) en verde con el inbox elegido.

`¤crm-conector/`
