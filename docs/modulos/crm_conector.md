# Módulo `crm_conector` — Conector al CRM (sistema de registro adoptado)
`¤crm-conector`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/crm_conector/` |
| Compuerta | `crm_conector_service.py` → `CRMConectorService` |
| Privados | `base_internal.py` (ABC `CRMConnector`), `fake_internal.py`, `ghl_internal.py` · `chatwoot_internal.py` · `attio_internal.py` (uno activo), `cola_internal.py`, `firma_internal.py`, `eventos_internal.py`, `tipos.py` |
| Config | `config_crm_conector.yaml` |
| Rol | `¤¤integration-engineer` |
| Requisitos | RF-CRM-01..05 · RNF-09 · INV_VENTA_FIRMADA_IDEMPOTENTE, INV_VENTA_NO_SE_PIERDE |
| Tareas | TASK-004 (interfaz + `FakeCRM`), TASK-007 (proveedor real, webhook, cola, eventos) |
| Decisión | Interfaz propia; CRM adoptado `[DECISIÓN PENDIENTE]` ADR-0008. Con ADR-0013 el CRM queda como sistema de registro de contactos y oportunidades (y opcionalmente inbox); la UI operativa es el panel propio. |

## Propósito
Publicar ventas y contactos al CRM de forma firmada e idempotente, recibir sus eventos, y asignar conversaciones a su inbox si ADR-0010 lo mantiene. Aísla al proveedor: `agente`, `arm_jarvis` y `panel_operativo` solo ven esta compuerta.

## Tipos del dominio

```python
@dataclass(frozen=True)
class Contacto: contacto_id: str; nombre_token: str; telefono_token: str; email_token: str | None; crm_ref: str | None
@dataclass(frozen=True)
class Oportunidad: oportunidad_id: str; contacto_id: str; propiedad_id: str | None; etapa: str; monto: Decimal | None; crm_ref: str | None
@dataclass(frozen=True)
class PublicacionVenta: venta_id: str; estado: Literal["pendiente", "ok", "error"]; intentos: int; ultima_respuesta: str | None; proximo_intento: datetime | None
@dataclass(frozen=True)
class EventoCRM: tipo: Literal["venta_validada", "venta_rechazada", "handoff_devuelto", "incidencia_resuelta", "mensaje_gestor"]; referencia: str; actor: str; datos: Mapping[str, Any]; recibido_en: datetime
```

## Compuerta

```python
class CRMConectorService:
    def buscar_contacto(self, telefono_token: str | None = None, email_token: str | None = None) -> Contacto | None: ...
    def crear_contacto(self, contacto: Contacto) -> Contacto: ...
    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad: ...
    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad: ...
    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta: ...                  # HMAC-SHA256 + venta_id (RF-CRM-03)
    def procesar_cola(self) -> int: ...                                                           # reintentos hasta 24 h (RF-CRM-04)
    def asignar_conversacion(self, conversacion_id: str, zona_id: str, resumen: str) -> str: ...  # inbox del proveedor o panel (ADR-0010)
    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str: ...
    def recibir_evento(self, cuerpo: bytes, firma: str) -> EventoCRM: ...                         # POST /crm/eventos
    def registrar_receptor(self, tipo: str, receptor: Callable[[EventoCRM], None]) -> None: ...    # app_core enlaza arm/agente/panel
```

## Configuración (`config_crm_conector.yaml`)
`proveedor: fake|ghl|chatwoot_attio`, `credenciales {url: ${CRM_URL}, token: ${CRM_TOKEN}, location_id}`, `webhook_ventas {url: ${CRM_INBOUND_WEBHOOK_URL}, secreto_hmac: ${CRM_HMAC_SECRET}, cabecera_firma: X-Glamping-Signature}`, `eventos_entrantes {secreto: ${CRM_EVENTS_SECRET}}`, `cola {backoff_s: [30, 120, 600, 3600], max_horas: 24}`, `mapeo_pipeline {etapa_por_validar, etapa_validada, etapa_rechazada}`, `inbox {usar_proveedor: true}`.

## Compuertas que consume
`observabilidad`. Si `inbox.usar_proveedor` es falso, `asignar_conversacion` delega en `panel_operativo` (a través de `app_core`, que enlaza el receptor; la sala no importa al panel).

## Errores
`CRMNoDisponible`, `ContactoDuplicado`, `WebhookRechazado` (→ cola), `LimiteDeTasa` (→ cola con backoff), `FirmaEventoInvalida` (401).

## Persistencia (`esquema crm`)
`publicaciones(venta_id PK, payload_json, firma, estado, intentos, ultima_respuesta, proximo_intento, creado_en)`; `eventos(evento_id PK, tipo, referencia, actor, datos_json, recibido_en, procesado_en)`; `referencias(entidad, id_local, crm_ref)`.

## Tests (árbitro)
`tests/crm_conector/test_contrato.py`, `test_seleccion_proveedor.py`, `test_publicar_venta.py` (receptor simulado que verifica HMAC; repetición sin duplicados), `test_cola_reintentos.py`, `test_confinamiento.py`, `test_eventos.py`.

`¤crm-conector/`
