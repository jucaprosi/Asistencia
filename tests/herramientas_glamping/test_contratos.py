# ¤herramientas-mcp
# ¤¤backend-developer
"""Pruebas de contratos, validación de esquemas y autorización de herramientas MCP (T-203)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping
import uuid

import pytest

from features.herramientas_glamping.herramientas_glamping_service import (
    EntradaInvalida,
    HerramientaDeshabilitada,
    HerramientaNoAutorizada,
    HerramientasGlampingService,
    ReservaNoAutorizada,
    cargar_config,
)
from features.pms_conector.tipos import (
    Cotizacion,
    Disponibilidad,
    Incidencia,
    InstruccionesCheckin,
    Reserva,
    Unidad,
)
from features.crm_conector.tipos import Contacto, Oportunidad
from features.seguridad.tipos import EventoAuditoria, Identidad, Rol, Veredicto


# --- Dobles de Compuertas ---

# ¤herramientas-mcp
class DobleSeguridad:
    def __init__(self, allowlist: Mapping[str, set[str]] | None = None) -> None:
        self.allowlist = allowlist or {
            "huesped_potencial": {"consultar_disponibilidad", "cotizar", "crear_reserva_preliminar", "solicitar_humano"},
            "huesped_activo": {
                "consultar_disponibilidad", "cotizar", "crear_reserva_preliminar",
                "obtener_instrucciones_checkin", "reportar_incidencia", "solicitar_humano",
            },
            "vendedor": {"solicitar_humano", "registrar_venta", "consultar_comision_propia"},
            "sistema": {"buscar_contacto_crm", "crear_oportunidad_crm"},
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
@dataclass(frozen=True)
class ResumenComisionFake:
    vendedor_id: str
    periodo: str
    validada: Decimal
    pendiente: Decimal
    ventas: int


# ¤herramientas-mcp
class DobleArm:
    def __init__(self) -> None:
        self.ventas_registradas: list[dict[str, Any]] = []
        self.comisiones: dict[str, dict[str, Any]] = {
            "vendedor_01": {
                "2026-11": {"validada": Decimal("250.00"), "pendiente": Decimal("75.00"), "ventas": 3},
                "2026-10": {"validada": Decimal("600.00"), "pendiente": Decimal("0.00"), "ventas": 5},
            }
        }
        self.duplicados_conocidos: set[str] = {"Domo Lago 101"}

    def registrar_venta(
        self,
        vendedor_id: str,
        texto_original: str,
        venta: Mapping[str, Any],
    ) -> dict[str, Any]:
        producto = venta.get("producto") or "producto_desconocido"
        es_duplicado = producto in self.duplicados_conocidos
        ticket_id = f"V-2026-{len(self.ventas_registradas) + 1:04d}"
        registro = {
            "ticket": ticket_id,
            "vendedor_id": vendedor_id,
            "texto_original": texto_original,
            "venta": dict(venta),
            "estado": "por_validar",
            "comision_estimada": Decimal("35.00"),
            "posible_duplicado": es_duplicado,
        }
        self.ventas_registradas.append(registro)
        return {
            "ticket": ticket_id,
            "estado": "por_validar",
            "comision_estimada": Decimal("35.00"),
            "posible_duplicado": es_duplicado,
        }

    def consultar_comision_propia(
        self,
        vendedor_id: str,
        periodo: str | None = None,
    ) -> ResumenComisionFake:
        per = periodo or f"{date.today().year}-{date.today().month:02d}"
        datos_vendedor = self.comisiones.get(vendedor_id, {})
        datos_periodo = datos_vendedor.get(per, {"validada": Decimal("0.00"), "pendiente": Decimal("0.00"), "ventas": 0})
        return ResumenComisionFake(
            vendedor_id=vendedor_id,
            periodo=per,
            validada=datos_periodo["validada"],
            pendiente=datos_periodo["pendiente"],
            ventas=datos_periodo["ventas"],
        )


# ¤herramientas-mcp
class DoblePMS:
    def __init__(self) -> None:
        self.reservas_titulares: dict[str, str] = {
            "RES-1001": "token_huesped_valido",
        }
        self.incidencias_registradas: list[Incidencia] = []

    def consultar_disponibilidad(self, propiedad_id: str, desde: date, hasta: date, huespedes: int) -> Disponibilidad:
        if propiedad_id == "prop_sin_cupo":
            return Disponibilidad(
                disponible=False,
                unidades=(),
                motivo="Fechas no disponibles",
                alternativas=(
                    ("u_alt_1", desde + timedelta(days=2), hasta + timedelta(days=2)),
                    ("u_alt_2", desde + timedelta(days=4), hasta + timedelta(days=4)),
                ),
            )
        return Disponibilidad(
            disponible=True,
            unidades=(
                Unidad(unidad_id="domo_1", propiedad_id=propiedad_id, nombre="Domo Bosque", capacidad=2),
                Unidad(unidad_id="domo_2", propiedad_id=propiedad_id, nombre="Domo Lago", capacidad=4),
            ),
            alternativas=(),
        )

    def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int) -> Cotizacion:
        return Cotizacion(
            total=Decimal("250.00"),
            moneda="USD",
            desglose=(("hospedaje", Decimal("220.00")), ("limpieza", Decimal("30.00"))),
            politica_cancelacion_id="flexible_48h",
        )

    def crear_reserva_preliminar(
        self,
        propiedad_id: str,
        unidad_id: str,
        desde: date,
        hasta: date,
        huespedes: int,
        huesped_token: str,
        clave_idempotencia: str,
    ) -> Reserva:
        from features.pms_conector.tipos import EstadoReserva
        return Reserva(
            codigo="RES-PREL-999",
            propiedad_id=propiedad_id,
            unidad_id=unidad_id,
            huesped_token=huesped_token,
            desde=desde,
            hasta=hasta,
            huespedes=huespedes,
            estado=EstadoReserva.PRELIMINAR,
            total=Decimal("250.00"),
            expira_en=datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
            pms_ref="fake_pms_ref_999",
        )

    def validar_titular_local(self, codigo_reserva: str, huesped_token: str) -> bool:
        return self.reservas_titulares.get(codigo_reserva) == huesped_token

    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin:
        return InstruccionesCheckin(
            propiedad="Glamping San Pablo",
            direccion="Km 5 Vía a las Lagunas",
            hora_checkin="15:00",
            acceso=("Entrada principal portón negro", "Cerradura digital código en SMS"),
            wifi_red="Glamping_Huespedes",
            wifi_clave_token="[[SECRETO:wifi_san_pablo]]",
            normas=("No fumar en domos", "Silencio a partir de las 22:00"),
            contacto_emergencia="+593987654321",
        )

    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia:
        self.incidencias_registradas.append(incidencia)
        return incidencia


# ¤herramientas-mcp
class DobleCRM:
    def __init__(self) -> None:
        self.handoffs: list[dict[str, Any]] = []
        self.contactos: dict[str, Contacto] = {
            "tok_tel_123": Contacto(
                contacto_id="crm_c_001",
                nombre_token="tok_nombre",
                telefono_token="tok_tel_123",
                email_token=None,
                crm_ref="ref_1",
            ),
        }
        self.oportunidades: list[Oportunidad] = []

    def solicitar_handoff(self, conversacion_id: str, zona_id: str, resumen: str) -> str:
        handoff_id = f"ho_{len(self.handoffs) + 1}"
        self.handoffs.append({
            "handoff_id": handoff_id,
            "conversacion_id": conversacion_id,
            "zona_id": zona_id,
            "resumen": resumen,
        })
        return handoff_id

    def buscar_contacto(self, telefono_token: str | None = None, email_token: str | None = None) -> Contacto | None:
        if telefono_token and telefono_token in self.contactos:
            return self.contactos[telefono_token]
        return None

    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        self.oportunidades.append(oportunidad)
        return oportunidad


# --- Fixtures ---

# ¤herramientas-mcp
@pytest.fixture
def servicio_herramientas() -> tuple[HerramientasGlampingService, DobleSeguridad, DoblePMS, DobleCRM]:
    config = dict(cargar_config())
    seguridad = DobleSeguridad()
    pms = DoblePMS()
    crm = DobleCRM()
    conocimiento = None
    servicio = HerramientasGlampingService(
        config=config,
        seguridad=seguridad,
        pms=pms,
        conocimiento=conocimiento,
        crm=crm,
    )
    return servicio, seguridad, pms, crm


# ¤herramientas-mcp
@pytest.fixture
def servicio_con_arm() -> tuple[HerramientasGlampingService, DobleSeguridad, DobleArm]:
    config = dict(cargar_config())
    seguridad = DobleSeguridad()
    pms = DoblePMS()
    crm = DobleCRM()
    arm = DobleArm()
    servicio = HerramientasGlampingService(
        config=config,
        seguridad=seguridad,
        pms=pms,
        conocimiento=None,
        crm=crm,
        arm=arm,
    )
    return servicio, seguridad, arm


# --- Tests de Requisitos RF-MCP ---

# ¤herramientas-mcp
def test_consultar_disponibilidad_exitosa(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL)
    res = svc.ejecutar(
        "consultar_disponibilidad",
        {
            "propiedad_id": "prop_glamping_1",
            "desde": "2026-11-10",
            "hasta": "2026-11-12",
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id="c_1",
    )
    assert res.error is None
    assert res.salida["disponible"] is True
    assert len(res.salida["unidades"]) == 2
    assert res.salida["unidades"][0]["unidad_id"] == "domo_1"
    assert res.salida["alternativas"] == []


# ¤herramientas-mcp
def test_consultar_disponibilidad_sin_cupo_devuelve_alternativas(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL)
    res = svc.ejecutar(
        "consultar_disponibilidad",
        {
            "propiedad_id": "prop_sin_cupo",
            "desde": "2026-11-10",
            "hasta": "2026-11-12",
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id="c_1",
    )
    assert res.salida["disponible"] is False
    assert res.salida["motivo"] == "Fechas no disponibles"
    assert len(res.salida["alternativas"]) == 2
    assert res.salida["alternativas"][0]["unidad_id"] == "u_alt_1"


# ¤herramientas-mcp
def test_cotizar_formato_moneda_y_desglose(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL)
    res = svc.ejecutar(
        "cotizar",
        {
            "propiedad_id": "prop_glamping_1",
            "unidad_id": "domo_1",
            "desde": "2026-11-10",
            "hasta": "2026-11-12",
            "huespedes": 2,
        },
        identidad=identidad,
        conversacion_id="c_1",
    )
    assert res.salida["total"] == "250.00"
    assert res.salida["moneda"] == "USD"
    assert res.salida["politica_cancelacion_id"] == "flexible_48h"
    assert len(res.salida["desglose"]) == 2
    assert res.salida["desglose"][0]["concepto"] == "hospedaje"
    assert res.salida["desglose"][0]["monto"] == "220.00"


# ¤herramientas-mcp
def test_crear_reserva_preliminar_con_idempotencia(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="usr_1", rol=Rol.HUESPED_POTENCIAL)
    idem_uuid = str(uuid.uuid4())
    res = svc.ejecutar(
        "crear_reserva_preliminar",
        {
            "propiedad_id": "prop_glamping_1",
            "unidad_id": "domo_1",
            "desde": "2026-11-10",
            "hasta": "2026-11-12",
            "huespedes": 2,
            "nombre_token": "[[TOKEN_NOMBRE]]",
            "clave_idempotencia": idem_uuid,
        },
        identidad=identidad,
        conversacion_id="c_1",
    )
    assert res.salida["codigo_reserva"] == "RES-PREL-999"
    assert res.salida["estado"] == "preliminar"
    assert "2026-11-02" in res.salida["expira_en"]


# ¤herramientas-mcp
def test_obtener_instrucciones_checkin_titular_valido(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="token_huesped_valido", rol=Rol.HUESPED_ACTIVO)
    res = svc.ejecutar(
        "obtener_instrucciones_checkin",
        {"codigo_reserva": "RES-1001"},
        identidad=identidad,
        conversacion_id="c_checkin",
    )
    assert res.salida["propiedad"] == "Glamping San Pablo"
    assert res.salida["wifi"]["clave_ref"] == "[[SECRETO:wifi_san_pablo]]"
    assert "No fumar en domos" in res.salida["normas"]


# ¤herramientas-mcp
def test_obtener_instrucciones_checkin_titular_invalido_rechaza_y_audita(servicio_herramientas: Any) -> None:
    svc, seg, _, crm = servicio_herramientas
    identidad = Identidad(remitente_token="intruso_token", rol=Rol.HUESPED_ACTIVO)

    with pytest.raises(ReservaNoAutorizada) as exc_info:
        svc.ejecutar(
            "obtener_instrucciones_checkin",
            {"codigo_reserva": "RES-1001"},
            identidad=identidad,
            conversacion_id="c_checkin",
        )
    assert exc_info.value.codigo_reserva == "RES-1001"
    assert len(seg.eventos_auditados) == 1
    assert seg.eventos_auditados[0].resultado == "denegado_titular_no_coincide"
    assert len(crm.handoffs) == 0


# ¤herramientas-mcp
def test_checkin_cinco_intentos_fallidos_escalan_a_humano(servicio_herramientas: Any) -> None:
    svc, _, _, crm = servicio_herramientas
    identidad = Identidad(remitente_token="atacante_fuerza_bruta", rol=Rol.HUESPED_ACTIVO)

    for i in range(4):
        with pytest.raises(ReservaNoAutorizada):
            svc.ejecutar(
                "obtener_instrucciones_checkin",
                {"codigo_reserva": f"RES-{i}"},
                identidad=identidad,
                conversacion_id="c_checkin",
            )
    assert len(crm.handoffs) == 0

    # 5to intento en 24h debe detonar handoff
    with pytest.raises(ReservaNoAutorizada):
        svc.ejecutar(
            "obtener_instrucciones_checkin",
            {"codigo_reserva": "RES-5"},
            identidad=identidad,
            conversacion_id="c_checkin",
        )
    assert len(crm.handoffs) == 1
    assert "5 intentos fallidos" in crm.handoffs[0]["resumen"]


# ¤herramientas-mcp
def test_reportar_incidencia_general(servicio_herramientas: Any) -> None:
    svc, _, pms, crm = servicio_herramientas
    identidad = Identidad(remitente_token="tok_huesped", rol=Rol.HUESPED_ACTIVO)
    res = svc.ejecutar(
        "reportar_incidencia",
        {
            "propiedad_id": "glamping_imbabura",
            "descripcion": "Falta una toalla extra en el domo",
            "categoria": "limpieza",
        },
        identidad=identidad,
        conversacion_id="c_inc",
    )
    assert res.salida["prioridad"] == "media"
    assert res.salida["eta_respuesta_horas"] == 4.0
    assert len(crm.handoffs) == 0
    assert len(pms.incidencias_registradas) == 1


# ¤herramientas-mcp
def test_reportar_incidencia_critica_seguridad_o_acceso_detona_handoff(servicio_herramientas: Any) -> None:
    svc, _, _, crm = servicio_herramientas
    identidad = Identidad(remitente_token="tok_huesped", rol=Rol.HUESPED_ACTIVO)
    res = svc.ejecutar(
        "reportar_incidencia",
        {
            "propiedad_id": "glamping_imbabura",
            "descripcion": "La cerradura digital no abre y es de noche",
            "categoria": "acceso",
        },
        identidad=identidad,
        conversacion_id="c_inc_critica",
    )
    assert res.salida["prioridad"] == "critica"
    assert res.salida["eta_respuesta_horas"] == 1.0
    assert len(crm.handoffs) == 1
    assert "Incidencia crítica de acceso" in crm.handoffs[0]["resumen"]


# ¤herramientas-mcp
def test_solicitar_humano_exitoso(servicio_herramientas: Any) -> None:
    svc, _, _, crm = servicio_herramientas
    identidad = Identidad(remitente_token="tok_huesped", rol=Rol.HUESPED_POTENCIAL)
    res = svc.ejecutar(
        "solicitar_humano",
        {
            "motivo": "peticion_explicita",
            "resumen": "El cliente desea cotización para evento corporativo",
        },
        identidad=identidad,
        conversacion_id="c_humano",
    )
    assert res.salida["canal"] == "panel"
    assert res.salida["minutos_estimados"] == 15
    assert len(crm.handoffs) == 1


# ¤herramientas-mcp
def test_crm_herramientas_solo_permitidas_a_rol_sistema(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    huesped = Identidad(remitente_token="tok_h", rol=Rol.HUESPED_ACTIVO)
    sistema = Identidad(remitente_token="tok_s", rol=Rol.SISTEMA)

    # Huesped no puede buscar contactos en CRM
    with pytest.raises(HerramientaNoAutorizada):
        svc.ejecutar(
            "buscar_contacto_crm",
            {"telefono_token": "tok_tel_123"},
            identidad=huesped,
            conversacion_id="c_crm",
        )

    # Sistema sí puede
    res = svc.ejecutar(
        "buscar_contacto_crm",
        {"telefono_token": "tok_tel_123"},
        identidad=sistema,
        conversacion_id="c_crm",
    )
    assert res.salida["encontrado"] is True
    assert res.salida["contacto_id"] == "crm_c_001"

    # Sistema crea oportunidad
    res_op = svc.ejecutar(
        "crear_oportunidad_crm",
        {
            "contacto_id": "crm_c_001",
            "propiedad_id": "glamping_imbabura",
            "etapa": "nueva",
            "monto": "350.00",
        },
        identidad=sistema,
        conversacion_id="c_crm",
    )
    assert "oportunidad_id" in res_op.salida


# ¤herramientas-mcp
def test_entrada_invalida_rechaza_con_mensaje_legible(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="tok_h", rol=Rol.HUESPED_POTENCIAL)

    # Fecha inválida
    with pytest.raises(EntradaInvalida) as exc:
        svc.ejecutar(
            "consultar_disponibilidad",
            {
                "propiedad_id": "prop_1",
                "desde": "fecha_invalida",
                "hasta": "2026-11-12",
                "huespedes": 2,
            },
            identidad=identidad,
            conversacion_id="c_err",
        )
    assert "desde" in str(exc.value)

    # Huéspedes negativos
    with pytest.raises(EntradaInvalida) as exc:
        svc.ejecutar(
            "consultar_disponibilidad",
            {
                "propiedad_id": "prop_1",
                "desde": "2026-11-10",
                "hasta": "2026-11-12",
                "huespedes": 0,
            },
            identidad=identidad,
            conversacion_id="c_err",
        )
    assert "huespedes" in str(exc.value)


# ¤herramientas-mcp
def test_herramienta_deshabilitada_rechaza(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    identidad = Identidad(remitente_token="tok_a", rol=Rol.ANFITRION)

    # consultar_estado_cuenta_anfitrion está deshabilitada en config
    with pytest.raises(HerramientaDeshabilitada):
        svc.ejecutar(
            "consultar_estado_cuenta_anfitrion",
            {},
            identidad=identidad,
            conversacion_id="c_deshab",
        )


# ¤herramientas-mcp
def test_listar_herramientas_filtra_por_rol_y_habilitadas(servicio_herramientas: Any) -> None:
    svc, _, _, _ = servicio_herramientas
    huesped_pot = svc.listar("huesped_potencial")
    nombres_pot = {h.nombre for h in huesped_pot}
    assert "consultar_disponibilidad" in nombres_pot
    assert "cotizar" in nombres_pot
    assert "crear_reserva_preliminar" in nombres_pot
    assert "solicitar_humano" in nombres_pot
    assert "obtener_instrucciones_checkin" not in nombres_pot

    huesped_act = svc.listar("huesped_activo")
    nombres_act = {h.nombre for h in huesped_act}
    assert "obtener_instrucciones_checkin" in nombres_act
    assert "reportar_incidencia" in nombres_act

    vendedor_herramientas = svc.listar("vendedor")
    nombres_vend = {h.nombre for h in vendedor_herramientas}
    assert "solicitar_humano" in nombres_vend
    assert "registrar_venta" in nombres_vend
    assert "consultar_comision_propia" in nombres_vend


# --- Tests RF-MCP-08 (registrar_venta) y RF-MCP-09 (consultar_comision_propia) ---

# ¤herramientas-mcp
def test_registrar_venta_exitoso(servicio_con_arm: Any) -> None:
    """Escenario: Registro de venta por el vendedor (RF-MCP-08)."""
    svc, _, arm = servicio_con_arm
    identidad = Identidad(remitente_token="tel_vend_01", rol=Rol.VENDEDOR, sujeto_id="vendedor_01")

    entrada = {
        "texto_original": "vendí Domo Bosque por 350 a Maria",
        "venta": {
            "es_venta": True,
            "cliente_token": "cli_maria_1",
            "telefono_cliente_token": "tel_maria_1",
            "producto": "Domo Bosque",
            "propiedad_id": "prop_glamping_1",
            "noches": 2,
            "monto": "350.00",
            "moneda": "USD",
            "fecha_venta": "2026-11-02",
            "fecha_llegada": "2026-11-15",
            "confianza": 0.95,
            "confianza_campos": {"producto": 0.98, "monto": 0.99},
            "campos_faltantes": [],
        },
    }

    resultado = svc.ejecutar(
        "registrar_venta",
        entrada,
        identidad=identidad,
        conversacion_id="conv_v1",
    )

    salida = resultado.salida
    assert salida["ticket"].startswith("V-2026-")
    assert salida["estado"] == "por_validar"
    assert salida["comision_estimada"] == "35.00"
    assert salida["posible_duplicado"] is False

    # Verificar que el vendedor_id registrado proviene de la identidad verificada
    assert len(arm.ventas_registradas) == 1
    assert arm.ventas_registradas[0]["vendedor_id"] == "vendedor_01"


# ¤herramientas-mcp
def test_registrar_venta_rechaza_vendedor_id_en_entrada(servicio_con_arm: Any) -> None:
    """Escenario: El vendedor no se declara en la entrada (@RF-MCP-08).

    Dado una llamada a "registrar_venta"
    Cuando el modelo envía un vendedor_id
    Entonces la validación del esquema la rechaza y el servidor usa el remitente verificado
    """
    svc, _, arm = servicio_con_arm
    identidad = Identidad(remitente_token="tel_vend_01", rol=Rol.VENDEDOR, sujeto_id="vendedor_01")

    # Intento 1: vendedor_id en la raíz de la entrada
    entrada_hack_raiz = {
        "vendedor_id": "hacker_vendor_999",
        "texto_original": "vendí Domo Bosque por 350",
        "venta": {
            "es_venta": True,
            "cliente_token": "cli_maria_1",
            "telefono_cliente_token": None,
            "producto": "Domo Bosque",
            "propiedad_id": None,
            "noches": 2,
            "monto": "350.00",
            "moneda": "USD",
            "fecha_venta": "2026-11-02",
            "fecha_llegada": None,
            "confianza": 0.90,
            "confianza_campos": {},
            "campos_faltantes": [],
        },
    }

    with pytest.raises(EntradaInvalida) as exc:
        svc.ejecutar(
            "registrar_venta",
            entrada_hack_raiz,
            identidad=identidad,
            conversacion_id="conv_v_hack1",
        )
    assert "vendedor_id" in str(exc.value)

    # Intento 2: vendedor_id dentro del objeto venta
    entrada_hack_venta = {
        "texto_original": "vendí Domo Bosque por 350",
        "venta": {
            "vendedor_id": "hacker_vendor_999",
            "es_venta": True,
            "cliente_token": "cli_maria_1",
            "telefono_cliente_token": None,
            "producto": "Domo Bosque",
            "propiedad_id": None,
            "noches": 2,
            "monto": "350.00",
            "moneda": "USD",
            "fecha_venta": "2026-11-02",
            "fecha_llegada": None,
            "confianza": 0.90,
            "confianza_campos": {},
            "campos_faltantes": [],
        },
    }

    with pytest.raises(EntradaInvalida) as exc:
        svc.ejecutar(
            "registrar_venta",
            entrada_hack_venta,
            identidad=identidad,
            conversacion_id="conv_v_hack2",
        )
    assert "vendedor_id" in str(exc.value)


# ¤herramientas-mcp
def test_registrar_venta_rechaza_rol_no_autorizado(servicio_con_arm: Any) -> None:
    """Escenario: INV_ALLOWLIST_POR_ACCION en registrar_venta."""
    svc, _, _ = servicio_con_arm
    identidad_huesped = Identidad(remitente_token="tel_huesped_01", rol=Rol.HUESPED_ACTIVO)

    entrada = {
        "texto_original": "vendí algo",
        "venta": {
            "es_venta": True,
            "cliente_token": None,
            "telefono_cliente_token": None,
            "producto": "Domo Bosque",
            "propiedad_id": None,
            "noches": 1,
            "monto": "100.00",
            "moneda": "USD",
            "fecha_venta": "2026-11-02",
            "fecha_llegada": None,
            "confianza": 0.90,
            "confianza_campos": {},
            "campos_faltantes": [],
        },
    }

    with pytest.raises(HerramientaNoAutorizada):
        svc.ejecutar(
            "registrar_venta",
            entrada,
            identidad=identidad_huesped,
            conversacion_id="conv_huesped_no_auth",
        )


# ¤herramientas-mcp
def test_registrar_venta_detecta_posible_duplicado(servicio_con_arm: Any) -> None:
    """Detecta posible duplicado si la venta coincide con registros previos."""
    svc, _, _ = servicio_con_arm
    identidad = Identidad(remitente_token="tel_vend_01", rol=Rol.VENDEDOR, sujeto_id="vendedor_01")

    entrada = {
        "texto_original": "vendí Domo Lago 101 por 500",
        "venta": {
            "es_venta": True,
            "cliente_token": "cli_pedro",
            "telefono_cliente_token": None,
            "producto": "Domo Lago 101",
            "propiedad_id": "prop_1",
            "noches": 2,
            "monto": "500.00",
            "moneda": "USD",
            "fecha_venta": "2026-11-02",
            "fecha_llegada": None,
            "confianza": 0.95,
            "confianza_campos": {},
            "campos_faltantes": [],
        },
    }

    res = svc.ejecutar("registrar_venta", entrada, identidad=identidad, conversacion_id="conv_dup")
    assert res.salida["posible_duplicado"] is True


# ¤herramientas-mcp
def test_consultar_comision_propia_sin_periodo(servicio_con_arm: Any) -> None:
    """Escenario: Consulta sin período (@RF-MCP-09 @INV_COMISION_PROPIA).

    Dado un vendedor que no indica período
    Cuando consulta su comisión
    Entonces recibe el período en curso
    """
    svc, _, _ = servicio_con_arm
    identidad = Identidad(remitente_token="tel_vend_01", rol=Rol.VENDEDOR, sujeto_id="vendedor_01")

    res = svc.ejecutar(
        "consultar_comision_propia",
        {},
        identidad=identidad,
        conversacion_id="conv_com_1",
    )

    salida = res.salida
    hoy = date.today()
    assert salida["periodo"] == f"{hoy.year}-{hoy.month:02d}"
    assert salida["validada"] == "250.00"
    assert salida["pendiente"] == "75.00"
    assert salida["ventas"] == 3


# ¤herramientas-mcp
def test_consultar_comision_propia_con_periodo(servicio_con_arm: Any) -> None:
    """Escenario: Consulta con período explícito (@RF-MCP-09)."""
    svc, _, _ = servicio_con_arm
    identidad = Identidad(remitente_token="tel_vend_01", rol=Rol.VENDEDOR, sujeto_id="vendedor_01")

    res = svc.ejecutar(
        "consultar_comision_propia",
        {"periodo": "2026-10"},
        identidad=identidad,
        conversacion_id="conv_com_2",
    )

    salida = res.salida
    assert salida["periodo"] == "2026-10"
    assert salida["validada"] == "600.00"
    assert salida["pendiente"] == "0.00"
    assert salida["ventas"] == 5


# ¤herramientas-mcp
def test_consultar_comision_propia_rechaza_campos_extra(servicio_con_arm: Any) -> None:
    """Rechaza parámetros adicionales o inyección de vendedor_id (@INV_COMISION_PROPIA)."""
    svc, _, _ = servicio_con_arm
    identidad = Identidad(remitente_token="tel_vend_01", rol=Rol.VENDEDOR, sujeto_id="vendedor_01")

    with pytest.raises(EntradaInvalida):
        svc.ejecutar(
            "consultar_comision_propia",
            {"vendedor_id": "vendedor_ajeno", "periodo": "2026-10"},
            identidad=identidad,
            conversacion_id="conv_com_extra",
        )


# ¤herramientas-mcp
def test_consultar_comision_propia_rechaza_rol_no_autorizado(servicio_con_arm: Any) -> None:
    """Escenario: INV_ALLOWLIST_POR_ACCION en consultar_comision_propia."""
    svc, _, _ = servicio_con_arm
    identidad_huesped = Identidad(remitente_token="tel_huesped_01", rol=Rol.HUESPED_ACTIVO)

    with pytest.raises(HerramientaNoAutorizada):
        svc.ejecutar(
            "consultar_comision_propia",
            {"periodo": "2026-10"},
            identidad=identidad_huesped,
            conversacion_id="conv_com_no_auth",
        )
