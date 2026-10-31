# ADR-0009 — Sistema de registro de comisiones (propio vs CRM)
`¤comisiones`

| Campo | Valor |
| :--- | :--- |
| Estado | **Propuesto** — `[DECISIÓN PENDIENTE]` (informe §14.3; recomendación del informe: propio) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto; líder comercial; contabilidad |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §6.2, §7, §14.3 |
| Bloquea | Tablero y cierre de período (fase 7). El cálculo (fase 6) es propio en cualquier caso |

## Contexto
La comisión se calcula al validar la venta. Hay que decidir dónde vive la **fuente de verdad** de comisiones y períodos: en la sala `comisiones` (PostgreSQL propio, reglas versionadas, cierre inmutable) o en el CRM (campos personalizados en la oportunidad).

## Opciones consideradas

| Criterio | Propio (`features/comisiones/`) | CRM como fuente de verdad |
| :--- | :--- | :--- |
| Reglas versionadas con vigencia | Nativo (RF-COM-01) | Difícil: los workflows no versionan reglas |
| Cierre de período inmutable y ajustes | Nativo (RF-COM-02) | No estándar |
| Reproducibilidad del cálculo | Total | Depende del proveedor |
| Exportación para contabilidad | CSV/JSON con esquema propio | Export del CRM, formato del proveedor |
| Visualización para el equipo | Requiere publicar agregados al CRM o a un BI | Nativa en dashboards del CRM |
| Lock-in | Nulo | Alto |

## Criterio de decisión propuesto
Registro propio salvo que contabilidad exija que la fuente de verdad sea el CRM. En ambos casos el CRM muestra los datos; la diferencia es quién manda cuando discrepan.

## Decisión
Pendiente. Fecha límite sugerida: antes de empezar la fase 6.

## Consecuencias previstas
- Si es propio: el tablero se publica al CRM o a un BI externo como lectura; el CRM nunca modifica comisiones.
- Si es el CRM: `comisiones` se reduce a calculadora sin estado y los tests de cierre de período (RF-COM-02) se reasignan al proveedor, lo que debe constar como limitación en `INVARIANTS.md`.

## Criterios de verificación (árbitro)
- `tests/arm_jarvis/test_tablero.py`: totales al centavo con la exportación.
- `tests/comisiones/test_cierre_periodo.py` (ruta propia).

`¤comisiones/`
