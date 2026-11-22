# ¤comisiones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Motor de reglas versionadas y cálculo reproducible (RF-COM-01, INV_COMISION_REPRODUCIBLE).

Calcula comisiones con la regla vigente a la fecha de venta. En modo escalonado:
comision(v) = F(base + monto) - F(base), con F(X) redondeada a 2 decimales (ROUND_HALF_UP).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import fnmatch
from typing import Any, Mapping

from features.comisiones.tipos import (
    Escalon,
    ModoEscalon,
    ReglaComision,
    TipoRegla,
)

__all__ = [
    "calcular_F",
    "calcular_comision_incremental",
    "desglosar_tramos",
    "resolver_regla",
    "validar_nueva_regla",
]


# ¤comisiones
def validar_nueva_regla(regla: ReglaComision, reglas_existentes: list[ReglaComision]) -> None:
    """Valida que la regla cumpla invariantes de fechas, tipos y versiones monótonas."""
    if regla.vigente_hasta is not None and regla.vigente_hasta < regla.vigente_desde:
        raise ValueError("vigente_hasta debe ser mayor o igual a vigente_desde")

    reglas_mismo_id = [r for r in reglas_existentes if r.regla_id == regla.regla_id]
    if reglas_mismo_id:
        versiones = [r.version for r in reglas_mismo_id]
        if regla.version in versiones:
            raise ValueError(f"La versión {regla.version} de la regla {regla.regla_id} ya existe")
        if regla.version <= max(versiones):
            raise ValueError(f"La versión {regla.version} debe ser estrictamente mayor a {max(versiones)}")

    if regla.tipo == TipoRegla.ESCALONADA:
        if not regla.escalones:
            raise ValueError("Una regla escalonada debe tener al menos un escalón")
        # Verificar que el primer escalón comience en 0 o menor
        desde_valores = [e.desde_monto for e in regla.escalones]
        if min(desde_valores) > Decimal("0"):
            raise ValueError("Los escalones deben cubrir desde 0.00")


# ¤comisiones
def resolver_regla(
    reglas: list[ReglaComision],
    vendedor_id: str,
    propiedad_id: str | None,
    producto: str,
    fecha_venta: date,
) -> ReglaComision:
    """Resuelve la regla vigente aplicable a la fecha de venta con mayor especificidad."""
    candidatas: list[tuple[int, ReglaComision]] = []

    for r in reglas:
        # Vigencia temporal a la fecha de la venta (no a la fecha de cálculo)
        if r.vigente_desde > fecha_venta:
            continue
        if r.vigente_hasta is not None and fecha_venta > r.vigente_hasta:
            continue

        # Coincidencia de ámbito
        if r.vendedor_id is not None and r.vendedor_id != vendedor_id:
            continue
        if r.propiedad_id is not None and r.propiedad_id != propiedad_id:
            continue
        if r.producto_patron is not None:
            if not fnmatch.fnmatch(producto.lower(), r.producto_patron.lower()) and r.producto_patron.lower() not in producto.lower():
                continue

        # Puntuación de especificidad
        score = (
            (4 if r.vendedor_id is not None else 0)
            + (2 if r.propiedad_id is not None else 0)
            + (1 if r.producto_patron is not None else 0)
        )
        candidatas.append((score, r))

    if not candidatas:
        from features.comisiones.comisiones_service import SinReglaVigente
        raise SinReglaVigente(
            f"Sin regla vigente para vendedor={vendedor_id}, propiedad={propiedad_id}, "
            f"producto={producto}, fecha_venta={fecha_venta.isoformat()}"
        )

    # Ordenar por especificidad descendente y versión descendente
    max_score = max(score for score, _ in candidatas)
    mejores = [r for score, r in candidatas if score == max_score]

    # Verificar solapamiento si hay diferentes regla_id con el mismo nivel de especificidad máxima
    regla_ids_distintos = {r.regla_id for r in mejores}
    if len(regla_ids_distintos) > 1:
        from features.comisiones.comisiones_service import ReglaSolapada
        raise ReglaSolapada(
            f"Reglas solapadas con la misma especificidad para fecha={fecha_venta}: {regla_ids_distintos}"
        )

    # Si hay varias versiones de la misma regla_id, tomar la de mayor versión
    mejores.sort(key=lambda r: r.version, reverse=True)
    return mejores[0]


# ¤comisiones
def calcular_F(regla: ReglaComision, volumen: Decimal) -> Decimal:
    """Calcula la función acumulada F(X) redondeada a 2 decimales (ROUND_HALF_UP)."""
    if volumen <= Decimal("0"):
        return Decimal("0.00")

    if regla.tipo == TipoRegla.FIJO:
        return regla.valor.quantize(Decimal("0.01"), ROUND_HALF_UP)

    if regla.tipo == TipoRegla.PORCENTAJE:
        tasa = regla.valor / Decimal("100")
        return (volumen * tasa).quantize(Decimal("0.01"), ROUND_HALF_UP)

    if regla.tipo == TipoRegla.ESCALONADA:
        tramos = sorted([(e.desde_monto, e.porcentaje / Decimal("100")) for e in regla.escalones], key=lambda x: x[0])

        if regla.modo_escalon == ModoEscalon.VOLUMEN:
            # En modo volumen, la tasa alcanzada aplica sobre todo el acumulado
            candidatos = [t for desde, t in tramos if volumen >= desde]
            tasa = candidatos[-1] if candidatos else tramos[0][1]
            return (volumen * tasa).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # En modo graduado, cada tasa aplica solo a su tramo
        total = Decimal("0")
        for (desde, tasa), (hasta, _) in zip(tramos, [*tramos[1:], (volumen, Decimal("0"))]):
            tramo_monto = max(min(volumen, hasta) - desde, Decimal("0"))
            total += tramo_monto * tasa
        return total.quantize(Decimal("0.01"), ROUND_HALF_UP)

    return Decimal("0.00")


# ¤comisiones
def calcular_comision_incremental(regla: ReglaComision, base: Decimal, monto: Decimal) -> Decimal:
    """Calcula comision(v) = F(base + monto) - F(base), redondeando F."""
    if regla.tipo == TipoRegla.FIJO:
        return regla.valor.quantize(Decimal("0.01"), ROUND_HALF_UP)

    f_despues = calcular_F(regla, base + monto)
    f_antes = calcular_F(regla, base)
    return f_despues - f_antes


# ¤comisiones
def desglosar_tramos(regla: ReglaComision, base: Decimal, monto: Decimal) -> list[dict[str, Any]]:
    """Genera el desglose de tramos para transparencia en el panel (RF-PAN-03, ADR-0015)."""
    tramos_resultado: list[dict[str, Any]] = []

    if regla.tipo == TipoRegla.FIJO:
        tramos_resultado.append({
            "tipo": "fijo",
            "desde": "0.00",
            "hasta": None,
            "porcentaje": "0.00",
            "monto_fijo": str(regla.valor),
            "base_en_tramo": str(monto),
            "comision_tramo": str(regla.valor.quantize(Decimal("0.01"), ROUND_HALF_UP)),
        })
        return tramos_resultado

    if regla.tipo == TipoRegla.PORCENTAJE:
        comision = calcular_comision_incremental(regla, base, monto)
        tramos_resultado.append({
            "tipo": "porcentaje",
            "desde": "0.00",
            "hasta": None,
            "porcentaje": str(regla.valor),
            "base_en_tramo": str(monto),
            "comision_tramo": str(comision),
        })
        return tramos_resultado

    if regla.tipo == TipoRegla.ESCALONADA:
        tramos = sorted([(e.desde_monto, e.porcentaje) for e in regla.escalones], key=lambda x: x[0])

        if regla.modo_escalon == ModoEscalon.VOLUMEN:
            volumen_total = base + monto
            candidatos = [(d, p) for d, p in tramos if volumen_total >= d]
            desde_alcanzado, porc_alcanzado = candidatos[-1] if candidatos else tramos[0]
            comision = calcular_comision_incremental(regla, base, monto)
            tramos_resultado.append({
                "tipo": "volumen",
                "desde": str(desde_alcanzado),
                "hasta": None,
                "porcentaje": str(porc_alcanzado),
                "volumen_total": str(volumen_total),
                "base_en_tramo": str(monto),
                "comision_tramo": str(comision),
            })
            return tramos_resultado

        # Modo graduado
        volumen_total = base + monto
        for i, (desde, porc) in enumerate(tramos):
            hasta = tramos[i + 1][0] if i + 1 < len(tramos) else None
            # Segmento cubierto por esta venta dentro del tramo
            tramo_desde = max(base, desde)
            tramo_hasta = min(volumen_total, hasta) if hasta is not None else volumen_total
            if tramo_hasta > tramo_desde:
                base_en_tramo = tramo_hasta - tramo_desde
                tasa = porc / Decimal("100")
                # Comisión proporcional del tramo
                f_tramo_despues = calcular_F(regla, tramo_hasta)
                f_tramo_antes = calcular_F(regla, tramo_desde)
                comision_tramo = f_tramo_despues - f_tramo_antes
                tramos_resultado.append({
                    "tipo": "graduado",
                    "desde": str(desde),
                    "hasta": str(hasta) if hasta is not None else None,
                    "porcentaje": str(porc),
                    "base_en_tramo": str(base_en_tramo),
                    "comision_tramo": str(comision_tramo),
                })

    return tramos_resultado
