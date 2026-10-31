# ADR-0001 — Construir el núcleo diferencial, adoptar la capa commodity detrás de interfaces abstractas
`¤adr-construir-adoptar`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto (según informe maestro) |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §3, §8 |
| Bloquea | — |

## Contexto
Glamping Imbabura necesita un asistente de WhatsApp, un ARM de ventas y una UI de CRM para un equipo sin perfil de desarrollo. Construirlo todo retrasa el valor; adoptarlo todo entrega el activo diferencial (conocimiento, reglas de negocio, canal) a un proveedor.

## Opciones consideradas
1. Plataforma cerrada integral (CRM con chatbot incorporado).
2. Todo construido en casa, incluida la UI de CRM e inbox.
3. **Núcleo propio + capa commodity adoptada tras interfaces abstractas.**

## Decisión
Opción 3. Se construyen: motor conversacional (Claude + MCP), RAG, conectores PMS y CRM como interfaces propias, enrutamiento multi-propiedad, ARM, comisiones, seguridad y observabilidad. Se adoptan: UI de CRM, inbox con handoff y constructor de workflows. Cada pieza adoptada entra solo por una compuerta (`pms_conector_service.py`, `crm_conector_service.py`) con tipos del dominio.

## Consecuencias
- El sistema funciona sin la capa commodity: si cambia el proveedor, solo cambia una implementación `*_internal.py`.
- Doble trabajo asumido: interfaz propia + implementación por proveedor. Se paga con `Fake*` que además sirven para pruebas.
- Ninguna lógica de negocio (comisiones, estados de venta, políticas) vive en workflows del CRM.

## Criterios de verificación (árbitro)
- `adpa_linter`: SDK de terceros importados solo dentro de su sala conectora.
- `tests/pms_conector/test_contrato.py` y `tests/crm_conector/test_contrato.py` pasan contra `Fake*` y contra la implementación real.
- `tests/test_sin_clientes_ota.py` en verde.

`¤adr-construir-adoptar/`
