# ¤seguridad-canal
# ¤¤security-engineer
"""Pruebas de aviso de privacidad y trazabilidad del consentimiento LOPDP (RF-PRIV-01)."""
from __future__ import annotations

import pytest

from features.seguridad.seguridad_service import (
    SeguridadService,
    Veredicto,
)
from tests.seguridad.dobles import DobleObservabilidad


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_aviso_en_primer_contacto_se_emite_una_sola_vez_y_se_guarda_version(
    servicio: SeguridadService,
) -> None:
    """Escenario: Aviso en el primer contacto (@US-17 @RF-PRIV-01).
    
    Dado un titular sin consentimiento registrado
    Cuando llega su primer mensaje
    Entonces recibe el aviso vigente una sola vez y queda el registro con su versión
    """
    remitente = "+593984443322"

    # Primer mensaje del titular
    msg1 = servicio.filtrar_entrada(remitente, "Hola, buenas noches", canal="huespedes")
    assert not isinstance(msg1, Veredicto)
    # Marca de primer contacto para emitir aviso
    assert "aviso_privacidad_primer_contacto" in msg1.marcas

    # Comprobar registro en base de datos
    cursor = servicio.conexion.execute(
        """
        SELECT consentimiento_id, titular_hash, base, version_aviso, otorgado_en, revocado_en
        FROM seguridad.consentimientos
        WHERE titular_hash = ?
        """,
        (msg1.identidad.numero_hash,),
    )
    fila = cursor.fetchone()
    assert fila is not None
    assert fila["base"] == "aviso_primer_contacto"
    assert fila["version_aviso"] == "1.0"
    assert fila["revocado_en"] is None

    # Segundo mensaje del mismo titular (sin cambio de versión)
    msg2 = servicio.filtrar_entrada(remitente, "¿Tienen cabañas con jacuzzi?", canal="huespedes")
    assert not isinstance(msg2, Veredicto)
    # Ya no debe emitirse el aviso una segunda vez
    assert "aviso_privacidad_primer_contacto" not in msg2.marcas


def test_revocacion_de_consentimiento_permite_reactivar_aviso(
    servicio: SeguridadService,
) -> None:
    """Tras la revocación del consentimiento, el titular vuelve a requerir aviso."""
    remitente = "+593985556677"
    msg1 = servicio.filtrar_entrada(remitente, "Mensaje inicial", canal="huespedes")
    assert not isinstance(msg1, Veredicto)
    titular_hash = msg1.identidad.numero_hash or ""

    # Revocar consentimiento
    servicio.revocar_consentimiento(titular_hash)
    assert not servicio.tiene_consentimiento(titular_hash, version_aviso="1.0")

    # Siguiente mensaje: vuelve a recibir el aviso y a registrar nuevo consentimiento
    msg_post_revocacion = servicio.filtrar_entrada(remitente, "Mensaje tras revocacion", canal="huespedes")
    assert not isinstance(msg_post_revocacion, Veredicto)
    assert "aviso_privacidad_primer_contacto" in msg_post_revocacion.marcas
    assert servicio.tiene_consentimiento(titular_hash, version_aviso="1.0")
