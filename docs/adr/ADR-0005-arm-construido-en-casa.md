# ADR-0005 — Construir el ARM «Jarvis» en casa
`¤arm-jarvis`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado. Reevaluable solo si aparece un repositorio verificable (informe §14.7) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §6, §14.7 |
| Bloquea | — (construir es la decisión por defecto) |

## Contexto
El video de @santaia.lab (28-10-2026) muestra un ARM en operación real cuyo flujo coincide con el que necesita Glamping Imbabura: venta escrita en un grupo, confirmación inmediata, validación por la líder, comisión automática, tablero y asistente «Jarvis». El repositorio se entrega a cambio de comentar «ARM» (captura de leads); no hay empresa identificable, API, MCP, modelo de IA declarado ni modelo de datos.

## Opciones consideradas
1. Adoptar el producto del video.
2. Adoptar alguno de los «Jarvis» comerciales (RGA, Whoptrends, getjarvis.eu) o `kirlts/jarvis`.
3. **Construir `arm_jarvis` en casa con Claude, usando el video como referencia funcional.**

## Decisión
Opción 3. Ninguna alternativa es verificable, integrable con Claude/MCP ni exportable. El costo de construir (1–2 semanas) es menor que el riesgo de una dependencia opaca. `kirlts/jarvis` queda además excluido por usar Baileys (ADR-0003).

## Consecuencias
- Control total del parsing de mensajes no estructurados, de la máquina de estados y de las reglas de comisión.
- El ARM tiene su propio extractor con Claude (DPD: no se acopla al agente de huéspedes).
- Reevaluación: si se obtiene el repositorio, se verifican licencia, calidad, API/MCP, modelo sustituible y exportación antes de reabrir este ADR.

## Criterios de verificación (árbitro)
- `scripts/run_evals.py --suite ventas`: ≥ 95 % de extracciones correctas (OP-07).
- `tests/arm_jarvis/test_estados.py`, `test_ticket.py` (concurrencia), `test_consulta_comision.py` (sin fuga entre vendedores).

`¤arm-jarvis/`
