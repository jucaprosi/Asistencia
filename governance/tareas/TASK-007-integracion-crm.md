```toml
id = "TASK-007"
titulo = "Conector CRM: Inbound Webhook firmado e idempotente, cola de reintentos, eventos del CRM, tablero y paso a producción"
fase = 7
estado = "pendiente"
sala = ["crm_conector", "arm_jarvis (tablero)", "comisiones (exportación)"]
rastro = ["¤crm-conector", "¤arm-jarvis", "¤comisiones", "¤infra-hibrida"]
rol = "¤¤integration-engineer"
depende_de = ["TASK-005"]
bloqueada_por = ["ADR-0008", "ADR-0011"]
propiedad = ["features/crm_conector/**", "features/arm_jarvis/tablero_internal.py", "features/comisiones/exportacion_internal.py", "features/comisiones/esquema_exportacion.json", "tests/crm_conector/**", "tests/arm_jarvis/test_tablero.py", "tests/comisiones/test_exportacion.py"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); test_publicar_venta.py (firma verificada, idempotencia); test_cola_reintentos.py; tablero cuadra al centavo con exportación; stack levantado en el servidor propio con compose.production.yaml"
```

# TASK-007 — Integración con CRM y producción
`¤crm-conector`

## Objetivo
Las ventas validadas llegan al CRM como contacto + oportunidad, firmadas e idempotentes; los eventos del CRM (validación, devolución de handoff, incidencia resuelta) vuelven al sistema; el tablero y la exportación cierran el primer período; el stack pasa al servidor propio.

## Requisitos cubiertos
RF-CRM-01..05, RF-ARM-08, RF-COM-03, RF-MCP-07, RNF-09, RNF-14 (producción). Invariantes: `INV_VENTA_FIRMADA_IDEMPOTENTE`, `INV_VENTA_NO_SE_PIERDE`, `INV_MISMO_COMPOSE`, `INV_RED_AISLADA` (en el servidor real).

## Entregables
1. Implementación del proveedor elegido (`ghl_internal.py` o `chatwoot_internal.py` + `attio_internal.py`), activada por configuración.
2. `publicar_venta` con HMAC-SHA256 y `venta_id`; receptor simulado en tests que verifica la firma; cola persistente de reintentos hasta 24 h.
3. `POST /crm/eventos` firmado → `crm_conector_service.recibir_evento` → `arm_jarvis` / `agente`.
4. Tablero (datos agregados) y exportación CSV/JSON validada contra esquema; visualización según ADR-0009.
5. Despliegue en el servidor propio con `compose.production.yaml`; prueba de conexión negativa hacia los servicios contables; backups cifrados si comparten almacenamiento.

## Criterios de fase completada
- RNF-09; publicación idempotente probada; tablero cuadra al centavo.
- Primer cierre de período de prueba exportado.
- **Hito de producción** aprobado por el propietario.

## Pantallas del panel operativo en esta tarea (ADR-0013)
`¤panel-operativo` · Sala adicional: `panel_operativo`. Entregables: P-05 Tablero, P-06 Cierre de período y exportación, P-11 Reglas de comisión, Plantillas, Conocimiento, Propiedades y zonas (RF-PAN-04, 05, 09 completo). Criterio: US-08 en `tests/e2e/test_tablero.py` (totales al centavo con la exportación); 409 tras cierre de período.
