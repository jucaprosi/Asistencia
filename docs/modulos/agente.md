# Módulo `agente` — Agente Claude y enrutador multi-propiedad
`¤agente-enrutador`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/agente/` |
| Compuerta | `agente_service.py` → `AgenteService` |
| Privados | `enrutador_internal.py`, `prompts_internal.py`, `bucle_herramientas_internal.py`, `memoria_internal.py`, `cache_internal.py`, `cliente_modelo_internal.py`, `tipos.py` |
| Config | `config_agente.yaml` |
| Rol | `¤¤machine-learning-engineer` |
| Requisitos | RF-AG-01..07 · RNF-01, 02, 16 · INV_PROPIEDAD_RESUELTA, INV_SIN_FUGA_ENTRE_PROPIEDADES, INV_CACHE_SIN_PRECIOS |
| Tareas | TASK-001 (02, 04, 05, 06), TASK-004 (01, 03), TASK-005 (07) |

## Propósito
Atender conversaciones de huéspedes: resolver la propiedad, componer el prompt, exponer solo las herramientas del rol, ejecutar el bucle de *tool use* con Claude, mantener memoria y degradar de forma explícita. El ARM tiene su propio cliente de modelo (DPD): esta sala no lo atiende.

## Tipos del dominio

```python
class ModoAgente(str, Enum): ACTIVO, SILENCIO           # silencio durante handoff
@dataclass(frozen=True)
class ContextoConversacion: conversacion_id: str; identidad_token: str; rol: str; propiedad_id: str | None; modo: ModoAgente; ventana_24h_hasta: datetime | None
@dataclass(frozen=True)
class Respuesta: texto: str; botones: tuple[tuple[str, str], ...]; lista: tuple[tuple[str, str], ...]; herramientas_usadas: tuple[str, ...]; chunks_citados: tuple[str, ...]; modelo: str; tokens_in: int; tokens_out: int; costo_usd: Decimal; degradada: bool
@dataclass(frozen=True)
class ResolucionPropiedad: propiedad_id: str | None; metodo: Literal["codigo_reserva", "nombre", "direccion", "contexto", "pregunta"]; candidatas: tuple[str, ...]
```

## Compuerta

```python
class AgenteService:
    def atender(self, mensaje: MensajeLimpio) -> Respuesta: ...                               # entrada principal
    def resolver_propiedad(self, mensaje: MensajeLimpio, contexto: ContextoConversacion) -> ResolucionPropiedad: ...  # RF-AG-01
    def herramientas_para(self, rol: str, propiedad_id: str | None) -> tuple[str, ...]: ...   # RF-AG-03
    def entrar_en_silencio(self, conversacion_id: str, motivo: str) -> None: ...               # handoff
    def reanudar(self, conversacion_id: str) -> None: ...
    def enviar_checkins_del_dia(self, fecha: date) -> int: ...                                 # tarea programada (US-03)
    def contexto(self, conversacion_id: str) -> ContextoConversacion: ...
```

## Configuración (`config_agente.yaml`)
`modelos {principal: ${MODELO_PRINCIPAL}, economico: ${MODELO_ECONOMICO}}`, `clave_api: ${ANTHROPIC_API_KEY}`, `tope_iteraciones: 6`, `timeout_modelo_s: 30`, `memoria {mensajes: 30, horas: 24}`, `prompts {enrutador: docs/prompts/system-prompt-enrutador.md, glamping: ..., departamentos: ...}`, `cache_semantico {activo: true, umbral_similitud: 0.92, excluir_si_contiene: [precio, tarifa, disponib, cancel]}`, `enrutamiento_modelos {economico_para: [horario, ubicacion, wifi, atractivos]}`, `acuse_si_tarda_s: 3`.

## Compuertas que consume
`seguridad` (`autorizar`, `tokenizar`/`rehidratar` vía `filtrar_salida`), `herramientas_glamping` (ejecución de herramientas), `conocimiento` (recuperación para preguntas sin herramienta), `pms_conector` (solo a través de herramientas; nunca directo), `canal_whatsapp` (`enviar`, `enviar_plantilla` para check-in), `observabilidad` (spans por llamada al modelo).

## Errores
`PropiedadAmbigua` (se convierte en pregunta con lista), `ModeloNoDisponible` (→ respuesta degradada + handoff), `TopeIteraciones` (→ escalamiento), `HerramientaFallida` (se comunica sin inventar), `ConversacionEnSilencio` (no responde).

## Persistencia (`esquema agente`)
`conversaciones(conversacion_id PK, identidad_token, canal, propiedad_id, estado, modo, ventana_24h_hasta, crm_ref, creada, actualizada)`; `mensajes(mensaje_id PK, conversacion_id, direccion, tipo, contenido_token, plantilla, estado_entrega, traza_id, timestamp)`; `cache_semantico(hash_consulta, embedding, respuesta, creado_en, expira_en)`.

## Tests (árbitro)
`tests/agente/test_enrutador.py` (20 conversaciones), `test_prompts.py`, `test_allowlist_herramientas.py`, `test_bucle_herramientas.py`, `test_degradacion.py`, `test_memoria.py`, `test_enrutamiento_modelos.py`; `scripts/run_evals.py --suite enrutador`.

`¤agente-enrutador/`
