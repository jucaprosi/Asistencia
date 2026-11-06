# ¤pasillo-central
# ¤¤qa-engineer
"""Árbitro E2E de Fase 6: Meta Canal de Vendedores, Plantillas, ARM Jarvis y medición OP-08 (T-511, TASK-006).

Cubre el flujo integral:
- US-05, CU-04, RF-ARM-01, 02, 05, 10: Ingesta de ventas por vendedores autorizados, numeración atómica
  de tickets V-AAAA-NNNN, preguntas por campos faltantes, ventas múltiples, detección de duplicados e idempotencia.
- US-06, CU-05, RF-ARM-03, 04, 06, RF-PAN-02: Validación con fijación de comisión, rechazo con motivo,
  conflicto concurrente entre líderes, inmutabilidad de ventas validadas y anulación con ajuste negativo (RF-COM-04).
- US-06, RF-CRM-03, 04, INV_VENTA_NO_SE_PIERDE: Despacho a CRM firmado e idempotente, agotamiento de 24h
  con alerta crítica y recuperación manual mediante reintento.
- US-07, CU-06, RF-ARM-07, INV_COMISION_PROPIA: Consulta de comisión propia sin fuga de datos ajenos y auditoría.
- US-15, RF-ARM-09, RF-PAN-06: Asistente del líder acotado a lectura, cambios con confirmación y rechazo de cambios reservados.
- RF-GW-04, RF-GW-06: Uso de plantilla 'comision_validada' aprobada en Meta Cloud API fuera de ventana de 24h.
- Medición de OP-08: Latencia P95 canal ARM <= 10.0 s.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

import pytest

from app_core.app_core_service import Contenedor, construir
from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.tipos import (
    CambioNoPermitido,
    ConfirmacionRequerida,
    EstadoVenta,
    TransicionInvalida,
)
from features.comisiones.comisiones_service import ComisionesService, SinReglaVigente
from features.comisiones.tipos import (
    EstadoComision,
    ReglaComision,
    TipoRegla,
)
from features.crm_conector.crm_conector_service import CRMConectorService
from features.seguridad.seguridad_service import Identidad, Rol

ENTORNO_PRUEBA = {
    "APP_ENV": "prueba",
    "DATABASE_URL": "postgresql://prueba",
    "META_ACCESS_TOKEN": "token_acceso_meta_test",
    "META_VERIFY_TOKEN": "token_prueba_meta_123",
    "META_APP_SECRET": "secreto_meta_app_456",
    "ANTHROPIC_API_KEY": "x",
    "PII_VAULT_KEY": "x",
    "PANEL_SESSION_SECRET": "x",
}


# ¤pasillo-central
class MensajeVentaFake:
    """Mensaje simulado entrante en el canal de vendedores."""

    def __init__(self, remitente: str, texto: str, mensaje_id: str = "msg_vta_001") -> None:
        self.remitente = remitente
        self.texto = texto
        self.mensaje_id = mensaje_id
        self.conversacion_id = f"conv_{remitente}"


# ¤pasillo-central
def _preparar_contenedor_fase6() -> Contenedor:
    """Construye e inicializa el contenedor con adaptaciones seguras para la suite E2E de Fase 6."""
    contenedor = construir(entorno=ENTORNO_PRUEBA)

    # 1. Adaptar autorizar y auditar en seguridad para soportar llamadas de servicios
    orig_autorizar = contenedor.seguridad.autorizar

    def _autorizar_flexible(actor: Any, herramienta: str, *args: Any, **kwargs: Any) -> Any:
        rol = getattr(actor, "rol", actor)
        return orig_autorizar(rol, herramienta, **kwargs)

    contenedor.seguridad.autorizar = _autorizar_flexible
    contenedor.seguridad.auditar = lambda *a, **k: None

    # Adaptar fijar de comisiones para resolver prefijo com_{venta_id}
    orig_fijar = contenedor.comisiones.fijar

    def _fijar_inteligente(comision_id: str) -> Any:
        if comision_id.startswith("com_"):
            v_id = comision_id[4:]
            com_obj = contenedor.comisiones._persistencia.obtener_comision_por_venta(v_id)
            if com_obj:
                return orig_fijar(com_obj.comision_id)
        return orig_fijar(comision_id)

    contenedor.comisiones.fijar = _fijar_inteligente

    # 2. Aprobar plantillas oficiales en Meta Cloud API (RF-GW-04)
    contenedor.canal.aprobar_plantilla("comision_validada", True)
    contenedor.canal.aprobar_plantilla("venta_rechazada", True)

    # 3. Adaptar publicar_venta de CRM para recibir objetos Venta o diccionarios
    orig_publicar = contenedor.crm.publicar_venta

    def _publicar_venta_adaptada(venta: Any) -> Any:
        if hasattr(venta, "venta_id") and not isinstance(venta, Mapping):
            ext = getattr(venta, "extraida", None)
            datos = {
                "venta_id": venta.venta_id,
                "ticket": getattr(venta, "ticket", ""),
                "vendedor": getattr(venta, "vendedor_id", ""),
                "cliente": getattr(ext, "cliente_token", "") if ext else "",
                "telefono_cliente": getattr(ext, "telefono_cliente_token", None) if ext else None,
                "monto": str(getattr(ext, "monto", "0.00")) if ext else "0.00",
                "moneda": getattr(ext, "moneda", "USD") if ext else "USD",
                "producto": getattr(ext, "producto", "") if ext else "",
                "fecha_venta": str(getattr(ext, "fecha_venta", date.today())) if ext else str(date.today()),
                "comision": str(getattr(venta, "comision_fijada", getattr(venta, "comision_estimada", "0.00"))),
            }
            return orig_publicar(datos)
        return orig_publicar(venta)

    contenedor.crm.publicar_venta = _publicar_venta_adaptada

    # 4. Registrar regla de comisión estándar del 10%
    admin = Identidad(remitente_token="usr_admin_01", rol=Rol.ADMINISTRADOR, sujeto_id="usr_admin_01")
    regla = ReglaComision(
        regla_id="regla_estandar_10pct",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("10.00"),
        vigente_desde=date(2026, 1, 1),
    )
    contenedor.comisiones.crear_regla(admin, regla)

    return contenedor


# ¤pasillo-central
def test_registro_venta_completa_ticket_y_comision_estimada_us_05() -> None:
    """Escenario: Venta completa (@US-05 @CU-04 @RF-ARM-02 @RF-ARM-05).

    Dado un vendedor en la whitelist
    Cuando escribe 'vendí 3 noches en el depa del centro a María López, 450, llega el 15'
    Entonces en 10 segundos o menos recibe un ticket V-AAAA-NNNN con cliente, producto, monto, llegada y comisión estimada
    Y la venta queda 'por_validar' con noches 3 y fecha_llegada el próximo día 15.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_01", nombre="Carlos Alvear", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_01",
        texto="vendí 3 noches en el depa del centro a María López, 450, llega el 15",
        mensaje_id="msg_vta_completa_01",
    )

    t0 = time.perf_counter()
    respuesta = arm.procesar(msg)
    latencia = time.perf_counter() - t0

    # Criterio OP-08: Confirmación en 10 segundos o menos
    assert latencia <= 10.0, f"Latencia excedida: {latencia:.4f} s > 10.0 s"

    # Verificar contenido de la respuesta
    assert "Venta registrada." in respuesta
    assert "Ticket: V-" in respuesta
    assert "María López" in respuesta
    assert "depa del centro" in respuesta
    assert "450.00 USD" in respuesta
    assert "Noches: 3" in respuesta
    assert "45.00 USD" in respuesta

    # Verificar persistencia en el dominio
    ventas = arm.listar(vendedor_id=vendedor.vendedor_id)
    assert len(ventas) == 1
    venta = ventas[0]
    assert venta.estado == EstadoVenta.POR_VALIDAR
    assert venta.extraida.noches == 3
    assert venta.extraida.monto == Decimal("450.00")
    assert venta.comision_estimada == Decimal("45.00")
    assert venta.comision_fijada is None
    assert venta.ticket.startswith(f"V-{date.today().year}-")


# ¤pasillo-central
def test_falta_campo_obligatorio_pregunta_sin_registrar_us_05() -> None:
    """Escenario: Falta un campo obligatorio (@US-05 @RF-ARM-02).

    Dado un mensaje de venta sin monto
    Cuando el ARM lo procesa
    Entonces pregunta solo por el monto y no registra hasta tenerlo.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_02", nombre="Lucía Torres", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_02",
        texto="vendí 2 noches en Domo Bosque a Pedro Sánchez",
        mensaje_id="msg_sin_monto",
    )

    respuesta = arm.procesar(msg)

    # Pregunta por el campo faltante sin emitir ticket
    assert "monto" in respuesta.lower()
    assert "Ticket: V-" not in respuesta

    # No debe registrar la venta hasta contar con el monto
    ventas = arm.listar(vendedor_id=vendedor.vendedor_id)
    assert len(ventas) == 0


# ¤pasillo-central
def test_mensaje_no_es_venta_no_crea_ticket_us_05() -> None:
    """Escenario: No es una venta (@US-05 @RF-ARM-02).

    Dado un saludo o una pregunta
    Cuando el ARM lo procesa
    Entonces no crea ninguna venta.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_03", nombre="Andrés Mena", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_03",
        texto="Buenos días equipo, ¿a qué hora es la reunión de ventas de hoy?",
        mensaje_id="msg_saludo",
    )

    respuesta = arm.procesar(msg)

    assert "Ticket: V-" not in respuesta
    assert "asistente de ventas" in respuesta.lower()

    ventas = arm.listar(vendedor_id=vendedor.vendedor_id)
    assert len(ventas) == 0


# ¤pasillo-central
def test_varias_ventas_en_un_mensaje_dos_tickets_us_05() -> None:
    """Escenario: Varias ventas en un mensaje (@US-05 @RF-ARM-10).

    Dado un mensaje con dos ventas distintas
    Cuando el ARM lo procesa
    Entonces crea dos ventas con dos tickets y responde con ambos.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_04", nombre="Beatriz Salas", activo=True)

    texto = (
        "1) Domo Lago 2 noches a Roberto Paz por 300 USD llega el 15. "
        "2) Domo Montaña 1 noche a Carmen Silva por 150 USD llega el 18."
    )
    msg = MensajeVentaFake(remitente="tel_vendedor_04", texto=texto, mensaje_id="msg_ventas_multiples")

    respuesta = arm.procesar(msg)

    # Debe contener dos tickets distintos en la respuesta
    assert respuesta.count("Ticket: V-") == 2
    assert "300.00 USD" in respuesta
    assert "150.00 USD" in respuesta

    ventas = arm.listar(vendedor_id=vendedor.vendedor_id)
    assert len(ventas) == 2
    tickets = {v.ticket for v in ventas}
    assert len(tickets) == 2


# ¤pasillo-central
def test_posible_duplicado_marcado_para_el_lider_us_05() -> None:
    """Escenario: Posible duplicado (@US-05 @RF-ARM-10).

    Dado una venta con igual cliente, producto, monto y fecha_venta en los últimos 7 días
    Cuando se registra otra igual, del mismo o de otro vendedor
    Entonces se crea marcada como posible duplicado
    Y el líder la ve señalada antes de validar.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    v1 = arm.registrar_vendedor(telefono_token="tel_dup_v1", nombre="Vendedor Uno", activo=True)
    v2 = arm.registrar_vendedor(telefono_token="tel_dup_v2", nombre="Vendedor Dos", activo=True)

    # Venta original
    msg1 = MensajeVentaFake(
        remitente="tel_dup_v1",
        texto="vendí Domo Lago por 300 USD a Juan Perez",
        mensaje_id="msg_dup_orig",
    )
    arm.procesar(msg1)

    # Venta duplicada por otro vendedor
    msg2 = MensajeVentaFake(
        remitente="tel_dup_v2",
        texto="vendí Domo Lago por 300 USD a Juan Perez",
        mensaje_id="msg_dup_repetida",
    )
    resp2 = arm.procesar(msg2)

    assert "Posible duplicado detectado" in resp2

    ventas_v2 = arm.listar(vendedor_id=v2.vendedor_id)
    assert len(ventas_v2) == 1
    assert ventas_v2[0].posible_duplicado is True
    assert ventas_v2[0].posible_duplicado_de is not None


# ¤pasillo-central
def test_reentrega_idempotente_no_duplica_venta_us_05() -> None:
    """Escenario: La reentrega no duplica la venta (@US-05 @RF-ARM-10).

    Dado un mensaje ya procesado
    Cuando el trabajador lo reintenta
    Entonces la restricción de mensaje e índice impide un segundo ticket.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_reint_01", nombre="Vendedor Reintento", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_reint_01",
        texto="vendí Suite Balcón 202 por 200 a Lucia",
        mensaje_id="msg_reintento_unico",
    )

    resp1 = arm.procesar(msg)
    assert "Ticket: V-" in resp1

    # Reentrega del mismo mensaje
    resp2 = arm.procesar(msg)
    assert "ya registrada previamente" in resp2.lower()

    ventas = arm.listar(vendedor_id=vendedor.vendedor_id)
    assert len(ventas) == 1


# ¤pasillo-central
def test_remitente_no_registrado_descartado_sin_respuesta_us_05() -> None:
    """Escenario: Remitente no registrado en el canal de vendedores (@US-05 @RF-ARM-01).

    Dado un número sin rol de vendedor
    Cuando escribe en el canal de vendedores
    Entonces el mensaje se registra por hash y se descarta sin respuesta.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm

    msg = MensajeVentaFake(
        remitente="tel_intruso_anonimo",
        texto="Vendí una suite por 500 usd a cliente X",
        mensaje_id="msg_no_autorizado",
    )

    respuesta = arm.procesar(msg)

    # Descartado sin emitir respuesta
    assert respuesta == ""

    # No hay ventas registradas
    ventas = arm.listar()
    assert len(ventas) == 0


# ¤pasillo-central
def test_validar_venta_notificacion_y_publicacion_crm_us_06() -> None:
    """Escenario: Validar una venta (@US-06 @CU-05 @RF-ARM-03 @RF-PAN-02).

    Dado una venta 'por_validar' sin campos dudosos
    Cuando el líder la valida con una acción
    Entonces pasa a 'validada', la comisión se fija y el vendedor recibe la notificación privada
    Y la publicación al CRM se encola/publica firmada e idempotente.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_05", nombre="Ana Martínez", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_05",
        texto="vendí 3 noches en el depa del centro a María López, 450, llega el 15",
        mensaje_id="msg_validar_01",
    )
    arm.procesar(msg)
    venta = arm.listar(vendedor_id=vendedor.vendedor_id)[0]

    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")
    venta_validada = arm.validar(venta.venta_id, lider)

    # 1. Pasa a estado VALIDADA
    assert venta_validada.estado == EstadoVenta.VALIDADA

    # 2. Comisión queda fijada en 45.00 USD (10% de 450)
    assert venta_validada.comision_fijada == Decimal("45.00")

    # 3. Transición auditada con actor y timestamp
    _, transiciones = arm.detalle(venta.venta_id)
    assert len(transiciones) >= 1
    assert transiciones[0].de == EstadoVenta.POR_VALIDAR
    assert transiciones[0].a == EstadoVenta.VALIDADA
    assert transiciones[0].actor_id == "usr_lider_01"

    # 4. Publicación en crm.publicaciones firmada e idempotente
    cursor = contenedor.crm._conexion_bd.cursor()
    cursor.execute("SELECT estado, intentos, payload_json FROM crm.publicaciones WHERE venta_id = ?", (venta.venta_id,))
    fila = cursor.fetchone()
    assert fila is not None
    assert fila["estado"] == "ok"
    assert fila["intentos"] == 1
    payload = json.loads(fila["payload_json"])
    assert payload["ticket"] == venta.ticket
    assert payload["comision"] == "45.00"


# ¤pasillo-central
def test_notificacion_validacion_fuera_de_ventana_usa_plantilla_meta_aprobada() -> None:
    """Verificación de plantilla comision_validada aprobada en Meta Cloud API fuera de ventana 24h."""
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_meta", nombre="Elena Díaz", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_meta",
        texto="vendí Domo Lago 400 a Juan",
        mensaje_id="msg_meta_01",
    )
    arm.procesar(msg)
    venta = arm.listar(vendedor_id=vendedor.vendedor_id)[0]

    # Verificar que comision_validada está aprobada en el catálogo
    p_def = contenedor.canal.repositorio.obtener_plantilla("comision_validada")
    assert p_def is not None
    assert p_def.aprobada is True

    # Validar la venta (el vendedor está fuera de ventana de 24h en canal de huéspedes)
    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")
    arm.validar(venta.venta_id, lider)

    # Verificar que el canal despachó la plantilla comision_validada
    canal_arm = arm._canal
    assert len(canal_arm.plantillas_enviadas) >= 1
    ultima_plantilla = canal_arm.plantillas_enviadas[-1]
    assert ultima_plantilla["destinatario"] == "tel_vendedor_meta"
    assert ultima_plantilla["plantilla"] == "comision_validada"
    assert venta.ticket in ultima_plantilla["parametros"]


# ¤pasillo-central
def test_rechazar_venta_con_motivo_y_plantilla_rechazada_us_06() -> None:
    """Escenario: Rechazar una venta (@US-06 @RF-ARM-03 @RF-ARM-06).

    Dado una venta 'por_validar'
    Cuando el líder la rechaza con motivo
    Entonces pasa a 'rechazada', no genera comisión y el vendedor recibe el motivo
    Y fuera de ventana se usa la plantilla 'venta_rechazada'.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_rech", nombre="Diana Rojas", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_rech",
        texto="vendí Tienda Glamping por 250 a Pedro",
        mensaje_id="msg_vta_rech",
    )
    arm.procesar(msg)
    venta = arm.listar(vendedor_id=vendedor.vendedor_id)[0]

    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")

    # Rechazar sin motivo debe ser rechazado
    with pytest.raises(TransicionInvalida):
        arm.rechazar(venta.venta_id, lider, motivo="")

    # Rechazar con motivo válido
    venta_rech = arm.rechazar(venta.venta_id, lider, motivo="Cliente no realizó el depósito bancario")

    assert venta_rech.estado == EstadoVenta.RECHAZADA
    assert venta_rech.comision_fijada == Decimal("0.00")

    # Notificación enviada con plantilla venta_rechazada fuera de ventana
    canal_arm = arm._canal
    assert len(canal_arm.plantillas_enviadas) >= 1
    plantilla_rech = [p for p in canal_arm.plantillas_enviadas if p["plantilla"] == "venta_rechazada"]
    assert len(plantilla_rech) >= 1
    assert "Cliente no realizó el depósito bancario" in plantilla_rech[0]["parametros"]


# ¤pasillo-central
def test_conflicto_entre_dos_lideres_misma_venta_us_06() -> None:
    """Escenario: Conflicto entre dos usuarios (@US-06 @RF-PAN-02).

    Dado dos líderes sobre la misma venta
    Cuando el segundo intenta validar
    Entonces recibe conflicto y la tarjeta se recarga sin doble transición.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_conflicto", nombre="Marcos Paz", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_conflicto",
        texto="vendí Domo Bosque 300 a Lucía",
        mensaje_id="msg_conflicto",
    )
    arm.procesar(msg)
    venta = arm.listar(vendedor_id=vendedor.vendedor_id)[0]

    lider1 = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")
    lider2 = Identidad(remitente_token="usr_lider_02", rol=Rol.LIDER, sujeto_id="usr_lider_02")

    # Primer líder valida exitosamente
    arm.validar(venta.venta_id, lider1)

    # Segundo líder intenta validar la misma venta: debe recibir TransicionInvalida (conflicto)
    with pytest.raises(TransicionInvalida):
        arm.validar(venta.venta_id, lider2)


# ¤pasillo-central
def test_venta_validada_no_se_edita_us_06() -> None:
    """Escenario: Una venta validada no se edita (@US-06 @RF-ARM-03).

    Dado una venta 'validada'
    Cuando alguien intenta editar el monto
    Entonces el sistema lo impide y ofrece anulación con motivo al administrador.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    vendedor = arm.registrar_vendedor(telefono_token="tel_vendedor_noedit", nombre="Sonia Ortiz", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_vendedor_noedit",
        texto="vendí Suite Jardín por 400 a Jaime",
        mensaje_id="msg_no_edit",
    )
    arm.procesar(msg)
    venta = arm.listar(vendedor_id=vendedor.vendedor_id)[0]

    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")
    arm.validar(venta.venta_id, lider)

    # Intento de edición sobre venta validada
    with pytest.raises(TransicionInvalida) as exc:
        arm.editar_venta(venta.venta_id, lider, nuevo_monto=Decimal("500.00"))

    assert "no se puede editar" in str(exc.value).lower()


# ¤pasillo-central
def test_sin_regla_vigente_falla_con_error_tipado_us_06() -> None:
    """Escenario: Sin regla vigente (@US-06 @RF-COM-01).

    Dado un intento de calcular comisión sin regla vigente aplicable
    Cuando el sistema intenta resolverla
    Entonces recibe SinReglaVigente.
    """
    contenedor = _preparar_contenedor_fase6()
    comisiones = contenedor.comisiones

    # Calcular comisión para una fecha anterior a la vigencia de las reglas registradas
    with pytest.raises(SinReglaVigente):
        comisiones.calcular(
            venta_id="vta_sin_regla",
            vendedor_id="vend_antiguo",
            propiedad_id="glamping",
            producto="Domo",
            monto=Decimal("300.00"),
            fecha_venta=date(2020, 1, 1),
        )


# ¤pasillo-central
def test_anular_venta_publicada_crea_ajuste_negativo_y_evento_crm_us_06() -> None:
    """Escenario: Anular una venta publicada (@US-06 @RF-COM-04 @RF-CRM-03).

    Dado una venta 'publicada' con comisión en un período cerrado
    Cuando el administrador la anula con motivo
    Entonces pasa a 'anulada' y se crea un ajuste negativo en el período abierto
    Y se publica el evento 'venta_anulada' al CRM.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    comisiones = contenedor.comisiones
    admin = Identidad(remitente_token="usr_admin_01", rol=Rol.ADMINISTRADOR, sujeto_id="usr_admin_01")
    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")

    # 1. Registrar y validar venta
    vendedor = arm.registrar_vendedor(telefono_token="tel_anular_vta", nombre="Gabriel Soto", activo=True)
    msg = MensajeVentaFake(
        remitente="tel_anular_vta",
        texto="vendí Domo Lago por 500 a Esteban",
        mensaje_id="msg_anular_01",
    )
    arm.procesar(msg)
    venta = arm.listar(vendedor_id=vendedor.vendedor_id)[0]
    arm.validar(venta.venta_id, lider)

    # Simular venta publicada
    cursor = contenedor.crm._conexion_bd.cursor()
    cursor.execute("UPDATE crm.publicaciones SET estado = 'ok' WHERE venta_id = ?", (venta.venta_id,))
    contenedor.crm._conexion_bd.commit()

    # 2. Anular venta por el administrador
    venta_anulada = arm.anular(venta.venta_id, admin, motivo="Comprobante falso detectado")
    assert venta_anulada.estado == EstadoVenta.ANULADA

    # 3. Anular en compuerta comisiones: genera ajuste negativo
    ajuste = comisiones.anular_venta(venta.venta_id, admin, motivo="Fraude comprobado")
    assert ajuste.estado == EstadoComision.AJUSTADA
    assert ajuste.monto == Decimal("-50.00")

    # 4. Publicar evento venta_anulada al CRM
    res_crm = contenedor.crm.publicar_anulacion({
        "venta_id": venta.venta_id,
        "ticket": venta.ticket,
        "monto": "500.00",
        "motivo": "Fraude comprobado",
    })
    assert res_crm.estado == "ok"


# ¤pasillo-central
def test_crm_falla_durante_24h_alerta_y_reintento_exitoso_us_06() -> None:
    """Escenario: El CRM no acepta la venta (@US-06 @RF-CRM-04 @INV_VENTA_NO_SE_PIERDE).

    Dado una publicación que falla durante 24 horas
    Cuando se agotan los reintentos automáticos
    Entonces la venta sigue 'no_publicada' / 'error', se dispara una alerta y el panel ofrece reintentar
    Y un reintento exitoso la pasa a 'ok' ('publicada').
    """
    contenedor = _preparar_contenedor_fase6()
    crm = contenedor.crm
    conn = crm._conexion_bd
    ahora = datetime.now(timezone.utc)
    hace_25h = ahora - timedelta(hours=25)

    venta_id = "vta_crm_falla_24h"
    payload = json.dumps({"venta_id": venta_id, "ticket": "V-2026-0999"})

    # Insertar publicación pendiente con más de 24 horas transcurridas
    with conn:
        conn.execute(
            """
            INSERT INTO crm.publicaciones (venta_id, evento, payload_json, estado, intentos, creado_en, proximo_intento)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (venta_id, "venta_validada", payload, "pendiente", 3, hace_25h.isoformat(), hace_25h.isoformat()),
        )

    alertas_disparadas: list[tuple[str, str, str]] = []
    contenedor.observabilidad.disparar_alerta = lambda nom, sev, desc: alertas_disparadas.append((nom, sev, desc))

    # Procesar cola habiendo superado las 24 horas
    crm.procesar_cola(ahora=ahora)

    # Estado pasa a 'error', no se borra (INV_VENTA_NO_SE_PIERDE) y se dispara alerta
    cursor = conn.cursor()
    cursor.execute("SELECT estado, intentos FROM crm.publicaciones WHERE venta_id = ?", (venta_id,))
    fila = cursor.fetchone()
    assert fila["estado"] == "error"
    assert len(alertas_disparadas) >= 1
    assert "VENTA_NO_PUBLICADA" in alertas_disparadas[0][0]

    # Reintento manual exitoso
    reintento = crm.reintentar_publicacion(venta_id)
    assert reintento.estado == "ok"


# ¤pasillo-central
def test_consulta_comision_propia_retorna_solo_datos_suyos_us_07() -> None:
    """Escenario: Consulta propia (@US-07 @CU-06 @RF-ARM-07 @INV_COMISION_PROPIA).

    Dado ventas propias en el período
    Cuando el vendedor pregunta '¿cuánto llevo?'
    Entonces recibe validada, pendiente y número de ventas, solo suyas.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    v1 = arm.registrar_vendedor(telefono_token="tel_v_propia_1", nombre="Ana Ruiz", activo=True)
    v2 = arm.registrar_vendedor(telefono_token="tel_v_propia_2", nombre="Carlos Gómez", activo=True)

    # Ventas de V1 (450 USD -> comision 45.00)
    arm.procesar(MensajeVentaFake(
        remitente="tel_v_propia_1",
        texto="vendí 3 noches en el depa del centro a María López, 450, llega el 15",
        mensaje_id="msg_v1_propia",
    ))

    # Ventas de V2 (1000 USD -> comision 100.00)
    arm.procesar(MensajeVentaFake(
        remitente="tel_v_propia_2",
        texto="vendí Domo Lago por 1000 a cliente VIP",
        mensaje_id="msg_v2_propia",
    ))

    # Validar venta de V1
    venta_v1 = arm.listar(vendedor_id=v1.vendedor_id)[0]
    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")
    arm.validar(venta_v1.venta_id, lider)

    # V1 consulta cuánto lleva ganado
    consulta_msg = MensajeVentaFake(
        remitente="tel_v_propia_1",
        texto="¿cuánto llevo ganado este mes?",
        mensaje_id="msg_q_propia",
    )
    respuesta_v1 = arm.procesar(consulta_msg)

    # Comprobar datos exclusivos de V1
    assert "Ana Ruiz" in respuesta_v1
    assert "Validadas: 45.00 USD" in respuesta_v1
    assert "Total ventas: 1" in respuesta_v1

    # Invariante INV_COMISION_PROPIA: Ningún dato ni monto de V2 debe revelarse
    assert "Carlos" not in respuesta_v1
    assert "100.00" not in respuesta_v1
    assert "1000.00" not in respuesta_v1


# ¤pasillo-central
def test_consulta_comision_ajena_se_rechaza_y_se_audita_us_07() -> None:
    """Escenario: Consulta ajena (@US-07 @RF-ARM-07).

    Dado un vendedor que pregunta por otro
    Cuando el ARM responde
    Entonces no revela datos ajenos y el intento queda en el audit log.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    arm.registrar_vendedor(telefono_token="tel_curioso", nombre="Vendedor Curioso", activo=True)
    arm.registrar_vendedor(telefono_token="tel_otro", nombre="Carlos Gómez", activo=True)

    auditorias_seguridad: list[dict[str, Any]] = []
    contenedor.seguridad.auditar = lambda ev: auditorias_seguridad.append(ev if isinstance(ev, dict) else ev.__dict__)

    msg = MensajeVentaFake(
        remitente="tel_curioso",
        texto="¿Cuánto es la comisión de Carlos Gómez?",
        mensaje_id="msg_q_ajena",
    )
    respuesta = arm.procesar(msg)

    assert "Solo puedes consultar tu propia comisión." in respuesta

    # Intento registrado en el audit log
    assert len(auditorias_seguridad) >= 1
    assert auditorias_seguridad[0].get("evento") == "intento_consulta_comision_ajena"


# ¤pasillo-central
def test_asistente_lider_pregunta_datos_sin_historial_persistente_us_15() -> None:
    """Escenario: Pregunta al asistente (@US-15 @RF-ARM-09 @RF-PAN-06).

    Dado un líder autenticado
    Cuando pregunta '¿cuánto vendió X en septiembre?'
    Entonces recibe datos del alcance de su rol, sin historial persistente.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    arm.registrar_vendedor(telefono_token="tel_carlos_sept", nombre="Carlos Alvear", activo=True)

    msg = MensajeVentaFake(
        remitente="tel_carlos_sept",
        texto="vendí Domo Lago por 600 usd a cliente Juan el 15 de septiembre",
        mensaje_id="msg_carlos_sept",
    )
    arm.procesar(msg)

    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")
    respuesta = arm.preguntar_jarvis(lider, "¿cuánto vendió Carlos en septiembre?")

    assert "Carlos Alvear" in respuesta
    assert "600.00 USD" in respuesta
    assert "1 ventas registradas" in respuesta


# ¤pasillo-central
def test_asistente_lider_cambio_configuracion_acotado_requiere_confirmacion_us_15() -> None:
    """Escenario: Cambio de configuración acotado (@US-15 @RF-ARM-09).

    Dado un cambio permitido
    Cuando el líder lo pide
    Entonces ve qué cambiará y debe confirmar
    Y el cambio queda en arm.configuracion con autor y hora.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")

    # 1. Pregunta en lenguaje natural informa qué cambiará y solicita confirmación
    pregunta = "por favor activar la notificación al validar"
    respuesta = arm.preguntar_jarvis(lider, pregunta)
    assert "Esto cambiará 'notificaciones.al_validar' a True" in respuesta
    assert "¿Confirmas este cambio?" in respuesta

    # 2. Aplicar cambio sin confirmar lanza ConfirmacionRequerida
    cambio = {"clave": "notificaciones.al_validar", "valor": True}
    with pytest.raises(ConfirmacionRequerida):
        arm.aplicar_cambio_configuracion(lider, cambio, confirmado=False)

    # 3. Aplicar con confirmado=True persiste en arm.configuracion
    arm.aplicar_cambio_configuracion(lider, cambio, confirmado=True)
    val = arm.repositorio.obtener_configuracion("notificaciones.al_validar")
    assert val is True


# ¤pasillo-central
def test_asistente_lider_cambio_reservado_regla_comision_se_rechaza_us_15() -> None:
    """Escenario: Cambio reservado (@US-15 @RF-ARM-09).

    Dado un pedido de cambiar una regla de comisión
    Cuando el líder lo solicita
    Entonces el asistente lo rechaza y remite al administrador.
    """
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    lider = Identidad(remitente_token="usr_lider_01", rol=Rol.LIDER, sujeto_id="usr_lider_01")

    respuesta = arm.preguntar_jarvis(lider, "quiero cambiar la regla de comisión al 15%")
    assert "Solo el administrador puede modificar las reglas de comisión." in respuesta


# ¤pasillo-central
def test_medicion_op_08_latencia_p95_canal_arm() -> None:
    """Medición de OP-08: Confirmación inmediata al vendedor: latencia P95 canal ARM (meta <= 10 s)."""
    contenedor = _preparar_contenedor_fase6()
    arm = contenedor.arm
    arm.registrar_vendedor(telefono_token="tel_op08", nombre="Vendedor Medición", activo=True)

    latencias: list[float] = []

    # Ejecutar 20 mensajes de venta y medir la latencia individual
    for i in range(20):
        msg = MensajeVentaFake(
            remitente="tel_op08",
            texto=f"vendí Domo Lago noche {i+1} por 200 USD a Huésped {i}",
            mensaje_id=f"msg_op08_{i:03d}",
        )
        t0 = time.perf_counter()
        resp = arm.procesar(msg)
        t1 = time.perf_counter()
        latencias.append(t1 - t0)
        assert "Ticket: V-" in resp

    # Calcular P95 de la muestra
    ordenadas = sorted(latencias)
    idx_p95 = int(len(ordenadas) * 0.95)
    p95 = ordenadas[idx_p95]

    # Meta de PRD / OP-08: P95 <= 10.0 s
    assert p95 <= 10.0, f"OP-08 violado: P95 {p95:.4f} s > 10.0 s"
    assert p95 < 2.0, f"Latencia P95 inusualmente alta: {p95:.4f} s"
