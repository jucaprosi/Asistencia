# ¤comisiones
# ¤¤backend-developer
"""Compuerta pública de la sala comisiones (RF-COM-01..04, INV_COMISION_REPRODUCIBLE).

Proporciona cálculo reproducible con reglas versionadas vigentes a la fecha de venta,
cierre inmutable de períodos mensuales, ajustes por anulación y exportación contable.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Mapping
import uuid

import yaml

from features.comisiones.exportacion_internal import exportar_periodo
from features.comisiones.persistencia_internal import PersistenciaComisiones
from features.comisiones.periodo_internal import (
    GestorBloqueos,
    calcular_resumen_periodo,
    periodo_de_fecha,
    resolver_periodo_destino,
)
from features.comisiones.reglas_internal import (
    calcular_F,
    calcular_comision_incremental,
    desglosar_tramos,
    resolver_regla,
    validar_nueva_regla,
)
from features.comisiones.tipos import (
    Comision,
    Escalon,
    EstadoComision,
    ModoEscalon,
    Periodo,
    ReglaComision,
    TipoRegla,
)

__all__ = [
    "Comision",
    "Escalon",
    "EstadoComision",
    "ModoEscalon",
    "Periodo",
    "ReglaComision",
    "TipoRegla",
    "ErrorComisiones",
    "SinReglaVigente",
    "PeriodoCerrado",
    "ComisionYaFijada",
    "ReglaSolapada",
    "ExportacionInvalida",
    "ComisionNoEncontrada",
    "ComisionesService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_comisiones.yaml")


# ¤comisiones
class ErrorComisiones(Exception):
    """Error base tipado de la sala comisiones."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤comisiones
class SinReglaVigente(ErrorComisiones):
    """No existe regla vigente para la fecha de venta (la venta sigue por_validar)."""

    def __init__(self, mensaje: str = "No existe regla vigente para la fecha de venta") -> None:
        super().__init__("SIN_REGLA_VIGENTE", mensaje)


# ¤comisiones
class PeriodoCerrado(ErrorComisiones):
    """El período mensual está cerrado y es inmutable."""

    def __init__(self, mensaje: str = "El período se encuentra cerrado y es inmutable") -> None:
        super().__init__("PERIODO_CERRADO", mensaje)


# ¤comisiones
class ComisionYaFijada(ErrorComisiones):
    """La comisión ya fue fijada previamente."""

    def __init__(self, mensaje: str = "La comisión ya se encuentra fijada") -> None:
        super().__init__("COMISION_YA_FIJADA", mensaje)


# ¤comisiones
class ReglaSolapada(ErrorComisiones):
    """Dos o más reglas vigentes se solapan para el mismo ámbito y fecha."""

    def __init__(self, mensaje: str = "Regla solapada con otra regla vigente") -> None:
        super().__init__("REGLA_SOLAPADA", mensaje)


# ¤comisiones
class ExportacionInvalida(ErrorComisiones):
    """La exportación no cumple el esquema json requerido."""

    def __init__(self, mensaje: str = "La exportación no cumple el esquema requerido") -> None:
        super().__init__("EXPORTACION_INVALIDA", mensaje)


# ¤comisiones
class ComisionNoEncontrada(ErrorComisiones):
    """No se encontró la comisión solicitada."""

    def __init__(self, mensaje: str = "Comisión no encontrada") -> None:
        super().__init__("COMISION_NO_ENCONTRADA", mensaje)


# ¤comisiones
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤comisiones
class ComisionesService:
    """Cálculo reproducible con la regla vigente a la fecha de la venta; períodos cerrados inmutables."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any,
        observabilidad: Any,
        persistencia: PersistenciaComisiones | None = None,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._observabilidad = observabilidad
        self._persistencia = persistencia or PersistenciaComisiones()
        self._bloqueos = GestorBloqueos()

    # ¤comisiones
    def calcular(
        self,
        venta_id: str,
        vendedor_id: str,
        propiedad_id: str | None,
        producto: str,
        monto: Decimal,
        fecha_venta: date,
    ) -> Comision:
        """Calcula una comisión preliminar en estado ESTIMADA usando la regla vigente a fecha_venta."""
        reglas_existentes = self._persistencia.obtener_reglas()
        regla = resolver_regla(reglas_existentes, vendedor_id, propiedad_id, producto, fecha_venta)

        mes_venta = periodo_de_fecha(fecha_venta)
        periodo_destino, periodo_origen, _ = resolver_periodo_destino(self._persistencia, fecha_venta)

        base_actual = self._persistencia.obtener_base_acumulada(vendedor_id, regla.regla_id, mes_venta)
        monto_estimado = calcular_comision_incremental(regla, base_actual, monto)

        comision_id = str(uuid.uuid4())
        comision = Comision(
            comision_id=comision_id,
            venta_id=venta_id,
            regla_id=regla.regla_id,
            regla_version=regla.version,
            monto=monto_estimado,
            periodo_id=periodo_destino,
            estado=EstadoComision.ESTIMADA,
            ajuste_de=None,
            base_acumulada=base_actual,
            periodo_origen=periodo_origen,
            vendedor_id=vendedor_id,
            fecha_venta=fecha_venta,
            monto_venta=monto,
        )
        self._persistencia.guardar_comision(comision)
        return comision

    # ¤comisiones
    def fijar(self, comision_id: str) -> Comision:
        """Fija la comisión al validar la venta, recalculando atómicamente con la base actual."""
        comision_previa = self._persistencia.obtener_comision(comision_id)
        if not comision_previa:
            raise ComisionNoEncontrada(f"No existe comisión con id {comision_id}")

        if comision_previa.estado == EstadoComision.FIJADA:
            raise ComisionYaFijada(f"La comisión {comision_id} ya se encuentra fijada")

        regla = self._persistencia.obtener_regla(comision_previa.regla_id, comision_previa.regla_version)
        if not regla:
            raise SinReglaVigente(f"Regla {comision_previa.regla_id} v{comision_previa.regla_version} no encontrada")

        fecha_v = comision_previa.fecha_venta or date.today()
        mes_venta = periodo_de_fecha(fecha_v)

        with self._bloqueos.obtener_lock(comision_previa.vendedor_id, regla.regla_id, mes_venta):
            periodo_destino, periodo_origen, _ = resolver_periodo_destino(self._persistencia, fecha_v)

            base_actual = self._persistencia.obtener_base_acumulada(
                comision_previa.vendedor_id, regla.regla_id, mes_venta
            )
            monto_fijado = calcular_comision_incremental(regla, base_actual, comision_previa.monto_venta)

            self._persistencia.actualizar_comision_fijada(
                comision_id=comision_id,
                monto=monto_fijado,
                base_acumulada=base_actual,
                periodo_id=periodo_destino,
                periodo_origen=periodo_origen,
            )

        comision_actualizada = self._persistencia.obtener_comision(comision_id)
        if not comision_actualizada:
            raise RuntimeError(f"Error al recuperar comisión {comision_id} recién fijada")
        return comision_actualizada

    # ¤comisiones
    def anular_venta(self, venta_id: str, actor: Any, motivo: str) -> Comision:
        """Crea un ajuste negativo en el período abierto tras anular una venta (RF-COM-04)."""
        if hasattr(self._seguridad, "autorizar"):
            self._seguridad.autorizar(actor, "anular_venta", venta_id)

        comision_orig = self._persistencia.obtener_comision_por_venta(venta_id)
        if not comision_orig:
            raise ComisionNoEncontrada(f"No existe comisión para la venta {venta_id}")

        regla = self._persistencia.obtener_regla(comision_orig.regla_id, comision_orig.regla_version)
        if not regla:
            raise SinReglaVigente(f"Regla {comision_orig.regla_id} v{comision_orig.regla_version} no encontrada")

        fecha_v = comision_orig.fecha_venta or date.today()
        mes_venta = periodo_de_fecha(fecha_v)

        with self._bloqueos.obtener_lock(comision_orig.vendedor_id, regla.regla_id, mes_venta):
            periodo_destino, periodo_origen, _ = resolver_periodo_destino(self._persistencia, fecha_v)

            base_actual = self._persistencia.obtener_base_acumulada(
                comision_orig.vendedor_id, regla.regla_id, mes_venta
            )
            total_comisiones_mes = self._persistencia.obtener_total_comisiones_mes(
                comision_orig.vendedor_id, regla.regla_id, mes_venta
            )

            # La nueva base disminuye por el monto de la venta anulada
            nueva_base = max(Decimal("0.00"), base_actual - comision_orig.monto_venta)
            nuevo_total_comision = calcular_F(regla, nueva_base)
            delta_comision = nuevo_total_comision - total_comisiones_mes

            ajuste_id = str(uuid.uuid4())
            ajuste = Comision(
                comision_id=ajuste_id,
                venta_id=venta_id,
                regla_id=regla.regla_id,
                regla_version=regla.version,
                monto=delta_comision,
                periodo_id=periodo_destino,
                estado=EstadoComision.AJUSTADA,
                ajuste_de=comision_orig.comision_id,
                base_acumulada=base_actual,
                periodo_origen=periodo_origen,
                vendedor_id=comision_orig.vendedor_id,
                fecha_venta=comision_orig.fecha_venta,
                monto_venta=-comision_orig.monto_venta,
                motivo=motivo,
            )
            self._persistencia.guardar_comision(ajuste)

        if hasattr(self._observabilidad, "registrar_evento"):
            self._observabilidad.registrar_evento(
                "venta_anulada",
                {
                    "venta_id": venta_id,
                    "comision_original_id": comision_orig.comision_id,
                    "ajuste_id": ajuste_id,
                    "delta": str(delta_comision),
                },
            )

        if hasattr(self._seguridad, "auditar"):
            self._seguridad.auditar(
                actor, "anular_venta", venta_id, {"motivo": motivo, "ajuste_id": ajuste_id}
            )

        return ajuste

    # ¤comisiones
    def ajustar(self, comision_id: str, actor: Any, nuevo_monto: Decimal, motivo: str) -> Comision:
        """Crea un ajuste para una comisión en el período abierto sin alterar la original."""
        if hasattr(self._seguridad, "autorizar"):
            self._seguridad.autorizar(actor, "ajustar", comision_id)

        comision_orig = self._persistencia.obtener_comision(comision_id)
        if not comision_orig:
            raise ComisionNoEncontrada(f"No existe comisión con id {comision_id}")

        fecha_v = comision_orig.fecha_venta or date.today()
        periodo_destino, periodo_origen, _ = resolver_periodo_destino(self._persistencia, fecha_v)

        # Si nuevo_monto es negativo, es un delta directo; si es positivo, es el nuevo monto objetivo
        if nuevo_monto < Decimal("0"):
            delta = nuevo_monto
        else:
            delta = nuevo_monto - comision_orig.monto

        ajuste_id = str(uuid.uuid4())
        ajuste = Comision(
            comision_id=ajuste_id,
            venta_id=comision_orig.venta_id,
            regla_id=comision_orig.regla_id,
            regla_version=comision_orig.regla_version,
            monto=delta,
            periodo_id=periodo_destino,
            estado=EstadoComision.AJUSTADA,
            ajuste_de=comision_orig.comision_id,
            base_acumulada=comision_orig.base_acumulada,
            periodo_origen=periodo_origen,
            vendedor_id=comision_orig.vendedor_id,
            fecha_venta=comision_orig.fecha_venta,
            monto_venta=Decimal("0.00"),
            motivo=motivo,
        )
        self._persistencia.guardar_comision(ajuste)

        if hasattr(self._seguridad, "auditar"):
            self._seguridad.auditar(
                actor, "ajustar_comision", comision_id, {"motivo": motivo, "delta": str(delta)}
            )

        return ajuste

    # ¤comisiones
    def resumen(self, vendedor_id: str | None, periodo_id: str) -> Mapping[str, Any]:
        """Resumen del período: validada, pendiente, ventas, ajustes y base acumulada."""
        comisiones = self._persistencia.obtener_comisiones_periodo(periodo_id)
        if vendedor_id is not None:
            comisiones = [c for c in comisiones if c.vendedor_id == vendedor_id]

        validada = Decimal("0.00")
        pendiente = Decimal("0.00")
        ajustes = Decimal("0.00")
        base_acumulada = Decimal("0.00")
        num_ventas = 0

        for c in comisiones:
            if c.estado in (EstadoComision.FIJADA, EstadoComision.PAGADA, EstadoComision.AJUSTADA):
                validada += c.monto
                if c.ajuste_de is None:
                    num_ventas += 1
                    base_acumulada += c.monto_venta
                else:
                    ajustes += c.monto
                    base_acumulada += c.monto_venta
            elif c.estado == EstadoComision.ESTIMADA:
                pendiente += c.monto

        return {
            "periodo_id": periodo_id,
            "vendedor_id": vendedor_id,
            "validada": validada,
            "pendiente": pendiente,
            "ventas": num_ventas,
            "ajustes": ajustes,
            "base_acumulada": base_acumulada,
        }

    # ¤comisiones
    def desglose(self, comision_id: str) -> Mapping[str, Any]:
        """Desglose detallado del cálculo: regla, versión, modo, base y tramos (RF-PAN-03, ADR-0015)."""
        comision = self._persistencia.obtener_comision(comision_id)
        if not comision:
            raise ComisionNoEncontrada(f"No existe comisión con id {comision_id}")

        regla = self._persistencia.obtener_regla(comision.regla_id, comision.regla_version)
        if not regla:
            raise SinReglaVigente(f"Regla {comision.regla_id} no encontrada")

        tramos = desglosar_tramos(regla, comision.base_acumulada, comision.monto_venta)

        return {
            "comision_id": comision.comision_id,
            "venta_id": comision.venta_id,
            "regla_id": comision.regla_id,
            "regla_version": comision.regla_version,
            "modo_escalon": regla.modo_escalon.value,
            "base_acumulada": str(comision.base_acumulada),
            "monto_venta": str(comision.monto_venta),
            "monto_comision": str(comision.monto),
            "estado": comision.estado.value,
            "periodo_id": comision.periodo_id,
            "periodo_origen": comision.periodo_origen or comision.periodo_id,
            "tramos": tramos,
        }

    # ¤comisiones
    def estado_cuenta(self, vendedor_id: str, periodo_id: str) -> Mapping[str, Any]:
        """Estado de cuenta mensual por vendedor con líneas por venta y ajuste (RF-PAN-04)."""
        comisiones = self._persistencia.obtener_comisiones_vendedor(vendedor_id, periodo_id)

        lineas: list[dict[str, Any]] = []
        total_ventas = Decimal("0.00")
        total_comisiones = Decimal("0.00")
        num_ventas = 0
        num_ajustes = 0

        for c in comisiones:
            if c.estado in (EstadoComision.FIJADA, EstadoComision.PAGADA, EstadoComision.AJUSTADA):
                tipo_linea = "ajuste" if c.ajuste_de is not None else "venta"
                if tipo_linea == "venta":
                    num_ventas += 1
                else:
                    num_ajustes += 1

                total_ventas += c.monto_venta
                total_comisiones += c.monto

                lineas.append({
                    "tipo": tipo_linea,
                    "comision_id": c.comision_id,
                    "venta_id": c.venta_id,
                    "fecha_venta": c.fecha_venta.isoformat() if c.fecha_venta else "",
                    "monto_venta": str(c.monto_venta),
                    "monto_comision": str(c.monto),
                    "estado": c.estado.value,
                    "periodo_origen": c.periodo_origen or c.periodo_id,
                    "motivo": c.motivo,
                })

        return {
            "vendedor_id": vendedor_id,
            "periodo_id": periodo_id,
            "lineas": lineas,
            "total_ventas": str(total_ventas),
            "total_comisiones": str(total_comisiones),
            "numero_ventas": num_ventas,
            "numero_ajustes": num_ajustes,
        }

    # ¤comisiones
    def reglas(self, vigentes_en: date | None = None) -> tuple[ReglaComision, ...]:
        """Lista las reglas vigentes en una fecha dada o todas las reglas registradas."""
        todas = self._persistencia.obtener_reglas()
        if vigentes_en is None:
            return tuple(todas)

        filtradas = [
            r
            for r in todas
            if r.vigente_desde <= vigentes_en and (r.vigente_hasta is None or vigentes_en <= r.vigente_hasta)
        ]
        return tuple(filtradas)

    # ¤comisiones
    def crear_regla(self, actor: Any, regla: ReglaComision) -> ReglaComision:
        """Crea una nueva regla o nueva versión. No edita reglas previas (inmutables)."""
        if hasattr(self._seguridad, "autorizar"):
            self._seguridad.autorizar(actor, "crear_regla", regla.regla_id)

        reglas_existentes = self._persistencia.obtener_reglas()
        validar_nueva_regla(regla, reglas_existentes)

        creada_por = actor.remitente_token if hasattr(actor, "remitente_token") else str(actor)
        self._persistencia.guardar_regla(regla, creada_por=creada_por)

        if hasattr(self._seguridad, "auditar"):
            self._seguridad.auditar(
                actor, "crear_regla", regla.regla_id, {"version": regla.version, "tipo": regla.tipo.value}
            )

        return regla

    # ¤comisiones
    def cerrar_periodo(self, periodo_id: str, actor: Any) -> Periodo:
        """Cierra el período mensual dejándolo inmutable y genera su resumen por vendedor (RF-COM-02)."""
        periodo_existente = self._persistencia.obtener_periodo(periodo_id)
        if periodo_existente and periodo_existente.cerrado_en is not None:
            raise PeriodoCerrado(f"El período {periodo_id} ya se encuentra cerrado")

        if hasattr(self._seguridad, "autorizar"):
            self._seguridad.autorizar(actor, "cerrar_periodo", periodo_id)

        resumen = calcular_resumen_periodo(self._persistencia, periodo_id)
        cerrador = actor.remitente_token if hasattr(actor, "remitente_token") else str(actor)

        periodo_cerrado = self._persistencia.cerrar_periodo(periodo_id, cerrador, resumen)

        if hasattr(self._seguridad, "auditar"):
            self._seguridad.auditar(actor, "cerrar_periodo", periodo_id, {"resumen": resumen})

        return periodo_cerrado

    # ¤comisiones
    def exportar(self, periodo_id: str, formato: Literal["csv", "json"]) -> bytes:
        """Exporta las comisiones fijadas del período a CSV o JSON validado (RF-COM-03)."""
        moneda = str(self._config.get("moneda", "USD"))
        return exportar_periodo(self._persistencia, periodo_id, formato, moneda=moneda)
