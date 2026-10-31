# ADR-0003 — API oficial de WhatsApp Cloud; prohibición de librerías no oficiales
`¤canal-whatsapp`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §9.4, §13 |
| Bloquea | — |

## Contexto
WhatsApp es el canal dominante del negocio. Las librerías no oficiales (Baileys, whatsapp-web.js, whatsmeow) violan los términos de servicio y pueden provocar suspensión permanente del número: perder el canal es perder la atención y la operación comercial.

## Opciones consideradas
1. Librerías no oficiales (gratis, sin ventana de 24 h, leen grupos sin restricción).
2. **WhatsApp Business Platform — Cloud API de Meta (oficial).**
3. Proveedor intermedio (Twilio, 360dialog) sobre la API oficial.

## Decisión
Opción 2 (3 queda abierta como implementación interna de `canal_whatsapp` si simplifica la verificación del número; no cambia la interfaz). Queda **prohibida** cualquier dependencia de las librerías de la opción 1.

## Consecuencias
- Hay que gestionar la ventana de 24 h y plantillas aprobadas (RF-GW-03/04) para check-in proactivo y notificaciones de comisión.
- La lectura del canal de vendedores depende de lo que la API oficial permita para grupos: supuesto S-01 y riesgo R-10 del PRD; el fallback es el chat 1:1 de cada vendedor con el número del negocio.
- Costo por conversación según tarifas de Meta, medido desde el día uno.

## Criterios de verificación (árbitro)
- `tests/test_canal_oficial.py`: recorre `pyproject.toml`, `requirements*.txt`, `package*.json` y falla si aparece `baileys`, `whatsapp-web.js` o `whatsmeow`.
- `tests/canal_whatsapp/test_ventana_24h.py`: texto libre fuera de ventana se rechaza en la compuerta.

`¤canal-whatsapp/`
