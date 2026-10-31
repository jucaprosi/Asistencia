# ADR-0013 — Panel operativo propio (frontend del equipo)
`¤panel-operativo`

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado** (decisión del propietario en sesión, 2026-10-30) |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto |
| Fuente | Revisión del PRD por el propietario: «no encuentro escritos módulos ni diseño del frontend»; informe §3, §6.3, §12 (fase 8), §14.4 |
| Revisa | [ADR-0001](ADR-0001-construir-vs-adoptar.md) (acota qué se adopta), [ADR-0010](ADR-0010-inbox-proveedor.md) (reformula la pregunta) |
| Bloquea | — (habilita RF-PAN-* en fases 4–7) |

## Contexto
El informe decidió **adoptar** la UI del CRM para el equipo no técnico y no construir frontend propio, reservando un «panel de handoff mínimo» para la fase 8 solo si se prescindía del inbox del proveedor. Al redactar el PRD quedó sin pantalla definida justamente lo que el video de referencia del ARM muestra como núcleo de la experiencia: la bandeja de ventas *por validar* con validación de un toque y corrección de campos, el tablero de ventas y comisiones, el asistente «Jarvis» y la administración (whitelist, reglas de comisión versionadas, plantillas, conocimiento, auditoría). Un CRM genérico no ofrece esas pantallas sin personalización profunda, y personalizarlo movería lógica de negocio (estados de venta, fijación de comisión, confirmación de cambios de Jarvis) a workflows del proveedor, lo que ADR-0001 prohíbe.

## Opciones consideradas
1. Mantener la UI del CRM y documentar su configuración (pipeline, campos, dashboards, inbox).
2. Panel mínimo propio solo para validar ventas, tablero y Jarvis; el resto en el CRM.
3. **Panel operativo propio completo** para líder, gestores y administrador: ventas, comisiones, Jarvis, handoff por zona, incidencias y administración; el CRM queda como sistema de registro de contactos y oportunidades (y, opcionalmente, inbox).

## Decisión
Opción 3. Nace la sala `features/panel_operativo/` con compuerta `panel_operativo_service.py`, un BFF que solo invoca compuertas y un frontend servido como estáticos. Diseño en [`../FRONTEND.md`](../FRONTEND.md); módulo en [`../modulos/panel_operativo.md`](../modulos/panel_operativo.md); requisitos RF-PAN-01..10 en el PRD §5.11.

Qué sigue siendo **adoptado** (ADR-0001 acotado): el CRM como sistema de registro de contactos y oportunidades, con sus reportes comerciales; el inbox del proveedor para conversaciones de huéspedes mientras ADR-0010 no decida lo contrario; el constructor de workflows para automatizaciones de marketing fuera del alcance de este sistema.

Qué deja de depender del CRM: validar/rechazar ventas, ver y cerrar comisiones, hablar con Jarvis, atender handoffs e incidencias por zona, administrar seguridad y configuración.

## Consecuencias
- Esfuerzo adicional estimado: 2–3 semanas repartidas en las fases 4–7 (ver `FRONTEND.md` §12), en lugar de una fase 8 condicional.
- ADR-0010 cambia de pregunta: ya no «¿inbox del proveedor o panel de handoff propio?» sino «¿inbox del proveedor o inbox completo de huéspedes dentro del panel operativo?». La bandeja de handoff por zona existe en el panel desde la fase 4 en cualquier caso.
- El criterio de costo a 12 meses de ADR-0008 cambia: el CRM se evalúa como sistema de registro e inbox, no como UI operativa, lo que favorece planes más baratos.
- Nueva invariante `INV_PANEL_POR_ROL`: el BFF rechaza con 403 cualquier acción fuera de la allowlist del rol aunque la UI la muestre.
- Nuevo rol de sala `¤¤frontend-developer`; stack técnico propuesto en `FRONTEND.md` §10, revisable sin tocar el diseño.
- El informe maestro no se modifica en su cuerpo; se añade el Anexo C con esta enmienda.

## Criterios de verificación (árbitro)
- `tests/panel_operativo/test_bff_*.py`: cada endpoint con cada rol, 403 donde corresponde.
- `tests/e2e/`: US-06 (validar con un toque), US-08 (tablero cuadra con exportación), US-09 y US-10 (handoff por zona) en navegador real sobre `localhost`.
- `tests/test_interfaz_purificada.py` sobre el build: 0 rastros, 0 nombres de proveedor.
- Presupuesto de rendimiento (LCP ≤ 2,5 s en P-03) medido en CI.

`¤panel-operativo/`
