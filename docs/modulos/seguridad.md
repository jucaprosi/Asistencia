# Módulo `seguridad` — Seguridad del canal
`¤seguridad-canal`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/seguridad/` |
| Compuerta | `seguridad_service.py` → `SeguridadService` |
| Privados | `identidad_internal.py`, `allowlist_internal.py`, `rate_limit_internal.py`, `injection_internal.py`, `pii_internal.py`, `audit_internal.py`, `tipos.py` |
| Config | `config_seguridad.yaml` |
| Rol | `¤¤security-engineer` |
| Requisitos | RF-SEC-01..08, RF-PRIV-01..06 · RNF-07, 17 · INV_WHITELIST_PRIMERO, INV_PII_FUERA_DEL_MODELO, INV_RATE_LIMIT_NO_ANULABLE, INV_ALLOWLIST_POR_ACCION, INV_INYECCION_CERO, INV_AUDIT_APPEND_ONLY, INV_RLS_MULTI_INQUILINO |
| Tareas | TASK-001 (01, 03, 05), TASK-005 (02, 04, 06, 07) |

## Propósito
Todo mensaje entrante la atraviesa antes del agente o del ARM; toda salida la atraviesa antes del gateway. Es la única sala que ve PII en claro (bóveda de tokens) y la que autoriza cada herramienta por rol.

## Tipos del dominio

```python
class Rol(str, Enum): HUESPED, VENDEDOR, LIDER, GESTOR, ADMINISTRADOR, DESCONOCIDO
@dataclass(frozen=True)
class Identidad: remitente_token: str; rol: Rol; sujeto_id: str | None   # huesped_id | vendedor_id | usuario_id
@dataclass(frozen=True)
class MensajeLimpio: identidad: Identidad; texto_tokenizado: str; marcas: tuple[str, ...]; conversacion_id: str
@dataclass(frozen=True)
class Veredicto: permitido: bool; motivo: str | None; escalar: bool
@dataclass(frozen=True)
class EventoAuditoria: actor_token: str; rol: Rol; accion: str; herramienta: str | None; propiedad_id: str | None; resultado: str; hash_prompt: str | None; traza_id: str
```

## Compuerta

```python
class SeguridadService:
    def identificar(self, remitente: str) -> Identidad: ...                                   # bloqueos, usuarios y reservas → rol (RF-SEC-01)
    def filtrar_entrada(self, remitente: str, texto: str, canal: str) -> MensajeLimpio | Veredicto: ...  # rate limit + injection + PII
    def autorizar(self, rol: Rol, herramienta: str) -> Veredicto: ...                          # allowlist (RF-SEC-02)
    def tokenizar(self, texto: str, conversacion_id: str) -> str: ...                          # PII → tokens (RF-SEC-05)
    def rehidratar(self, texto: str, conversacion_id: str) -> str: ...
    def filtrar_salida(self, texto: str, conversacion_id: str) -> str: ...                     # rehidrata + verifica interfaz purificada
    def auditar(self, evento: EventoAuditoria) -> None: ...                                    # RF-SEC-06 (INSERT only)
    def informe_semanal(self, desde: date, hasta: date) -> bytes: ...                           # CSV para revisión manual
    def administrar_usuarios(self, actor: Identidad, numero: str, rol: Rol, alta: bool) -> None: ...  # solo ADMINISTRADOR
```

## Configuración (`config_seguridad.yaml`)
`identidad {canal_huespedes: abierto, fuente_usuarios, fuente_bloqueos}`, `allowlist` por rol idéntica a [`dominio.yaml`](../spec/contratos/dominio.yaml), `rate_limit`, `injection`, `pii`, `rls`.

## Compuertas que consume
`observabilidad` (traza). Ninguna otra: la seguridad no depende de nadie.

## Errores
`RemitenteNoAutorizado` (se registra, no se responde), `LimiteExcedido`, `AccionNoAutorizada`, `InyeccionDetectada`, `TokenDesconocido` (rehidratación), `ActorSinPrivilegio`.

## Persistencia (`esquema seguridad`)
Tablas del esquema `seguridad` en [`esquema.sql`](../spec/esquema.sql): `usuarios`, `bloqueos`, `boveda_tokens` (cifrada con `PII_VAULT_KEY`), `rate_limit`, `consentimientos`, `solicitudes_titular` y `audit_log` (solo `INSERT`).

## Tests (árbitro)
`tests/seguridad/test_identidad.py`, `test_allowlist.py` (enumera cada rol), `test_rate_limit.py` (intenta desactivarlo con cada rol), `test_pii.py` (captura del cliente HTTP al modelo), `test_audit_log.py` (UPDATE/DELETE fallan), `test_rls.py` (PostgreSQL real); `scripts/run_evals.py --suite inyecciones`.

`¤seguridad-canal/`
