# Módulo `anfitriones`
`¤anfitriones`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/anfitriones/` |
| Requisitos | [`PRD.md` §5.13](../PRD.md) (RF-ANF-01..08) |
| Decisión | [ADR-0018](../adr/ADR-0018-plataforma-local-de-hospedajes.md) |

## Propósito
Dueña de los anfitriones, la publicación de hospedajes, la solicitud de reserva y la comisión que la plataforma cobra al anfitrión. No mueve dinero: emite estados de cuenta y registra pagos. La comisión de vendedores sigue en `comisiones`.

## Compuerta

```python
class AnfitrionesService:
    def registrar_anfitrion(self, anfitrion: Anfitrion, telefono_token: str, actor_id: str) -> Anfitrion: ...
    def guardar_hospedaje(self, hospedaje: Hospedaje, actor_id: str) -> Hospedaje: ...
    def publicados(self) -> tuple[Hospedaje, ...]: ...             # solo publicados de anfitriones activos
    def solicitar_reserva(self, codigo_reserva: str) -> Solicitud: ...  # fechas y total salen del PMS
    def responder_solicitud(self, solicitud: str, anfitrion_id: str, acepta: bool, motivo: str | None) -> Solicitud: ...
    def reportar_resultado(self, solicitud: str, anfitrion_id: str, resultado: EstadoSolicitud) -> Solicitud: ...
    def cerrar_periodo(self, periodo: str) -> tuple[EstadoDeCuenta, ...]: ...
    def estado_de_cuenta(self, anfitrion_id: str, periodo: str) -> EstadoDeCuenta: ...
    def registrar_pago(self, estado_cuenta_id: str, actor_id: str) -> EstadoDeCuenta: ...
```

## Reglas
- `comision = redondear(total × porcentaje / 100)`, con el porcentaje congelado al crear la solicitud.
- Una estadía confirmada pasa a `completada` si el anfitrión no reporta otra cosa en `reporte_estadia_dias`.
- `no_show` y `cancelada` no generan comisión.
- El período es el mes de `hasta` en `America/Guayaquil`. Lo completado tras un cierre entra al período abierto.

## Configuración (`config_anfitriones.yaml`)
Vigencia de la solicitud, días para reportar, día de cierre, plazo de pago y días para pausar tras un vencimiento.

## Compuertas que consume
`seguridad_service`, `canal_whatsapp_service`, `pms_conector_service` y `observabilidad_service`.

## Errores
`ErrorAnfitriones` con `mensaje_usuario`.

## Persistencia (`esquema anfitriones`)
`anfitriones`, `hospedajes`, `solicitudes`, `estados_cuenta` y `lineas_cuenta`. El teléfono se guarda como token.

## Tests (árbitro)
`tests/anfitriones/test_publicacion.py`, `test_solicitudes.py`, `test_resultado.py`, `test_estado_cuenta.py`, `test_aislamiento.py`.

`¤anfitriones/`
