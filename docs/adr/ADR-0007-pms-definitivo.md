# ADR-0007 — Calendario propio en lugar de un PMS externo
`¤pms-conector`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado por el propietario el 2026-10-31 |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto; recomendación técnica del equipo |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §5.4, §14.1 |
| Bloquea | — |

## Contexto
El agente necesita disponibilidad, cotización, reserva preliminar, instrucciones de check-in y, si el PMS lo cubre, housekeeping e incidencias, para un glamping y hasta 20 departamentos sincronizados con OTAs. La interfaz `PMSConnector` ya está definida en el PRD (RF-PMS-01) y no depende de esta decisión.

## Opciones consideradas

> Las tres columnas de abajo son las opciones evaluadas cuando el producto era un solo negocio. [ADR-0018](ADR-0018-plataforma-local-de-hospedajes.md) cambió la premisa: con varios anfitriones, no todos tendrán un PMS ni usarán el mismo.

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

La plataforma lleva su propio calendario y sus tarifas, detrás de la misma interfaz `PMSConnector`, con el proveedor `plataforma`.

| Tema | Decisión | Alternativa descartada |
| :--- | :--- | :--- |
| Disponibilidad | Una fila por noche ocupada, con clave primaria por unidad y noche. | Comparar rangos en la aplicación: dos reservas simultáneas podrían pasar. |
| Precio | Una tarifa por unidad y noche. Una noche sin tarifa no se vende. | Precio por defecto: podría ofrecer un valor falso. |
| Mantenimiento | El equipo carga tarifas y calendario en el panel. El anfitrión bloquea o libera fechas por WhatsApp. | Exigir un PMS a cada anfitrión. |
| Confirmación | La reserva se confirma cuando el anfitrión acepta la solicitud (RF-ANF-05). | Confirmar al verificar un pago: la plataforma no ve el pago. |
| Incidencias | Quedan en `pms_conector`. La sala `operaciones` no nace. | Sala aparte sin necesidad. |
| Otros sitios | Importar calendarios queda para una fase futura. | Hacerlo ahora. |

## Consecuencias

- Riesgo aceptado: si el anfitrión también vende por otro canal y no bloquea la fecha, el calendario puede quedar desactualizado. La confirmación del anfitrión detiene esa reserva antes de cerrarla.
- Nacen RF-PMS-07, RF-PMS-08, `INV_SIN_DOBLE_RESERVA` y la herramienta `actualizar_calendario`.
- T-212 construye el proveedor `plataforma`. T-204 se retira.
- La sala `agente` no cambia: la interfaz es la misma.

## Criterios de verificación (árbitro)
- Contrato en verde contra `FakePMS` y contra el proveedor `plataforma`.
- Dos reservas simultáneas de la misma noche: solo una pasa (`docs/spec/verificacion_esquema.sql` en la CI).

`¤pms-conector/`
