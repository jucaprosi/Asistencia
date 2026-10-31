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
| Tareas | TASK-001 (01, 02), TASK-005 (03, 04) |

## Propósito
Dar a cada mensaje una traza con *spans* por sala y por llamada al modelo, emitir logs JSON sin PII, calcular las métricas del PRD a partir de las trazas, ejecutar las evaluaciones con umbral y disparar alertas.

## Tipos del dominio

```python
@dataclass(frozen=True)
class Span: span_id: str; traza_id: str; sala: str; nombre: str; inicio: datetime; duracion_ms: int; atributos: Mapping[str, Any]   # modelo, tokens, costo, chunks, herramientas
@dataclass(frozen=True)
class Traza: traza_id: str; mensaje_id: str | None; conversacion_id: str | None; canal: str; inicio: datetime; fin: datetime | None; resultado: str | None; spans: tuple[Span, ...]
@dataclass(frozen=True)
class Metrica: nombre: str; valor: float; unidad: str; ventana: str; calculada_en: datetime
@dataclass(frozen=True)
class Alerta: nombre: str; severidad: Literal["aviso", "critica"]; mensaje: str; disparada_en: datetime
```

## Compuerta

```python
class ObservabilidadService:
    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str) -> str: ...   # traza_id
    def span(self, traza_id: str, sala: str, nombre: str) -> ContextManager[Span]: ...                     # with obs.span(...): ...
    def cerrar_traza(self, traza_id: str, resultado: str) -> Traza: ...
    def log(self, nivel: str, evento: str, **campos: Any) -> None: ...                                      # JSON, sin PII (se verifica)
    def metricas(self, ventana: str = "7d") -> tuple[Metrica, ...]: ...                                     # OP-01..OP-10 calculables
    def evaluar(self, suites: tuple[str, ...] = ("rag", "ventas", "inyecciones", "enrutador")) -> Mapping[str, Mapping[str, float]]: ...
    def alertas_activas(self) -> tuple[Alerta, ...]: ...
```

## Configuración (`config_observabilidad.yaml`)
`logs {nivel: INFO, destino: stdout|archivo, ruta: /var/log/glamping, redaccion_verificada: true}`, `trazas {retencion_dias: 90, muestreo: 1.0}`, `costos {tabla_precios_por_modelo}`, `umbrales {rag: {fidelidad: 0.95, abstencion: 0.90}, ventas: {exactitud: 0.95}, inyecciones: {exitos: 0}, enrutador: {aciertos: 1.0}}`, `alertas {silencio_webhook_horas: 2, tasa_errores_15m: 0.05, cola_crm_max: 10, costo_diario_usd: ${COSTO_DIARIO_MAX}, canal_aviso: correo|whatsapp_admin}`.

## Compuertas que consume
Ninguna (es la base). Las demás la consumen.

## Errores
`TrazaDesconocida`, `LogConPII` (se bloquea el registro y se emite un log de advertencia sin el contenido), `SuiteNoEncontrada`.

## Persistencia (`esquema observabilidad`)
`trazas(traza_id PK, mensaje_id, conversacion_id, canal, inicio, fin, resultado)`, `spans(span_id PK, traza_id FK, sala, nombre, inicio, duracion_ms, atributos_json)`, `evaluaciones(ejecucion_id, suite, metrica, valor, umbral, ok, commit, ejecutada_en)`, `alertas(...)`. Logs en volumen separado del flujo contable.

## Tests (árbitro)
`tests/observabilidad/test_logs.py` (sin patrones de teléfono/correo), `test_trazas.py` (100 % de mensajes), `test_alertas.py` (cada alerta con datos sintéticos); `scripts/run_evals.py` como parte del arnés.

`¤observabilidad/`
