# ADR-0018 — Plataforma local de hospedajes
`¤spec-glamping`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado por el propietario el 2026-10-31 en lo funcional. Los puntos abiertos siguen pendientes |
| Fecha | 2026-10-31 |
| Rol | `¤¤solutions-architect` |
| Bloquea | Especificación 0.3.0; T-111 y las tareas de PMS, comisiones y datos reales que dependan de los puntos abiertos |

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

## Puntos abiertos

1. **Comisión con pago directo:** cómo se confirma que una reserva ocurrió y cómo cobra la plataforma al anfitrión. Sin esa regla, la comisión no se puede calcular.
2. **Disponibilidad y precios:** si todos los anfitriones usan un PMS común o si cada uno informa por otra vía. Esto reabre ADR-0007.
3. **Marca:** nombre comercial de la plataforma.
4. **Legal:** términos con anfitriones, responsabilidad ante un reclamo y rol sobre los datos personales. Se suman a ADR-0012.
5. **Dos comisiones:** si la comisión del vendedor sale de la comisión de la plataforma o se calcula aparte.

## Consecuencias

- Los datos de Glamping Imbabura dejan de ser requisito del producto. Se piden cuando se publique ese hospedaje.
- T-105 sigue válida: usa datos sintéticos y solo lectura.
- Hasta la especificación 0.3.0 faltan anfitrión, publicación, comisión de plataforma y aislamiento por anfitrión en PRD, esquema, roles, escenarios y tareas.
- La web pública y WhatsApp deben decir quién ofrece cada hospedaje.

`¤spec-glamping/`
