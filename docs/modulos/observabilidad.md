# Módulo `observabilidad` — Logs, trazas, evaluaciones y alertas
`¤observabilidad`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/observabilidad/` (+ `scripts/run_evals.py` como CLI, `evals/` como datos) |
| Compuerta | `observabilidad_service.py` → `ObservabilidadService` |
| Privados | `logs_internal.py`, `trazas_internal.py`, `alertas_internal.py`, `metricas_internal.py`, `tipos.py` |
| Config | `config_observabilidad.yaml` |
| Rol | `¤¤devops-engineer` |
| Requisitos | RF-OBS-01..04 · RNF-13 · INV_TRAZA_POR_MENSAJE, INV_PII_FUERA_DEL_MODELO (logs) |
| Tareas | TASK-001 (01, 02), TASK-005 (03, 04), T-402 (03, 04) |

## Propósito
Dar a cada mensaje entrante una traza persistida con *spans* por sala y por llamada al modelo (con cálculo de tokens y costo en USD), emitir logs estructurados JSON sin PII en claro bajo rechazo estricto (`LogConPII`), calcular las métricas del PRD (OP-01..OP-10) directamente a partir de las trazas sin instrumentación extra, despachar evaluaciones automáticas con umbrales rigurosos (`scripts/run_evals.py`) y disparar alertas operativas proactivas ante anomalías en canales, colas, costos y eventos.

## Tipos del dominio (`tipos.py`)

```python
@dataclass(frozen=True)
class Span:
    span_id: str
    traza_id: str
    sala: str
    nombre: str
    inicio: datetime
    duracion_ms: int
    modelo: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    costo_usd: Decimal | None = None
    atributos: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Traza:
    traza_id: str
    mensaje_id: str | None
    conversacion_id: str | None
    canal: str
    inicio: datetime
    fin: datetime | None = None
    resultado: str | None = None
    spans: tuple[Span, ...] = field(default_factory=tuple)

@dataclass(frozen=True)
class Metrica:
    nombre: str
    valor: float
    unidad: str
    ventana: str
    calculada_en: datetime

@dataclass(frozen=True)
class Alerta:
    nombre: str
    severidad: Literal["aviso", "critica"]
    mensaje: str
    disparada_en: datetime
```

## Arquitectura de Módulos Privados

- **`logs_internal.py` (`LoggerObservabilidad`):** Emite logs estructurados JSON por línea con `timestamp`, `nivel`, `evento`, `conversacion_id`, `propiedad_id`, `rol`, `sala`, `duracion_ms`. Implementa detección coercitiva de PII (teléfonos y correos electrónicos). Si `redaccion_verificada: true` y un log contiene PII en claro, rechaza el registro lanzando `LogConPII`. Permite redacción con `redactar_pii(...)` y emisión a `stdout` o `archivo`.
- **`trazas_internal.py` (`GestorTrazas`, `AlmacenTrazas`):** Persiste trazas y spans en SQLite/PostgreSQL según el `esquema observabilidad`. Instrumenta spans con context manager midiendo la duración en milisegundos (`duracion_ms`). Calcula tokens de entrada/salida y costo estimado en USD (`costo_usd`) redondeado a 6 decimales según la tabla de precios configurada.
- **`metricas_internal.py` (`calcular_metricas_prd`):** Calcula las métricas operativas completas del PRD (OP-01..OP-10) directamente desde las trazas y spans sin instrumentación secundaria:
  - `OP-01`: Latencia P95 canal huéspedes sin herramientas (meta ≤ 5 s).
  - `OP-02`: Latencia P95 canal huéspedes con llamada a PMS (meta ≤ 10 s).
  - `OP-03`: Tasa de conversaciones de huésped resueltas sin handoff (meta ≥ 60 %).
  - `OP-04`: Fidelidad del RAG en spans de conocimiento (meta ≥ 95 %).
  - `OP-05`: Tasa de abstención ante consultas fuera de corpus (meta ≥ 90 %).
  - `OP-06`: Adopción del ARM por vendedores activos (meta ≥ 90 %).
  - `OP-07`: Parsing fiable de ventas extraídas sin corrección (meta ≥ 95 %).
  - `OP-08`: Confirmación inmediata al vendedor: latencia P95 canal ARM (meta ≤ 10 s).
  - `OP-09`: Costo en USD por conversación de huésped resuelta (meta ≤ 0.10 USD).
  - `OP-10`: Inyecciones exitosas no autorizadas (meta = 0).
- **`alertas_internal.py` (`DetectorAlertas`):** Evalúa 7 reglas operativas y dispara alertas tipadas (`Alerta` con severidad `"aviso"` o `"critica"`):
  1. `silencio_webhook`: webhook sin mensajes en > 2h durante horario operativo (08:00 a 20:00).
  2. `tasa_errores_alta`: tasa de errores > 5 % en ventana móvil de 15 minutos.
  3. `cola_crm_congestionada`: más de 10 elementos pendientes en la cola de publicaciones al CRM.
  4. `costo_diario_excedido`: costo acumulado de modelos en el día > umbral configurado (ej. 20 USD).
  5. `evento_muerto_canal`: presencia de evento con estado `'muerto'` en `canal.eventos_entrantes`.
  6. `handoff_desatendido`: handoff sin tomar por un agente humano durante > 15 minutos en `crm.handoffs`.
  7. `venta_no_publicada_24h`: venta en estado `'no_publicada'` o `'pendiente'` tras más de 24 horas.

## Compuerta Pública (`observabilidad_service.py`)

```python
class ObservabilidadService:
    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str = "huespedes") -> str: ...
    def span(self, traza_id: str, sala: str, nombre: str, **atributos: Any) -> ContextManager[Span]: ...
    def cerrar_traza(self, traza_id: str, resultado: str) -> Traza: ...
    def obtener_traza(self, traza_id: str) -> Traza: ...
    def log(self, nivel: str, evento: str, **campos: Any) -> None: ...
    def metricas(self, ventana: str = "7d") -> tuple[Metrica, ...]: ...
    def evaluar(self, suites: tuple[str, ...] = ("rag", "ventas", "inyecciones", "enrutador", "pii")) -> Mapping[str, Mapping[str, float]]: ...
    def alertas_activas(self, fuente_datos: Mapping[str, Any] | None = None) -> tuple[Alerta, ...]: ...
```

## Evaluaciones en CI y Arnés (`scripts/run_evals.py`)
Despacha la ejecución de las suites de evaluación (`rag`, `enrutador`, `ventas`, `inyecciones`, `pii`) consumiendo las compuertas `_service.py` de cada sala y contrastando contra los umbrales de `config_observabilidad.yaml`:
- Si una sala no implementa todavía su evaluador, o su set no tiene casos, se reporta formalmente como `OMITIDA`, **nunca verde ficticio**.
- Si una suite ejecutada no alcanza el umbral especificado, falla con Exit Code 1 (`FALLO_UMBRAL`).

## Configuración (`config_observabilidad.yaml`)
`logs {nivel: INFO, destino: stdout|archivo, ruta: /var/log/glamping, redaccion_verificada: true}`, `trazas {retencion_dias: 90, muestreo: 1.0}`, `costos {tabla_precios_por_modelo}`, `umbrales {rag, ventas, inyecciones, enrutador, pii}`, `alertas {silencio_webhook_horas: 2, tasa_errores_15m: 0.05, cola_crm_max: 10, costo_diario_usd: 20, canal_aviso: correo}`.

## Compuertas que consume
- `conocimiento_service.evaluar` (suite RAG)
- `agente_service.evaluar` (suite enrutador)
- `arm_jarvis_service.evaluar` (suite ventas)
- `seguridad_service.evaluar` (suite inyecciones / PII)

## Errores
- `TrazaDesconocida`: la traza solicitada no existe o no ha sido creada.
- `LogConPII`: se rechaza el registro de log por contener información personal en claro (`INV_PII_FUERA_DEL_MODELO`).
- `SuiteNoEncontrada`: suite de evaluación desconocida.

## Persistencia (`esquema observabilidad`)
- `observabilidad.trazas`: `traza_id PK, mensaje_id, conversacion_id, canal, resultado, iniciada, cerrada`.
- `observabilidad.spans`: `span_id PK, traza_id FK, sala, nombre, inicio, duracion_ms, modelo, tokens_in, tokens_out, costo_usd, atributos`.
- `observabilidad.evaluaciones`: ejecuciones históricas de suites.
- `observabilidad.alertas`: historial de alertas.
- `observabilidad.cuota_inferencia`: `dia PK (AAAA-MM-DD, día del Pacífico como las cuotas de Google Cloud; ADR-0021, enmienda 1), gastado_micro bigint ≥ 0`. Tope diario del gasto en inferencia (ADR-0021, K1).

### Runbook: cuota de inferencia en PostgreSQL

- La tabla la crea la migración `202611250145_observabilidad_cuota_inferencia.sql` y el permiso de `app_glamping` (SELECT, INSERT, UPDATE; sin DELETE) lo da `202611250146_seguridad_permisos_cuota_inferencia.sql`. Se aplican con `python scripts/migrar_db.py --url <DATABASE_URL>` antes de desplegar.
- **Sin la tabla, la cuota niega toda inferencia** (falla cerrada): el síntoma es que el agente nunca llama al modelo. Se comprueba con `SELECT * FROM observabilidad.cuota_inferencia ORDER BY dia DESC LIMIT 3;`.
- La reserva es un único `UPDATE … WHERE gastado_micro + costo <= tope RETURNING`; varias instancias de Cloud Run comparten el tope sin pasarlo. La prueba `tests/observabilidad/test_k1_cuota_postgresql.py` lo verifica en CI con `TEST_DATABASE_URL`.
- Si la base cae entre reservar y conciliar, la reserva del peor caso se queda y aparece la alerta `conciliacion_fallida` (contador del proceso; se reinicia al reiniciar la instancia).
- El día cambia a medianoche del Pacífico (`America/Los_Angeles`): a las 03:00 de Ecuador desde el primer domingo de noviembre hasta el segundo domingo de marzo, y a las 02:00 el resto del año.
- En `APP_ENV=produccion` sin una `DATABASE_URL` de PostgreSQL, `construir()` no inyecta la cuota (sería por instancia, en SQLite en memoria): la inferencia queda no disponible con motivo `sin_tope_diario` (falla cerrada, r4). Se prueba en `tests/app_core/test_r4_cuota_produccion.py`.
- Ajuste manual de un día (solo con el propietario): `UPDATE observabilidad.cuota_inferencia SET gastado_micro = 0 WHERE dia = 'AAAA-MM-DD';`, como un rol con permiso de escritura.

## Tests (árbitro)
- `tests/observabilidad/test_logs.py`: rechazo de PII en claro, campos requeridos, ausencia de patrones.
- `tests/observabilidad/test_trazas.py`: traza por mensaje, 3 spans persistidos y recuperados, cálculo de tokens y costo.
- `tests/observabilidad/test_metricas.py`: cálculo unificado OP-01..OP-10 a partir de trazas sintéticas.
- `tests/observabilidad/test_alertas.py`: disparo sintético de cada una de las 7 condiciones de alerta.
- `tests/observabilidad/test_evaluaciones.py`: falla de evaluación bajo umbral con exit code ≠ 0 y omisión sin falsos verdes.

`¤observabilidad/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
