# ADR-0015 — Qué se toma de los referentes de interfaz
`¤frontend-glamping`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado por el responsable técnico, a pedido del propietario |
| Fecha | 2026-10-30 |
| Rol | `¤¤frontend-architect` |

## Contexto

Un informe externo propuso referentes por superficie: PMS, inbox de WhatsApp, comisiones y reserva directa. El panel ya tiene diseño, alcance y presupuesto en [`FRONTEND.md`](../FRONTEND.md), y cada propuesta se evaluó contra ese diseño. Las puntuaciones y capacidades que cita el informe no se verificaron, salvo lo indicado en [`FUENTES_Y_BIBLIOGRAFIA.md`](../../governance/artefactos/FUENTES_Y_BIBLIOGRAFIA.md).

## Decisión

| Propuesta | Decisión | Motivo |
| :--- | :--- | :--- |
| Cálculo visible en cada comisión | Adoptar | El monto de una venta depende de su acumulado. Sin desglose, cada cifra invita a una disputa. |
| Estado de cuenta por vendedor | Adoptar | Une ventas y ajustes y cuadra con la exportación. |
| Inbox en tres columnas | Adoptar solo en ≥ 1024 px | El gestor trabaja en teléfono: en móvil sigue una columna. |
| Primitivas accesibles MIT | Permitir | Ahorran trabajo de accesibilidad en diálogos y hojas, sujetas al presupuesto de JS. |
| Next.js, Supabase o reutilizar wacrm | Rechazar | Duplicaría base, autenticación y lógica fuera de FastAPI y las salas. Se estudia solo como patrón. |
| Kits de UI de pago | Rechazar | Los componentes ya están definidos con tokens propios. |
| Ranking de vendedores | Rechazar por ahora | El tablero ya lista por vendedor. Hacerlos competir es una decisión comercial. |
| Tablero de limpieza con fotos y pagos | Aplazar | Depende del PMS de ADR-0007. |
| Motor de reserva directa y grid de tarifas | Aplazar | PRD §11 excluye una web para huéspedes, y tarifas y disponibilidad son del PMS. |

## Consecuencias

- Nacen `comisiones.desglose` y `comisiones.estado_cuenta`. Las pantallas no calculan.
- No se copia código, logotipos ni estilos de terceros.
- Un cambio de stack o de alcance exige otro ADR.

`¤frontend-glamping/`
