# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PRIV-04 e INV_CRIPTOBORRADO (Eliminación irreversible por criptoborrado).

Verifica:
1. La eliminación por criptoborrado borra las filas de la bóveda de tokens del titular.
2. Los tokens en audit log e historial quedan irrecuperables.
3. Rehidratar un token borrado devuelve un marcador neutro ([DATO_BORRADO]).
4. Las filas existentes del audit log no se modifican bajo ninguna circunstancia.
"""
from __future__ import annotations

import pytest

from features.seguridad.seguridad_service import SeguridadService
from tests.seguridad.dobles import DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_eliminacion_por_criptoborrado_invalida_tokens_y_preserva_audit_log(
    servicio: SeguridadService,
) -> None:
    """Escenario: Eliminación por criptoborrado (@US-17 @RF-PRIV-04 @INV_CRIPTOBORRADO).
    
    Dado una solicitud de eliminación aprobada
    Cuando el administrador la ejecuta
    Entonces se borran las filas de la bóveda del titular
    Y los tokens en audit log e historial quedan irrecuperables
    Y las filas del audit log no se modifican
    """
    remitente = "+593991122334"
    titular_hash = "hash_titular_carlos_123"
    conversacion_id = "conv_cripto_001"

    # 1. El titular envía un mensaje con PII
    mensaje_original = "Mi nombre es Carlos Andrade y mi teléfono es 0991122334"
    limpio = servicio.filtrar_entrada(
        remitente, mensaje_original, canal="huespedes", conversacion_id=conversacion_id
    )
    assert not isinstance(limpio, str)
    texto_tokenizado = limpio.texto_tokenizado

    # Verificar que se puede rehidratar antes del criptoborrado
    rehidratado_inicial = servicio.rehidratar(texto_tokenizado, conversacion_id)
    assert "Carlos Andrade" in rehidratado_inicial

    # Verificar que las filas existen en la bóveda
    boveda_antes = servicio.conexion.execute(
        "SELECT COUNT(*) as c FROM seguridad.boveda_tokens WHERE titular_hash = ?",
        (limpio.identidad.numero_hash,),
    ).fetchone()["c"]
    assert boveda_antes >= 1

    # Capturar estado del audit_log antes del criptoborrado
    filas_audit_antes = [
        dict(f)
        for f in servicio.conexion.execute(
            "SELECT audit_id, instante, actor_token, accion, resultado FROM seguridad.audit_log ORDER BY instante ASC"
        ).fetchall()
    ]
    total_audit_antes = len(filas_audit_antes)

    # 2. Cuando el administrador ejecuta el criptoborrado del titular
    resultado = servicio.ejecutar_criptoborrado(limpio.identidad.numero_hash, actor_id="usr_admin")
    assert resultado["tokens_eliminados"] >= 1

    # 3. Entonces se borran las filas de la bóveda del titular
    boveda_despues = servicio.conexion.execute(
        "SELECT COUNT(*) as c FROM seguridad.boveda_tokens WHERE titular_hash = ?",
        (limpio.identidad.numero_hash,),
    ).fetchone()["c"]
    assert boveda_despues == 0, "Todas las filas de la bóveda del titular deben eliminarse"

    # 4. Y rehidratar un token borrado devuelve un marcador neutro ([DATO_BORRADO])
    rehidratado_despues = servicio.rehidratar(texto_tokenizado, conversacion_id)
    assert "Carlos Andrade" not in rehidratado_despues, "La PII no debe poder restituirse"
    assert "[DATO_BORRADO]" in rehidratado_despues, (
        f"Rehidratar token borrado debe devolver marcador neutro [DATO_BORRADO], obtenido: {rehidratado_despues}"
    )

    # 5. Y las filas del audit log previas NO se modificaron
    filas_audit_despues = [
        dict(f)
        for f in servicio.conexion.execute(
            "SELECT audit_id, instante, actor_token, accion, resultado FROM seguridad.audit_log ORDER BY instante ASC"
        ).fetchall()
    ]
    # Las filas previas son exactamente idénticas
    assert filas_audit_despues[:total_audit_antes] == filas_audit_antes, (
        "INV_CRIPTOBORRADO: Las filas históricas del audit log deben permanecer inalteradas"
    )

    # Solo se añadió el evento del criptoborrado
    ultimo_evento = filas_audit_despues[-1]
    assert ultimo_evento["accion"] == "criptoborrado"
    assert ultimo_evento["actor_token"] == "usr_admin"
    assert ultimo_evento["resultado"] == "ejecutado"
