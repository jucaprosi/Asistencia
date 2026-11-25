# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-406 (propuesta): la numeración de tokens PII no reutiliza un token para valores distintos (INV_PII_FUERA_DEL_MODELO).

Defectos reproducidos en main 077ab65:
- el contador por tipo se reinicia en cada llamada a ``tokenizar``: dos teléfonos distintos de una misma
  conversación reciben ``[TELEFONO_1]`` y al rehidratar el primero se entrega el segundo;
- la rehidratación cae a la bóveda global por token sin conversación: una conversación ajena rehidrata
  ``[TELEFONO_1]`` con el teléfono de otra persona.
"""
from __future__ import annotations

import pytest

from features.seguridad.seguridad_service import SeguridadService
from tests.seguridad.dobles import DobleObservabilidad

TELEFONO_A = "0991111111"
TELEFONO_B = "0982222222"


@pytest.fixture
def servicio() -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


def test_t406_dos_telefonos_distintos_en_llamadas_sucesivas_reciben_tokens_distintos(servicio: SeguridadService) -> None:
    primero = servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    segundo = servicio.tokenizar(f"el de mi esposa es {TELEFONO_B}", "conv-1")
    token_a = primero.removeprefix("mi telefono es ")
    token_b = segundo.removeprefix("el de mi esposa es ")
    assert TELEFONO_A not in primero and TELEFONO_B not in segundo
    assert token_a != token_b


def test_t406_rehidratar_el_primer_mensaje_devuelve_su_propio_telefono(servicio: SeguridadService) -> None:
    primero = servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    servicio.tokenizar(f"el de mi esposa es {TELEFONO_B}", "conv-1")
    assert servicio.rehidratar(primero, "conv-1") == f"mi telefono es {TELEFONO_A}"


def test_t406_el_mismo_valor_en_la_misma_conversacion_conserva_su_token(servicio: SeguridadService) -> None:
    primero = servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    repetido = servicio.tokenizar(f"repito: {TELEFONO_A}", "conv-1")
    assert primero.removeprefix("mi telefono es ") == repetido.removeprefix("repito: ")


def test_t406_una_conversacion_ajena_no_rehidrata_tokens_de_otra(servicio: SeguridadService) -> None:
    token_a = servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-A").removeprefix("mi telefono es ")
    rehidratado = servicio.rehidratar(f"llamar a {token_a}", "conv-C")
    assert TELEFONO_A not in rehidratado


def test_t406_el_modelo_escribiendo_un_token_en_conversacion_ajena_no_rehidrata_nada(servicio: SeguridadService) -> None:
    servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-A")
    salida = servicio.filtrar_salida("Puedes llamar a [TELEFONO_1] o escribir a [CORREO_1].", "conv-sin-tokens")
    assert TELEFONO_A not in salida
    assert "[TELEFONO_1]" not in salida  # queda el marcador neutro, nunca un dato


def test_t406_tras_reiniciar_la_cache_un_telefono_nuevo_no_reutiliza_un_token_de_la_boveda(
    servicio: SeguridadService,
) -> None:
    primero = servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    # Un servicio nuevo sobre la misma conexión equivale a un reinicio: la bóveda persiste, la caché no.
    reiniciado = SeguridadService({}, observabilidad=DobleObservabilidad(), conexion=servicio.conexion)
    segundo = reiniciado.tokenizar(f"el de mi esposa es {TELEFONO_B}", "conv-1")
    assert primero.removeprefix("mi telefono es ") != segundo.removeprefix("el de mi esposa es ")
    assert reiniciado.rehidratar(primero, "conv-1") == f"mi telefono es {TELEFONO_A}"
    assert reiniciado.rehidratar(segundo, "conv-1") == f"el de mi esposa es {TELEFONO_B}"
