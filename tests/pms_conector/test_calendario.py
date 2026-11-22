# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de calendario y tarifas propios con concurrencia (RF-PMS-07, RF-PMS-08, INV_SIN_DOBLE_RESERVA, INV_AISLAMIENTO_ANFITRION)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal

import pytest

from features.pms_conector.persistencia_internal import inicializar_base_datos
from features.pms_conector.plataforma_internal import PlataformaPMS
from features.pms_conector.pms_conector_service import PMSConectorService
from features.pms_conector.tipos import (
    AislamientoAnfitrionError,
    Reserva,
    SinDisponibilidad,
)
from tests.pms_conector.dobles import DobleObservabilidad


# ¤pms-conector
def test_dos_huespedes_piden_misma_noche_concurrencia() -> None:
    """Escenario: Dos huéspedes piden la misma noche (@RF-PMS-07 @INV_SIN_DOBLE_RESERVA).
    
    Dado una unidad libre y con tarifa
    Cuando dos reservas preliminares llegan al mismo tiempo
    Entonces solo una ocupa la noche y la otra recibe SinDisponibilidad
    """
    conector = PlataformaPMS()
    prop_id = "glamping_imbabura"
    unidad_id = "domo_lago"
    desde = date(2026, 12, 1)
    hasta = date(2026, 12, 3)

    resultados: list[Reserva] = []
    errores: list[Exception] = []

    def intentar_reserva(token: str, idemp: str) -> None:
        try:
            res = conector.crear_reserva_preliminar(
                propiedad_id=prop_id,
                unidad_id=unidad_id,
                desde=desde,
                hasta=hasta,
                huespedes=2,
                huesped_token=token,
                clave_idempotencia=idemp,
            )
            resultados.append(res)
        except Exception as exc:
            errores.append(exc)

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        f1 = ejecutor.submit(intentar_reserva, "tok_huesped_A", "idemp_A_001")
        f2 = ejecutor.submit(intentar_reserva, "tok_huesped_B", "idemp_B_001")
        f1.result()
        f2.result()

    # Exactamente una reserva tuvo éxito y la otra falló con SinDisponibilidad
    assert len(resultados) == 1
    assert len(errores) == 1
    assert isinstance(errores[0], SinDisponibilidad)


# ¤pms-conector
def test_noche_sin_tarifa_no_se_ofrece() -> None:
    """Escenario: Noche sin tarifa (@RF-PMS-07).
    
    Dado una unidad libre sin tarifa para una noche
    Cuando un huésped consulta esa fecha
    Entonces la unidad no se ofrece
    """
    conn = inicializar_base_datos()
    conector = PlataformaPMS(conexion=conn)

    prop_id = "glamping_imbabura"
    unidad_id = "domo_lago"
    fecha_futura_sin_tarifa = date(2028, 5, 1)
    hasta_futura = date(2028, 5, 3)

    # Asegurar que no hay tarifas para esa fecha futura
    conn.execute(
        "DELETE FROM pms.tarifas_noche WHERE unidad_id = ? AND noche >= ?",
        (unidad_id, fecha_futura_sin_tarifa.isoformat()),
    )
    conn.commit()

    disp = conector.consultar_disponibilidad(prop_id, fecha_futura_sin_tarifa, hasta_futura, huespedes=2)
    ids_disponibles = [u.unidad_id for u in disp.unidades]
    assert unidad_id not in ids_disponibles


# ¤pms-conector
def test_respeto_minimo_noches() -> None:
    """RF-PMS-07: Se respeta la estancia mínima requerida para la unidad."""
    conector = PlataformaPMS()
    prop_id = "glamping_imbabura"
    unidad_id = "domo_bosque"  # configurado con mínimo 2 noches
    desde = date(2026, 12, 1)
    hasta_1_noche = date(2026, 12, 2)
    hasta_2_noches = date(2026, 12, 3)

    # Consulta de 1 sola noche: domo_bosque no debe ofrecerse
    disp_1 = conector.consultar_disponibilidad(prop_id, desde, hasta_1_noche, huespedes=2)
    ids_1 = [u.unidad_id for u in disp_1.unidades]
    assert "domo_bosque" not in ids_1

    # Consulta de 2 noches: domo_bosque sí se ofrece
    disp_2 = conector.consultar_disponibilidad(prop_id, desde, hasta_2_noches, huespedes=2)
    ids_2 = [u.unidad_id for u in disp_2.unidades]
    assert "domo_bosque" in ids_2


# ¤pms-conector
def test_anfitrion_bloquea_fechas_y_aislamiento() -> None:
    """Escenario: El anfitrión bloquea fechas (@RF-PMS-08 @INV_AISLAMIENTO_ANFITRION).
    
    Dado un anfitrión con una unidad propia
    Cuando bloquea fechas por WhatsApp
    Entonces esas noches dejan de ofrecerse
    Y no puede cambiar la unidad de otro anfitrión
    """
    conector = PlataformaPMS()
    prop_id = "glamping_imbabura"
    unidad_propia = "domo_lago"       # Dueño: anf_imbabura_01
    unidad_ajena = "suite_101"         # Dueño: anf_ibarra_01
    desde = date(2026, 12, 5)
    hasta = date(2026, 12, 8)

    # 1. El anfitrión bloquea fechas en su unidad propia
    afectadas, omitidas = conector.actualizar_calendario(
        unidad_id=unidad_propia,
        desde=desde,
        hasta=hasta,
        accion="bloquear",
        actor_id="anf_imbabura_01",
    )
    assert afectadas == 3
    assert omitidas == 0

    # 2. Las noches dejan de ofrecerse en la consulta de disponibilidad
    disp = conector.consultar_disponibilidad(prop_id, desde, hasta, huespedes=2)
    ids_disponibles = [u.unidad_id for u in disp.unidades]
    assert unidad_propia not in ids_disponibles

    # 3. No puede cambiar la unidad de otro anfitrión (INV_AISLAMIENTO_ANFITRION)
    with pytest.raises(AislamientoAnfitrionError):
        conector.actualizar_calendario(
            unidad_id=unidad_ajena,
            desde=desde,
            hasta=hasta,
            accion="bloquear",
            actor_id="anf_imbabura_01",
        )


# ¤pms-conector
def test_liberar_no_toca_reservas() -> None:
    """Escenario: Liberar no toca reservas (@RF-PMS-08).
    
    Dado noches con una reserva dentro del rango
    Cuando el anfitrión libera ese rango
    Entonces solo se liberan los bloqueos y la respuesta indica cuántas noches se omitieron
    """
    conector = PlataformaPMS()
    prop_id = "glamping_imbabura"
    unidad_id = "domo_lago"

    # Noche 1: reservada por un huésped
    desde_reserva = date(2026, 12, 10)
    hasta_reserva = date(2026, 12, 11)
    reserva = conector.crear_reserva_preliminar(
        prop_id, unidad_id, desde_reserva, hasta_reserva, 2, "tok_huesped", "idemp_res_001"
    )
    conector.confirmar_reserva(reserva.codigo, "idemp_conf_001")

    # Noche 2 y 3: bloqueadas manualmente por el anfitrión
    desde_bloqueo = date(2026, 12, 11)
    hasta_bloqueo = date(2026, 12, 13)
    conector.actualizar_calendario(
        unidad_id, desde_bloqueo, hasta_bloqueo, accion="bloquear", actor_id="anf_imbabura_01"
    )

    # Cuando el anfitrión intenta liberar todo el rango [10, 13)
    desde_total = date(2026, 12, 10)
    hasta_total = date(2026, 12, 13)
    afectadas, omitidas = conector.actualizar_calendario(
        unidad_id, desde_total, hasta_total, accion="liberar", actor_id="anf_imbabura_01"
    )

    # Entonces solo se liberan los bloqueos (2 noches) y la noche reservada se omite (1 noche)
    assert afectadas == 2
    assert omitidas == 1

    # La reserva original sigue intacta
    res_actual = conector.obtener_reserva(reserva.codigo)
    assert res_actual.codigo == reserva.codigo


# ¤pms-conector
def test_actualizar_calendario_registra_en_observabilidad() -> None:
    """RF-PMS-08 (c): cada cambio de calendario queda registrado en el audit log."""
    obs = DobleObservabilidad()
    servicio = PMSConectorService(
        config={"proveedor": "plataforma"},
        observabilidad=obs,
    )
    desde = date(2026, 12, 15)
    hasta = date(2026, 12, 17)

    servicio.actualizar_calendario(
        unidad_id="domo_lago",
        desde=desde,
        hasta=hasta,
        accion="bloquear",
        actor_id="anf_imbabura_01",
    )

    logs_cal = [l for l in obs.logs if l[1] == "calendario_actualizado"]
    assert len(logs_cal) >= 1
    assert logs_cal[0][2]["accion"] == "bloquear"
    assert logs_cal[0][2]["actor_id"] == "anf_imbabura_01"
    assert logs_cal[0][2]["afectadas"] == 2
