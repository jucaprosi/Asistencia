# ADR-0004 — Infraestructura híbrida y aislamiento del flujo contable
`¤infra-hibrida`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §9 |
| Bloquea | — |

## Contexto
El servidor propio ya ejecuta flujos contables críticos. La fase beta corre en un PC Ubuntu con un solo disco SATA que además aloja un MCP en producción interna. Hay que proteger ambos y garantizar que lo probado en beta sea lo que corre en producción.

## Opciones consideradas
1. Todo en nube gestionada (incluida la lógica).
2. Todo en el servidor propio (incluida la base de datos).
3. **Híbrido: datos críticos en nube gestionada; lógica stateless en el servidor propio, aislada por red Docker.**

## Decisión
Opción 3. pgvector/PostgreSQL y archivos en servicios gestionados con PITR; gateway, agente, ARM y conectores en contenedores reconstruibles desde Git. Red Docker dedicada `agent-net` sin ruta a los servicios contables; en beta, `glamping-beta-net` sin acceso al MCP existente. `compose.yaml` + `compose.production.yaml` como único mecanismo de diferencia entre entornos.

## Consecuencias
- El PC beta puede perderse sin perder datos reales (ninguno vive allí).
- Límites de CPU/RAM por contenedor, credenciales de mínimo privilegio por servicio, logs en volúmenes separados.
- La residencia de datos de ADR-0012 puede obligar a mantener algún dato on-prem: se resolvería con un PostgreSQL adicional en `agent-net`, sin cambiar este ADR.

## Criterios de verificación (árbitro)
- `docker compose -f compose.yaml -f compose.production.yaml config` válido en CI (RNF-14).
- Prueba de conexión negativa desde `agent-net` a los puertos contables en el arnés de despliegue (RNF-10).
- Restauración de backup externo documentada al menos una vez por fase (RNF-15).

`¤infra-hibrida/`
