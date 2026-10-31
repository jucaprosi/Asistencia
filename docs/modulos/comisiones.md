# Módulo `comisiones` — Reglas, cálculo y cierre de período
`¤comisiones`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/comisiones/` |
| Compuerta | `comisiones_service.py` → `ComisionesService` |
| Privados | `reglas_internal.py`, `periodo_internal.py`, `exportacion_internal.py`, `esquema_exportacion.json`, `tipos.py` |
| Config | `config_comisiones.yaml` |
| Rol | `¤¤backend-developer` |
| Requisitos | RF-COM-01..03 · INV_COMISION_REPRODUCIBLE |
| Tareas | TASK-006 (01, 02), TASK-007 (03) |
| Decisión | Construir; sistema de registro `[DECISIÓN PENDIENTE]` ADR-0009 (recomendado: esta sala) |

## Propósito
Calcular comisiones de forma reproducible con reglas versionadas vigentes a la fecha de la venta, cerrar períodos inmutables con ajustes en el siguiente y exportar para contabilidad.

## Tipos del dominio

```python
class TipoRegla(str, Enum): PORCENTAJE, FIJO, ESCALONADA
class ModoEscalon(str, Enum): GRADUADO, VOLUMEN
@dataclass(frozen=True)
class Escalon: desde_monto: Decimal; porcentaje: Decimal
@dataclass(frozen=True)
class ReglaComision: regla_id: str; version: int; vendedor_id: str | None; propiedad_id: str | None; producto_patron: str | None; tipo: TipoRegla; valor: Decimal; escalones: tuple[Escalon, ...]; modo_escalon: ModoEscalon; vigente_desde: date; vigente_hasta: date | None
class EstadoComision(str, Enum): ESTIMADA, FIJADA, PAGADA, AJUSTADA
@dataclass(frozen=True)
class Comision: comision_id: str; venta_id: str; regla_id: str; regla_version: int; monto: Decimal; periodo_id: str; estado: EstadoComision; ajuste_de: str | None
@dataclass(frozen=True)
class Periodo: periodo_id: str; cerrado_en: datetime | None; cerrado_por: str | None; resumen: Mapping[str, Any]
```

## Compuerta

```python
class ComisionesService:
    def calcular(self, venta_id: str, vendedor_id: str, propiedad_id: str | None, producto: str, monto: Decimal, fecha_venta: date) -> Comision: ...  # ESTIMADA
    def fijar(self, comision_id: str) -> Comision: ...                                        # al validar la venta → recalcula con la base actual; FIJADA, inmutable (D-10)
    def resumen(self, vendedor_id: str | None, periodo_id: str) -> Mapping[str, Any]: ...      # validada, pendiente, ventas
    def desglose(self, comision_id: str) -> Mapping[str, Any]: ...                             # regla, versión, modo, base y tramos (RF-PAN-03)
    def estado_cuenta(self, vendedor_id: str, periodo_id: str) -> Mapping[str, Any]: ...       # líneas por venta y ajuste (RF-PAN-04)
    def reglas(self, vigentes_en: date | None = None) -> tuple[ReglaComision, ...]: ...
    def crear_regla(self, actor: Identidad, regla: ReglaComision) -> ReglaComision: ...        # nueva versión; nunca edita la anterior
    def cerrar_periodo(self, periodo_id: str, actor: Identidad) -> Periodo: ...                # RF-COM-02
    def ajustar(self, comision_id: str, actor: Identidad, nuevo_monto: Decimal, motivo: str) -> Comision: ...  # crea AJUSTADA en el período abierto
    def exportar(self, periodo_id: str, formato: Literal["csv", "json"]) -> bytes: ...          # RF-COM-03
```

## Configuración (`config_comisiones.yaml`)
`periodo: mensual`, `moneda: USD`, `redondeo {decimales: 2, modo: ROUND_HALF_UP}`, `cierre_automatico_dia: 1`, `esquema_exportacion: esquema_exportacion.json`.

## Compuertas que consume
`seguridad` (`autorizar`, `auditar`), `observabilidad`.

## Errores
`SinReglaVigente`, `PeriodoCerrado`, `ComisionYaFijada`, `ReglaSolapada` (dos reglas vigentes para el mismo ámbito), `ExportacionInvalida` (no valida contra el esquema).

## Persistencia (`esquema comisiones`)
`reglas(regla_id, version, ..., PK(regla_id, version))`, `comisiones(comision_id PK, venta_id, regla_id, regla_version, monto, periodo_id, estado, ajuste_de)`, `periodos(periodo_id PK, cerrado_en, cerrado_por, resumen_json)`; disparador que rechaza `UPDATE` en comisiones de períodos cerrados.

## Tests (árbitro)
`tests/comisiones/test_reglas.py` (vigencia a fecha de venta, versiones), `test_cierre_periodo.py`, `test_exportacion.py` (valida contra esquema).

`¤comisiones/`
