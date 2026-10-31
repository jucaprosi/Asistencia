# ADR-0007 — PMS definitivo (Kamra / Repull MCP / Hospitable)
`¤pms-conector`

| Campo | Valor |
| :--- | :--- |
| Estado | **Propuesto** — `[DECISIÓN PENDIENTE]` (informe §14.1) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto; recomendación técnica del equipo |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §5.4, §14.1 |
| Bloquea | Fase 3 (RF-PMS-*, RF-MCP-01..05); decide si nace la sala `operaciones` para incidencias |

## Contexto
El agente necesita disponibilidad, cotización, reserva preliminar, instrucciones de check-in y, si el PMS lo cubre, housekeeping e incidencias, para un glamping y hasta 20 departamentos sincronizados con OTAs. La interfaz `PMSConnector` ya está definida en el PRD (RF-PMS-01) y no depende de esta decisión.

## Opciones consideradas

> **Nota de ADR-0018:** con varios anfitriones aparece una cuarta opción recomendada: calendario propio de la plataforma detrás de la misma interfaz, con importación iCal después. Sigue pendiente de decisión.

| Criterio | Kamra PMS (open source, AGPL-3.0) | Repull MCP (API unificada) | Hospitable (comercial, MCP oficial) |
| :--- | :--- | :--- | :--- |
| Control y datos | Total, on-prem posible (favorece ADR-0012) | Abstracción sobre 50+ PMS y OTAs | SaaS |
| MCP | 116 herramientas gobernadas | Sí; *read-mostly* por defecto (`REPULL_MCP_ENABLE_WRITES`) | Oficial |
| Multi-propiedad | Sí | Sí | Sí |
| Incidencias / housekeeping | Sí (front desk, housekeeping, POS) | Depende del PMS subyacente | Parcial |
| Carga operativa | Alta (hospedar, actualizar, backups) | Baja | Baja |
| Riesgo de escritura destructiva | A gobernar con la allowlist propia | Bajo por defecto | A gobernar |
| Licencia | AGPL-3.0: revisar implicaciones si se modifica y se expone como servicio | Comercial | Comercial |

## Criterio de decisión propuesto
1. Prueba de concepto de 2 días con cada candidato finalista contra `tests/pms_conector/test_contrato.py` usando un entorno de pruebas del proveedor.
2. Residencia de datos (ADR-0012): si obliga a on-prem para reservas, Kamra gana por defecto.
3. Costo a 12 meses incluyendo horas de operación.
4. Cobertura de incidencias: si el elegido no las cubre, se crea `features/operaciones/` en la fase 3.

## Decisión
Pendiente. Fecha límite sugerida: antes de cerrar la fase 2.

## Consecuencias previstas
- Solo cambia `config_pms_conector.yaml` y nace un `*_internal.py`; `agente` y `herramientas_glamping` no se tocan.
- Las escrituras al PMS quedan deshabilitadas por defecto en cualquier opción (RF-PMS-02 b).

## Criterios de verificación (árbitro)
- Contrato en verde contra `FakePMS` y contra el proveedor elegido con *fixtures* grabados.
- Reserva preliminar real creada y leída en el entorno de pruebas (fase 3).

`¤pms-conector/`
