# ADR-0016 — Terminal móvil de la app
`¤panel-operativo`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado por el responsable técnico, a pedido del propietario |
| Fecha | 2026-10-31 |
| Rol | `¤¤frontend-architect` |

## Contexto

El propietario pidió una terminal para celulares de la app, sin funciones contables. El panel ya estaba diseñado para teléfono, pero solo se usaba desde el navegador, sin avisos ni comportamiento definido sin red. Se aplicó el método de un informe de otro proyecto: capas, DDL, invariantes y escenarios, con una tarea atómica. Su contenido contable, de inventario y de facturación no aplica.

## Decisión

La terminal es el panel operativo instalado como aplicación web progresiva, dentro de la sala `panel_operativo`.

| Tema | Decisión | Alternativa descartada |
| :--- | :--- | :--- |
| Tecnología | App web instalable, una sola base para Android, iPhone y escritorio. | App nativa Android: otro código, otra publicación y sin iPhone. |
| Usuarios | Líder, gestor y administrador, con sus roles actuales. | Vendedores y huéspedes: PRD §11 mantiene WhatsApp como su canal. |
| Avisos | Web Push sin datos personales. | Texto con cliente y monto en la pantalla bloqueada. |
| Sin red | Solo lectura de lo que hay en memoria. | Guardar datos en el teléfono: un equipo perdido expondría personas y comisiones. |
| Escritura sin red | Prohibida. | Cola local: validar sin red choca con otro validador y cambia el orden de la base de comisión. |
| Reintentos | `Idempotency-Key` en cada acción. | Confiar en deshabilitar el botón. |

## Consecuencias

- Nacen `panel.dispositivos`, `panel.acciones_idempotentes`, RF-PAN-11..14, cuatro invariantes, T-801 y T-810.
- En iPhone los avisos exigen instalar la app en la pantalla de inicio.
- Las claves VAPID son secretos: viven en variables de entorno.
- Si hiciera falta publicar en tiendas o usar cámara nativa, se necesita otro ADR.

`¤panel-operativo/`
