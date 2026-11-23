# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de rate limit no anulable por remitente (RF-SEC-03, INV_RATE_LIMIT_NO_ANULABLE)."""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from features.seguridad.seguridad_service import (
    Identidad,
    Rol,
    SeguridadService,
    Veredicto,
)
from tests.seguridad.dobles import DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_limite_30_mensajes_por_minuto_emite_un_solo_aviso_y_descarta(servicio: SeguridadService) -> None:
    """Escenario: Límite por remitente.
    
    Dado un remitente que supera 30 mensajes por minuto
    Cuando sigue escribiendo
    Entonces recibe un solo aviso y sus mensajes se descartan hasta el fin de la ventana
    """
    remitente = "+593991112233"

    # Enviar los 30 mensajes permitidos
    for i in range(30):
        t = datetime(2026, 11, 1, 10, 0, i % 30, tzinfo=timezone.utc)
        limpio = servicio.filtrar_entrada(remitente, f"Mensaje {i+1}", canal="huespedes", instante=t)
        assert not isinstance(limpio, Veredicto), f"Mensaje {i+1} no debió ser bloqueado"

    # Mensaje 31 (supera 30/min): debe ser rechazado con el primer y único aviso
    t31 = datetime(2026, 11, 1, 10, 0, 31, tzinfo=timezone.utc)
    res_aviso = servicio.filtrar_entrada(remitente, "Mensaje 31", canal="huespedes", instante=t31)
    assert isinstance(res_aviso, Veredicto)
    assert res_aviso.permitido is False
    assert "aviso" in (res_aviso.motivo or "").lower()

    # Mensaje 32 en adelante: debe ser descartado silenciosamente (sin aviso repetido)
    t32 = datetime(2026, 11, 1, 10, 0, 32, tzinfo=timezone.utc)
    res_descarte = servicio.filtrar_entrada(remitente, "Mensaje 32", canal="huespedes", instante=t32)
    assert isinstance(res_descarte, Veredicto)
    assert res_descarte.permitido is False
    assert "descartado" in (res_descarte.motivo or "").lower()


def test_limite_2_mensajes_por_segundo(servicio: SeguridadService) -> None:
    """Control de ráfagas: máximo 2 mensajes por segundo."""
    remitente = "+593994445566"
    mismo_segundo = datetime(2026, 11, 1, 12, 30, 15, tzinfo=timezone.utc)

    # Mensaje 1 y 2 en el mismo segundo: permitidos
    res1 = servicio.filtrar_entrada(remitente, "Hola 1", canal="huespedes", instante=mismo_segundo)
    assert not isinstance(res1, Veredicto)

    res2 = servicio.filtrar_entrada(remitente, "Hola 2", canal="huespedes", instante=mismo_segundo)
    assert not isinstance(res2, Veredicto)

    # Mensaje 3 en el mismo segundo: bloqueado
    res3 = servicio.filtrar_entrada(remitente, "Hola 3", canal="huespedes", instante=mismo_segundo)
    assert isinstance(res3, Veredicto)
    assert res3.permitido is False
    assert "LimiteExcedido" in (res3.motivo or "")


@pytest.mark.parametrize(
    "rol",
    [
        Rol.HUESPED_POTENCIAL,
        Rol.HUESPED_ACTIVO,
        Rol.VENDEDOR,
        Rol.LIDER,
        Rol.GESTOR,
        Rol.ADMINISTRADOR,
        Rol.ANFITRION,
        Rol.SISTEMA,
        Rol.DESCONOCIDO,
    ],
)
def test_intento_desactivar_limite_con_cada_rol_falla_y_aplica_rate_limit(
    servicio: SeguridadService, rol: Rol
) -> None:
    """Hecho cuando: test_rate_limit.py intenta desactivar el límite con cada rol y falla.
    
    Invariante INV_RATE_LIMIT_NO_ANULABLE: Ningún rol ni configuración puede desactivar
    el límite de tasa por remitente.
    """
    remitente_hash = f"hash_prueba_rol_{rol.value}"

    # 1. Verificación directa en el motor de RateLimiter:
    # Se simulan intentos deliberados de evadir o anular el rate limiter con el rol indicado
    for i in range(30):
        t = datetime(2026, 11, 1, 14, 0, i % 30, tzinfo=timezone.utc)
        veredicto = servicio._rate_limiter.verificar(
            remitente_hash,
            rol=rol,
            instante=t,
            desactivar=True,
            bypass_rate_limit=True,
            limite=None,
            skip_limits=True,
        )
        assert veredicto.permitido is True, f"Mensaje {i+1} para rol {rol.value} debió ser permitido dentro de cuota"

    # Mensaje 31: a pesar de intentar anular el límite con el rol (incluso ADMINISTRADOR), el límite actúa y falla la evasión
    t31 = datetime(2026, 11, 1, 14, 0, 31, tzinfo=timezone.utc)
    veredicto_excedido = servicio._rate_limiter.verificar(
        remitente_hash,
        rol=rol,
        instante=t31,
        desactivar=True,
        bypass_rate_limit=True,
    )
    assert veredicto_excedido.permitido is False, f"El rol {rol.value} no debe poder anular el rate limit"
    assert "LimiteExcedido" in (veredicto_excedido.motivo or "")

    # 2. Verificación adicional a través de filtrar_entrada si el remitente interactúa por canal
    remitente_tel = f"+593996600{abs(hash(rol.value)) % 1000:03d}"
    if rol in {Rol.VENDEDOR, Rol.LIDER, Rol.GESTOR, Rol.ADMINISTRADOR, Rol.ANFITRION}:
        admin_actor = Identidad(remitente_token="tok_admin", rol=Rol.ADMINISTRADOR, sujeto_id="admin_01")
        servicio.administrar_usuarios(admin_actor, remitente_tel, rol, alta=True, sujeto_id=f"usr_{rol.value}")
        canal = "vendedores"
    elif rol == Rol.HUESPED_ACTIVO:
        servicio.registrar_reserva_activa(remitente_tel)
        canal = "huespedes"
    else:
        canal = "huespedes"

    for i in range(30):
        t = datetime(2026, 11, 1, 15, 0, i % 30, tzinfo=timezone.utc)
        servicio.filtrar_entrada(remitente_tel, f"Msg {i+1}", canal=canal, instante=t, desactivar=True)

    t_tope = datetime(2026, 11, 1, 15, 0, 31, tzinfo=timezone.utc)
    res_tope = servicio.filtrar_entrada(remitente_tel, "Msg 31", canal=canal, instante=t_tope, desactivar=True)
    assert isinstance(res_tope, Veredicto)
    assert res_tope.permitido is False
    assert "LimiteExcedido" in (res_tope.motivo or "")
