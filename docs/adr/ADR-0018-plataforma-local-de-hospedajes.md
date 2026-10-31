# ADR-0018 — Plataforma local de hospedajes
`¤spec-glamping`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado por el propietario el 2026-10-31 en lo funcional; el modelo de comisión lo fijó el responsable técnico a su pedido y es revisable |
| Fecha | 2026-10-31 |
| Rol | `¤¤solutions-architect` |
| Bloquea | Publicar hospedajes reales: faltan marca, términos y revisión legal |

## Contexto

El proyecto nació como asistente de un negocio propio, Glamping Imbabura. El propietario redefinió el producto: es una plataforma local de hospedajes, parecida a Airbnb, con funciones extras. Glamping Imbabura pasa a ser un hospedaje más y no define el producto. Esto cambia el PRD §1, ADR-0017 en la comparación y la premisa de propiedades propias.

## Decisión

| Tema | Decisión | Alternativa descartada |
| :--- | :--- | :--- |
| Producto | Plataforma con hospedajes de varios anfitriones. | Asistente de un solo negocio. |
| Publicación | El equipo de la plataforma revisa y carga cada hospedaje. | Registro autónomo de anfitriones: más alcance desde el inicio. |
| Reserva y pago | Se concretan por WhatsApp. La plataforma no cobra ni custodia el dinero del huésped. | Pasarela propia: exige retener y devolver dinero de terceros. |
| Ingresos | Comisión de la plataforma por reserva. | Suscripción del anfitrión. |
| Vendedores | Jarvis y las comisiones de vendedores se mantienen como función extra. | Retirarlos o limitarlos a un solo negocio. |
| Comparación | Entre hospedajes publicados en la plataforma, hasta tres. | Solo propiedades propias. |
| Nombres internos | Repositorio, salas y rastros conservan sus nombres. | Renombrar ahora: costo sin efecto para el usuario. |

## Comparación con plataformas similares

| Plataforma | Cómo asegura su comisión | Qué se toma |
| :--- | :--- | :--- |
| Airbnb | El pago ocurre dentro de la plataforma y limita los cobros por fuera. | No aplica: exige custodiar dinero. Se toma que el canal sea el punto de control. |
| Hostelworld | El huésped paga un depósito al reservar y el resto al hospedaje. | Queda como plan B si la comisión no se cobra. |
| Booking.com | Emite facturas periódicas con un detalle de reservas, y el hospedaje marca los no-show. | Modelo adoptado. |

Las condiciones de pago en destino de Booking.com no se confirmaron en fuente oficial. Las fechas exactas de su ciclo tampoco, así que las de este proyecto son valores propios.

## Modelo de comisión

| Tema | Decisión | Alternativa descartada |
| :--- | :--- | :--- |
| Registro | Toda reserva nace como solicitud con código antes de que el huésped y el anfitrión tengan el contacto del otro. | Registrar después: sin evidencia de la reserva. |
| Confirmación | El anfitrión confirma por WhatsApp. | Confirmar por el huésped: no sabe si el pago llegó. |
| Devengo | Tras la salida, sin reporte en 3 días pasa a completada. `no_show` y `cancelada` no pagan. | Devengar al confirmar: cobra estadías que no ocurrieron. |
| Cobro | Estado de cuenta mensual el día 5, pago en 14 días y pausa a los 15 días de vencido. | Depósito del huésped: la plataforma recibiría dinero, contra lo decidido. |
| Porcentaje | Se pacta por anfitrión y se congela en cada solicitud. | Un porcentaje global fijo en la especificación: el valor aún no existe. |
| Comisión del vendedor | Se calcula aparte, sobre la venta, y no cambia lo que paga el anfitrión. Revisable. | Descontarla al anfitrión. |

**Riesgo aceptado:** huésped y anfitrión pueden acordar por fuera, y un anfitrión puede reportar `cancelada` sin que sea cierto. Los controles son los términos, la pausa y `ON-06`. Si el cobro queda por debajo del umbral, se debe reevaluar el depósito.

## Puntos abiertos

1. **Disponibilidad y precios:** ADR-0007 sigue pendiente. Se recomienda un calendario propio detrás de la interfaz del PMS.
2. **Marca:** nombre comercial de la plataforma.
3. **Legal y tributario:** términos con anfitriones, responsabilidad ante un reclamo, rol sobre datos personales y comprobantes de la comisión. Se suman a ADR-0012.
4. **Porcentaje:** valor comercial por anfitrión.

## Consecuencias

- Los datos de Glamping Imbabura dejan de ser requisito del producto. Se piden cuando se publique ese hospedaje.
- Nacen la sala `anfitriones`, el rol `anfitrion`, RF-ANF-01..08, US-19, US-20, T-305, T-306, T-405 y T-506.
- T-105 sigue válida: usa datos sintéticos y solo lectura. T-405 limita el catálogo a lo publicado.

`¤spec-glamping/`
