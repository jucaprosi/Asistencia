# Módulo `crm_conector` — Conector al CRM (sistema de registro adoptado)
`¤crm-conector`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/crm_conector/` |
| Compuerta | `crm_conector_service.py` → `CRMConectorService` |
| Privados | `base_internal.py` (ABC `CRMConnector`), `fake_internal.py`, `firma_internal.py`, `cola_internal.py`, `eventos_internal.py`, `http_internal.py`, `ghl_internal.py`, `chatwoot_internal.py`, `persistencia_internal.py`, `tipos.py` |
| Config | `config_crm_conector.yaml` |
| Rol | `¤¤integration-engineer` |
| Requisitos | RF-CRM-01..06, RF-MCP-06, RF-MCP-07 · INV_HANDOFF_UNICO, INV_VENTA_FIRMADA_IDEMPOTENTE, INV_VENTA_NO_SE_PIERDE |
| Tareas | T-302 (interfaz abstracta, `FakeCRM`, handoffs por zona), T-601 (proveedor real GHL/Chatwoot, webhook firmado HMAC, cola con backoff, eventos entrantes) |
| Decisión | Interfaz propia; CRM adoptado `[DECISIÓN PENDIENTE]` ADR-0008. Con ADR-0013 el CRM queda como sistema de registro de contactos y oportunidades (y opcionalmente inbox); la UI operativa es el panel propio. |

## Propósito
Publicar ventas y contactos al CRM de forma firmada e idempotente, recibir sus eventos, y ser dueña de zonas y handoffs (RF-CRM-06). La bandeja es el panel; el inbox del proveedor es un espejo opcional sujeto a ADR-0010. Aísla al proveedor: `agente`, `arm_jarvis` y `panel_operativo` solo ven esta compuerta.

## Tipos del dominio

```python
@dataclass(frozen=True)
class Contacto:
    contacto_id: str
    nombre_token: str
    telefono_token: str
    email_token: str | None = None
    crm_ref: str | None = None

@dataclass(frozen=True)
class Oportunidad:
    oportunidad_id: str
    contacto_id: str
    propiedad_id: str | None
    etapa: str
    monto: Decimal | None = None
    crm_ref: str | None = None

@dataclass(frozen=True)
class PublicacionVenta:
    venta_id: str
    estado: Literal["pendiente", "ok", "error"]
    intentos: int
    ultima_respuesta: str | None = None
    proximo_intento: datetime | None = None

@dataclass(frozen=True)
class EventoCRM:
    tipo: Literal["venta_validada", "venta_rechazada", "handoff_devuelto", "incidencia_resuelta", "mensaje_gestor"]
    referencia: str
    actor: str
    datos: Mapping[str, Any]
    recibido_en: datetime

@dataclass(frozen=True)
class Zona:
    zona_id: str
    nombre: str
    gestor_principal_id: str
    gestor_respaldo_id: str

@dataclass(frozen=True)
class Handoff:
    handoff_id: str
    conversacion_id: str
    motivo: str
    zona_id: str | None
    estado: Literal["pendiente", "tomado", "devuelto"]
    asignado_a: str | None
    resumen_token: str
    inicio: datetime
    tomado_en: datetime | None = None
    ultima_actividad: datetime | None = None
    devuelto_en: datetime | None = None
    devuelto_por: Literal["gestor", "vencimiento"] | None = None

@dataclass(frozen=True)
class ResultadoHandoff:
    handoff_id: str
    asignado_a: str
    canal: Literal["panel"] = "panel"
    minutos_estimados: int = 15

@dataclass(frozen=True)
class ReferenciaCRM:
    entidad: str
    id_local: str
    crm_ref: str
```

## Compuerta (`CRMConectorService`)

```python
class CRMConectorService:
    def buscar_contacto(self, telefono_token: str | None = None, email_token: str | None = None, *, telefono: str | None = None, email: str | None = None) -> Contacto | None: ...
    def crear_contacto(self, contacto: Contacto) -> Contacto: ...
    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad: ...
    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad: ...
    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta: ...
    def publicar_anulacion(self, venta: Mapping[str, Any]) -> PublicacionVenta: ...
    def procesar_cola(self) -> int: ...
    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str: ...
    def recibir_evento(self, cuerpo: bytes, firma: str) -> EventoCRM: ...
    def registrar_receptor(self, tipo: str, receptor: Callable[[EventoCRM], Any]) -> None: ...
    def despachar_evento(self, evento: EventoCRM) -> None: ...

    # Handoffs por zona (RF-CRM-06, RF-MCP-06)
    def solicitar_handoff(self, conversacion_id: str, zona_id: str | None = None, resumen: str = "", motivo: str = "peticion_explicita", propiedad_id: str | None = None) -> str: ...
    def solicitar_humano(self, motivo: str, resumen: str, propiedad_id: str | None = None, conversacion_id: str | None = None) -> dict[str, Any]: ...
    def tomar_handoff(self, handoff_id: str, gestor_id: str) -> None: ...
    def devolver_al_asistente(self, handoff_id: str, gestor_id: str | None = None, devuelto_por: str = "gestor", reanudar_callback: Callable[[str], None] | None = None) -> None: ...
    def revisar_plazos_handoffs(self, ahora: datetime | None = None) -> dict[str, int]: ...

    # Herramientas MCP
    def buscar_contacto_crm(self, telefono_token: str | None = None, email_token: str | None = None) -> dict[str, Any]: ...
    def crear_oportunidad_crm(self, contacto_id: str, propiedad_id: str, etapa: str, monto: Decimal | float | None = None) -> dict[str, Any]: ...
```

## Invariantes
| Código | Predicado | Mecanismo obligatorio |
| :--- | :--- | :--- |
| `INV_HANDOFF_UNICO` | `∀ c : ∣{h ∈ handoffs(c) : estado(h) ≠ devuelto}∣ ≤ 1` | Índice único parcial `un_handoff_abierto` en `crm.handoffs (conversacion_id) WHERE estado <> 'devuelto'`. |
| `INV_VENTA_FIRMADA_IDEMPOTENTE` | `∀ (v, e) : ∣{p ∈ publicaciones : venta_id(p) = v ∧ evento(p) = e ∧ estado(p) = 'ok'}∣ ≤ 1` | Clave primaria compuesta `(venta_id, evento)` en `crm.publicaciones` y verificación previa de estado para evitar reenvíos al CRM. |
| `INV_VENTA_NO_SE_PIERDE` | `∀ p ∈ publicaciones : p no se elimina de la base de datos` | Tras agotar la ventana de 24 horas, la publicación pasa a `estado = 'error'` (`no_publicada`) y emite alerta crítica `VENTA_NO_PUBLICADA`, permitiendo reintento manual desde panel. |

## Configuración (`config_crm_conector.yaml`)
`proveedor: ${CRM_PROVEEDOR:-fake}`, `admin_id: ${CRM_ADMIN_ID}`, `contacto_humano_escalamiento: ${CONTACTO_HUMANO_ESCALAMIENTO}`, `bandeja_handoff_activa: true`, `minutos_estimados_atencion: 15`, `tiempo_limite_sin_tomar_minutos: 15`, `tiempo_limite_abandono_horas: 24`, `propiedades_zonas {glamping_imbabura, dep_ibarra_centro}`, `credenciales {url, token, location_id}`, `webhook_ventas`, `cola`, `mapeo_pipeline`, `inbox`.

## Compuertas que consume
- `observabilidad_service`: Registro estructurado de eventos de handoff (`handoff_solicitado`, `handoff_tomado`, `handoff_devuelto`, `alerta_handoff_no_tomado`, `escalamiento_sin_bandeja`).

## Errores
- `CRMNoDisponible`: Proveedor no alcanzable o desconocido.
- `ContactoDuplicado`: Intento de registrar un contacto con identificador o teléfono repetido.
- `ContactoNoEncontrado`: Contacto no localizado.
- `OportunidadInexistente`: Oportunidad no encontrada para actualización.
- `HandoffExistente`: Violación de `INV_HANDOFF_UNICO`.
- `HandoffInexistente`: Identificador de handoff no localizado.
- `ZonaInexistente`: Zona no encontrada en el catálogo.
- `BandejaHandoffInactiva`: Escalamiento previo a fase 4 cuando la bandeja no está activa.
- `WebhookRechazado`, `LimiteDeTasa`, `FirmaEventoInvalida`: Errores reservados para la integración de proveedor real en T-601.

## Persistencia (`esquema crm`)
- `crm.zonas`: Catálogo de zonas con gestor principal y respaldo (`gestor_principal_id <> gestor_respaldo_id`).
- `crm.handoffs`: Solicitudes de intervención humana por conversación, zona y estado (`pendiente`, `tomado`, `devuelto`), con índice `un_handoff_abierto`.
- `crm.publicaciones`: Cola de eventos de venta para despacho idempotente al CRM.
- `crm.eventos`: Registro de webhooks y eventos entrantes recibidos.
- `crm.referencias`: Asociación entre identidades locales y referencias externas del CRM (`crm_ref`).

## Tests (árbitro)
- `tests/crm_conector/test_contrato.py`: Contrato parametrizado contra `FakeCRM` y dobles alternativos con tipos puros de dominio.
- `tests/crm_conector/test_seleccion_proveedor.py`: Resolución de proveedor y fallback por configuración (RF-CRM-02).
- `tests/crm_conector/test_handoff.py`: Handoff por zona, asignación a admin, reasignación a respaldo en 15 min, vencimiento por abandono en 24 h, `INV_HANDOFF_UNICO` y herramientas MCP.
- `tests/crm_conector/test_publicar_venta.py`: Publicación firmada con HMAC-SHA256 (`X-Glamping-Date` + cuerpo canónico), verificación en receptor HTTP simulado e idempotencia (`INV_VENTA_FIRMADA_IDEMPOTENTE`).
- `tests/crm_conector/test_cola_reintentos.py`: Cola de reintentos con backoff exponencial, traducción de errores HTTP tipados, ventana de 24 horas y reintento manual desde panel (`INV_VENTA_NO_SE_PIERDE`).
- `tests/crm_conector/test_eventos.py`: Recepción y validación estricta de eventos firmados del CRM, persistencia en `crm.eventos` y despacho a receptores registrados.
- `tests/crm_conector/test_confinamiento.py`: Confinamiento estricto ADPA de la sala `features/crm_conector/`.
- `tests/crm_conector/test_confinamiento.py`: Confinamiento ADPA y pureza de compuerta.

`¤crm-conector/`
