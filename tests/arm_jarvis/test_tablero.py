# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del tablero de métricas y marcado de publicación en CRM (T-602, RF-ARM-08, RF-CRM-04)."""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
from typing import Any

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.dobles_internal import DobleObservabilidad
from features.arm_jarvis.tipos import EstadoVenta


# ¤arm-jarvis
class ActorFake:
    def __init__(self, sujeto_id: str, rol: str) -> None:
        self.sujeto_id = sujeto_id
        self.rol = rol


# ¤arm-jarvis
def test_tablero_cuadra_totales_y_coincide_con_exportacion() -> None:
    """Escenario: Tablero que cuadra (@US-08 @CU-07 @RF-ARM-08 @RF-PAN-04).

    Dado ventas validadas en el mes
    Cuando el líder abre el tablero
    Entonces ve ventas por mes, vendedor y propiedad y comisiones validadas y pendientes
    Y los totales coinciden al centavo con la exportación CSV
    """
    obs = DobleObservabilidad()
    servicio = ArmJarvisService(observabilidad=obs)
    periodo = "2026-11"

    # Registrar vendedores
    v1 = servicio.registrar_vendedor(telefono_token="tel_carlos", nombre="Carlos Alvear")
    v2 = servicio.registrar_vendedor(telefono_token="tel_lucia", nombre="Lucia Mendez")

    lider = ActorFake("lider_01", "lider")
    admin = ActorFake("admin_01", "administrador")

    # Helper para simular e insertar ventas
    class Msg:
        def __init__(self, remitente: str, texto: str, mensaje_id: str) -> None:
            self.remitente = remitente
            self.texto = texto
            self.mensaje_id = mensaje_id

    # Venta 1: Carlos, Domo Bosque, $500, comision 10% ($50) -> validada -> publicada
    servicio.procesar(Msg("tel_carlos", "vendí Domo Bosque por 500 a Juan el 05 de noviembre", "m1"))
    ventas_v1 = servicio.listar(vendedor_id=v1.vendedor_id)
    vt1 = ventas_v1[0]
    servicio.validar(vt1.venta_id, lider)
    servicio.marcar_publicacion(vt1.venta_id, ok=True)

    # Venta 2: Carlos, Domo Lago, $300, comision 10% ($30) -> validada -> fallo CRM (no_publicada)
    servicio.procesar(Msg("tel_carlos", "vendí Domo Lago por 300 a Pedro el 10 de noviembre", "m2"))
    ventas_v1 = servicio.listar(vendedor_id=v1.vendedor_id)
    vt2 = [v for v in ventas_v1 if v.venta_id != vt1.venta_id][0]
    servicio.validar(vt2.venta_id, lider)
    servicio.marcar_publicacion(vt2.venta_id, ok=False, detalle="Timeout de red al conectar al CRM")

    # Venta 3: Lucia, Domo Bosque, $400, comision 10% ($40) -> validada
    servicio.procesar(Msg("tel_lucia", "vendí Domo Bosque por 400 a Ana el 12 de noviembre", "m3"))
    ventas_v2 = servicio.listar(vendedor_id=v2.vendedor_id)
    vt3 = ventas_v2[0]
    servicio.validar(vt3.venta_id, lider)

    # Venta 4: Lucia, Domo Lago, $200, comision estimada $20 -> por_validar
    servicio.procesar(Msg("tel_lucia", "vendí Domo Lago por 200 a Luis el 15 de noviembre", "m4"))

    # Venta 5: Carlos, $100 -> rechazada
    servicio.procesar(Msg("tel_carlos", "vendí Domo Bosque por 100 a Mario el 18 de noviembre", "m5"))
    ventas_v1 = servicio.listar(vendedor_id=v1.vendedor_id)
    vt5 = [v for v in ventas_v1 if v.estado == EstadoVenta.POR_VALIDAR and v.extraida.monto == Decimal("100.00")][0]
    servicio.rechazar(vt5.venta_id, lider, motivo="Monto incorrecto sin depósito")

    # Venta 6: Lucia, $150 -> anulada por administrador
    servicio.procesar(Msg("tel_lucia", "vendí Domo Lago por 150 a Sofia el 20 de noviembre", "m6"))
    ventas_v2 = servicio.listar(vendedor_id=v2.vendedor_id)
    vt6 = [v for v in ventas_v2 if v.estado == EstadoVenta.POR_VALIDAR and v.extraida.monto == Decimal("150.00")][0]
    servicio.anular(vt6.venta_id, admin, motivo="Huésped canceló antes de validar")

    # 1. Obtener tablero consolidado
    tablero = servicio.tablero(periodo)

    # Comisiones validadas: 50.00 (V1) + 30.00 (V2) + 40.00 (V3) = 120.00 USD
    assert tablero.comisiones_validadas == Decimal("120.00")

    # Comisiones pendientes: V4 por_validar con 200 * 10% = 20.00 USD
    assert tablero.comisiones_pendientes == Decimal("20.00")
    assert tablero.por_validar == 1

    # Ventas en validada, publicada, no_publicada: 500 + 300 + 400 = 1200.00 USD
    total_esperado_ventas = Decimal("1200.00")

    # Coincidencia al centavo por vendedor:
    total_por_vendedor = sum(monto for _, monto, _ in tablero.ventas_por_vendedor)
    assert total_por_vendedor == total_esperado_ventas

    carlos_data = next((item for item in tablero.ventas_por_vendedor if "Carlos" in item[0]), None)
    lucia_data = next((item for item in tablero.ventas_por_vendedor if "Lucia" in item[0]), None)
    assert carlos_data is not None and carlos_data[1] == Decimal("800.00") and carlos_data[2] == 2
    assert lucia_data is not None and lucia_data[1] == Decimal("400.00") and lucia_data[2] == 1

    # Coincidencia al centavo por propiedad:
    total_por_propiedad = sum(monto for _, monto in tablero.ventas_por_propiedad)
    assert total_por_propiedad == total_esperado_ventas

    # Coincidencia al centavo por mes:
    mes_actual_data = next((monto for mes, monto in tablero.ventas_por_mes if mes == periodo), None)
    assert mes_actual_data == total_esperado_ventas

    # 2. Exportación CSV y verificación de totales al centavo
    csv_tablero = servicio.exportar_csv(periodo)
    reader = csv.reader(io.StringIO(csv_tablero))
    filas = list(reader)

    # Encabezado
    assert filas[0] == ["seccion", "concepto", "monto", "cantidad"]

    mapa_csv = {(f[0], f[1]): (f[2], f[3]) for f in filas[1:]}

    assert mapa_csv[("totales", "comisiones_validadas")][0] == "120.00"
    assert mapa_csv[("totales", "comisiones_pendientes")][0] == "20.00"
    assert mapa_csv[("totales", "por_validar")][1] == "1"

    # Suma de ventas por vendedor en el CSV
    suma_csv_vendedores = sum(
        Decimal(f[2]) for f in filas if f[0] == "ventas_por_vendedor"
    )
    assert suma_csv_vendedores == total_esperado_ventas

    # Suma de ventas por propiedad en el CSV
    suma_csv_propiedades = sum(
        Decimal(f[2]) for f in filas if f[0] == "ventas_por_propiedad"
    )
    assert suma_csv_propiedades == total_esperado_ventas


# ¤arm-jarvis
def test_crm_falla_publicacion_queda_no_publicada_alerta_y_reintento_pasa_a_publicada() -> None:
    """Escenario: El CRM no acepta la venta (@US-06 @RF-CRM-04 @INV_VENTA_NO_SE_PIERDE).

    Dado una publicación que falla durante 24 horas
    Cuando se agotan los reintentos automáticos
    Entonces la venta sigue "no_publicada", se dispara una alerta y el panel ofrece reintentar
    Y un reintento exitoso la pasa a "publicada"
    """
    obs = DobleObservabilidad()
    servicio = ArmJarvisService(observabilidad=obs)

    v = servicio.registrar_vendedor(telefono_token="tel_vend_crm", nombre="Vendedor CRM")
    lider = ActorFake("lider_01", "lider")

    class Msg:
        remitente = "tel_vend_crm"
        texto = "vendí Suite Balcón 202 por 450 a Carlos el 10 de noviembre"
        mensaje_id = "msg_crm_01"

    servicio.procesar(Msg())
    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 1
    venta = ventas[0]

    # Validar la venta
    servicio.validar(venta.venta_id, lider)

    # 1. Simular fallo de publicación en CRM (se agotan reintentos automáticos)
    venta_fallida = servicio.marcar_publicacion(
        venta.venta_id,
        ok=False,
        detalle="HTTP 503 Webhook CRM no disponible tras 24h",
    )

    # La venta sigue existiendo y queda en 'no_publicada' (INV_VENTA_NO_SE_PIERDE)
    assert venta_fallida.estado == EstadoVenta.NO_PUBLICADA
    venta_db = servicio.repositorio.obtener_venta(venta.venta_id)
    assert venta_db.estado == EstadoVenta.NO_PUBLICADA

    # Se dispara una alerta a observabilidad
    assert len(obs.alertas) == 1
    assert obs.alertas[0]["tipo"] == "venta_no_publicada"
    assert venta.ticket in obs.alertas[0]["mensaje"]

    # La transición queda registrada en arm.transiciones
    transiciones = servicio.repositorio.listar_transiciones(venta.venta_id)
    ult_trans = transiciones[-1]
    assert ult_trans.de == EstadoVenta.VALIDADA
    assert ult_trans.a == EstadoVenta.NO_PUBLICADA
    assert "HTTP 503" in (ult_trans.motivo or "")

    # 2. Reintento manual exitoso desde el panel
    venta_publicada = servicio.marcar_publicacion(
        venta.venta_id,
        ok=True,
        detalle="Reintento manual exitoso desde el panel",
    )

    # Ahora pasa a 'publicada'
    assert venta_publicada.estado == EstadoVenta.PUBLICADA
    venta_db2 = servicio.repositorio.obtener_venta(venta.venta_id)
    assert venta_db2.estado == EstadoVenta.PUBLICADA

    # Transición registrada de no_publicada -> publicada
    transiciones2 = servicio.repositorio.listar_transiciones(venta.venta_id)
    assert len(transiciones2) == len(transiciones) + 1
    assert transiciones2[-1].de == EstadoVenta.NO_PUBLICADA
    assert transiciones2[-1].a == EstadoVenta.PUBLICADA


# ¤arm-jarvis
def test_exportar_ventas_csv_incluye_columnas_y_datos_completos() -> None:
    """Verifica la exportación detallada de ventas del período a formato CSV."""
    servicio = ArmJarvisService()
    periodo = "2026-11"

    v = servicio.registrar_vendedor(telefono_token="tel_exp", nombre="Vendedor Export")
    lider = ActorFake("lider_01", "lider")

    class Msg:
        def __init__(self, mensaje_id: str, texto: str) -> None:
            self.remitente = "tel_exp"
            self.texto = texto
            self.mensaje_id = mensaje_id

    servicio.procesar(Msg("m_exp_1", "vendí Domo Bosque por 300 a Martin el 10 de noviembre"))
    servicio.procesar(Msg("m_exp_2", "vendí Domo Lago por 500 a Clara el 12 de noviembre"))

    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    servicio.validar(ventas[0].venta_id, lider)

    csv_detalle = servicio.exportar_ventas_csv(periodo)
    reader = csv.reader(io.StringIO(csv_detalle))
    filas = list(reader)

    # Encabezado
    assert filas[0] == [
        "venta_id", "ticket", "vendedor_id", "producto", "propiedad_id",
        "monto", "moneda", "fecha_venta", "estado", "comision_estimada", "comision_fijada",
    ]

    assert len(filas) == 3  # Encabezado + 2 ventas
    tickets = [f[1] for f in filas[1:]]
    assert all(t.startswith("V-2026-") for t in tickets)
    montos = [f[5] for f in filas[1:]]
    assert "300.00" in montos and "500.00" in montos
