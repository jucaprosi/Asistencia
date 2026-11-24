# Módulo `agente` — Agente Google Gemini / Claude y enrutador multi-propiedad
`¤agente-enrutador`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/agente/` |
| Compuerta | `agente_service.py` → `AgenteService` |
| Privados | `enrutador_internal.py`, `prompts_internal.py`, `bucle_herramientas_internal.py`, `memoria_internal.py`, `cache_internal.py`, `cliente_modelo_internal.py`, `tipos.py` |
| Config | `config_agente.yaml` |
| Rol | `¤¤machine-learning-engineer` |
| Requisitos | RF-AG-01..07 · RNF-01, 02, 16 · INV_PROPIEDAD_RESUELTA, INV_SIN_FUGA_ENTRE_PROPIEDADES, INV_CACHE_SIN_PRECIOS, INV_PII_FUERA_DEL_MODELO |
| Tareas | TASK-001 (02, 04, 05, 06), TASK-004 (01, 03), TASK-005 (07), T-903 (ADR-0019) |

## Propósito
Atender conversaciones de huéspedes: resolver la propiedad, componer el prompt del glamping/propiedad aislando datos sintéticos, exponer solo las herramientas del rol, ejecutar el bucle de *tool use* con Google Gemini (`gemini-3.8-flash` y `gemini-3.5-flash-lite` vía Vertex AI, a través de la compuerta de la sala `inferencia`; ADR-0021) con tope de 6 iteraciones, mantener memoria persistida de los últimos 30 mensajes (24 horas) redactada de PII y degradar de forma explícita ante caídas de servicios externos o del modelo. El ARM consume el modelo por la misma compuerta `inferencia_service.py`, no por esta sala: compuerta de inferencia inyectada por `app_core` (ADR-0021).

## Tipos del dominio (`tipos.py`)

```python
class ModoAgente(str, Enum): ACTIVO, SILENCIO           # silencio durante handoff
@dataclass(frozen=True)
class ContextoConversacion: conversacion_id: str; identidad_token: str; rol: str; propiedad_id: str | None; modo: ModoAgente; ventana_24h_hasta: datetime | None
@dataclass(frozen=True)
class Respuesta: texto: str; botones: tuple[tuple[str, str], ...]; lista: tuple[tuple[str, str], ...]; herramientas_usadas: tuple[str, ...]; chunks_citados: tuple[str, ...]; modelo: str; tokens_in: int; tokens_out: int; costo_usd: Decimal; degradada: bool
@dataclass(frozen=True)
class ResolucionPropiedad: propiedad_id: str | None; metodo: Literal["codigo_reserva", "nombre", "direccion", "contexto", "pregunta"]; candidatas: tuple[str, ...]
@dataclass(frozen=True)
class LlamadaHerramienta: id: str; nombre: str; argumentos: Mapping[str, Any]
@dataclass(frozen=True)
class RespuestaModelo: texto: str; llamadas_herramientas: tuple[LlamadaHerramienta, ...]; tokens_in: int; tokens_out: int; costo_usd: Decimal; modelo: str
@dataclass(frozen=True)
class MensajeMemoria: mensaje_id: str; conversacion_id: str; direccion: Literal["in", "out"]; tipo: str; contenido_token: str; traza_id: str | None; instante: datetime
```

## Arquitectura de Módulos Privados

- **`prompts_internal.py` (`PromptsManager`):** Carga en arranque la plantilla `docs/prompts/system-prompt-glamping.md` e inyecta únicamente los datos sintéticos de la propiedad resuelta (`config_agente.yaml`). Garantiza `INV_SIN_FUGA_ENTRE_PROPIEDADES` asegurando que variables de una propiedad nunca se mezclan con otra. Calcula el hash SHA-256 canónico del prompt para versionarlo en cada traza de observabilidad.
- **`cliente_modelo_internal.py` (`ClienteModelo`, `DobleClienteModelo`):** Gestiona la comunicación con el modelo de lenguaje aplicando timeout de 30 s (`timeout_modelo_s`). Mide tokens entrantes y salientes y calcula costos en USD. Ante timeouts lanza `TimeoutModelo` y ante errores lanza `ModeloNoDisponible`. Incluye doble de pruebas programable para simulaciones clean-room.
- **`bucle_herramientas_internal.py` (`BucleHerramientas`):** Orquesta el ciclo de invocación al modelo y ejecución de herramientas con tope por defecto de 6 iteraciones (`tope_iteraciones`). Verifica `INV_PROPIEDAD_RESUELTA` antes de despachar herramientas que requieren propiedad. Emite acuse «un momento…» si una herramienta tarda más de 3 s (`acuse_si_tarda_s`), registrando `acuse_espera_herramienta` en observabilidad y notificando por canal. Si una herramienta falla o el PMS/RAG cae, no inventa disponibilidad ni datos; genera respuesta degradada ofreciendo handoff humano configurado y registra el motivo en la traza. Si el bucle supera 6 iteraciones, escala con motivo `limite_iteraciones`.
- **`cache_internal.py` (`CacheSemantico`, `seleccionar_modelo`):** Implementa el caché semántico persistente (`agente_cache_semantico`) y el enrutamiento inteligente entre modelo principal (`claude-opus-5-5`) y económico (`claude-haiku-5-5`). Garantiza la invariante `INV_CACHE_SIN_PRECIOS`: rechaza almacenar o servir respuestas o consultas que contengan términos de precio, costo, tarifa, cotización o disponibilidad. Enruta preguntas frecuentes de bajo riesgo (horario, ubicación, wifi, clima) al modelo económico y consultas críticas o con herramientas al modelo principal, registrando la decisión en la traza para auditar RNF-16 (costo ≤ 0.10 USD).
- **`memoria_internal.py` (`MemoriaConversacion`):** Persiste el estado de las conversaciones y los mensajes en tablas SQLite/PostgreSQL que implementan el `esquema agente`. Aplica la invariante `INV_PII_FUERA_DEL_MODELO`: almacena exclusivamente `contenido_token` (redactado de PII). Recupera los últimos 30 mensajes dentro de una ventana de 24 horas. Permite la conservación íntegra del contexto y el historial tras reinicios simulados del contenedor.

## Compuerta (`agente_service.py`)

```python
class AgenteService:
    def atender(self, mensaje: MensajeLimpio) -> Respuesta: ...                               # entrada principal (RF-AG-04, 05)
    def resolver_propiedad(self, mensaje: MensajeLimpio, contexto: ContextoConversacion) -> ResolucionPropiedad: ...  # RF-AG-01 (TASK-004)
    def herramientas_para(self, rol: str, propiedad_id: str | None) -> tuple[str, ...]: ...   # RF-AG-03 (TASK-004)
    def entrar_en_silencio(self, conversacion_id: str, motivo: str) -> None: ...               # handoff
    def reanudar(self, conversacion_id: str) -> None: ...
    def enviar_checkins_del_dia(self, fecha: date) -> int: ...                                 # tarea programada (US-03)
    def contexto(self, conversacion_id: str) -> ContextoConversacion: ...                     # RF-AG-06
```

## Configuración (`config_agente.yaml`)
`modelos {principal: ${MODELO_PRINCIPAL}, economico: ${MODELO_ECONOMICO}}`, `clave_api: ${ANTHROPIC_API_KEY}`, `tope_iteraciones: 6`, `timeout_modelo_s: 30`, `memoria {mensajes: 30, horas: 24}`, `prompts {enrutador: docs/prompts/system-prompt-enrutador.md, glamping: ..., departamentos: ...}`, `propiedades {glamping: {...}, departamento_centro: {...}}`, `escalamiento {contacto_humano_defecto, nombre_gestor_defecto}`.

## Compuertas que consume
`seguridad` (`autorizar`, `tokenizar`/`rehidratar` vía `filtrar_salida`), `herramientas_glamping` (ejecución de herramientas), `conocimiento` (recuperación para preguntas sin herramienta), `pms_conector` (solo a través de herramientas; nunca directo), `canal_whatsapp` (`enviar`, `enviar_plantilla` para check-in), `observabilidad` (iniciar traza, spans, logs estructurados, cerrar traza).

## Errores
`PropiedadAmbigua` (se convierte en pregunta con lista), `ModeloNoDisponible` (→ respuesta degradada + handoff), `TimeoutModelo` (→ degradada + handoff), `TopeIteraciones` (→ escalamiento con motivo limite_iteraciones), `HerramientaFallida` (se comunica sin inventar disponibilidad/datos), `PropiedadRequeridaNoResuelta` (violación de `INV_PROPIEDAD_RESUELTA`), `ConversacionEnSilencio` (no responde).

## Persistencia (`esquema agente`)
- `agente.conversaciones`: `conversacion_id PK, identidad_token, canal, propiedad_id, estado, modo, resultado, abstenciones_seguidas, ventana_24h_hasta, creada, actualizada`.
- `agente.mensajes`: `mensaje_id PK, conversacion_id FK, direccion, tipo, contenido_token, traza_id, instante`.
- `agente.envios_programados`: `codigo_reserva, plantilla, fecha, mensaje_id, creado_en PK (codigo_reserva, plantilla, fecha)` (`INV_ENVIO_UNICO`).
- `agente.cache_semantico`: `hash_consulta PK, embedding, respuesta, creado_en, expira_en`.

## Invariantes Garantizadas
- **`INV_PII_FUERA_DEL_MODELO`:** Todo texto ingresado al modelo y almacenado en `agente.mensajes` (`contenido_token`) está purificado de PII. La rehidratación a texto claro se ejecuta exclusivamente al retornar vía `seguridad_service.filtrar_salida`.
- **`INV_PROPIEDAD_RESUELTA`:** Ninguna herramienta con dependencia de propiedad se ejecuta sin que `propiedad_id` esté previamente validado y resuelto en el contexto. Ante ambigüedad, el agente pregunta con lista de opciones sin invocar herramientas.
- **`INV_SIN_FUGA_ENTRE_PROPIEDADES`:** La renderización de prompts aísla estrictamente la información de cada propiedad sin filtrar datos de inmuebles vecinos.
- **`INV_ENVIO_UNICO`:** `enviar_checkins_del_dia` aplica `INSERT ... ON CONFLICT DO NOTHING` en `agente.envios_programados` garantizando que una reserva no reciba instrucciones duplicadas en un mismo día tras reinicios.
- **`INV_ALLOWLIST_POR_ACCION`:** La compuerta expone y permite únicamente las herramientas explícitamente autorizadas para el rol del remitente, registrando el conjunto expuesto en la traza.
- **`INV_CACHE_SIN_PRECIOS`:** `servida_de_cache(r) ⇒ ¬contiene(r, precio ∨ disponibilidad)`. Se rechaza almacenar o servir respuestas o consultas que incluyan precios, tarifas, cotizaciones, costos o cupos, canalizándolas siempre a través del modelo principal.

## Tests (árbitro)
`tests/agente/test_prompts.py`, `tests/agente/test_bucle_herramientas.py`, `tests/agente/test_degradacion.py`, `tests/agente/test_memoria.py`, `tests/agente/test_enrutador.py`, `tests/agente/test_allowlist_herramientas.py`, `tests/agente/test_planificador.py`, `tests/agente/test_enrutamiento_modelos.py`. Suite de evaluación: `evals/enrutador.jsonl` (20/20 aciertos en CI).

`¤agente-enrutador/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
