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
| Requisitos | RF-MCP-01..09, RF-ANF-04..06, RF-PMS-08 · INV_ALLOWLIST_POR_ACCION, INV_SIN_FUGA_ENTRE_PROPIEDADES, INV_CONTACTO_TRAS_CONFIRMAR, INV_AISLAMIENTO_ANFITRION, INV_COMISION_PROPIA |
| Tareas | TASK-003 (01..07: T-203), TASK-005 (T-306: solicitud, respuesta, resultado y calendario), TASK-007 (T-504: registrar_venta y consultar_comision_propia) |

## Propósito
Exponer a Claude y al agente conversacional herramientas tipadas con esquemas JSON Draft 2020-12. Cada herramienta valida su entrada, exige autorización estricta a `seguridad` (`INV_ALLOWLIST_POR_ACCION`), delega la operación a la compuerta dueña del dato (`pms_conector`, `conocimiento`, `crm_conector`, `anfitriones`) y formatea la salida asegurando la ausencia de fuga de datos entre propiedades (`INV_SIN_FUGA_ENTRE_PROPIEDADES`) y el aislamiento entre anfitriones (`INV_AISLAMIENTO_ANFITRION`). No persiste estado de negocio directo ni contiene lógica contable.

En las herramientas de anfitrión (`responder_solicitud`, `reportar_resultado_estadia`, `actualizar_calendario`), el `anfitrion_id` se extrae obligatoriamente de la `identidad` del actor (`sujeto_id` o `remitente_token`), nunca de los parámetros del modelo ni del mensaje entrante.

## Tipos del dominio

```python
@dataclass(frozen=True)
class DefinicionHerramienta:
    nombre: str
    descripcion: str
    esquema_entrada: Mapping[str, Any]
    esquema_salida: Mapping[str, Any]
    roles: tuple[str, ...]
    sala_destino: str

@dataclass(frozen=True)
class ResultadoHerramienta:
    nombre: str
    salida: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None
    duracion_ms: int = 0
```

## Compuerta Pública (`HerramientasGlampingService`)

```python
class HerramientasGlampingService:
    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any,
        pms: Any,
        conocimiento: Any,
        crm: Any,
        arm: Any = None,
        comisiones: Any = None,
        anfitriones: Any = None,
        observabilidad: Any = None,
    ) -> None: ...

    def catalogo_declarado(self) -> tuple[str, ...]: ...
    def listar(self, rol: str, propiedad_id: str | None = None) -> tuple[DefinicionHerramienta, ...]: ...
    def ejecutar(
        self,
        nombre: str,
        entrada: Mapping[str, Any],
        identidad: Any,
        conversacion_id: str,
    ) -> ResultadoHerramienta: ...
    def esquema(self, nombre: str) -> DefinicionHerramienta: ...
```

## Herramientas Implementadas (T-203 y T-306)

| Herramienta | Requisito | Sala destino | Roles Permitidos | Contrato de Salida |
| :--- | :--- | :--- | :--- | :--- |
| `consultar_disponibilidad` | RF-MCP-01 | `pms_conector` | `huesped_potencial`, `huesped_activo` | `{disponible: bool, unidades: list, alternativas: list (max 3), motivo?: str}` |
| `cotizar` | RF-MCP-02 | `pms_conector` | `huesped_potencial`, `huesped_activo` | `{total: str (2 dec), moneda: "USD", desglose: list, politica_cancelacion_id: str}` |
| `crear_reserva_preliminar` | RF-MCP-03 | `pms_conector` | `huesped_potencial`, `huesped_activo` | `{codigo_reserva: str, estado: "preliminar", expira_en: iso8601}` |
| `obtener_instrucciones_checkin`| RF-MCP-04 | `pms_conector` (+ `conocimiento`) | `huesped_activo` | `{propiedad: str, direccion: str, hora_checkin: str, acceso: list, wifi: {red, clave_ref}, normas: list, contacto_emergencia: str}` |
| `reportar_incidencia` | RF-MCP-05 | `pms_conector` (+ `crm_conector`) | `huesped_activo` | `{incidencia_id: str (I-YYYY-NNNN), prioridad: enum, gestor_asignado: str, eta_respuesta_horas: float}` |
| `solicitar_humano` | RF-MCP-06 | `crm_conector` | `huesped_potencial`, `huesped_activo`, `vendedor` | `{handoff_id: str, asignado_a: str, canal: "panel", minutos_estimados: int}` |
| `buscar_contacto_crm` | RF-MCP-07 | `crm_conector` | `sistema` | `{encontrado: bool, contacto_id?: str}` |
| `crear_oportunidad_crm` | RF-MCP-07 | `crm_conector` | `sistema` | `{oportunidad_id: str}` |
| `solicitar_reserva` | RF-ANF-04 | `anfitriones` | `huesped_potencial`, `huesped_activo` | `{solicitud: str (PL-YYYY-NNNN), estado: "solicitada", vence_en: iso8601}` |
| `responder_solicitud` | RF-ANF-05 | `anfitriones` | `anfitrion` | `{solicitud: str, estado: "confirmada" \| "rechazada"}` |
| `reportar_resultado_estadia` | RF-ANF-06 | `anfitriones` | `anfitrion` | `{solicitud: str, estado: "cancelada" \| "no_show" \| "completada"}` |
| `actualizar_calendario` | RF-PMS-08 | `pms_conector` | `anfitrion` | `{unidad_id: str, noches: int, omitidas: int}` |
| `registrar_venta` | RF-MCP-08 | `arm_jarvis` | `vendedor` | `{ticket: str (V-AAAA-NNNN), estado: "por_validar", comision_estimada?: str, posible_duplicado: bool}` |
| `consultar_comision_propia` | RF-MCP-09 | `arm_jarvis` | `vendedor` | `{validada: str, pendiente: str, ventas: int, periodo: str (AAAA-MM)}` |

## Anotaciones PII en los esquemas de salida (T-408, decisión A1)

La sala dueña del dato declara en el esquema de `salida` qué campos son PII, con dos palabras clave de anotación (JSON Schema 2020-12). `entrada` nunca las lleva: los argumentos del modelo ya llegan tokenizados.

- **`x-pii`**: su valor es uno de `nombre`, `telefono`, `correo`, `documento`, `tarjeta` o `direccion` (`TIPOS_PII` de la sala `seguridad`). El campo se tokeniza entero, sin detector.
- **`x-pii-exento`**: vale `true` y exige un `pattern` en el mismo nodo. El valor queda intacto solo si cumple `re.fullmatch(pattern)`; el resto pasa por el detector. Un nodo no lleva `x-pii` y `x-pii-exento` a la vez.
- Los campos de texto sin anotación pasan por el detector.

| Herramienta | Ruta de `salida` | Anotación |
| :--- | :--- | :--- |
| `obtener_instrucciones_checkin` | `contacto_emergencia` | `x-pii: telefono` |
| `obtener_instrucciones_checkin` | `direccion` | `x-pii: direccion` |
| `obtener_instrucciones_checkin` | `wifi.clave_ref` | `x-pii-exento` (por origen: marcador `[[SECRETO:...]]` que genera el sistema) |
| `solicitar_humano` | `asignado_a` | `x-pii: nombre` (defensa en profundidad: hoy lleva un id) |
| `reportar_incidencia` | `gestor_asignado` | `x-pii: nombre` (defensa en profundidad: hoy lleva un id) |
| `crear_reserva_preliminar` | `codigo_reserva` | `x-pii-exento`, pattern `^RES-(\d{4}-\d{4,5}|PREL-\d{1,6})$` (por forma) |

`reportar_incidencia.incidencia_id` queda sin anotación: su pattern acepta sufijos de 6 dígitos o más que el detector lee como teléfono. Acotarlo y eximirlo es de T-419. Las rutas se arman como `a.b` y `lista[]`; el consumo de las anotaciones en producción es de T-407.

## Manejo de Errores e Invariantes

- **`INV_ALLOWLIST_POR_ACCION`**: Se verifica siempre llamando a `seguridad.autorizar(rol, nombre)`. Si el veredicto no es permitido, levanta `HerramientaNoAutorizada`.
- **`INV_COMISION_PROPIA`**: En `registrar_venta` y `consultar_comision_propia`, el `vendedor_id` nunca se acepta desde los argumentos del modelo (`additionalProperties: false`). El servidor lo inyecta obligatoriamente desde la `identidad` verificada del remitente (`sujeto_id` o `remitente_token`).
- **`EntradaInvalida`**: Levantada cuando la entrada incumple el esquema JSON Draft 2020-12. El mensaje detalla el campo infractor de manera legible para el usuario o agente.
- **`ReservaNoAutorizada`**: Levantada cuando un remitente intenta consultar instrucciones de check-in (`obtener_instrucciones_checkin`) para un código de reserva que no le pertenece (verificado con `pms.validar_titular_local`). Se audita en `seguridad` y, ante 5 intentos acumulados en 24h, escala automáticamente a handoff humano.
- **`INV_CONTACTO_TRAS_CONFIRMAR`**: En el flujo de solicitud y anfitrión, la información de contacto solo se entrega una vez que el anfitrión confirma la reserva.
- **`INV_AISLAMIENTO_ANFITRION`**: Cada anfitrión solo puede operar sobre sus propias solicitudes y actualizar el calendario de sus propias unidades. Intentos cruzados levantan excepción envuelta en `SalaDestinoFallida`.
- **`HerramientaDeshabilitada`**: Levantada si la herramienta está desactivada en `config_herramientas_glamping.yaml` (`habilitada: false`).
- **`SalaDestinoFallida`**: Envoltorio de excepciones inesperadas provenientes de las salas dueñas del dato.

## Transporte MCP (`server.py`)

Implementa el protocolo JSON-RPC 2.0 estándar de Model Context Protocol:
- `initialize`: handshake con capabilities de herramientas y metadatos de versión.
- `ping`: verificación de disponibilidad.
- `tools/list`: catálogo filtrado por rol y habilitación.
- `tools/call`: ejecución segura encapsulando errores tipados en respuestas MCP (`isError: true/false`).

## Tests (Árbitro)

- `tests/herramientas_glamping/test_contratos.py`: Dobles de compuertas, validación de esquemas, invariantes de seguridad y contratos de las herramientas de huéspedes y vendedores (T-203, T-504).
- `tests/herramientas_glamping/test_server.py`: Transporte stdio y procesamiento JSON-RPC.
- `tests/herramientas_glamping/test_anfitriones.py`: Árbitro de T-306 (solicitud, confirmación/rechazo, reporte de estadía y actualización de calendario con aislamiento de anfitrión).
- `tests/herramientas_glamping/test_x_pii_esquemas.py`: Árbitro de T-408 (anotaciones `x-pii` y `x-pii-exento`, pattern de `codigo_reserva` y su integración con `tokenizar_estructura`).

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
