# Módulo `canal_whatsapp` — Canal de WhatsApp (Cloud API oficial)
`¤canal-whatsapp`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/canal_whatsapp/` |
| Compuerta | `canal_whatsapp_service.py` → `CanalWhatsappService` |
| Privados | `webhook_internal.py`, `envio_internal.py`, `plantillas_internal.py`, `medios_internal.py`, `enrutamiento_canal_internal.py`, `tipos.py` |
| Config | `config_canal_whatsapp.yaml` |
| Rol | `¤¤integration-engineer` |
| Requisitos | RF-GW-01..06 · RNF-01 · INV_FIRMA_WEBHOOK_META, INV_VENTANA_24H, INV_CANAL_OFICIAL, INV_INTERFAZ_PURIFICADA |
| Tareas | TASK-001 (01..05), TASK-006 (06) |
| Decisión | Construir (ADR-0003) |

## Propósito
Única sala que habla con la Cloud API de Meta. Convierte el webhook en `MensajeEntrante` tipado, envía `MensajeSaliente` o `Plantilla` respetando la ventana de 24 h, gestiona medios y separa el canal de huéspedes del de vendedores.

## Tipos del dominio (`tipos.py`)

```python
class Canal(str, Enum): HUESPEDES = "huespedes"; VENDEDORES = "vendedores"
class TipoContenido(str, Enum): TEXTO, BOTON, LISTA, IMAGEN, AUDIO, DOCUMENTO, UBICACION, DESCONOCIDO

@dataclass(frozen=True)
class MensajeEntrante:
    mensaje_id: str; remitente: str; canal: Canal; tipo: TipoContenido
    texto: str | None; medio_ref: str | None; ubicacion: tuple[float, float] | None
    recibido_en: datetime; contexto_respuesta_a: str | None

@dataclass(frozen=True)
class Boton: id: str; titulo: str                      # máx. 3 por mensaje, título ≤ 20 caracteres
@dataclass(frozen=True)
class OpcionLista: id: str; titulo: str; descripcion: str | None   # máx. 10

@dataclass(frozen=True)
class MensajeSaliente:
    destinatario: str; texto: str; botones: tuple[Boton, ...] = (); lista: tuple[OpcionLista, ...] = ()
    medio_ref: str | None = None; en_respuesta_a: str | None = None

@dataclass(frozen=True)
class Plantilla: nombre: str; idioma: str; variables: tuple[str, ...]
@dataclass(frozen=True)
class ResultadoEnvio: mensaje_id: str; estado: Literal["sent", "delivered", "read", "failed"]; detalle: str | None
```

## Compuerta

```python
class CanalWhatsappService:
    def verificar_webhook(self, modo: str, token: str, desafio: str) -> str | None: ...          # RF-GW-01 a
    def recibir(self, cuerpo: bytes, firma_sha256: str) -> list[MensajeEntrante]: ...           # RF-GW-01 b–d; lanza FirmaInvalida
    def clasificar_canal(self, remitente: str, grupo_id: str | None) -> Canal: ...               # RF-GW-06
    def en_ventana_24h(self, destinatario: str) -> bool: ...                                     # RF-GW-03
    def enviar(self, mensaje: MensajeSaliente) -> ResultadoEnvio: ...                           # RF-GW-02; lanza FueraDeVentana
    def enviar_plantilla(self, destinatario: str, plantilla: Plantilla) -> ResultadoEnvio: ...  # RF-GW-04; lanza PlantillaNoAprobada
    def actualizar_estado(self, mensaje_id: str, estado: str) -> None: ...                      # status updates de Meta
    def descargar_medio(self, medio_id: str) -> str: ...                                         # RF-GW-05; devuelve medio_ref en S3
    def registrar_receptor(self, canal: Canal, receptor: Callable[[MensajeEntrante], None]) -> None: ...  # app_core enlaza agente/arm
```

## Configuración (`config_canal_whatsapp.yaml`)
`numero_id`, `cuenta_negocio_id`, `token_acceso: ${META_ACCESS_TOKEN}`, `verify_token: ${META_VERIFY_TOKEN}`, `secreto_app: ${META_APP_SECRET}`, `version_api`, `reintentos {max: 3, backoff_s: [1, 4, 10]}`, `ventana_servicio_horas: 24`, `plantillas: [{nombre, idioma, variables, aprobada}]`, `canal_vendedores {modo: grupo|uno_a_uno, grupo_id}`, `medios {bucket, prefijo, max_mb}`, `audio {transcribir: false}`.

## Compuertas que consume
`observabilidad` (traza, logs), `seguridad` (solo para `descargar_medio`: no descarga medios de remitentes fuera de whitelist). No consume `agente` ni `arm_jarvis`: les entrega mensajes por el receptor registrado (inversión de dependencias).

## Errores
`FirmaInvalida` (401), `MensajeDuplicado` (descartado silencioso), `FueraDeVentana`, `PlantillaNoAprobada`, `VariablesPlantillaInvalidas`, `ApiMetaNoDisponible` (tras reintentos), `MedioNoPermitido`.

## Persistencia (`esquema canal`)
`mensajes_meta(mensaje_id PK, direccion, remitente_token, canal, tipo, estado, plantilla, enviado_en, actualizado_en)` para dedup y ventana de 24 h; `plantillas(nombre, idioma, aprobada, actualizada_en)`.

## Tests (árbitro)
`tests/canal_whatsapp/test_webhook.py` (firma, dedup, desafío), `test_envio.py` (API simulada, reintentos), `test_ventana_24h.py`, `test_plantillas.py`, `test_medios.py`, `test_enrutamiento_canal.py`; `tests/test_canal_oficial.py`.

## Pendientes
S-01 (grupo vs 1:1) fija `canal_vendedores.modo`; transcripción de audio se decide en TASK-001.

`¤canal-whatsapp/`
