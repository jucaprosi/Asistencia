# ADR-0014 — Decisiones de la especificación 0.2 para Spec-Driven Development
`¤spec-glamping`

| Campo | Valor |
| :--- | :--- |
| Estado | **Propuesto**: cada decisión espera la aprobación del propietario |
| Fecha | 2026-10-30 |
| Rol | `¤¤solutions-architect` |
| Bloquea | Congelar la especificación en la versión 1.0 |

## Contexto

La auditoría del PRD 0.1 encontró reglas contradictorias y decisiones sin tomar que cada implementador habría resuelto a su manera. Bajo Spec-Driven Development, la especificación debe bastar para construir cada sala sin consultar a las demás. Este ADR fija un valor por defecto para cada vacío, de modo que el trabajo pueda avanzar. Son propuestas de la IA: ninguna sustituye a una decisión del propietario, y las marcas `[DECISIÓN PENDIENTE]` de ADR-0007 a ADR-0012 siguen abiertas.

## Decisiones

Las marcadas con **Negocio** o **Legal** requieren revisión expresa; las técnicas pueden aceptarse en bloque.

| ID | Tema | Decisión propuesta | Alternativa descartada | Tipo |
| :--- | :--- | :--- | :--- | :--- |
| D-01 | Whitelist de huéspedes | Canal de huéspedes abierto: todo número entra como `huesped_potencial` con permisos mínimos, y la protección son el rate limit y una lista de bloqueo. La whitelist aplica a vendedor, líder, gestor y administrador. | Whitelist previa de huéspedes: rompe el primer contacto. | Negocio |
| D-02 | Roles y allowlist | `huesped` se divide en potencial y activo; se añade `sistema`; `registrar_venta` es el nombre único; el vendedor conserva `solicitar_humano`; el líder cierra el período. | Mantener un solo rol de huésped. | Técnica |
| D-03 | Orden de seguridad | Allowlist, audit log y filtro de inyección nacen en la fase 1. La fase 5 añade la evaluación completa y la RLS sigue en la 4. | Dejarlos en la fase 5: habría un número real sin control. | Técnica |
| D-04 | Dueño del handoff | `crm_conector` guarda zonas y handoffs en tablas propias; el panel es la bandeja; el inbox del proveedor es un espejo opcional sujeto a ADR-0010. | Depender del inbox: ADR-0013 ya lo descartó como interfaz. | Técnica |
| D-05 | Handoff antes de la fase 4 | Se entrega el contacto humano configurado y se registra el motivo en la traza. | Adelantar la bandeja a la fase 1. | Técnica |
| D-06 | Estados de la venta | Se añade `no_publicada → publicada`. Tras 24 horas de reintentos sigue `no_publicada`, alerta y reintento manual. `anulada` es final y solo la aplica el administrador. | Reintentar sin fin. | Técnica |
| D-07 | Reserva cancelada tras la comisión | No hay reversión automática: el administrador anula la venta y se genera el ajuste. | Reversión automática desde el PMS. | Negocio |
| D-08 | Moneda y redondeo | USD como única moneda, dos decimales, `ROUND_HALF_UP`. | Multimoneda: sin caso de uso. | Negocio |
| D-09 | Período de una comisión | Mes de `fecha_venta` en `America/Guayaquil`. Si ese período cerró, entra al período abierto más antiguo con `periodo_origen`. | Reabrir períodos cerrados. | Negocio |
| D-10 | Escalones por volumen | La tasa usa el acumulado validado del vendedor antes de esta venta, y ese acumulado se guarda en `base_acumulada`. Así el cálculo es reproducible. | Liquidar escalones al cierre. | Negocio |
| D-11 | Sin regla aplicable | La validación falla con `SinReglaVigente` y la venta sigue `por_validar`. | Comisión cero silenciosa. | Negocio |
| D-12 | Mensajes de venta | Un mensaje puede crear varias ventas. Duplicado por cliente, producto, monto y `fecha_venta` en 7 días: se registra y se señala al líder. `fecha_llegada` y `noches` son campos propios. | Rechazar duplicados automáticamente. | Negocio |
| D-13 | Datos personales | Aviso y consentimiento versionados, retención configurable, solicitudes del titular y eliminación por criptoborrado de la bóveda. Los plazos son propuestas sujetas a ADR-0012 y revisión legal. | Dejarlo para después del piloto. | Legal |
| D-14 | Acceso físico | `obtener_instrucciones_checkin` exige que el remitente sea titular de una reserva confirmada, desde 24 horas antes de la llegada. Claves y códigos son secretos operativos: el modelo solo ve marcadores. | Confiar en el código de reserva. | Técnica |
| D-15 | Ingesta durable | El webhook persiste antes de responder 200. Un trabajador procesa en orden por remitente, agrupa mensajes de 3 segundos y reintenta hasta 5 veces. | Procesar en memoria. | Técnica |
| D-16 | Repositorio público | El corpus real, las evaluaciones con datos reales y las reglas de comisión viven fuera del repositorio, en `CORPUS_DIR` y `evals/privado/`. El repositorio solo guarda datos sintéticos. Los prompts se consideran públicos y no contienen secretos. | Publicar el corpus. | Negocio |
| D-17 | Entornos | Beta: fases 0 a 5. Piloto en el mismo equipo con vendedores reales: fases 6 y 7. Producción tras la fase 7. | Producción antes del ARM. | Negocio |
| D-18 | Reservas | La preliminar expira a las 24 horas. El gestor confirma el pago en el PMS. Cancelar o cambiar pasa por una persona. Los pasos de pago salen del corpus. | Cancelación autónoma en la versión 0.2. | Negocio |
| D-19 | Handoff sin respuesta | 15 minutos sin tomar pasa al respaldo con alerta; 24 horas sin actividad vuelve al asistente con aviso. | Silencio indefinido. | Negocio |
| D-20 | Métricas | Conversación cerrada tras 24 horas de inactividad; baja confianza significa 2 abstenciones seguidas; la línea base de `ON-01` se mide las dos semanas previas a T0; la fidelidad combina comparación exacta de cifras y juicio de un modelo evaluador. | Dejar los términos a criterio del implementador. | Técnica |
| D-21 | PII | Teléfono, correo, documento y tarjeta por reglas con recall 100 %. Nombres y direcciones con reconocimiento de entidades y recall mínimo de 95 % en un set sintético de 200 casos. | Prometer 100 % en nombres: no es verificable. | Técnica |

## Consecuencias

- La especificación ejecutable vive en [`docs/spec/`](../spec/README.md), y el árbitro es `tests/test_especificacion.py`.
- Cambian contratos de `seguridad`, `arm_jarvis`, `comisiones`, `canal_whatsapp`, `pms_conector`, `crm_conector` y `herramientas_glamping` antes de que exista código real, lo que evita retrabajo.
- Si el propietario rechaza una decisión, se ajustan contrato, escenarios y tareas, y se sube la versión del PRD.

`¤spec-glamping/`
