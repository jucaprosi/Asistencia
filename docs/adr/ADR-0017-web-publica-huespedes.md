# ADR-0017 — Web pública para huéspedes
`¤web-huespedes`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado por el propietario el 2026-10-31 en lo funcional; detalles técnicos por el responsable técnico. La comparación cambia con [ADR-0018](ADR-0018-plataforma-local-de-hospedajes.md) |
| Fecha | 2026-10-31 |
| Rol | `¤¤frontend-architect` |

## Contexto

El propietario decidió que los huéspedes deben poder buscar y comparar opciones, con una web pública construida desde el inicio. La app en tiendas queda como fase futura. Esto modifica el PRD §11, que excluía una web para huéspedes.

## Decisión

| Tema | Decisión | Alternativa descartada |
| :--- | :--- | :--- |
| Sala | `web_huespedes`, separada del panel. | Extender el panel: mezclaría acceso público y datos del equipo. |
| Inicio | Fase 1 con catálogo y paso a WhatsApp; búsqueda y comparación en la fase 3 contra `FakePMS`. | Esperar al PMS: retrasaría todo por ADR-0007. |
| Render | HTML en el servidor con FastAPI y Jinja2. | SPA del panel: los buscadores leen peor y carga más JavaScript. |
| Comparación | Solo propiedades propias, hasta tres. | Comparar con terceros: exige otros datos y permisos. |
| Reserva y pago | Terminan en WhatsApp. | Motor de reserva propio: añade pago y más alcance. |
| Identidad | Sin cuentas ni datos personales. | Registro previo: frena al visitante y crea datos que proteger. |
| Precios | En vivo del PMS en cada búsqueda. | Caché: podría mostrar un precio falso. |
| App en tiendas | Fase futura, con ADR propio y según uso medido. | Hacerla ahora: costo sin demanda comprobada. |

## Consecuencias

- Nacen la sala `web_huespedes`, el esquema `web`, US-18, RF-WEB-01..06, cuatro invariantes, T-105 y T-205.
- La web es la primera superficie pública: su exposición exige límites por IP desde el primer día.
- Con el PMS real, los precios dependen de ADR-0007. Hasta entonces la búsqueda solo corre con datos de prueba y no debe publicarse.
- Publicar exige tener aviso de privacidad, catálogo real y fotos con derechos de uso.

`¤web-huespedes/`
