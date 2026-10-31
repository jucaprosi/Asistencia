# Especificación ejecutable (Spec-Driven Development)
`¤spec-glamping`

Esta carpeta convierte el PRD en contratos que una persona o un agente puede implementar sin consultar a las otras salas. Dos implementaciones independientes de la misma tarea deben producir piezas compatibles.

| Artefacto | Qué fija | Quién lo verifica |
| :--- | :--- | :--- |
| [`contratos/dominio.yaml`](contratos/dominio.yaml) | Roles, allowlist, enums, máquina de estados de la venta, plantillas, tiempos y umbrales de negocio. | `tests/test_especificacion.py`, contra tipos y configuración de las salas. |
| [`contratos/herramientas.yaml`](contratos/herramientas.yaml) | Entrada y salida de cada herramienta MCP y del payload de venta, como JSON Schema. | `tests/test_especificacion.py`. |
| [`esquema.sql`](esquema.sql) | DDL canónico de PostgreSQL por sala, con restricciones y disparadores. | La CI lo aplica en PostgreSQL real y corre [`verificacion_esquema.sql`](verificacion_esquema.sql). |
| [`features/`](features/) | Comportamiento en Gherkin, un archivo por capacidad. Reemplaza los criterios Given/When/Then del PRD. | `tests/test_especificacion.py`; los tests de cada sala implementan sus escenarios. |
| [`TRAZABILIDAD.md`](TRAZABILIDAD.md) | Matriz generada: requisito, tareas y escenarios. | `tests/test_especificacion.py` falla si está desactualizada. |

## Precedencia

1. **Forma de los datos:** mandan `contratos/` y `esquema.sql`.
2. **Comportamiento observable:** mandan `features/`.
3. **Intención, alcance y prioridades:** manda [`../PRD.md`](../PRD.md).
4. **Diseño interno de una sala:** manda [`../modulos/`](../modulos/README.md), sin contradecir lo anterior.

Si dos artefactos difieren, es un defecto de la especificación: se corrige aquí antes de escribir código.

## Reglas de cambio

- El código nunca se adelanta a la especificación. Un comportamiento nuevo entra primero aquí.
- Cambiar un contrato, una tabla o un escenario ya implementado exige subir la versión del PRD y anotar el motivo en [`../PRD.md` §16](../PRD.md#16-control-de-cambios-de-la-especificación).
- Una tarea no interpreta: si la especificación no alcanza, anota `contrato_pendiente` y se resuelve antes de seguir.

Regenerar la matriz:

```bash
python scripts/generar_trazabilidad.py
```

`¤spec-glamping/`
