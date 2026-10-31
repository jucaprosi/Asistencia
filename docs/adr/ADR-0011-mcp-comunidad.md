# ADR-0011 — Verificación de MCP de comunidad antes de usarlos
`¤pms-conector` `¤crm-conector`

| Campo | Valor |
| :--- | :--- |
| Estado | **Propuesto** — `[DECISIÓN PENDIENTE]` (informe §14.5) |
| Fecha | 2026-10-30 |
| Decisores | Equipo técnico; propietario para la licencia |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §7.2, §8.2, §14.5 |
| Bloquea | Implementaciones `*_internal.py` de `pms_conector` y `crm_conector` que quieran apoyarse en un MCP de comunidad (pueden empezar con la API directa) |

## Contexto
Existen MCP de comunidad para GoHighLevel (`ashively101/MCP_GoHighLevel`, ~100 herramientas), WhatsApp (`pywa-mcp-server`), Attio, HubSpot, Chatwoot y n8n. Ahorran trabajo pero introducen código de terceros con mantenimiento incierto en el camino de acciones con efectos reales (crear contactos, enviar mensajes).

## Opciones consideradas
1. Usar los MCP de comunidad directamente desde el agente.
2. **Usarlos solo dentro de la sala conectora, tras verificación, y nunca expuestos al modelo sin pasar por la allowlist propia.**
3. No usarlos: API directa en cada `*_internal.py`.

## Criterio de verificación propuesto (checklist por MCP)
- [ ] Publicado en `modelcontextprotocol.io`, `smithery.ai` o `mcp.so`, con repositorio público.
- [ ] Licencia compatible (MIT/Apache-2.0/BSD) y sin dependencia de Baileys ni similares (ADR-0003).
- [ ] Último commit < 6 meses; issues abiertos con respuesta.
- [ ] Separa herramientas de lectura y escritura, o permite deshabilitar escrituras.
- [ ] Sin secretos en logs; configuración por variables de entorno.
- [ ] Pasa `tests/<sala>/test_contrato.py` envuelto en la compuerta.

## Decisión
Pendiente por MCP. Mientras no se verifique, la implementación usa la API directa del proveedor (opción 3). En ningún caso un MCP de comunidad se conecta al agente fuera de la sala conectora (opción 1 queda descartada por ADR-0001 y RF-CRM-05).

## Consecuencias previstas
- La verificación se registra en `FUENTES_Y_BIBLIOGRAFIA.md` con fecha y versión.
- Un MCP que deje de mantenerse se sustituye dentro de la sala sin tocar otras.

## Criterios de verificación (árbitro)
- `tests/crm_conector/test_confinamiento.py` y `adpa_linter`: cero imports del MCP fuera de la sala.

`¤pms-conector/`
