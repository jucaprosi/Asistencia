# Módulo `canal_whatsapp` — Canal de WhatsApp (Cloud API oficial)
`¤canal-whatsapp`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/canal_whatsapp/` |
| Compuerta | `canal_whatsapp_service.py` → `CanalWhatsappService` |
| Privados | `webhook_internal.py`, `envio_internal.py`, `plantillas_internal.py`, `medios_internal.py`, `persistencia_internal.py`, `trabajador_internal.py`, `enrutamiento_canal_internal.py`, `tipos.py` |
| Config | `config_canal_whatsapp.yaml` |
| Rol | `¤¤integration-engineer` |
| Requisitos | RF-GW-01..08 · RNF-01 · INV_FIRMA_WEBHOOK_META, INV_INGESTA_DURABLE, INV_VENTANA_24H, INV_CANAL_OFICIAL |
| Tareas | TASK-001 (01..05, 07, 08), TASK-006 (06), T-503 (06) |
| Decisión | Construir (ADR-0003) |

## Propósito
Única sala que habla con la Meta WhatsApp Cloud API oficial. Recibe webhooks (GET de desafío y POST de eventos), valida firmas HMAC SHA-256 en tiempo constante, persiste de forma durable y deduplica mensajes, aplica la ventana de servicio de 24 horas (`INV_VENTANA_24H`), gestiona el envío de texto, botones y listas con reintentos exponenciales, valida y despacha plantillas aprobadas, y almacena medios entregando únicamente referencias URI (`medio_ref`) al agente.

## Tipos del dominio (`tipos.py`)

```python
class Canal(str, Enum): HUESPEDES = "huespedes"; VENDEDORES = "vendedores"
class TipoContenido(str, Enum): TEXTO, BOTON, LISTA, IMAGEN, AUDIO, DOCUMENTO, UBICACION, DESCONOCIDO

@dataclass(frozen=True)
class MensajeEntrante:
    mensaje_id: str; remitente: str; canal: Canal; tipo: TipoContenido
    texto: str | None; medio_ref: str | None; ubicacion: tuple[float, float] | None
    recibido_en: datetime; contexto_respuesta_a: str | None = None
    mensajes_agrupados: tuple[MensajeEntrante, ...] = ()

@dataclass(frozen=True)
class Boton: id: str; titulo: str                      # máx. 3 por mensaje, título ≤ 20 caracteres
@dataclass(frozen=True)
class OpcionLista: id: str; titulo: str; descripcion: str | None   # máx. 10 opciones

@dataclass(frozen=True)
class MensajeSaliente:
    destinatario: str; texto: str; botones: tuple[Boton, ...] = (); lista: tuple[OpcionLista, ...] = ()
    medio_ref: str | None = None; en_respuesta_a: str | None = None

@dataclass(frozen=True)
class Plantilla: nombre: str; idioma: str; variables: tuple[str, ...]
@dataclass(frozen=True)
class ResultadoEnvio: mensaje_id: str; estado: Literal["sent", "delivered", "read", "failed"]; detalle: str | None = None
```

## Compuerta (`canal_whatsapp_service.py`)

```python
class CanalWhatsappService:
    def verificar_webhook(self, modo: str, token: str, desafio: str) -> str | None: ...          # RF-GW-01 a
    def recibir(self, cuerpo: bytes, firma_sha256: str) -> list[MensajeEntrante]: ...           # RF-GW-01 b–d, RF-GW-07
    def clasificar_canal(self, remitente: str, grupo_id: str | None = None) -> Canal: ...       # RF-GW-06
    def registrar_vendedor(self, remitente: str) -> None: ...                                    # RF-GW-06 (modo 1a1)
    def despachar(self, mensaje: MensajeEntrante) -> Any: ...                                    # RF-GW-06
    def en_ventana_24h(self, destinatario: str) -> bool: ...                                     # RF-GW-03, INV_VENTANA_24H
    def enviar(self, mensaje: MensajeSaliente) -> ResultadoEnvio: ...                           # RF-GW-02, INV_VENTANA_24H
    def enviar_plantilla(self, destinatario: str, plantilla: Plantilla) -> ResultadoEnvio: ...  # RF-GW-04
    def actualizar_estado(self, mensaje_id: str, estado: str) -> None: ...                      # RF-GW-02 a
    def descargar_medio(self, medio_id: str, remitente: str | None = None) -> str: ...          # RF-GW-05
    def registrar_receptor(self, canal: Canal, receptor: Callable[[MensajeEntrante], None]) -> None: ...  # Inversión de dependencias
    def procesar_ingesta(self) -> int: ...                                                       # RF-GW-07, RF-GW-08
    def recuperar_caidas(self) -> int: ...                                                       # RF-GW-07
```

## Módulos internos
- `webhook_internal.py`: Validación de firma HMAC SHA-256 (`INV_FIRMA_WEBHOOK_META`) en tiempo constante con `hmac.compare_digest`. Desafío de verificación `hub.challenge`. Parseo y extracción de mensajes y actualizaciones de estado.
- `persistencia_internal.py`: Repositorio SQLite thread-safe para el esquema `canal`. Inserción `ON CONFLICT (mensaje_id) DO NOTHING` para garantizar deduplicación e ingesta durable (`INV_INGESTA_DURABLE`). Registro de marcas de tiempo y transiciones de estado.
- `envio_internal.py`: Envíos con backoff exponencial (hasta 3 reintentos con esperas configuradas: 1, 4, 10 s). Validación de botones (máx. 3, título ≤ 20 caracteres) y listas (máx. 10 opciones). Registro de estados `sent`, `delivered`, `read`, `failed`.
- `plantillas_internal.py`: Validación de aprobación de plantillas en el catálogo y verificación estricta de cantidad y tipo de variables (`utility`, `authentication`). Armado de payload JSON para Meta Cloud API.
- `medios_internal.py`: Verificación de remitente bloqueado mediante `seguridad_service`. Descarga de medios desde Meta, almacenamiento seguro y retorno exclusivo de URI `medio_ref` (nunca expone bytes crudos al agente). Envío de imágenes y documentos.
- `enrutamiento_canal_internal.py`: Enrutamiento y segregación de canales (RF-GW-06). Clasificación de canal de vendedores en modo grupo (por `grupo_id`) o en modo 1:1 (por rol vendedor en `seguridad_service` o registro explícito). Despacho estricto garantizando que ningún mensaje de vendedores llegue al agente de huéspedes y ningún mensaje de huéspedes llegue al ARM. Definición local de la plantilla `comision_validada`.
- `trabajador_internal.py`: Procesador asíncrono que toma eventos en estado `pendiente`. Serialización por remitente (concurrency lock por `conversacion_clave`). Agrupación de mensajes recibidos en ventana de 3 segundos en un solo turno. Recuperación de caídas: reintenta hasta 5 veces eventos en estado `procesando` y marca a `muerto` con alerta crítica en observabilidad si agota intentos.

## Configuración (`config_canal_whatsapp.yaml`)
`numero_id`, `cuenta_negocio_id`, `token_acceso: ${META_ACCESS_TOKEN}`, `verify_token: ${META_VERIFY_TOKEN}`, `secreto_app: ${META_APP_SECRET}`, `version_api`, `reintentos {max: 3, backoff_s: [1, 4, 10]}`, `ventana_servicio_horas: 24`, `plantillas: [...]`, `ingesta {reintentos_evento: 5, agrupacion_segundos: 3}`, `medios {bucket, prefijo, max_mb}`.

## Compuertas que consume
- `seguridad_service`: Consumida exclusivamente para `descargar_medio` a fin de validar que el remitente no esté bloqueado o descartado.
- `observabilidad_service`: Trazas, logs estructurados sin PII y disparo de alertas críticas (`EVENTO_MUERTO`, `ENVIO_META_FALLIDO`).

## Errores tipados
- `FirmaInvalida`: Código `FIRMA_INVALIDA` (HTTP 401).
- `MensajeDuplicado`: Código `MENSAJE_DUPLICADO` (descarte idempotente).
- `FueraDeVentana`: Código `FUERA_DE_VENTANA` (rechazo en compuerta para texto libre fuera de 24 h).
- `PlantillaNoAprobada`: Código `PLANTILLA_NO_APROBADA`.
- `VariablesPlantillaInvalidas`: Código `VARIABLES_PLANTILLA_INVALIDAS`.
- `ApiMetaNoDisponible`: Código `API_META_NO_DISPONIBLE` (tras agotar reintentos).
- `MedioNoPermitido`: Código `MEDIO_NO_PERMITIDO`.

## Persistencia (`esquema canal`)
- `canal.eventos_entrantes`: `(evento_id PK, mensaje_id UNIQUE, conversacion_clave, cuerpo_cifrado, estado, intentos, recibido_en, procesado_en)`
- `canal.mensajes_meta`: `(mensaje_id PK, direccion, remitente_token, canal, tipo, estado, plantilla, enviado_en, actualizado_en)`
- `canal.plantillas`: `(nombre PK, idioma, categoria, variables_csv, aprobada, actualizada_en)`
- `canal.medios`: `(medio_id PK, mensaje_id FK, medio_ref, tipo, bytes, expira_en)`

## Invariantes
| Código | Predicado | Mecanismo |
| :--- | :--- | :--- |
| `INV_CANAL_OFICIAL` | `∀ d ∈ dependencias : d ∉ {baileys, whatsapp-web.js, whatsmeow}` | Dependencias oficiales de Meta Cloud API. |
| `INV_FIRMA_WEBHOOK_META` | `procesado(m) ⇒ HMAC_SHA256(secreto, cuerpo_crudo(m)) = firma(m)` | `hmac.compare_digest` sobre bytes crudos. |
| `INV_INGESTA_DURABLE` | `respondio_200(m) ⇒ persistido(m)` | `INSERT ... ON CONFLICT (mensaje_id) DO NOTHING`. |
| `INV_VENTANA_24H` | `enviado(m) ∧ ¬plantilla(m) ⇒ ahora − ultimo_mensaje_usuario < 24 h` | Rechazo tipado en compuerta con `FueraDeVentana`. |

## Tests (árbitro)
- `tests/canal_whatsapp/test_webhook.py`: Verificación de desafío GET, firma HMAC SHA-256 válida/inválida, persistencia previa y deduplicación.
- `tests/canal_whatsapp/test_envio.py`: Envío de texto, botones, listas, actualización de estados y reintentos con backoff exponencial.
- `tests/canal_whatsapp/test_ventana_24h.py`: Ventana de 24 horas para texto libre vs plantillas aprobadas.
- `tests/canal_whatsapp/test_plantillas.py`: Validación de variables y control de aprobación de plantillas.
- `tests/canal_whatsapp/test_medios.py`: Recepción de medios, bloqueo de números y entrega de `medio_ref`.
- `tests/canal_whatsapp/test_enrutamiento_canal.py`: Separación de canales en modos grupo y 1a1, mamparos estrictos entre receptores, y definición local de `comision_validada`.
- `tests/canal_whatsapp/test_ingesta_durable.py`: Persistencia previa y recuperación de caídas hasta muerte con alerta.
- `tests/canal_whatsapp/test_orden.py`: Serialización por remitente y agrupación de ráfagas en ventana de 3 segundos.
- `tests/test_canal_oficial.py`: Verificación de uso de Meta Cloud API oficial.

`¤canal-whatsapp/`
