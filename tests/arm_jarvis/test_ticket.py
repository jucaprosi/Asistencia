# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas del generador de tickets numerados y prueba de concurrencia (RF-ARM-05, INV_TICKET_UNICO)."""
from __future__ import annotations

import concurrent.futures
from decimal import Decimal
from typing import Any

import pytest

from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.persistencia_internal import RepositorioArm
from features.arm_jarvis.ticket_internal import GeneradorTickets
from features.arm_jarvis.tipos import EstadoVenta


# ¤arm-jarvis
def test_venta_completa_recibe_ticket_con_resumen() -> None:
    """Escenario: Venta completa (@US-05 @CU-04 @RF-ARM-02 @RF-ARM-05).

    Dado un vendedor en la whitelist
    Cuando escribe 'vendí 3 noches en el depa del centro a María López, 450, llega el 15'
    Entonces recibe un ticket V-AAAA-NNNN con cliente, producto, monto, llegada y comisión estimada
    Y la venta queda 'por_validar' con noches 3 y fecha_llegada
    """
    servicio = ArmJarvisService()
    v = servicio.registrar_vendedor(telefono_token="tel_ticket_1", nombre="Vendedor Whitelist")

    class Msg:
        remitente = "tel_ticket_1"
        texto = "vendí 3 noches en el depa del centro a María López, 450, llega el 15"
        mensaje_id = "msg_completo_1"

    respuesta = servicio.procesar(Msg())

    # Formato de ticket
    assert "Ticket: V-" in respuesta
    assert "María López" in respuesta
    assert "depa del centro" in respuesta
    assert "450.00 USD" in respuesta
    assert "Noches: 3" in respuesta
    assert "Comisión estimada:" in respuesta

    # Sin rastros de marcas de gobernanza en el texto de respuesta al usuario
    assert "¤" not in respuesta
    assert "¦" not in respuesta

    ventas = servicio.listar(vendedor_id=v.vendedor_id)
    assert len(ventas) == 1
    assert ventas[0].estado == EstadoVenta.POR_VALIDAR
    assert ventas[0].extraida.noches == 3
    assert ventas[0].extraida.fecha_llegada is not None
    assert ventas[0].extraida.fecha_llegada.day == 15


# ¤arm-jarvis
def test_tickets_bajo_concurrencia_sin_huecos_ni_duplicados() -> None:
    """Escenario: Tickets bajo concurrencia (@RF-ARM-05 @INV_TICKET_UNICO).

    Dado 50 ventas registradas en paralelo, algunas con fallo y ROLLBACK
    Cuando terminan
    Entonces los tickets son consecutivos, sin huecos ni repetidos
    """
    repo = RepositorioArm()
    generador = GeneradorTickets(repo.conexion)
    anio = 2026

    tickets_exitosos: list[str] = []
    errores_provocados = 0

    def _operacion(indice: int) -> str:
        def _insercion(ticket: str) -> str:
            # Provocar fallos intencionales cada 5 iteraciones para verificar que el ROLLBACK no deja huecos
            if indice % 5 == 0:
                raise RuntimeError(f"Fallo forzado en insercion {indice}")
            return ticket

        ticket_gen, _ = generador.generar_ticket_con_transaccion(anio, _insercion)
        return ticket_gen

    # Ejecutar 50 operaciones en paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futuros = [executor.submit(_operacion, i + 1) for i in range(50)]
        for f in futuros:
            try:
                t = f.result()
                tickets_exitosos.append(t)
            except RuntimeError:
                errores_provocados += 1

    # Hubo fallos y rollbacks
    assert errores_provocados == 10
    assert len(tickets_exitosos) == 40

    # Extraer números secuenciales
    numeros = [int(t.split("-")[-1]) for t in tickets_exitosos]
    numeros_ordenados = sorted(numeros)

    # Verificar que no hay duplicados
    assert len(numeros_ordenados) == len(set(numeros_ordenados))

    # Verificar que son estrictamente consecutivos desde 1 hasta 40 sin huecos (INV_TICKET_UNICO)
    assert numeros_ordenados == list(range(1, 41))
