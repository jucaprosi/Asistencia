# Módulo `pms_conector` — Calendario, tarifas y reservas
`¤pms-conector`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/pms_conector/` |
| Compuerta | `pms_conector_service.py` → `PMSConectorService` |
| Privados | `base_internal.py` (ABC `PMSConnector`), `fake_internal.py`, `plataforma_internal.py`, `persistencia_internal.py`, `tipos.py` |
| Config | `config_pms_conector.yaml` |
| Rol | `¤¤integration-engineer` |
| Requisitos | RF-PMS-01..08 · RNF-02 · INV_SIN_CLIENTES_OTA, INV_ESCRITURA_PMS_EXPLICITA, INV_SIN_DOBLE_RESERVA, INV_AISLAMIENTO_ANFITRION, INV_TICKET_UNICO |
| Tareas | T-202 (interfaz abstracta, `FakePMS`, escrituras deshabilitadas), T-212 (calendario y tarifas propios, `PlataformaPMS`) |
| Decisión | Calendario propio y FakePMS, ADR-0007 |

## Propósito
Abstraer el acceso a disponibilidad, tarifas, reservas e instrucciones de check-in detrás de tipos puros de dominio. Garantiza independencia total de proveedores externos y OTA directas (`INV_SIN_CLIENTES_OTA`). Mantiene lecturas libres con política de reintentos y escrituras deshabilitadas por defecto sujetas a verificación estricta de idempotencia (`INV_ESCRITURA_PMS_EXPLICITA`). En `T-212` implementa `PlataformaPMS` respaldado por el esquema `pms` (`pms.noches_ocupadas`, `pms.tarifas_noche`), aislamiento de anfitriones (`INV_AISLAMIENTO_ANFITRION`) y prevención de sobreventa (`INV_SIN_DOBLE_RESERVA`).

## Tipos del dominio

```python
class TipoPropiedad(str, Enum):
    GLAMPING = "glamping"
    CABANA = "cabana"
    CASA = "casa"
    DEPARTAMENTO = "departamento"
    HABITACION = "habitacion"
    HOSTAL = "hostal"
    HOSTERIA = "hosteria"
    HOTEL = "hotel"
    HACIENDA = "hacienda"
    OTRO = "otro"

class EstadoReserva(str, Enum):
    PRELIMINAR = "preliminar"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    EXPIRADA = "expirada"
    COMPLETADA = "completada"

@dataclass(frozen=True)
class Propiedad:
    propiedad_id: str
    tipo: TipoPropiedad
    nombre: str
    zona_id: str
    direccion: str
    activa: bool
    pms_ref: str
    prompt_variante: str = "glamping"

@dataclass(frozen=True)
class Unidad:
    unidad_id: str
    propiedad_id: str
    nombre: str
    capacidad: int
    edificio: str | None = None
    piso: str | None = None
    acceso_ref: str | None = None
    wifi_ref: str | None = None

@dataclass(frozen=True)
class Disponibilidad:
    disponible: bool
    unidades: tuple[Unidad, ...]
    motivo: str | None = None
    alternativas: tuple[tuple[str, date, date], ...] = ()

@dataclass(frozen=True)
class Cotizacion:
    total: Decimal
    moneda: str
    desglose: tuple[tuple[str, Decimal], ...]
    politica_cancelacion_id: str

@dataclass(frozen=True)
class Reserva:
    codigo: str
    propiedad_id: str
    unidad_id: str
    huesped_token: str
    desde: date
    hasta: date
    huespedes: int
    estado: EstadoReserva
    total: Decimal
    expira_en: datetime | None
    pms_ref: str

@dataclass(frozen=True)
class InstruccionesCheckin:
    propiedad: str
    direccion: str
    hora_checkin: str
    acceso: tuple[str, ...]
    wifi_red: str
    wifi_clave_token: str
    normas: tuple[str, ...]
    contacto_emergencia: str

@dataclass(frozen=True)
class Incidencia:
    incidencia_id: str
    propiedad_id: str
    unidad_id: str | None
    reserva_codigo: str | None
    categoria: str
    prioridad: str
    descripcion_token: str
    estado: str
    gestor_id: str | None

class AislamientoAnfitrionError(ErrorPMS): ...
```

## Compuerta (`PMSConectorService`)

```python
class PMSConectorService:
    def __init__(self, config: Mapping[str, Any] | None = None, *, observabilidad: Any = None, conector: PMSConnector | None = None, conexion: sqlite3.Connection | None = None) -> None: ...
    def proveedor(self) -> str: ...
    def listar_propiedades(self) -> tuple[Propiedad, ...]: ...
    def consultar_disponibilidad(self, propiedad_id: str, desde: date, hasta: date, huespedes: int) -> Disponibilidad: ...
    def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int) -> Cotizacion: ...
    def crear_reserva_preliminar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int, huesped_token: str, clave_idempotencia: str) -> Reserva: ...
    def confirmar_reserva(self, codigo: str, clave_idempotencia: str) -> Reserva: ...
    def obtener_reserva(self, codigo: str) -> Reserva: ...
    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]: ...
    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva: ...
    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin: ...
    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia: ...
    def registrar_tarea_housekeeping(self, propiedad_id: str, unidad_id: str, fecha: date, nota: str, clave_idempotencia: str) -> str: ...
    def guardar_tarifas(self, unidad_id: str, desde: date, hasta: date, precio: Decimal, minimo_noches: int, actor_id: str) -> int: ...
    def actualizar_calendario(self, unidad_id: str, desde: date, hasta: date, accion: str, actor_id: str) -> tuple[int, int]: ...
    def validar_titular_local(self, codigo_reserva: str, huesped_token: str) -> bool: ...
```

## Invariantes Garantizados
1. **`INV_ESCRITURA_PMS_EXPLICITA`**: Las escrituras están deshabilitadas por defecto y requieren activación en `config_pms_conector.yaml`. Toda escritura exige `clave_idempotencia`.
2. **`INV_SIN_CLIENTES_OTA`**: No existen dependencias ni imports de clientes directos de OTA en el repositorio.
3. **`INV_SIN_DOBLE_RESERVA`**: Clave primaria `(unidad_id, noche)` en `pms.noches_ocupadas` y transacción atómica con lock que impide sobreventas simultáneas.
4. **`INV_AISLAMIENTO_ANFITRION`**: El anfitrión solo puede bloquear o liberar unidades propias; intentar modificar unidades de otro anfitrión lanza `AislamientoAnfitrionError`.
5. **`INV_TICKET_UNICO`**: Identificadores correlativos e irrepetibles para incidencias (`I-YYYY-NNNN`) generados mediante secuencia atómica.

## Persistencia (`esquema pms`)
- `pms.propiedades`: Catálogo físico de propiedades locales y sus metadatos.
- `pms.unidades`: Alojamientos y capacidades por propiedad.
- `pms.reservas_ref`: Tabla local para validación rápida del titular sin invocar al PMS remoto.
- `pms.tarifas_noche`: Precios por noche y estancia mínima (`RF-PMS-07`).
- `pms.noches_ocupadas`: Bloqueos de calendario por reservas confirmadas/preliminares o mantenimiento (`RF-PMS-07`, `RF-PMS-08`).
- `pms.incidencias`: Registro de incidencias operativas.
- `pms.idempotencia`: Claves UUID y respuestas cacheadas para asegurar idempotencia.
- `pms.secuencia_incidencias`: Control correlativo de tickets sin huecos ni repeticiones.

## Tests y Árbitro
- `tests/pms_conector/test_contrato.py`: Contrato parametrizado para `FakePMS` y `PlataformaPMS`.
- `tests/pms_conector/test_seleccion_proveedor.py`: Selección de `fake` o `plataforma` y control de escrituras.
- `tests/pms_conector/test_calendario.py`: Concurrencia (dos huéspedes misma noche), noches sin tarifa, mínimo de noches, aislamiento del anfitrión y liberación sin tocar reservas.
- `tests/pms_conector/test_errores.py`: Manejo riguroso de excepciones tipadas.
- `tests/pms_conector/test_ciclo_reserva.py`: Expiración de reservas preliminares en 24h.
- `tests/pms_conector/test_reservas_ref.py`: Validación local del titular.
- `tests/test_sin_clientes_ota.py`: Cero clientes OTA.

`¤pms-conector/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
