# Módulo `arm_jarvis` — ARM «Jarvis»
`¤arm-jarvis`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/arm_jarvis/` |
| Compuerta | `arm_jarvis_service.py` → `ArmJarvisService` |
| Privados | `extractor_internal.py` (cliente Claude propio), `estados_internal.py`, `ticket_internal.py`, `notificador_internal.py`, `tablero_internal.py`, `asistente_lider_internal.py`, `tipos.py` |
| Config | `config_arm_jarvis.yaml` |
| Rol | `¤¤backend-developer` |
| Requisitos | RF-ARM-01..09 · RNF-03 · INV_ESTADOS_VENTA, INV_COMISION_PROPIA, INV_TICKET_UNICO, INV_VENTA_NO_SE_PIERDE |
| Tareas | TASK-006 (01..07, 09), TASK-007 (08) |
| Decisión | Construir (ADR-0005). La UI de validación, tablero y Jarvis vive en `panel_operativo` (ADR-0013); esta sala expone los casos de uso. |

## Propósito
Convertir mensajes de vendedores en ventas estructuradas, gestionar su ciclo de vida con auditoría, calcular la comisión a través de `comisiones`, confirmar con ticket, notificar al validar, responder consultas de comisión propia, servir los datos del tablero y atender al asistente del líder.

## Tipos del dominio

```python
class EstadoVenta(str, Enum): POR_VALIDAR, VALIDADA, RECHAZADA, PUBLICADA, NO_PUBLICADA, ANULADA
@dataclass(frozen=True)
class Vendedor: vendedor_id: str; telefono_token: str; nombre: str; activo: bool; regla_comision_default_id: str | None
@dataclass(frozen=True)
class VentaExtraida: cliente_token: str | None; telefono_cliente_token: str | None; producto: str | None; propiedad_id: str | None; monto: Decimal | None; moneda: str; fecha_venta: date | None; confianza: float; campos_faltantes: tuple[str, ...]; es_venta: bool
@dataclass(frozen=True)
class Venta: venta_id: str; ticket: str; vendedor_id: str; extraida: VentaExtraida; texto_original_token: str; estado: EstadoVenta; comision_estimada: Decimal | None; comision_fijada: Decimal | None; reserva_ref: str | None; creada: datetime; actualizada: datetime
@dataclass(frozen=True)
class Transicion: venta_id: str; de: EstadoVenta; a: EstadoVenta; actor_id: str; rol: str; motivo: str | None; timestamp: datetime
@dataclass(frozen=True)
class ResumenComision: vendedor_id: str; periodo: str; validada: Decimal; pendiente: Decimal; ventas: int
@dataclass(frozen=True)
class Tablero: periodo: str; ventas_por_mes: tuple[tuple[str, Decimal], ...]; ventas_por_vendedor: tuple[tuple[str, Decimal, int], ...]; ventas_por_propiedad: tuple[tuple[str, Decimal], ...]; comisiones_validadas: Decimal; comisiones_pendientes: Decimal; por_validar: int
```

## Compuerta

```python
class ArmJarvisService:
    def procesar(self, mensaje: MensajeLimpio) -> str: ...                                    # texto de respuesta al vendedor (ticket o pregunta)
    def extraer(self, texto: str) -> VentaExtraida: ...                                       # RF-ARM-02
    def validar(self, venta_id: str, actor: Identidad, correcciones: Mapping[str, Any] | None = None) -> Venta: ...   # RF-ARM-03/04
    def rechazar(self, venta_id: str, actor: Identidad, motivo: str) -> Venta: ...
    def anular(self, venta_id: str, actor: Identidad, motivo: str) -> Venta: ...               # solo administrador
    def marcar_publicacion(self, venta_id: str, ok: bool, detalle: str | None) -> None: ...    # receptor de crm_conector
    def consultar_comision_propia(self, vendedor_id: str, periodo: str | None = None) -> ResumenComision: ...  # RF-ARM-07
    def listar(self, estado: EstadoVenta | None, vendedor_id: str | None, periodo: str | None, pagina: int) -> tuple[Venta, ...]: ...
    def detalle(self, venta_id: str) -> tuple[Venta, tuple[Transicion, ...]]: ...
    def tablero(self, periodo: str) -> Tablero: ...                                            # RF-ARM-08
    def preguntar_jarvis(self, actor: Identidad, pregunta: str, conversacion_id: str) -> str: ...   # RF-ARM-09, solo lectura + cambios con confirmación
    def aplicar_cambio_configuracion(self, actor: Identidad, cambio: Mapping[str, Any], confirmado: bool) -> None: ...
```

## Configuración (`config_arm_jarvis.yaml`, valores por defecto; los cambios de Jarvis se guardan en `arm.configuracion`)
`modelo_extractor: ${MODELO_PRINCIPAL}`, `clave_api: ${ANTHROPIC_API_KEY}`, `canal {modo: grupo|uno_a_uno}`, `ticket {prefijo: V, reinicio: anual}`, `confianza_minima: 0.80`, `campos_obligatorios: [monto, producto]`, `notificaciones {al_validar: true, al_rechazar: true, plantilla: comision_validada}`, `asistente_lider {cambios_permitidos: [notificaciones.al_validar, notificaciones.al_rechazar], requiere_confirmacion: true}`, `evals: evals/ventas.jsonl`.

## Compuertas que consume
`seguridad` (`autorizar`, `auditar`, `rehidratar`), `comisiones` (`calcular`, `fijar`, `resumen`), `crm_conector` (`publicar_venta`), `canal_whatsapp` (`enviar`, `enviar_plantilla`), `observabilidad`.

## Errores
`VendedorNoRegistrado`, `TransicionInvalida`, `CamposFaltantes` (se convierte en pregunta), `NoEsVenta`, `ComisionAjena`, `CambioNoPermitido`, `ConfirmacionRequerida`.

## Persistencia (`esquema arm`)
`vendedores`, `ventas(venta_id PK, ticket UNIQUE, vendedor_id, ..., estado, comision_estimada, comision_fijada, crm_publicacion_estado, creada, actualizada)`, `transiciones(venta_id, de, a, actor_id, rol, motivo, timestamp)`, `secuencia_tickets(anio PK, ultimo)` con bloqueo de fila para `INV_TICKET_UNICO`.

## Tests (árbitro)
`tests/arm_jarvis/test_ingesta.py`, `test_estados.py`, `test_comision.py`, `test_ticket.py` (concurrencia), `test_notificacion.py`, `test_consulta_comision.py`, `test_tablero.py`, `test_asistente_lider.py`; `scripts/run_evals.py --suite ventas`.

`¤arm-jarvis/`
