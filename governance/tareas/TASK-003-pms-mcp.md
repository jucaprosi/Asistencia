```toml
id = "TASK-003"
titulo = "Conector PMS por compuerta y herramientas MCP de disponibilidad, cotización, reserva, check-in e incidencias"
fase = 3
estado = "pendiente"
sala = ["pms_conector", "herramientas_glamping", "operaciones (condicional)"]
rastro = ["¤pms-conector", "¤herramientas-mcp", "¤operaciones-incidencias"]
rol = "¤¤integration-engineer"
depende_de = ["TASK-001"]
bloqueada_por = ["ADR-0007"]
propiedad = ["features/pms_conector/**", "features/herramientas_glamping/**", "features/operaciones/**", "tests/pms_conector/**", "tests/herramientas_glamping/**", "tests/operaciones/**"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); contrato en verde contra FakePMS y proveedor real con fixtures; reserva preliminar real en entorno de pruebas; RNF-02"
```

# TASK-003 — PMS vía MCP
`¤pms-conector` `¤herramientas-mcp`

## Objetivo
El agente consulta disponibilidad real, cotiza, crea reservas preliminares, entrega instrucciones de check-in y registra incidencias a través del servidor MCP propio, que llama a la compuerta del PMS.

## Requisitos cubiertos
RF-PMS-01..04, RF-MCP-01..05 (y esqueleto de 06..09 con `NotImplementedError`). Invariantes: `INV_SIN_CLIENTES_OTA`, `INV_ESCRITURA_PMS_EXPLICITA`, `INV_PROPIEDAD_RESUELTA` (uso), `INV_TICKET_UNICO` (incidencias).

## Entregables
1. `PMSConnector` con tipos del dominio; `FakePMS` completo; implementación del proveedor elegido en `*_internal.py`; escrituras deshabilitadas por defecto.
2. Servidor MCP `server.py` con esquemas JSON por herramienta y autorización vía `seguridad_service` antes de ejecutar.
3. Registro de incidencias: en el PMS si lo cubre; si no, sala `operaciones` con compuerta y numeración `I-AAAA-NNNN`.
4. Fixtures grabados del proveedor para pruebas sin red.

## Criterios de fase completada
- `tests/pms_conector/test_contrato.py` en verde contra `FakePMS` y real.
- Reserva preliminar creada y leída en el entorno de pruebas del PMS.
- RNF-02 (P95 ≤ 10 s con una herramienta) medido.
