# ADR-0012 — Residencia de datos en Ecuador
`¤infra-hibrida`

| Campo | Valor |
| :--- | :--- |
| Estado | **Propuesto** — `[DECISIÓN PENDIENTE]` (informe §14.6) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto con asesoría legal |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §9.1, §14.6 |
| Bloquea | Elección Neon vs Render (fase 0); indexación de datos reales (fase 2); ubicación de reservas y datos de huéspedes |

## Contexto
El modelo híbrido (ADR-0004) lleva pgvector, historial, ventas y auditoría a una nube gestionada fuera de Ecuador. El sistema trata datos personales de huéspedes y vendedores (teléfonos, nombres, documentos en algún caso). Ecuador cuenta con legislación de protección de datos personales; hay que confirmar si impone condiciones a la transferencia internacional o a la ubicación de algún dato, y qué exige en cuanto a consentimiento e información al titular.

## Opciones consideradas
1. Todo en nube gestionada (región más cercana disponible), con tokenización de PII antes de salir del servidor propio.
2. PII y reservas on-prem (PostgreSQL adicional en `agent-net`), resto en nube.
3. Todo on-prem (pierde PITR gestionado; sube el riesgo R-01).

## Criterio de decisión propuesto
Inventario de datos por entidad (PRD §9) con clasificación (personal / sensible / operativo) y una opinión legal escrita sobre transferencia internacional. Si solo la PII está restringida, la opción 1 ya la mantiene tokenizada en la bóveda de `seguridad`; esa bóveda puede ubicarse on-prem (opción 2) sin tocar otras salas.

## Decisión
Pendiente. Fecha límite: antes de indexar o almacenar datos reales (fase 2).

## Consecuencias previstas
- Puede fijar el proveedor de PostgreSQL (ADR-0002) por región.
- Puede exigir un aviso de privacidad en el primer contacto con el huésped (texto del system prompt, fase 1) y un registro de consentimiento en `seguridad`.

## Criterios de verificación (árbitro)
- Inventario de datos por ubicación versionado en este ADR y referenciado desde `INVARIANTS.md`.
- `tests/seguridad/test_pii.py`: ningún valor de PII en claro sale hacia servicios fuera de la ubicación aprobada.

`¤infra-hibrida/`
