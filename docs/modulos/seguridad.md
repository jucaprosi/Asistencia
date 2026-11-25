# Módulo `seguridad` — Seguridad del canal y Privacidad de Datos
`¤seguridad-canal`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/seguridad/` |
| Compuerta | `seguridad_service.py` → `SeguridadService` |
| Privados | `identidad_internal.py`, `allowlist_internal.py`, `rate_limit_internal.py`, `injection_internal.py`, `patrones_inyeccion.yaml`, `pii_internal.py`, `audit_internal.py`, `consentimiento_internal.py`, `persistencia_internal.py`, `secretos_internal.py`, `rls_internal.py`, `retencion_internal.py`, `titulares_internal.py`, `migraciones_rls.sql`, `tipos.py` |
| Config | `config_seguridad.yaml` |
| Rol | `¤¤security-engineer` |
| Requisitos | RF-SEC-01..08, RF-PRIV-01..06 · RNF-07, 17, 18 · INV_ALLOWLIST_POR_ACCION, INV_AUDIT_APPEND_ONLY, INV_CRIPTOBORRADO, INV_INYECCION_CERO, INV_PII_FUERA_DEL_MODELO, INV_RATE_LIMIT_NO_ANULABLE, INV_SECRETO_OPERATIVO, INV_SIN_FUGA_ENTRE_PROPIEDADES |
| Tareas | TASK-001 (01, 03, 05), TASK-005 (02, 04, 06, 07), T-304 (07, 08), T-401 (04, PRIV-03, 04, 05, 06) |

## Propósito
Todo mensaje entrante atraviesa la sala `seguridad` antes del agente conversacional o del motor de ventas (ARM); toda salida la atraviesa antes del gateway hacia WhatsApp. Es la única sala autorizada a tratar y visualizar PII en claro mediante su bóveda criptográfica de tokens (`seguridad.boveda_tokens`) y es el árbitro que autoriza la ejecución de cada herramienta según el rol verificado del remitente. Además, gobierna las políticas de Row-Level Security (RLS) para aislamiento multi-inquilino por `propiedad_id` y custodia los secretos operativos (credenciales de WiFi y accesos a cerraduras).

## Tipos del dominio

```python
class Rol(str, Enum):
    HUESPED_POTENCIAL = "huesped_potencial"
    HUESPED_ACTIVO = "huesped_activo"
    VENDEDOR = "vendedor"
    LIDER = "lider"
    GESTOR = "gestor"
    ADMINISTRADOR = "administrador"
    ANFITRION = "anfitrion"
    SISTEMA = "sistema"
    DESCONOCIDO = "desconocido"

@dataclass(frozen=True)
class Identidad:
    remitente_token: str
    rol: Rol
    sujeto_id: str | None = None
    numero_hash: str | None = None

@dataclass(frozen=True)
class MensajeLimpio:
    identidad: Identidad
    texto_tokenizado: str
    marcas: tuple[str, ...]
    conversacion_id: str

@dataclass(frozen=True)
class Veredicto:
    permitido: bool
    motivo: str | None = None
    escalar: bool = False

@dataclass(frozen=True)
class EventoAuditoria:
    actor_token: str
    rol: Rol
    accion: str
    herramienta: str | None = None
    propiedad_id: str | None = None
    resultado: str = "ok"
    hash_prompt: str | None = None
    traza_id: str = ""
    audit_id: str | None = None
    instante: datetime | None = None
```

## Compuerta Pública (`SeguridadService`)

```python
class SeguridadService:
    def __init__(self, config: Mapping[str, Any] | None = None, *, observabilidad: Any = None, conexion: sqlite3.Connection | None = None) -> None: ...
    def identificar(self, remitente: str, canal: str = "huespedes") -> Identidad: ...
    def filtrar_entrada(self, remitente: str, texto: str, canal: str = "huespedes", conversacion_id: str | None = None, **kwargs: Any) -> MensajeLimpio | Veredicto: ...
    def autorizar(self, rol: Rol | str, herramienta: str, *, estricto: bool = False) -> Veredicto: ...
    def exigir_autorizacion(self, rol: Rol | str, herramienta: str) -> None: ...
    def tokenizar(self, texto: str, conversacion_id: str, titular_hash: str | None = None) -> str: ...
    def rehidratar(self, texto: str, conversacion_id: str) -> str: ...
    def filtrar_salida(self, texto: str, conversacion_id: str) -> str: ...
    def tokenizar_estructura(self, valor: Any, conversacion_id: str, titular_hash: str | None = None, campos_pii: Iterable[str] | None = None, campos_exentos: Mapping[str, str] | None = None) -> Any: ...
    def estado(self) -> dict[str, bool]: ...  # {"clave_efimera": bool}
    def auditar(self, evento: EventoAuditoria) -> None: ...
    def informe_semanal(self, desde: date, hasta: date) -> bytes: ...
    def administrar_usuarios(self, actor: Identidad, numero: str, rol: Rol, alta: bool, sujeto_id: str | None = None, correo: str | None = None) -> None: ...
    def bloquear_numero(self, actor: Identidad, numero: str, motivo: str) -> None: ...
    def desbloquear_numero(self, actor: Identidad, numero: str) -> None: ...
    def guardar_secreto_operativo(self, token_id: str, tipo: str, valor_plano: str, titular_hash: str = "global") -> str: ...
    def obtener_secreto_operativo(self, token_o_marcador: str) -> str | None: ...
    def rehidratar_secretos(self, texto: str) -> str: ...
    def validar_acceso_reserva(self, codigo_reserva: str, remitente_token: str, es_titular: bool, fecha_llegada: datetime | date | None = None, reserva_confirmada: bool = True, instante: datetime | None = None, traza_id: str = "") -> Veredicto: ...
    def contexto_inquilino(self, propiedad_id: str | None, conexion: Any = None) -> Any: ...
    def generar_migraciones_rls(self, rol_aplicacion: str = "app_glamping") -> str: ...
    def purgar_retencion(self, fecha_referencia: datetime | date | None = None, dias_override: Mapping[str, int] | None = None) -> dict[str, int]: ...
    def registrar_solicitud_titular(self, titular_hash: str, tipo: str, recibida_en: datetime | None = None) -> SolicitudTitular: ...
    def listar_solicitudes_titular(self, estado: str | None = None) -> list[SolicitudTitular]: ...
    def solicitudes_proximas_a_vencer(self, dias_aviso: int = 3, ahora: datetime | None = None) -> list[SolicitudTitular]: ...
    def atender_solicitud_titular(self, solicitud_id: str, atendida_por: str = "usr_admin", sujeto_a_conservacion: bool = False, motivo_conservacion: str | None = None) -> SolicitudTitular: ...
    def ejecutar_criptoborrado(self, titular_hash: str, actor_id: str = "administrador") -> dict[str, Any]: ...
    def evaluar(self, ruta_inyecciones: Path | str, suite: str = "inyecciones") -> dict[str, Any]: ...
```

## Invariantes Garantizados

1. **`INV_ALLOWLIST_POR_ACCION`**: `ejecutada(h, rol) ⇒ h ∈ allowlist(rol)`. Se valida estrictamente en `seguridad.autorizar` contra el mapa canónico de `dominio.yaml`.
2. **`INV_AUDIT_APPEND_ONLY`**: La tabla `seguridad.audit_log` es de solo inserción. Se revocan a nivel de base de datos (`REVOKE`) los comandos `UPDATE`, `DELETE` y `TRUNCATE`. La tarea de retención nunca purga este registro.
3. **`INV_CRIPTOBORRADO`**: `borrado(t) ⇒ ¬rehidratable(tokens(t)) ∧ audit_log' = audit_log`. El borrado de las filas en `seguridad.boveda_tokens` deja irrecuperables los datos personales del titular sin alterar el historial ni el audit log; rehidratar tokens borrados devuelve el marcador neutro `[DATO_BORRADO]`.
4. **`INV_INYECCION_CERO`**: Ningún intento de inyección de prompt elude el filtrado (OP-10 = 0 éxitos). Se detectan ≥ 40 patrones multilingües (español, inglés, portugués, francés) y anomalías estructurales devolviendo respuestas neutras. Reincidencias (≥ 3) escalan a humano.
5. **`INV_PII_FUERA_DEL_MODELO`**: Los datos personales (`nombre`, `telefono`, `correo`, `documento`, `tarjeta`, `direccion`) se extraen y reemplazan por tokens reversibles antes de emitir cualquier petición HTTP al LLM, trazas o logs.
6. **`INV_RATE_LIMIT_NO_ANULABLE`**: Se aplican cuotas por remitente (2 msg/s, 30/min, 300/día). Ningún rol, actor administrativo ni ajuste de configuración puede desactivar este límite.
7. **`INV_SECRETO_OPERATIVO`**: `∀ s ∈ secretos : s ∉ payload ∪ historial ∧ (enviado(s, r) ⇒ titular(r))`. Las credenciales de WiFi y códigos de acceso viven en la bóveda cifrada AES-256-GCM. El modelo y el historial de la conversación solo ven marcadores opacos `[[SECRETO:...]]`. El valor real se resuelve única y exclusivamente en el mensaje saliente (`filtrar_salida`) hacia el titular con reserva confirmada dentro de las 24 horas de la llegada.
8. **`INV_SIN_FUGA_ENTRE_PROPIEDADES`**: Políticas de Row-Level Security activas (`FORCE ROW LEVEL SECURITY`) con rol de aplicación `NOBYPASSRLS` (`app_glamping`) que restringen toda consulta en tablas con `propiedad_id` a la propiedad fijada en `app.propiedad_id` o filas marcadas como `'global'`.

## Bóveda de tokens PII (T-406, T-406-b)

- **Clave (T-406-b).** La bóveda cifra con `pii.clave_boveda` o, en su defecto, `PII_VAULT_KEY`. Un marcador `${VAR:-defecto}` sin resolver (la configuración YAML leída sin el pasillo central) se resuelve contra el entorno y, si queda vacío, cuenta como clave no configurada. Sin clave configurada no se falla cerrado: la sala usa una **clave aleatoria efímera por proceso** (`secrets.token_hex(32)` al importar `pii_internal`), compartida por las instancias del mismo proceso (y por los secretos operativos, que la reciben como respaldo), nunca una constante del repositorio. `SeguridadService.estado()` devuelve `{"clave_efimera": True}` en ese caso.
- **Conducta deliberada sin clave configurada.** Los tokens dejan de ser legibles tras reiniciar el proceso: la fila sigue en la bóveda, pero su descifrado falla y `rehidratar` devuelve el marcador neutro `[DATO_BORRADO]`, igual que ante un token borrado o ajeno. Dos arranques sin clave no se leen entre sí. En producción el arranque con clave efímera lo rechaza otra tarea (P-1); dos instancias con la misma clave configurada sí rehidratan los tokens de la otra.
- **Numeración y colisiones.** El token es `[TIPO_n]` y la fila de la bóveda se guarda con la clave `conversacion_id:[TIPO_n]`. El número es el primero libre en la caché y en la bóveda; si el `INSERT` choca con la clave primaria (`IntegrityError`: otro escritor eligió el mismo número entre la consulta y la escritura), ese número se descarta y se prueba el siguiente. Nunca se sobrescribe ni se reutiliza un token que pertenece a otro valor. Tras `MAX_NUMEROS_DESCARTADOS` (5) números descartados el error ya no es una carrera (`NOT NULL`, `CHECK`, FK) y se relanza el `IntegrityError` original.
- **Fila ilegible.** Si una fila no se descifra con la clave actual (`InvalidTag`: rotación de clave o manipulación), `rehidratar` devuelve `[DATO_BORRADO]` y la sala registra un aviso `bóveda: fila ilegible con la clave actual` en el logger `features.seguridad.pii_internal`, sin token, valor ni conversación.

### `tokenizar_estructura`

Tokeniza recursivamente `dict` (cualquier `Mapping`), `list` y `tuple`, conservando la forma (una tupla sigue siendo tupla). Las claves nunca se tokenizan.

| Valor en la ruta | Tratamiento |
| :--- | :--- |
| Ruta en `campos_pii`, texto no vacío | Se tokeniza entero, como un solo valor. Tipo: el último segmento de la ruta si es un tipo PII (`telefono`, `correo`…); si no, el que el detector reconoce en el valor completo; si no, `nombre`. |
| Ruta en `campos_exentos`, texto que cumple `re.fullmatch(pattern)` | Pasa intacto. Si no lo cumple, pasa por el detector como cualquier texto. |
| Otro texto | Pasa por `tokenizar` (detector). |
| `int`, `float`, `bool`, `None` | Sin cambio, también en rutas declaradas. |
| Cualquier otro tipo (`set`, `bytes`, `Path`, objetos…) | `EstructuraNoAdmitida` (subclase de `ErrorSeguridad` y de `TypeError`, exportada por la compuerta). |

**Nomenclatura de rutas.** `.` anida campos de un mapa (`huesped.contacto.telefono`) y `[]` marca los elementos de una lista o tupla, sin índice (`unidades[].nombre`; los elementos de una raíz lista son `[]`, y sus campos `[].nombre`). Un mismo valor recibe el mismo token en `tokenizar` y en `tokenizar_estructura` dentro de la misma conversación.

## Persistencia y Tablas del Esquema `seguridad`

- `seguridad.usuarios`: Credenciales anonimizadas (hash SHA-256) de colaboradores internos.
- `seguridad.huespedes`: Registro y mapeo de tokens de huéspedes.
- `seguridad.bloqueos`: Lista de números bloqueados indexados por hash SHA-256.
- `seguridad.boveda_tokens`: Almacén cifrado con AES-256-GCM para PII y secretos operativos (`clave_wifi`, `codigo_acceso`).
- `seguridad.rate_limit`: Tablas de recuento de ventanas con resolución de conflictos `INSERT ... ON CONFLICT DO UPDATE`.
- `seguridad.consentimientos`: Registro inmutable de avisos de privacidad y consentimientos otorgados.
- `seguridad.solicitudes_titular`: Registro de derechos ARCO con plazo límite operativo de 15 días y trazabilidad.
- `seguridad.audit_log`: Registro de auditoría append-only para todas las operaciones con RLS.

## Árbitro y Suites de Prueba

- `tests/seguridad/test_identidad.py`
- `tests/seguridad/test_allowlist.py`
- `tests/seguridad/test_rate_limit.py`
- `tests/seguridad/test_pii.py`
- `tests/seguridad/test_audit_log.py`
- `tests/seguridad/test_consentimiento.py`
- `tests/seguridad/test_inventario_datos.py` (Árbitro RF-PRIV-02, RF-PRIV-06: inventario de datos y encargados)
- `tests/seguridad/test_inyecciones.py` (Árbitro RF-SEC-04: neutralización y reincidencias)
- `tests/seguridad/test_retencion.py` (Árbitro RF-PRIV-03: purga automática y preservación estricta de audit log)
- `tests/seguridad/test_criptoborrado.py` (Árbitro RF-PRIV-04: borrado irreversible en bóveda, marcador neutro y audit log intacto)
- `tests/seguridad/test_solicitudes_titular.py` (Árbitro RF-PRIV-05: solicitudes ARCO, 15 días de plazo y conservación legal)
- `tests/seguridad/test_rls.py` (Árbitro RF-SEC-07: migraciones RLS, rol `NOBYPASSRLS`, aislamiento de consultas entre propiedades)
- `tests/seguridad/test_secretos_operativos.py` (Árbitro RF-SEC-08: marcadores `[[SECRETO:...]]`, resolución exclusiva en salida, validación de titular, auditoría y 5 intentos escalando a humano)
- `tests/seguridad/test_t406_contador_tokens.py` y `tests/seguridad/test_t406b_clave_y_estructura.py` (Árbitro T-406 / T-406-b: tokens únicos por conversación, clave efímera, reintento ante colisión y `tokenizar_estructura`)
- `scripts/run_evals.py --suite inyecciones` (Árbitro RF-SEC-04 / OP-10: 0 ataques exitosos y ≤ 2% falsos positivos sobre `evals/inyecciones.jsonl`)

`¤seguridad-canal/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
