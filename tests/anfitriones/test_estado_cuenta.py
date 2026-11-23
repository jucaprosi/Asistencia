# ¤anfitriones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-ANF-07 y RF-ANF-08: Estado de cuenta mensual, cobro, ajustes y pausa por mora.

Verifica:
- Cierre mensual agrupado por anfitrión con cálculo de comisión y notificación WhatsApp.
- Invariante INV_COMISION_PLATAFORMA_UNICA (cada estadía se cobra a lo sumo una vez).
- Estadías canceladas y no_show no generan comisión.
- Consulta de estado de cuenta con invariante INV_AISLAMIENTO_ANFITRION.
- Ajustes posteriores en períodos abiertos.
- Registro de pago por administrador con actor y fecha.
- Proceso diario de morosidad y pausa de hospedajes tras 15 días de vencimiento.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest

from features.anfitriones.anfitriones_service import (
    Anfitrion,
    AnfitrionesService,
    ErrorAnfitriones,
    EstadoCuenta,
    EstadoHospedaje,
    EstadoSolicitud,
    Hospedaje,
    Solicitud,
    cargar_config,
)
from tests.anfitriones.dobles import (
    DobleCanalWhatsApp,
    DobleObservabilidad,
    DoblePMS,
    DobleSeguridad,
    ReservaDoble,
)


# ¤anfitriones
def _crear_servicio_con_anfitriones() -> tuple[AnfitrionesService, DobleSeguridad, DobleCanalWhatsApp, DoblePMS, DobleObservabilidad]:
    seg = DobleSeguridad()
    canal = DobleCanalWhatsApp()
    pms = DoblePMS()
    obs = DobleObservabilidad()
    config = dict(cargar_config())
    srv = AnfitrionesService(config, seguridad=seg, canal=canal, pms=pms, observabilidad=obs)

    # Anfitrión 1: 10% comisión
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-01",
            nombre_comercial="Glamping Paraiso",
            comision_porcentaje=Decimal("10.00"),
            terminos_version="v2026.1",
        ),
        "+593991112233",
        actor_id="admin_01",
    )
    srv.guardar_hospedaje(
        Hospedaje(propiedad_id="DOMO-01", anfitrion_id="ANF-01", estado=EstadoHospedaje.PUBLICADO),
        actor_id="admin_01",
    )

    # Anfitrión 2: 12% comisión
    srv.registrar_anfitrion(
        Anfitrion(
            anfitrion_id="ANF-02",
            nombre_comercial="Glamping Volcan",
            comision_porcentaje=Decimal("12.00"),
            terminos_version="v2026.1",
        ),
        "+593994445566",
        actor_id="admin_01",
    )
    srv.guardar_hospedaje(
        Hospedaje(propiedad_id="DOMO-02", anfitrion_id="ANF-02", estado=EstadoHospedaje.PUBLICADO),
        actor_id="admin_01",
    )

    return srv, seg, canal, pms, obs


# ¤anfitriones
def _completar_estadia(
    srv: AnfitrionesService,
    pms: DoblePMS,
    codigo_reserva: str,
    propiedad_id: str,
    anfitrion_id: str,
    desde: date,
    hasta: date,
    total: Decimal,
) -> Solicitud:
    pms.agregar_reserva(
        ReservaDoble(
            codigo=codigo_reserva,
            propiedad_id=propiedad_id,
            unidad_id="U-01",
            huesped_token="[[TOKEN:huesped_ec]]",
            desde=desde,
            hasta=hasta,
            huespedes=2,
            total=total,
        )
    )
    sol = srv.solicitar_reserva(codigo_reserva)
    srv.responder_solicitud(sol.solicitud, anfitrion_id, acepta=True)

    # Simular paso del plazo de reporte y completado automático
    fecha_proceso = hasta + timedelta(days=4)
    srv.procesar_estadias_completadas(ahora_fecha=fecha_proceso)
    sol_completada = srv._persistencia.obtener_solicitud(sol.solicitud)
    assert sol_completada is not None
    assert sol_completada.estado == EstadoSolicitud.COMPLETADA
    return sol_completada


# ¤anfitriones
def test_cierre_mensual_calcula_comisiones_y_total_coincide_con_lineas() -> None:
    # US-20 @RF-ANF-07 @INV_COMISION_PLATAFORMA_UNICA
    srv, _seg, canal, pms, _obs = _crear_servicio_con_anfitriones()

    # Dos estadías completadas para ANF-01 con salida en octubre 2026 (período "2026-10")
    # Estancia 1: total $300, comisión 10% = $30.00
    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-01",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 10),
        hasta=date(2026, 10, 12),
        total=Decimal("300.00"),
    )
    # Estancia 2: total $500, comisión 10% = $50.00
    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-02",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 15),
        hasta=date(2026, 10, 18),
        total=Decimal("500.00"),
    )

    # Una estadía completada para ANF-02 en octubre: total $400, comisión 12% = $48.00
    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-03",
        propiedad_id="DOMO-02",
        anfitrion_id="ANF-02",
        desde=date(2026, 10, 20),
        hasta=date(2026, 10, 22),
        total=Decimal("400.00"),
    )

    # Cuando corre el cierre el día 5 de noviembre para el período 2026-10
    fecha_cierre = datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc)
    estados = srv.cerrar_periodo("2026-10", ahora=fecha_cierre)

    # Entonces se generan estados de cuenta para ambos anfitriones
    assert len(estados) == 2
    ec_anf01 = next(ec for ec in estados if ec.anfitrion_id == "ANF-01")
    ec_anf02 = next(ec for ec in estados if ec.anfitrion_id == "ANF-02")

    # Para ANF-01: total $80.00 coincidiendo con la suma de sus líneas
    assert ec_anf01.periodo == "2026-10"
    assert ec_anf01.estado == EstadoCuenta.EMITIDO
    assert len(ec_anf01.lineas) == 2
    assert sum(l.comision for l in ec_anf01.lineas) == ec_anf01.total
    assert ec_anf01.total == Decimal("80.00")
    # Plazo de pago: 14 días desde emisión (2026-11-05 + 14 = 2026-11-19)
    assert ec_anf01.vence_en == date(2026, 11, 19)

    # Para ANF-02: total $48.00
    assert ec_anf02.total == Decimal("48.00")
    assert len(ec_anf02.lineas) == 1

    # Y cada anfitrión recibe notificación por WhatsApp
    destinatarios = [dest for dest, _plantilla in canal.plantillas_enviadas]
    anf01 = srv._persistencia.obtener_anfitrion("ANF-01")
    anf02 = srv._persistencia.obtener_anfitrion("ANF-02")
    assert anf01 is not None and anf01.telefono_token in destinatarios
    assert anf02 is not None and anf02.telefono_token in destinatarios


# ¤anfitriones
def test_estadia_no_se_cobra_dos_veces() -> None:
    # INV_COMISION_PLATAFORMA_UNICA
    srv, _seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-01",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 5),
        hasta=date(2026, 10, 8),
        total=Decimal("250.00"),
    )

    # Primer cierre
    fecha_cierre = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)
    srv.cerrar_periodo("2026-10", ahora=fecha_cierre)
    ec1 = srv.estado_de_cuenta("ANF-01", "2026-10", actor_id="ANF-01")
    assert len(ec1.lineas) == 1
    assert ec1.total == Decimal("25.00")

    # Segundo cierre del mismo período (idempotente: no debe duplicar el cobro de la estadía)
    srv.cerrar_periodo("2026-10", ahora=fecha_cierre)
    ec2 = srv.estado_de_cuenta("ANF-01", "2026-10", actor_id="ANF-01")
    assert len(ec2.lineas) == 1
    assert ec2.total == Decimal("25.00")


# ¤anfitriones
def test_estadias_canceladas_y_no_show_no_generan_comision() -> None:
    # RF-ANF-06 @RF-ANF-07
    srv, _seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    # Reserva 1: cancelada por el anfitrión dentro del plazo
    pms.agregar_reserva(
        ReservaDoble(
            codigo="RES-CANCELADA",
            propiedad_id="DOMO-01",
            unidad_id="U-01",
            huesped_token="[[TOKEN:h_canc]]",
            desde=date(2026, 10, 1),
            hasta=date(2026, 10, 3),
            huespedes=2,
            total=Decimal("300.00"),
        )
    )
    sol1 = srv.solicitar_reserva("RES-CANCELADA")
    srv.responder_solicitud(sol1.solicitud, "ANF-01", acepta=True)
    srv.reportar_resultado(
        sol1.solicitud,
        "ANF-01",
        EstadoSolicitud.CANCELADA,
        ahora_fecha=date(2026, 10, 4),
    )

    # Reserva 2: no_show reportado dentro del plazo
    pms.agregar_reserva(
        ReservaDoble(
            codigo="RES-NOSHOW",
            propiedad_id="DOMO-01",
            unidad_id="U-01",
            huesped_token="[[TOKEN:h_noshow]]",
            desde=date(2026, 10, 5),
            hasta=date(2026, 10, 7),
            huespedes=2,
            total=Decimal("350.00"),
        )
    )
    sol2 = srv.solicitar_reserva("RES-NOSHOW")
    srv.responder_solicitud(sol2.solicitud, "ANF-01", acepta=True)
    srv.reportar_resultado(
        sol2.solicitud,
        "ANF-01",
        EstadoSolicitud.NO_SHOW,
        ahora_fecha=date(2026, 10, 8),
    )

    # Cuando corre el cierre para 2026-10
    estados = srv.cerrar_periodo("2026-10", ahora=datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc))

    # Entonces no se genera cobro alguno para ANF-01 (sin estadías completadas)
    assert not any(ec.anfitrion_id == "ANF-01" for ec in estados)


# ¤anfitriones
def test_anfitrion_consulta_estado_cuenta_por_whatsapp_mcp() -> None:
    # US-20 @RF-ANF-07
    srv, _seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-CONSULTA",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 10),
        hasta=date(2026, 10, 12),
        total=Decimal("200.00"),
    )
    srv.cerrar_periodo("2026-10", ahora=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc))

    # El anfitrión consulta por la compuerta y por el helper MCP
    ec = srv.estado_de_cuenta("ANF-01", "2026-10", actor_id="ANF-01")
    assert ec.periodo == "2026-10"
    assert ec.total == Decimal("20.00")

    datos_mcp = srv.consultar_estado_cuenta("ANF-01", "2026-10", actor_id="ANF-01")
    assert datos_mcp["periodo"] == "2026-10"
    assert datos_mcp["total"] == "20.00"
    assert datos_mcp["estado"] == "emitido"
    assert datos_mcp["estadias"] == 1


# ¤anfitriones
def test_correccion_posterior_como_linea_ajuste() -> None:
    # RF-ANF-07 (c)
    srv, _seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-AJUSTE",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 1),
        hasta=date(2026, 10, 3),
        total=Decimal("400.00"),
    )
    srv.cerrar_periodo("2026-10", ahora=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc))

    # Se agrega una corrección posterior (ajuste de -$10.00 por reclamo admitido)
    linea = srv.agregar_ajuste(
        anfitrion_id="ANF-01",
        periodo="2026-10",
        solicitud="SOL-AJUSTE-01",
        comision=Decimal("-10.00"),
        actor_id="admin_01",
    )
    assert linea.tipo == "ajuste"
    assert linea.comision == Decimal("-10.00")

    # El estado de cuenta ahora refleja el ajuste y su total coincide
    ec = srv.estado_de_cuenta("ANF-01", "2026-10", actor_id="ANF-01")
    assert len(ec.lineas) == 2
    assert ec.total == Decimal("30.00")  # $40 cargo - $10 ajuste
    assert sum(l.comision for l in ec.lineas) == ec.total


# ¤anfitriones
def test_administrador_registra_pago_con_actor_y_fecha() -> None:
    # US-20 @RF-ANF-08
    srv, seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-PAGO",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 1),
        hasta=date(2026, 10, 3),
        total=Decimal("500.00"),
    )
    estados = srv.cerrar_periodo("2026-10", ahora=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc))
    ec_id = estados[0].estado_cuenta_id

    # Cuando el administrador registra el pago
    fecha_pago = datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc)
    actualizado = srv.registrar_pago(ec_id, actor_id="admin_finanzas", ahora=fecha_pago)

    # Entonces pasa a pagado con actor y fecha
    assert actualizado.estado == EstadoCuenta.PAGADO
    assert actualizado.pago_registrado_por == "admin_finanzas"
    assert actualizado.pagado_en == fecha_pago

    # Y se audita la acción en seguridad
    acciones_auditadas = [getattr(e, "accion", "") for e in seg.eventos]
    assert "registrar_pago" in acciones_auditadas


# ¤anfitriones
def test_estado_cuenta_vencido_pausa_hospedajes_tras_15_dias() -> None:
    # RF-ANF-08
    srv, _seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-MORA",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 1),
        hasta=date(2026, 10, 3),
        total=Decimal("500.00"),
    )
    # Emitido el 5 de noviembre con vence_en = 19 de noviembre (14 días de plazo)
    srv.cerrar_periodo("2026-10", ahora=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc))

    # Al día siguiente del vencimiento (20 de noviembre), pasa a vencido pero aún no se pausa (dentro de los 15 días)
    srv.procesar_cuentas_vencidas(ahora_fecha=date(2026, 11, 20))
    ec = srv.estado_de_cuenta("ANF-01", "2026-10", actor_id="ANF-01")
    assert ec.estado == EstadoCuenta.VENCIDO
    # Hospedajes siguen publicados
    publicados = srv.publicados()
    assert any(h.propiedad_id == "DOMO-01" for h in publicados)

    # A los 15 días tras el vencimiento (19 nov + 15 = 4 de diciembre)
    pausadas = srv.procesar_cuentas_vencidas(ahora_fecha=date(2026, 12, 4))
    assert "DOMO-01" in pausadas

    # Entonces los hospedajes del anfitrión moroso pasan a pausado
    publicados_tras_mora = srv.publicados()
    assert not any(h.propiedad_id == "DOMO-01" for h in publicados_tras_mora)


# ¤anfitriones
def test_aislamiento_anfitrion_no_puede_consultar_cuenta_ajena() -> None:
    # INV_AISLAMIENTO_ANFITRION
    srv, seg, _canal, pms, _obs = _crear_servicio_con_anfitriones()

    _completar_estadia(
        srv,
        pms,
        codigo_reserva="RES-OCT-AISL",
        propiedad_id="DOMO-01",
        anfitrion_id="ANF-01",
        desde=date(2026, 10, 1),
        hasta=date(2026, 10, 3),
        total=Decimal("200.00"),
    )
    srv.cerrar_periodo("2026-10", ahora=datetime(2026, 11, 5, 8, 0, tzinfo=timezone.utc))

    # Anfitrión ANF-02 intenta consultar el estado de cuenta de ANF-01
    with pytest.raises(ErrorAnfitriones) as exc:
        srv.estado_de_cuenta("ANF-01", "2026-10", actor_id="ANF-02")

    assert exc.value.codigo == "ACCESO_DENEGADO"

    # Se audita la denegación en seguridad
    resultados_auditados = [getattr(e, "resultado", "") for e in seg.eventos]
    assert "denegado_aislamiento_anfitrion" in resultados_auditados
