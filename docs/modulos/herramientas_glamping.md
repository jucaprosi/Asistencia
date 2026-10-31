# Módulo `herramientas_glamping` — Servidor MCP de herramientas
`¤herramientas-mcp`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/herramientas_glamping/` |
| Compuerta | `herramientas_glamping_service.py` → `HerramientasGlampingService` |
| Ejecutable | `server.py` (proceso MCP; importa solo su propia compuerta) |
| Privados | `herramientas_internal.py`, `esquemas/*.json`, `tipos.py` |
| Config | `config_herramientas_glamping.yaml` |
| Rol | `¤¤backend-developer` |
| Requisitos | RF-MCP-01..09 · INV_ALLOWLIST_POR_ACCION |
| Tareas | TASK-003 (01..07), TASK-006 (08, 09) |

## Propósito
Exponer a Claude herramientas tipadas con esquema JSON. Cada herramienta valida la entrada, pide autorización a `seguridad`, llama a la compuerta de la sala dueña del dato y devuelve una salida tipada. No contiene lógica de negocio propia.

## Tipos del dominio

```python
@dataclass(frozen=True)
class DefinicionHerramienta: nombre: str; descripcion: str; esquema_entrada: Mapping[str, Any]; esquema_salida: Mapping[str, Any]; roles: tuple[str, ...]; sala_destino: str
@dataclass(frozen=True)
class ResultadoHerramienta: nombre: str; salida: Mapping[str, Any]; error: str | None; duracion_ms: int
```

## Compuerta

```python
class HerramientasGlampingService:
    def listar(self, rol: str, propiedad_id: str | None) -> tuple[DefinicionHerramienta, ...]: ...   # lo que agente expone al modelo
    def ejecutar(self, nombre: str, entrada: Mapping[str, Any], identidad: Identidad, conversacion_id: str) -> ResultadoHerramienta: ...
    def esquema(self, nombre: str) -> DefinicionHerramienta: ...
```

## Catálogo (entrada/salida completas en [`../PRD.md` §5.10](../PRD.md#510-mcp-serversglamping-tools--sala-herramientas_glamping))

| Herramienta | Sala destino | Roles |
| :--- | :--- | :--- |
| `consultar_disponibilidad`, `cotizar`, `crear_reserva_preliminar`, `obtener_instrucciones_checkin` | `pms_conector` (+ `conocimiento` para política y normas) | huésped |
| `reportar_incidencia` | `pms_conector` u `operaciones`; notifica por `crm_conector` | huésped activo |
| `solicitar_humano` | `crm_conector` (inbox) o `panel_operativo` (bandeja) según ADR-0010 | huésped, vendedor |
| `buscar_contacto_crm`, `crear_oportunidad_crm` | `crm_conector` | agente (interno) |
| `registrar_venta`, `consultar_comision_propia` | `arm_jarvis` (+ `comisiones`) | vendedor |

## Configuración (`config_herramientas_glamping.yaml`)
`transporte: stdio|http`, `puerto: 8090` (solo `agent-net`), `herramientas: [{nombre, esquema: esquemas/<nombre>.json, roles, sala_destino, habilitada}]`, `timeout_por_herramienta_s: 8`.

## Compuertas que consume
`seguridad` (`autorizar`), `pms_conector`, `conocimiento`, `crm_conector`, `arm_jarvis`, `comisiones`, `observabilidad`.

## Errores
`EntradaInvalida` (no valida contra el esquema; mensaje legible con el campo), `HerramientaNoAutorizada`, `HerramientaDeshabilitada`, `SalaDestinoFallida` (envuelve el error tipado de la sala).

## Persistencia
Ninguna propia; las ejecuciones quedan en el audit log de `seguridad` y en las trazas.

## Tests (árbitro)
`tests/herramientas_glamping/test_contratos.py` (cada herramienta: esquema, autorización, `Fake*`), `test_server.py` (arranque stdio y listado).

`¤herramientas-mcp/`
