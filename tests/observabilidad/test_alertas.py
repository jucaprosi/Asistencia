# ¤observabilidad
# ¤¤devops-engineer
"""Pruebas del motor y detectores de alertas operativas (RF-OBS-04)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from features.observabilidad.alertas_internal import DetectorAlertas
from features.observabilidad.observabilidad_service import ObservabilidadService, cargar_config
from features.observabilidad.tipos import Span, Traza


# ¤observabilidad
def test_alerta_silencio_webhook_en_horario_operativo() -> None:
    """Dispara silencio_webhook solo si pasan > 2h sin mensajes dentro del horario 08:00-20:00."""
    detector = DetectorAlertas(cargar_config())

    # Caso 1: 14:00 UTC (operativo), último mensaje a las 11:30 (2.5h atrás) -> DISPARA
    ahora_operativo = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)
    ultimo_mensaje_viejo = ahora_operativo - timedelta(hours=2, minutes=30)
    alerta = detector.verificar_silencio_webhook(ahora_operativo, ultimo_mensaje_viejo)
    assert alerta is not None
    assert alerta.nombre == "silencio_webhook"
    assert alerta.severidad == "critica"

    # Caso 2: 22:00 UTC (fuera de horario operativo), último mensaje a las 18:00 -> NO DISPARA
    ahora_nocturno = datetime(2026, 11, 1, 22, 0, 0, tzinfo=timezone.utc)
    alerta_nocturna = detector.verificar_silencio_webhook(ahora_nocturno, ultimo_mensaje_viejo)
    assert alerta_nocturna is None

    # Caso 3: 14:00 UTC, último mensaje a las 13:30 (30m atrás) -> NO DISPARA
    ultimo_reciente = ahora_operativo - timedelta(minutes=30)
    alerta_reciente = detector.verificar_silencio_webhook(ahora_operativo, ultimo_reciente)
    assert alerta_reciente is None


# ¤observabilidad
def test_alerta_tasa_errores_15m() -> None:
    """Dispara tasa_errores_alta si en los últimos 15 min los errores superan el 5%."""
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 20 trazas recientes: 2 con error (10% > 5%) -> DISPARA
    trazas_con_error: list[Traza] = []
    for i in range(18):
        trazas_con_error.append(
            Traza(
                traza_id=f"ok_{i}",
                mensaje_id=f"m_{i}",
                conversacion_id="c1",
                canal="huespedes",
                inicio=ahora - timedelta(minutes=5),
                resultado="resuelta",
            )
        )
    for i in range(2):
        trazas_con_error.append(
            Traza(
                traza_id=f"err_{i}",
                mensaje_id=f"m_err_{i}",
                conversacion_id="c1",
                canal="huespedes",
                inicio=ahora - timedelta(minutes=5),
                resultado="error",
            )
        )

    alerta = detector.verificar_tasa_errores(trazas_con_error, ahora)
    assert alerta is not None
    assert alerta.nombre == "tasa_errores_alta"
    assert alerta.severidad == "critica"

    # 20 trazas sin errores (0% <= 5%) -> NO DISPARA
    trazas_limpias = [
        Traza(
            traza_id=f"clean_{i}",
            mensaje_id=f"m_{i}",
            conversacion_id="c1",
            canal="huespedes",
            inicio=ahora - timedelta(minutes=5),
            resultado="resuelta",
        )
        for i in range(20)
    ]
    assert detector.verificar_tasa_errores(trazas_limpias, ahora) is None


# ¤observabilidad
def test_alerta_cola_crm_congestionada() -> None:
    """Dispara cola_crm_congestionada si la cola supera el límite configurado (10)."""
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 11 elementos en cola -> DISPARA
    alerta = detector.verificar_cola_crm(11, ahora)
    assert alerta is not None
    assert alerta.nombre == "cola_crm_congestionada"
    assert alerta.severidad == "aviso"

    # 8 elementos en cola -> NO DISPARA
    assert detector.verificar_cola_crm(8, ahora) is None


# ¤observabilidad
def test_alerta_costo_diario_excedido() -> None:
    """Dispara costo_diario_excedido si el costo supera el umbral configurado (20 USD)."""
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # 25 USD acumulados -> DISPARA
    alerta = detector.verificar_costo_diario(25.0, ahora)
    assert alerta is not None
    assert alerta.nombre == "costo_diario_excedido"
    assert alerta.severidad == "aviso"

    # 15 USD acumulados -> NO DISPARA
    assert detector.verificar_costo_diario(15.0, ahora) is None


# ¤observabilidad
def test_alerta_evento_muerto_en_canal() -> None:
    """Dispara evento_muerto_canal si hay eventos con estado 'muerto' en canal.eventos_entrantes."""
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    eventos = [
        {"id": "ev_1", "estado": "procesado"},
        {"id": "ev_2", "estado": "muerto"},
    ]
    alerta = detector.verificar_evento_muerto(eventos, ahora)
    assert alerta is not None
    assert alerta.nombre == "evento_muerto_canal"
    assert alerta.severidad == "critica"

    eventos_ok = [{"id": "ev_1", "estado": "procesado"}]
    assert detector.verificar_evento_muerto(eventos_ok, ahora) is None


# ¤observabilidad
def test_alerta_handoff_desatendido() -> None:
    """Dispara handoff_desatendido si un handoff lleva > 15 minutos sin tomar."""
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Handoff creado hace 20 minutos -> DISPARA
    handoffs_demorados = [
        {"id": "h_1", "estado": "pendiente", "creado_en": ahora - timedelta(minutes=20)},
    ]
    alerta = detector.verificar_handoff_desatendido(handoffs_demorados, ahora)
    assert alerta is not None
    assert alerta.nombre == "handoff_desatendido"
    assert alerta.severidad == "critica"

    # Handoff creado hace 5 minutos -> NO DISPARA
    handoffs_recientes = [
        {"id": "h_2", "estado": "pendiente", "creado_en": ahora - timedelta(minutes=5)},
    ]
    assert detector.verificar_handoff_desatendido(handoffs_recientes, ahora) is None


# ¤observabilidad
def test_alerta_venta_no_publicada_tras_24h() -> None:
    """Dispara venta_no_publicada_24h si una venta sigue sin publicar tras 24 horas."""
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Venta creada hace 26 horas -> DISPARA
    ventas_viejas = [
        {"id": "v_1", "estado": "no_publicada", "creado_en": ahora - timedelta(hours=26)},
    ]
    alerta = detector.verificar_venta_no_publicada(ventas_viejas, ahora)
    assert alerta is not None
    assert alerta.nombre == "venta_no_publicada_24h"
    assert alerta.severidad == "aviso"

    # Venta creada hace 4 horas -> NO DISPARA
    ventas_recientes = [
        {"id": "v_2", "estado": "no_publicada", "creado_en": ahora - timedelta(hours=4)},
    ]
    assert detector.verificar_venta_no_publicada(ventas_recientes, ahora) is None


# ¤observabilidad
def test_todas_las_alertas_se_disparan_una_vez() -> None:
    """Escenario: Alertas (@RF-OBS-04).

    Dado datos sintéticos de cada condición de alerta
    Cuando corre la verificación
    Entonces se dispara cada alerta una vez
    """
    detector = DetectorAlertas(cargar_config())
    ahora = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)

    # Sintetizar las 7 condiciones simultáneamente
    trazas_error = [
        Traza("t_err", "m1", "c1", "huespedes", ahora - timedelta(minutes=2), resultado="error")
    ]
    datos_sinteticos = {
        "ultimo_mensaje_at": ahora - timedelta(hours=3),  # 1. Silencio webhook
        "trazas": trazas_error,                            # 2. Tasa de errores (100% > 5%)
        "cola_crm": 15,                                    # 3. Cola CRM > 10
        "costo_diario_usd": 25.50,                         # 4. Costo diario > 20
        "eventos": [{"id": "ev1", "estado": "muerto"}],    # 5. Evento muerto
        "handoffs": [{"id": "h1", "estado": "pendiente", "creado_en": ahora - timedelta(minutes=25)}],  # 6. Handoff > 15m
        "ventas": [{"id": "v1", "estado": "no_publicada", "creado_en": ahora - timedelta(hours=25)}],   # 7. Venta > 24h
    }

    alertas = detector.verificar_todas(ahora=ahora, fuente_datos=datos_sinteticos)
    assert len(alertas) == 7

    nombres = {a.nombre for a in alertas}
    assert nombres == {
        "silencio_webhook",
        "tasa_errores_alta",
        "cola_crm_congestionada",
        "costo_diario_excedido",
        "evento_muerto_canal",
        "handoff_desatendido",
        "venta_no_publicada_24h",
    }


# ¤observabilidad
def test_observabilidad_service_alertas_activas() -> None:
    """Verifica que ObservabilidadService.alertas_activas() delega y retorna alertas."""
    servicio = ObservabilidadService(cargar_config())
    ahora = datetime(2026, 11, 1, 14, 0, 0, tzinfo=timezone.utc)

    fuente = {
        "cola_crm": 12,
        "eventos": [{"id": "e_muerto", "estado": "muerto"}],
    }
    alertas = servicio.alertas_activas(fuente_datos=fuente)
    nombres = {a.nombre for a in alertas}
    assert "cola_crm_congestionada" in nombres
    assert "evento_muerto_canal" in nombres
