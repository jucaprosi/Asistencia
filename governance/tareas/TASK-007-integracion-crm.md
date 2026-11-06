```toml
id = "TASK-007"
titulo = "Conector CRM: Inbound Webhook firmado e idempotente, cola de reintentos, eventos del CRM, tablero y paso a producción"
fase = 7
estado = "sellada"
sala = ["crm_conector", "arm_jarvis (tablero)", "comisiones (exportación)"]
rastro = ["¤crm-conector", "¤arm-jarvis", "¤comisiones", "¤infra-hibrida"]
rol = "¤¤integration-engineer"
depende_de = ["TASK-005"]
bloqueada_por = ["ADR-0008", "ADR-0011"]
propiedad = ["features/crm_conector/**", "features/arm_jarvis/tablero_internal.py", "features/comisiones/exportacion_internal.py", "features/comisiones/esquema_exportacion.json", "tests/crm_conector/**", "tests/arm_jarvis/test_tablero.py", "tests/comisiones/test_exportacion.py", "tests/integracion/test_fase7.py"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); test_publicar_venta.py (firma verificada, idempotencia); test_cola_reintentos.py; tablero cuadra al centavo con exportación; stack levantado en el servidor propio con compose.production.yaml; test_fase7.py (Exit Code 0)"
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
6. Suite E2E de producción en `tests/integracion/test_fase7.py` cubriendo la totalidad de los escenarios de validación, CRM, comisiones y cierre de período.

## Criterios de fase completada
- RNF-09; publicación idempotente probada; tablero cuadra al centavo.
- Primer cierre de período de prueba exportado.
- **Hito de producción** aprobado por el propietario.

## Pantallas del panel operativo en esta tarea (ADR-0013)
`¤panel-operativo` · Sala adicional: `panel_operativo`. Entregables: P-05 Tablero, P-06 Cierre de período y exportación, P-11 Reglas de comisión, Plantillas, Conocimiento, Propiedades y zonas (RF-PAN-04, 05, 09 completo). Criterio: US-08 en `tests/e2e/test_tablero.py` (totales al centavo con la exportación); 409 tras cierre de período.

## Verificación y Cierre (T-611)
- `tests/integracion/test_fase7.py` ejecutado exitosamente con 14/14 pruebas en verde (Exit Code 0).
- Publicación de ventas hacia el webhook del CRM con 100% de firmas HMAC-SHA256 válidas y 0 duplicados por `venta_id` (`INV_VENTA_FIRMADA_IDEMPOTENTE`).
- Invariante `INV_COMISION_REPRODUCIBLE` verificado:
  - Modo graduado: 110.00 USD sobre ventas de 333.33, 700.10 y 566.57.
  - Modo volumen: 160.00 USD sobre el mismo conjunto.
  - Independencia del orden de validación confirmada al centavo (A->B vs B->A).
  - Anulación de venta con ajuste negativo (-65.00 USD) preservando inalteradas las comisiones ya fijadas.
  - Venta tardía asignada al período abierto con `periodo_origen` del mes cerrado.
- Cierre inmutable de período mensual con confirmación escrita y respuesta 409 a mutaciones posteriores.
- Control de acceso RBAC: Líder bloqueado con 403 al intentar acceder a la administración; administrador auditable en `seguridad.audit_log`.
