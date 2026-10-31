# Módulo `app_core` — Pasillo central
`¤pasillo-central`

| Campo | Valor |
| :--- | :--- |
| Ubicación | `app_core/` (no es una sala: es el corredor que las conecta) |
| Archivos | `app_core_service.py` (compuerta: reexporta `construir`, `Contenedor`, `ConfiguracionInvalida`, `resolver_secretos`), `contenedor.py` (privado), `main.py`, `config_app.yaml` |
| Rol | `¤¤solutions-architect` |
| Tarea | TASK-000 |

## Propósito
Arrancar la aplicación, construir cada compuerta con su configuración y secretos, enlazarlas por inyección de dependencias, registrar los puntos de entrada HTTP y disparar las tareas programadas. **No contiene lógica de negocio y no importa ningún módulo privado de ninguna sala.**

## Interfaz

```python
# app_core/contenedor.py
@dataclass(frozen=True)
class Contenedor:
    observabilidad: ObservabilidadService
    seguridad: SeguridadService
    conocimiento: ConocimientoService
    pms: PMSConectorService
    crm: CRMConectorService
    comisiones: ComisionesService
    herramientas: HerramientasGlampingService
    agente: AgenteService
    arm: ArmJarvisService
    canal: CanalWhatsappService
    panel: PanelOperativoService

def construir(ruta_config: Path = RUTA_CONFIG, entorno: Mapping[str, str] = os.environ) -> Contenedor: ...
def resolver_secretos(config: Mapping[str, Any], entorno: Mapping[str, str]) -> Mapping[str, Any]: ...  # ${VAR} y ${VAR:-defecto}
```

```python
# app_core/main.py
def salud() -> dict[str, str]: ...                    # {"estado": "ok", "entorno": "beta", "version": "..."}
def crear_app(contenedor: Contenedor | None = None) -> FastAPI: ...
# Rutas registradas: GET /health · POST /webhook (→ canal) · GET /webhook (verificación Meta)
#                    POST /crm/eventos (→ crm_conector) · /panel/* (→ panel_operativo, BFF y estáticos)
```

Orden de construcción (una compuerta solo recibe las ya construidas): `observabilidad → seguridad → conocimiento → pms → crm → comisiones → canal → arm → herramientas → agente → panel`. El canal se construye antes que `arm` y `agente` porque ambos lo usan para enviar; sus receptores se registran al final con `canal.registrar_receptor` (inversión de dependencias).

## Tareas programadas (disparadas por `app_core`, ejecutadas por compuertas)

| Cron (`config_app.yaml`) | Compuerta | Método |
| :--- | :--- | :--- |
| `checkin_del_dia` | `agente` | `enviar_checkins_del_dia(fecha)` |
| `reintentos_cola_crm` | `crm` | `procesar_cola()` |
| `cierre_periodo_comisiones` | `comisiones` | `cerrar_periodo(periodo_anterior)` |

## Configuración
`config_app.yaml`: nombre, entorno (`beta`/`produccion`), zona horaria, puerto, orden de salas, lista de egreso permitido (RNF-10), crons.

## Errores
`ConfiguracionInvalida` (falta una variable referenciada, YAML inválido) detiene el arranque con mensaje que nombra la variable, nunca su valor.

## Tests (árbitro)
`tests/test_estructura_adpa.py` (solo importa `_service`), `tests/app_core/test_contenedor.py` (construye con `Fake*` y variables de entorno de prueba; falla si falta una variable), `tests/app_core/test_salud.py`.

`¤pasillo-central/`
