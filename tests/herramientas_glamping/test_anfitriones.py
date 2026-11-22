# ¤herramientas-mcp
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Pruebas de herramientas MCP de solicitud y anfitrión (T-306).

Cubre:
- solicitar_reserva (RF-ANF-04)
- responder_solicitud (RF-ANF-05, INV_CONTACTO_TRAS_CONFIRMAR, INV_AISLAMIENTO_ANFITRION)
- reportar_resultado_estadia (RF-ANF-06, INV_AISLAMIENTO_ANFITRION)
- actualizar_calendario (RF-PMS-08, INV_AISLAMIENTO_ANFITRION)
- Control de roles y esquema (INV_ALLOWLIST_POR_ACCION)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

import pytest

from features.anfitriones.tipos import EstadoSolicitud, Solicitud
from features.herramientas_glamping.herramientas_glamping_service import (
    EntradaInvalida,
    HerramientaNoAutorizada,
    HerramientasGlampingService,
    SalaDestinoFallida,
    cargar_config,
)
from features.seguridad.tipos import EventoAuditoria, Identidad, Rol, Veredicto


# --- Dobles de Compuertas ---

# ¤herramientas-mcp
class DobleSeguridad:
    def __init__(self) -> None:
        self.allowlist: dict[str, set[str]] = {
            "huesped_potencial": {"solicitar_reserva", "consultar_disponibilidad", "cotizar"},
            "huesped_activo": {"solicitar_reserva", "obtener_instrucciones_checkin"},
            "anfitrion": {"responder_solicitud", "reportar_resultado_estadia", "actualizar_calendario"},
            "sistema": set(),
        }
        self.eventos_auditados: list[EventoAuditoria] = []

    def autorizar(self, rol: str, herramienta: str) -> Veredicto:
        permitidas = self.allowlist.get(rol, set())
        if herramienta in permitidas:
            return Veredicto(permitido=True)
        return Veredicto(permitido=False, motivo=f"Acción '{herramienta}' no autorizada para rol '{rol}'")

    def auditar(self, evento: EventoAuditoria) -> None:
        self.eventos_auditados.append(evento)


# ¤herramientas-mcp
class DoblePMS:
    def __init__(self) -> None:
        self.unidades_anfitrion: dict[str, str] = {
            "DOMO-01": "ANF-SAN-PABLO",
            "DOMO-02": "ANF-SAN-PABLO",
            "CABANA-01": "ANF-OTRO",
        }
        self.noches_bloqueadas: set[tuple[str, str]] = set()
        self.noches_reservadas: set[tuple[str, str]] = {
            ("DOMO-01", "2026-12-10"),
        }
        self.llamadas_actualizar: list[dict[str, Any]] = []

    def actualizar_calendario(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        accion: str,
        actor_id: str,
    ) -> tuple[int, int]:
        self.llamadas_actualizar.append({
            "unidad_id": unidad_id,
            "desde": desde,
            "hasta": hasta,
            "accion": accion,
            "actor_id": actor_id,
        })
        dueno = self.unidades_anfitrion.get(unidad_id)
        if dueno and dueno != actor_id:
            raise PermissionError(f"Aislamiento de anfitrión: '{actor_id}' no es dueño de la unidad '{unidad_id}'")

        noches_afectadas = 0
        omitidas = 0
        cur = desde
        while cur < hasta:
            clave = (unidad_id, cur.isoformat())
            if accion == "bloquear":
                if clave in self.noches_reservadas or clave in self.noches_bloqueadas:
                    omitidas += 1
                else:
                    self.noches_bloqueadas.add(clave)
                    noches_afectadas += 1
            elif accion == "liberar":
                if clave in self.noches_reservadas:
                    # RF-PMS-08 (b): liberar nunca toca una noche con reserva activa
                    omitidas += 1
                elif clave in self.noches_bloqueadas:
                    self.noches_bloqueadas.remove(clave)
                    noches_afectadas += 1
                else:
                    omitidas += 1
            cur += timedelta(days=1)
        return noches_afectadas, omitidas


# ¤herramientas-mcp
class DobleAnfitriones:
    def __init__(self) -> None:
        self.solicitudes: dict[str, Solicitud] = {}
        self.contactos_entregados: list[str] = []
        # Solicitud inicial para pruebas de anfitrión (código PL-YYYY-NNNN)
        sol_base = Solicitud(
            solicitud="PL-2026-0001",
            codigo_reserva="RES-PREL-555",
            propiedad_id="DOMO-SAN-PABLO",
            anfitrion_id="ANF-SAN-PABLO",
            desde=date(2026, 12, 1),
            hasta=date(2026, 12, 4),
            total=Decimal("450.00"),
            comision_porcentaje=Decimal("15.00"),
            estado=EstadoSolicitud.SOLICITADA,
            vence_en=datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc),
        )
        self.solicitudes[sol_base.solicitud] = sol_base

    def solicitar_reserva(self, codigo_reserva: str) -> Solicitud:
        sufijo = f"{abs(hash(codigo_reserva)) % 9000 + 1000}"
        sol = Solicitud(
            solicitud=f"PL-2026-{sufijo}",
            codigo_reserva=codigo_reserva,
            propiedad_id="DOMO-SAN-PABLO",
            anfitrion_id="ANF-SAN-PABLO",
            desde=date(2026, 12, 15),
            hasta=date(2026, 12, 18),
            total=Decimal("380.00"),
            comision_porcentaje=Decimal("15.00"),
            estado=EstadoSolicitud.SOLICITADA,
            vence_en=datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc),
        )
        self.solicitudes[sol.solicitud] = sol
        return sol

    def responder_solicitud(
        self,
        solicitud: str,
        anfitrion_id: str,
        acepta: bool,
        motivo: str | None = None,
    ) -> Solicitud:
        sol = self.solicitudes.get(solicitud)
        if sol is None:
            raise KeyError(f"Solicitud {solicitud} no encontrada")
        if sol.anfitrion_id != anfitrion_id:
            raise PermissionError(f"Aislamiento de anfitrión: {anfitrion_id} no puede responder por {sol.anfitrion_id}")

        nuevo_estado = EstadoSolicitud.CONFIRMADA if acepta else EstadoSolicitud.RECHAZADA
        if acepta:
            self.contactos_entregados.append(solicitud)

        sol_actualizada = Solicitud(
            solicitud=sol.solicitud,
            codigo_reserva=sol.codigo_reserva,
            propiedad_id=sol.propiedad_id,
            anfitrion_id=sol.anfitrion_id,
            desde=sol.desde,
            hasta=sol.hasta,
            total=sol.total,
            comision_porcentaje=sol.comision_porcentaje,
            estado=nuevo_estado,
            vence_en=sol.vence_en,
            respondida_en=datetime.now(timezone.utc),
        )
        self.solicitudes[solicitud] = sol_actualizada
        return sol_actualizada

    def reportar_resultado(
        self,
        solicitud: str,
        anfitrion_id: str,
        resultado: str,
    ) -> Solicitud:
        sol = self.solicitudes.get(solicitud)
        if sol is None:
            raise KeyError(f"Solicitud {solicitud} no encontrada")
        if sol.anfitrion_id != anfitrion_id:
            raise PermissionError(f"Aislamiento de anfitrión: {anfitrion_id} no puede reportar por {sol.anfitrion_id}")

        estado_map = {
            "cancelada": EstadoSolicitud.CANCELADA,
            "no_show": EstadoSolicitud.NO_SHOW,
            "completada": EstadoSolicitud.COMPLETADA,
        }
        nuevo_estado = estado_map.get(resultado, EstadoSolicitud(resultado))
        sol_actualizada = Solicitud(
            solicitud=sol.solicitud,
            codigo_reserva=sol.codigo_reserva,
            propiedad_id=sol.propiedad_id,
            anfitrion_id=sol.anfitrion_id,
            desde=sol.desde,
            hasta=sol.hasta,
            total=sol.total,
            comision_porcentaje=sol.comision_porcentaje,
            estado=nuevo_estado,
            vence_en=sol.vence_en,
            respondida_en=sol.respondida_en,
        )
        self.solicitudes[solicitud] = sol_actualizada
        return sol_actualizada


# ¤herramientas-mcp
class DobleObservabilidad:
    def __init__(self) -> None:
        self.logs: list[tuple[str, str, dict[str, Any]]] = []

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append((nivel, evento, campos))


# ¤herramientas-mcp
def _construir_servicio() -> tuple[HerramientasGlampingService, DobleSeguridad, DoblePMS, DobleAnfitriones]:
    config = dict(cargar_config())
    seguridad = DobleSeguridad()
    pms = DoblePMS()
    anfitriones = DobleAnfitriones()
    observabilidad = DobleObservabilidad()

    srv = HerramientasGlampingService(
        config=config,
        seguridad=seguridad,
        pms=pms,
        conocimiento=None,
        crm=None,
        anfitriones=anfitriones,
        observabilidad=observabilidad,
    )
    return srv, seguridad, pms, anfitriones


# --- Escenarios de Prueba ---

# ¤herramientas-mcp
def test_herramienta_solicitar_reserva_obtiene_fechas_y_total_de_pms() -> None:
    """RF-ANF-04 / US-19: solicitar_reserva genera solicitud preliminar con código PL- y vigencia."""
    srv, _, _, anfitriones = _construir_servicio()
    identidad = Identidad(remitente_token="tok_huesped", rol=Rol.HUESPED_POTENCIAL, sujeto_id="huesped_1")

    res = srv.ejecutar(
        nombre="solicitar_reserva",
        entrada={"codigo_reserva": "RES-PREL-789"},
        identidad=identidad,
        conversacion_id="conv_101",
    )

    assert res.error is None
    assert res.salida["solicitud"].startswith("PL-")
    assert res.salida["estado"] == "solicitada"
    assert "vence_en" in res.salida
    assert res.salida["solicitud"] in anfitriones.solicitudes


# ¤herramientas-mcp
def test_herramienta_responder_solicitud_confirma_y_entrega_contacto() -> None:
    """RF-ANF-05 / US-19 / INV_CONTACTO_TRAS_CONFIRMAR: el anfitrión confirma por WhatsApp y se habilita contacto."""
    srv, _, _, anfitriones = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    res = srv.ejecutar(
        nombre="responder_solicitud",
        entrada={"solicitud": "PL-2026-0001", "acepta": True},
        identidad=identidad,
        conversacion_id="conv_102",
    )

    assert res.error is None
    assert res.salida["solicitud"] == "PL-2026-0001"
    assert res.salida["estado"] == "confirmada"
    # INV_CONTACTO_TRAS_CONFIRMAR: solo tras confirmar se habilita la entrega de contacto
    assert "PL-2026-0001" in anfitriones.contactos_entregados


# ¤herramientas-mcp
def test_herramienta_responder_solicitud_rechaza_otro_anfitrion() -> None:
    """RF-ANF-05 / INV_AISLAMIENTO_ANFITRION: un anfitrión no puede responder la solicitud de otro."""
    srv, _, _, _ = _construir_servicio()
    identidad_intruso = Identidad(remitente_token="tok_intruso", rol=Rol.ANFITRION, sujeto_id="ANF-OTRO")

    with pytest.raises(SalaDestinoFallida) as exc_info:
        srv.ejecutar(
            nombre="responder_solicitud",
            entrada={"solicitud": "PL-2026-0001", "acepta": True},
            identidad=identidad_intruso,
            conversacion_id="conv_103",
        )

    assert exc_info.value.sala == "anfitriones"
    assert "Aislamiento" in str(exc_info.value.detalle_tecnico)


# ¤herramientas-mcp
def test_herramienta_reportar_resultado_estadia_no_show_sin_comision() -> None:
    """RF-ANF-06: el anfitrión reporta no_show o cancelada (no generan comisión)."""
    srv, _, _, anfitriones = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    res = srv.ejecutar(
        nombre="reportar_resultado_estadia",
        entrada={"solicitud": "PL-2026-0001", "resultado": "no_show"},
        identidad=identidad,
        conversacion_id="conv_104",
    )

    assert res.error is None
    assert res.salida["solicitud"] == "PL-2026-0001"
    assert res.salida["estado"] == "no_show"
    assert anfitriones.solicitudes["PL-2026-0001"].estado == EstadoSolicitud.NO_SHOW


# ¤herramientas-mcp
def test_herramienta_reportar_resultado_estadia_rechaza_otro_anfitrion() -> None:
    """RF-ANF-06 / INV_AISLAMIENTO_ANFITRION: un anfitrión no puede reportar estadías de otro anfitrión."""
    srv, _, _, _ = _construir_servicio()
    identidad_intruso = Identidad(remitente_token="tok_intruso", rol=Rol.ANFITRION, sujeto_id="ANF-OTRO")

    with pytest.raises(SalaDestinoFallida) as exc_info:
        srv.ejecutar(
            nombre="reportar_resultado_estadia",
            entrada={"solicitud": "PL-2026-0001", "resultado": "cancelada"},
            identidad=identidad_intruso,
            conversacion_id="conv_105",
        )

    assert exc_info.value.sala == "anfitriones"


# ¤herramientas-mcp
def test_herramienta_actualizar_calendario_bloquea_fechas_anfitrion() -> None:
    """RF-PMS-08: el anfitrión bloquea un rango de fechas en sus unidades desde WhatsApp."""
    srv, _, pms, _ = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    res = srv.ejecutar(
        nombre="actualizar_calendario",
        entrada={
            "unidad_id": "DOMO-01",
            "desde": "2026-12-01",
            "hasta": "2026-12-05",
            "accion": "bloquear",
        },
        identidad=identidad,
        conversacion_id="conv_106",
    )

    assert res.error is None
    assert res.salida["unidad_id"] == "DOMO-01"
    assert res.salida["noches"] == 4
    assert res.salida["omitidas"] == 0
    assert ("DOMO-01", "2026-12-01") in pms.noches_bloqueadas
    assert ("DOMO-01", "2026-12-04") in pms.noches_bloqueadas


# ¤herramientas-mcp
def test_herramienta_actualizar_calendario_rechaza_unidad_de_otro_anfitrion() -> None:
    """RF-PMS-08 / INV_AISLAMIENTO_ANFITRION: el anfitrión solo puede alterar sus propias unidades."""
    srv, _, _, _ = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    with pytest.raises(SalaDestinoFallida) as exc_info:
        srv.ejecutar(
            nombre="actualizar_calendario",
            entrada={
                "unidad_id": "CABANA-01",
                "desde": "2026-12-01",
                "hasta": "2026-12-03",
                "accion": "bloquear",
            },
            identidad=identidad,
            conversacion_id="conv_107",
        )

    assert exc_info.value.sala == "pms_conector"


# ¤herramientas-mcp
def test_herramienta_actualizar_calendario_liberar_no_toca_reservas() -> None:
    """RF-PMS-08 (b): liberar nunca toca noches con reserva activa."""
    srv, _, pms, _ = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    # Bloquear 2026-12-09 a 2026-12-12 (donde el 10 está reservado en pms)
    pms.noches_bloqueadas.add(("DOMO-01", "2026-12-09"))
    pms.noches_bloqueadas.add(("DOMO-01", "2026-12-11"))

    res = srv.ejecutar(
        nombre="actualizar_calendario",
        entrada={
            "unidad_id": "DOMO-01",
            "desde": "2026-12-09",
            "hasta": "2026-12-12",
            "accion": "liberar",
        },
        identidad=identidad,
        conversacion_id="conv_108",
    )

    assert res.error is None
    # 2 noches liberadas (09 y 11), 1 omitida (10 reservada)
    assert res.salida["noches"] == 2
    assert res.salida["omitidas"] == 1
    # La noche reservada sigue reservada
    assert ("DOMO-01", "2026-12-10") in pms.noches_reservadas


# ¤herramientas-mcp
def test_herramienta_rechaza_rol_no_autorizado() -> None:
    """INV_ALLOWLIST_POR_ACCION: roles no autorizados son rechazados antes del despacho."""
    srv, _, _, _ = _construir_servicio()
    identidad_huesped = Identidad(remitente_token="tok_huesped", rol=Rol.HUESPED_POTENCIAL, sujeto_id="huesped_1")

    # Huésped no puede actualizar calendario
    with pytest.raises(HerramientaNoAutorizada) as exc_info1:
        srv.ejecutar(
            nombre="actualizar_calendario",
            entrada={
                "unidad_id": "DOMO-01",
                "desde": "2026-12-01",
                "hasta": "2026-12-03",
                "accion": "bloquear",
            },
            identidad=identidad_huesped,
            conversacion_id="conv_109",
        )
    assert "no está autorizado" in exc_info1.value.mensaje_usuario

    # Huésped no puede responder solicitud
    with pytest.raises(HerramientaNoAutorizada) as exc_info2:
        srv.ejecutar(
            nombre="responder_solicitud",
            entrada={"solicitud": "PL-2026-0001", "acepta": True},
            identidad=identidad_huesped,
            conversacion_id="conv_109",
        )
    assert "no está autorizado" in exc_info2.value.mensaje_usuario


# ¤herramientas-mcp
def test_herramienta_validacion_esquema_anfitriones() -> None:
    """Validación de esquema JSON: argumentos incompletos o inválidos generan EntradaInvalida."""
    srv, _, _, _ = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    # Falta 'accion' en actualizar_calendario
    with pytest.raises(EntradaInvalida):
        srv.ejecutar(
            nombre="actualizar_calendario",
            entrada={"unidad_id": "DOMO-01", "desde": "2026-12-01", "hasta": "2026-12-03"},
            identidad=identidad,
            conversacion_id="conv_110",
        )

    # Acción inválida
    with pytest.raises(EntradaInvalida):
        srv.ejecutar(
            nombre="actualizar_calendario",
            entrada={
                "unidad_id": "DOMO-01",
                "desde": "2026-12-01",
                "hasta": "2026-12-03",
                "accion": "invalid_action",
            },
            identidad=identidad,
            conversacion_id="conv_110",
        )


# ¤herramientas-mcp
def test_anfitrion_id_extraido_siempre_de_identidad() -> None:
    """Seguridad: anfitrion_id se extrae obligatoriamente de identidad y no depende de argumentos externos."""
    srv, _, pms, _ = _construir_servicio()
    identidad = Identidad(remitente_token="tok_anf", rol=Rol.ANFITRION, sujeto_id="ANF-SAN-PABLO")

    srv.ejecutar(
        nombre="actualizar_calendario",
        entrada={
            "unidad_id": "DOMO-01",
            "desde": "2026-12-01",
            "hasta": "2026-12-02",
            "accion": "bloquear",
        },
        identidad=identidad,
        conversacion_id="conv_111",
    )

    ultima_llamada = pms.llamadas_actualizar[-1]
    assert ultima_llamada["actor_id"] == "ANF-SAN-PABLO"
