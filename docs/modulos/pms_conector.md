# Módulo `pms_conector` — Conector al PMS / channel manager
`¤pms-conector`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/pms_conector/` |
| Compuerta | `pms_conector_service.py` → `PMSConectorService` |
| Privados | `base_internal.py` (ABC `PMSConnector`), `fake_internal.py`, `kamra_internal.py` · `repull_internal.py` · `hospitable_internal.py` (uno activo), `tipos.py` |
| Config | `config_pms_conector.yaml` |
| Rol | `¤¤integration-engineer` |
| Requisitos | RF-PMS-01..04 · RNF-02 · INV_SIN_CLIENTES_OTA, INV_ESCRITURA_PMS_EXPLICITA |
| Tarea | TASK-003 |
| Decisión | Construir sobre MCP; proveedor `[DECISIÓN PENDIENTE]` ADR-0007 |

## Propósito
Abstraer el PMS detrás de tipos del dominio para que el agente y las herramientas nunca conozcan al proveedor. Lecturas libres; escrituras deshabilitadas por defecto y con clave de idempotencia.

## Tipos del dominio

```python
class TipoPropiedad(str, Enum): GLAMPING, DEPARTAMENTO
@dataclass(frozen=True)
class Propiedad: propiedad_id: str; tipo: TipoPropiedad; nombre: str; zona_id: str; direccion: str; activa: bool; pms_ref: str
@dataclass(frozen=True)
class Unidad: unidad_id: str; propiedad_id: str; nombre: str; capacidad: int
@dataclass(frozen=True)
class Disponibilidad: disponible: bool; unidades: tuple[Unidad, ...]; motivo: str | None
@dataclass(frozen=True)
class Cotizacion: total: Decimal; moneda: str; desglose: tuple[tuple[str, Decimal], ...]; politica_cancelacion_id: str
class EstadoReserva(str, Enum): PRELIMINAR, CONFIRMADA, CANCELADA, COMPLETADA
@dataclass(frozen=True)
class Reserva: codigo: str; propiedad_id: str; unidad_id: str; huesped_token: str; desde: date; hasta: date; huespedes: int; estado: EstadoReserva; total: Decimal; expira_en: datetime | None; pms_ref: str
@dataclass(frozen=True)
class InstruccionesCheckin: propiedad: str; direccion: str; hora_checkin: str; acceso: tuple[str, ...]; wifi_red: str; wifi_clave_token: str; normas: tuple[str, ...]; contacto_emergencia: str
@dataclass(frozen=True)
class Incidencia: incidencia_id: str; propiedad_id: str; unidad_id: str | None; reserva_codigo: str | None; categoria: str; prioridad: str; descripcion_token: str; estado: str; gestor_id: str | None
```

## Compuerta (misma firma que la ABC interna)

```python
class PMSConectorService:
    def listar_propiedades(self) -> tuple[Propiedad, ...]: ...
    def consultar_disponibilidad(self, propiedad_id: str, desde: date, hasta: date, huespedes: int) -> Disponibilidad: ...
    def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int) -> Cotizacion: ...
    def crear_reserva_preliminar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int, huesped_token: str, clave_idempotencia: str) -> Reserva: ...  # escritura
    def obtener_reserva(self, codigo: str) -> Reserva: ...
    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]: ...
    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva: ...  # escritura
    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin: ...
    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia: ...  # escritura; o sala operaciones (ADR-0007)
    def registrar_tarea_housekeeping(self, propiedad_id: str, unidad_id: str, fecha: date, nota: str, clave_idempotencia: str) -> str: ...
```

## Configuración (`config_pms_conector.yaml`)
`proveedor: fake|kamra|repull|hospitable`, `credenciales {url: ${PMS_URL}, token: ${PMS_TOKEN}}`, `timeout_s: 8`, `reintentos_lectura: 2`, `escrituras_habilitadas {crear_reserva_preliminar: false, cancelar_reserva: false, registrar_incidencia: false, housekeeping: false}`, `cache_propiedades_s: 300`.

## Compuertas que consume
`observabilidad`. Ninguna otra.

## Errores
`PMSNoDisponible`, `PropiedadInexistente`, `FechasInvalidas`, `SinDisponibilidad`, `EscrituraDeshabilitada`, `ReservaInexistente`, `IdempotenciaRequerida`.

## Persistencia (`esquema pms`)
Solo caché y referencias: `propiedades_cache(propiedad_id, datos_json, actualizado_en)`, `idempotencia(clave PK, operacion, resultado_json, creado_en)`. La fuente de verdad es el PMS.

## Tests (árbitro)
`tests/pms_conector/test_contrato.py` (parametrizado: `FakePMS` y real con *fixtures*), `test_seleccion_proveedor.py`, `test_errores.py`; `tests/test_sin_clientes_ota.py`.

`¤pms-conector/`
