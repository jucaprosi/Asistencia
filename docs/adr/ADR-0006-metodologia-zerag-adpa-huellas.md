# ADR-0006 — Metodología ZERAG: salas ADPA, compuertas, rastros y arnés
`¤adr-zerag`

| Campo | Valor |
| :--- | :--- |
| Estado | Aceptado |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto (instrucción del 2026-10-30: «tomar la metodología ZERAG: ADPA, huellas, etc.») |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) Anexo B; doctrina ZERAG (`ADPA.md`, `HUELLAS.md`, `GLOSARIO.md`) |
| Bloquea | — |

## Contexto
El informe propone un monorepo con `apps/`, `packages/` y `mcp-servers/`, cada carpeta con su `pyproject.toml`, para testear piezas por separado y cambiar proveedores sin tocar el agente. El propietario exige además que el proyecto se construya bajo ZERAG: salas estancas, compuertas únicas, rastros estigmérgicos y árbitro exógeno.

## Opciones consideradas
1. Monorepo del informe tal cual (paquetes independientes, imports libres entre ellos).
2. **Disposición ADPA: una sala por componente bajo `features/`, compuerta `<sala>_service.py`, `config_<sala>.yaml`, pasillo central `app_core/`; rastros `¤` en PRD, invariantes, tareas, ADR y código.**

## Decisión
Opción 2. La intención del informe (aislamiento, sustituibilidad, pruebas por pieza) se cumple con más fuerza: el `adpa_linter` prohíbe imports laterales, y la compuerta es el único contrato público. La estructura de §11 del informe se conserva como catálogo de componentes; la equivalencia componente → sala está en [`ARQUITECTURA.md` §3](../ARQUITECTURA.md#3-salas-adpa-equivalencia-con-la-estructura-del-informe).

Reglas adoptadas:
- Dependencias entre salas solo por compuertas; `app_core` orquesta compuertas y no importa nada privado.
- Protocolo Boceto → arnés → Sellado por tarea; «fase completada» = `ejecutar_arnes_glamping.(bat|sh)` en Exit Code 0 con certificado en `governance/artefactos/data/`.
- Rastros `¤` definitivos; huellas `¦` solo durante la edición; cero `¦` en código sellado.
- Nido de artefactos vivos en `governance/artefactos/` antes de escribir código; el tablero `TASKS.md` y el `VPA_MAP.md` los sirve el servidor MCP ZERAG; las tareas se especifican en `governance/tareas/`.
- Interfaz purificada: ningún rastro en textos de cara a huésped, vendedor o equipo.
- Roles `¤¤` por sala con títulos de industria (ESCO/O*NET): `integration-engineer`, `security-engineer`, `machine-learning-engineer`, `data-engineer`, `backend-developer`, `devops-engineer`, `solutions-architect`, `qa-engineer`.

## Consecuencias
- Nombres de sala en `snake_case` (`canal_whatsapp`, `pms_conector`…) en lugar de los `kebab-case` del informe: exigencia de paquete Python, no cambio de alcance.
- Cada ADR, tarea e invariante lleva el rastro de su sala, de modo que `git grep --untracked "¤arm-jarvis"` devuelve toda la historia de la capacidad.
- Los triajes del servidor ZERAG y sus linters (ADPA, huellas, UTF-8, IP) actúan como hooks en cada escritura.

## Criterios de verificación (árbitro)
- `adpa_linter` y `huellas_linter` sin errores en las salas tocadas.
- `tests/test_estructura_adpa.py`: cada `features/<sala>/` tiene `<sala>_service.py` (o `server.py`) y `config_<sala>.yaml`; `app_core/` solo importa compuertas.
- `tests/test_interfaz_purificada.py`: 0 rastros en plantillas, mensajes y exportaciones.

`¤adr-zerag/`
