# Módulo `anfitriones` — Gestión de anfitriones, publicación y solicitudes
`¤anfitriones`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/anfitriones/` |
| Compuerta | `anfitriones_service.py` → `AnfitrionesService` |
| Privados | `registro_internal.py`, `solicitudes_internal.py`, `estado_cuenta_internal.py`, `persistencia_internal.py`, `tipos.py` |
| Config | `config_anfitriones.yaml` |
| Rol | `¤¤backend-developer` |
| Requisitos | [`PRD.md` §5.13](../PRD.md) (RF-ANF-01..08) · US-19 |
| Invariantes | `INV_AISLAMIENTO_ANFITRION`, `INV_COMISION_PLATAFORMA_UNICA`, `INV_CONTACTO_TRAS_CONFIRMAR`, `INV_SOLO_PUBLICADO` |
| Tareas | T-305 (Ola 4, Fase 4: alta, publicación, solicitud y resultado de la estadía), T-506 (liquidación y estados de cuenta) |
| Decisión | [ADR-0018](../adr/ADR-0018-plataforma-local-de-hospedajes.md) |

## Propósito
Dueña del registro y ciclo de vida de los anfitriones, la publicación revisada de hospedajes, la solicitud y confirmación de reservas preliminares, y la liquidación de la comisión que la plataforma percibe por estadía. Opera bajo estricto aislamiento entre anfitriones (`INV_AISLAMIENTO_ANFITRION`), protegiendo los datos de contacto hasta que la reserva queda confirmada (`INV_CONTACTO_TRAS_CONFIRMAR`). No mueve dinero directamente: genera estados de cuenta y asienta registros de cobro.

## Tipos del dominio (`tipos.py`)

```python
class EstadoAnfitrion(str, Enum):
    ACTIVO = "activo"
    SUSPENDIDO = "suspendido"

class EstadoHospedaje(str, Enum):
    BORRADOR = "borrador"
    PUBLICADO = "publicado"
    PAUSADO = "pausado"

class EstadoSolicitud(str, Enum):
    SOLICITADA = "solicitada"
    CONFIRMADA = "confirmada"
    RECHAZADA = "rechazada"
    EXPIRADA = "expirada"
    CANCELADA = "cancelada"
    NO_SHOW = "no_show"
    COMPLETADA = "completada"

class EstadoCuenta(str, Enum):
    EMITIDO = "emitido"
    PAGADO = "pagado"
    VENCIDO = "vencido"

@dataclass(frozen=True)
class Anfitrion:
    anfitrion_id: str
    nombre_comercial: str
    comision_porcentaje: Decimal
    terminos_version: str
    estado: EstadoAnfitrion = EstadoAnfitrion.ACTIVO
    telefono_token: str | None = None
    terminos_aceptados_en: datetime | None = None
    creado_en: datetime | None = None

@dataclass(frozen=True)
class Hospedaje:
    propiedad_id: str
    anfitrion_id: str
    estado: EstadoHospedaje
    publicado_por: str | None = None
    publicado_en: datetime | None = None

@dataclass(frozen=True)
class Solicitud:
    solicitud: str
    codigo_reserva: str
    propiedad_id: str
    anfitrion_id: str
    desde: date
    hasta: date
    total: Decimal
    comision_porcentaje: Decimal
    estado: EstadoSolicitud
    vence_en: datetime
    respondida_en: datetime | None = None
    creado_en: datetime | None = None

@dataclass(frozen=True)
class LineaCuenta:
    solicitud: str
    base: Decimal
    porcentaje: Decimal
    comision: Decimal
    tipo: str = "cargo"

@dataclass(frozen=True)
class EstadoDeCuenta:
    estado_cuenta_id: str
    anfitrion_id: str
    periodo: str
    total: Decimal
    estado: EstadoCuenta
    vence_en: date
    lineas: tuple[LineaCuenta, ...] = field(default_factory=tuple)
    emitido_en: datetime | None = None
    pagado_en: datetime | None = None
    pago_registrado_por: str | None = None
```

## Compuerta (`AnfitrionesService`)

```python
class AnfitrionesService:
    def registrar_anfitrion(self, anfitrion: Anfitrion, telefono_token: str, actor_id: str) -> Anfitrion: ...  # RF-ANF-01
    def guardar_hospedaje(self, hospedaje: Hospedaje, actor_id: str) -> Hospedaje: ...                        # RF-ANF-02
    def publicados(self) -> tuple[Hospedaje, ...]: ...                                                        # RF-ANF-02, INV_SOLO_PUBLICADO
    def solicitar_reserva(self, codigo_reserva: str) -> Solicitud: ...                                         # RF-ANF-04 (fechas y total del PMS)
    def responder_solicitud(self, solicitud: str, anfitrion_id: str, acepta: bool, motivo: str | None = None) -> Solicitud: ... # RF-ANF-05
    def reportar_resultado(self, solicitud: str, anfitrion_id: str, resultado: EstadoSolicitud | str, ahora_fecha: date | None = None) -> Solicitud: ... # RF-ANF-06
    def expirar_solicitudes_vencidas(self, ahora: datetime | None = None) -> tuple[Solicitud, ...]: ...       # RF-ANF-05
    def procesar_estadias_completadas(self, ahora_fecha: date | None = None) -> tuple[Solicitud, ...]: ...    # RF-ANF-06
    def cerrar_periodo(self, periodo: str, ahora: datetime | None = None) -> tuple[EstadoDeCuenta, ...]: ...   # RF-ANF-07
    def estado_de_cuenta(self, anfitrion_id: str, periodo: str, actor_id: str | None = None) -> EstadoDeCuenta: ... # RF-ANF-07, INV_AISLAMIENTO_ANFITRION
    def registrar_pago(self, estado_cuenta_id: str, actor_id: str, ahora: datetime | None = None) -> EstadoDeCuenta: ... # RF-ANF-08
    def agregar_ajuste(self, anfitrion_id: str, periodo: str, solicitud: str, comision: Decimal, base: Decimal = Decimal("0.00"), porcentaje: Decimal = Decimal("0.00"), actor_id: str = "admin") -> LineaCuenta: ... # RF-ANF-07
    def procesar_cuentas_vencidas(self, ahora_fecha: date | None = None) -> tuple[str, ...]: ...               # RF-ANF-08
    def consultar_estado_cuenta(self, anfitrion_id: str, periodo: str, actor_id: str | None = None) -> dict[str, Any]: ... # RF-ANF-07
```

## Reglas de Negocio e Invariantes

| Código | Predicado | Mecanismo obligatorio |
| :--- | :--- | :--- |
| `INV_AISLAMIENTO_ANFITRION` | `actor = anfitrion ⇒ anfitrion_id(fila) = identidad(actor)` | Validación estricta en cada operación de solicitud y reporte; auditoría de seguridad ante denegación. |
| `INV_COMISION_PLATAFORMA_UNICA` | `∀ s : ∣cargos(s)∣ ≤ 1` | Clave única `(solicitud, tipo)` en `anfitriones.lineas_cuenta`. |
| `INV_CONTACTO_TRAS_CONFIRMAR` | `contacto_entregado(s) ⇒ estado(s) = confirmada` | El contacto del huésped y anfitrión se entrega exclusivamente dentro de la transición a `confirmada` en `responder_solicitud`. |
| `INV_SOLO_PUBLICADO` | `visible(h) ⇒ estado(h) = publicado ∧ estado(anfitrion(h)) = activo` | La compuerta `publicados()` realiza filtro conjunto sobre hospedajes en `publicado` y anfitriones en `activo`. |

- **Alta (RF-ANF-01):** Sin versión de términos aceptada no hay alta. El teléfono se guarda como token anónimo y cada alta se audita.
- **Publicación revisada (RF-ANF-02):** Un hospedaje pasa por `borrador`, `publicado` y `pausado`. Publicar requiere `actor_id` y fecha. El anfitrión no puede publicarse a sí mismo.
- **Congelación de comisión (RF-ANF-04):** Al crearse la solicitud con código `PL-YYYY-NNNN`, el porcentaje pactado del anfitrión se copia y congela en la solicitud. Fechas y totales provienen inmutables del PMS.
- **Vigencia de 24 horas (RF-ANF-04 / RF-ANF-05):** Si el anfitrión no responde en 24 horas, la solicitud pasa a `expirada`.
- **Reporte de estadía (RF-ANF-06):** El anfitrión dispone de hasta 3 días posteriores a la fecha de salida (`hasta + 3 días`) para reportar `cancelada` o `no_show`. Ninguno de estos estados devenga comisión. Si no se reporta en dicho plazo, pasa a `completada`.
- **Estado de cuenta mensual (RF-ANF-07):** El día 5 de cada mes (`cierre_dia_del_mes: 5`), el proceso mensual agrupa todas las estadías completadas del mes de salida previo por anfitrión. Calcula la comisión pactada para cada una (`base * porcentaje / 100`). Cada estadía se cobra una sola vez (`INV_COMISION_PLATAFORMA_UNICA`). El total del estado de cuenta coincide exactamente con la suma de sus líneas. Se envía notificación por plantilla WhatsApp y el anfitrión puede consultar su estado de cuenta. Cualquier corrección posterior se asienta como línea de tipo `ajuste` en el período abierto.
- **Cobro y pausa por morosidad (RF-ANF-08):** El anfitrión abona off-platform en un plazo de 14 días (`pago_plazo_dias: 14`). El administrador registra el pago con actor y marca de tiempo. Si transcurren 15 días posteriores al vencimiento (`pausa_tras_vencimiento_dias: 15`) sin registrar el pago, el proceso diario marca la cuenta como vencida y transiciona los hospedajes del anfitrión a `pausado` (dejando de ser visibles en el catálogo). La plataforma nunca retiene fondos del huésped.

## Herramientas MCP que atiende esta sala
- `solicitar_reserva`: Inicia solicitud `PL-` a partir de reserva preliminar del PMS.
- `responder_solicitud`: Confirma o rechaza solicitud pendiente desde el anfitrión.
- `reportar_resultado_estadia`: Reporta `cancelada`, `no_show` o `completada`.
- `consultar_estado_cuenta_anfitrion`: Consulta estados de cuenta y comisiones por período.

## Configuración (`config_anfitriones.yaml`)
- `solicitud_vigencia_h`: Vigencia en horas de la solicitud de reserva (24).
- `reporte_estadia_dias`: Días máximos posteriores a la salida para reportar novedad (3).
- `cierre_dia_del_mes`: Día mensual para emisión de estados de cuenta (5).
- `pago_plazo_dias`: Días de plazo para abono de comisiones (14).
- `pausa_tras_vencimiento_dias`: Días de gracia antes de pausar listados por mora (15).

## Compuertas que consume
- `seguridad_service`: Tokenización de PII (`tokenizar`), auditoría inmutable de accesos y violaciones de aislamiento (`auditar`).
- `canal_whatsapp_service`: Envío de plantillas oficiales de solicitud (`solicitud_reserva_anfitrion`) y confirmación (`reserva_confirmada`).
- `pms_conector_service`: Lectura de reservas confirmadas/preliminares para extracción de fechas y total (`obtener_reserva`).
- `observabilidad_service`: Trazas y eventos estructurados del módulo (`log`).

## Persistencia (`esquema anfitriones`)

```sql
CREATE TABLE anfitriones.anfitriones (
  anfitrion_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre_comercial    text NOT NULL,
  telefono_token      text NOT NULL UNIQUE,
  comision_porcentaje numeric(5,2) NOT NULL CHECK (comision_porcentaje BETWEEN 0 AND 100),
  terminos_version    text NOT NULL,
  terminos_aceptados_en timestamptz NOT NULL,
  estado              text NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','suspendido')),
  creado_en           timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE anfitriones.hospedajes (
  propiedad_id     text PRIMARY KEY,
  anfitrion_id     uuid NOT NULL REFERENCES anfitriones.anfitriones (anfitrion_id),
  estado           text NOT NULL DEFAULT 'borrador' CHECK (estado IN ('borrador','publicado','pausado')),
  publicado_por    text,
  publicado_en     timestamptz,
  CHECK (estado <> 'publicado' OR (publicado_por IS NOT NULL AND publicado_en IS NOT NULL))
);

CREATE TABLE anfitriones.solicitudes (
  solicitud        text PRIMARY KEY CHECK (solicitud ~ '^PL-[0-9]{4}-[0-9]{4,}$'),
  codigo_reserva   text NOT NULL UNIQUE,
  propiedad_id     text NOT NULL REFERENCES anfitriones.hospedajes (propiedad_id),
  anfitrion_id     uuid NOT NULL REFERENCES anfitriones.anfitriones (anfitrion_id),
  desde            date NOT NULL,
  hasta            date NOT NULL,
  total            numeric(12,2) NOT NULL CHECK (total >= 0),
  comision_porcentaje numeric(5,2) NOT NULL CHECK (comision_porcentaje BETWEEN 0 AND 100),
  estado           text NOT NULL DEFAULT 'solicitada' CHECK (estado IN ('solicitada','confirmada','rechazada','expirada','cancelada','no_show','completada')),
  vence_en         timestamptz NOT NULL,
  respondida_en    timestamptz,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  CHECK (hasta > desde)
);

CREATE TABLE anfitriones.estados_cuenta (
  estado_cuenta_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  anfitrion_id     uuid NOT NULL REFERENCES anfitriones.anfitriones (anfitrion_id),
  periodo          text NOT NULL CHECK (periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  total            numeric(12,2) NOT NULL,
  estado           text NOT NULL DEFAULT 'emitido' CHECK (estado IN ('emitido','pagado','vencido')),
  emitido_en       timestamptz NOT NULL DEFAULT now(),
  vence_en         date NOT NULL,
  pagado_en        timestamptz,
  pago_registrado_por text,
  UNIQUE (anfitrion_id, periodo),
  CHECK (estado <> 'pagado' OR (pagado_en IS NOT NULL AND pago_registrado_por IS NOT NULL))
);

CREATE TABLE anfitriones.lineas_cuenta (
  linea_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  estado_cuenta_id uuid NOT NULL REFERENCES anfitriones.estados_cuenta (estado_cuenta_id),
  solicitud        text NOT NULL,
  tipo             text NOT NULL DEFAULT 'cargo' CHECK (tipo IN ('cargo','ajuste')),
  base             numeric(12,2) NOT NULL,
  porcentaje       numeric(5,2) NOT NULL,
  comision         numeric(12,2) NOT NULL,
  UNIQUE (solicitud, tipo)
);
```

## Árbitro y Pruebas
- `tests/anfitriones/test_publicacion.py`: Alta con términos y porcentaje, tokenización de teléfono, auditoría y publicación revisada (RF-ANF-01, RF-ANF-02, INV_SOLO_PUBLICADO).
- `tests/anfitriones/test_solicitudes.py`: Creación de solicitud con datos del PMS, porcentaje congelado, vigencia de 24 horas, confirmación, entrega de contactos y expiración (RF-ANF-04, RF-ANF-05, INV_CONTACTO_TRAS_CONFIRMAR, US-19).
- `tests/anfitriones/test_resultado.py`: Reporte de `no_show` y `cancelada` sin comisión dentro de 3 días, rechazo tras vencimiento, y cierre automático a `completada` (RF-ANF-06).
- `tests/anfitriones/test_aislamiento.py`: Verificación de aislamiento estricto impidiendo respuestas, reportes o visualización entre anfitriones y auditoría de seguridad (INV_AISLAMIENTO_ANFITRION).
- `tests/anfitriones/test_estado_cuenta.py`: Cierre mensual con comisión única, cálculo de total exacto con líneas, notificación por WhatsApp, ajustes posteriores, registro de pago por administrador, pausa por morosidad tras 15 días de vencimiento y aislamiento entre anfitriones (RF-ANF-07, RF-ANF-08, INV_COMISION_PLATAFORMA_UNICA, INV_AISLAMIENTO_ANFITRION, US-20).

`¤anfitriones/`
