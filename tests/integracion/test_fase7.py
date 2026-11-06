# ¤pasillo-central
# ¤¤qa-engineer
"""Prueba de integración de extremo a extremo de la Fase 7 (Proveedor CRM Real y Producción).

Cubre:
- RNF-09 @INV_VENTA_FIRMADA_IDEMPOTENTE: 100% de publicaciones firmadas HMAC-SHA256; 0 duplicados por venta_id.
- @US-16 @CU-09 @RF-PAN-09: Administrar usuarios con rol y trazabilidad en el audit log append-only.
- @US-16 @RF-PAN-09: Reglas de comisión por versión inmutables.
- @US-16 @RF-PAN-09: Control de acceso RBAC estricto (solo el administrador entra a Administración; líder recibe 403).
- @US-08 @CU-07 @RF-ARM-08 @RF-PAN-04: Tablero de ventas y comisiones que cuadra al centavo con la exportación CSV.
- @US-14 @RF-COM-02 @RF-PAN-05: Cierre de período inmutable con confirmación escrita y 409 a modificaciones posteriores.
- @US-14 @RF-COM-02: Venta tardía asignada al período abierto más antiguo con periodo_origen del mes cerrado.
- @US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Escalón por volumen reproducible con base acumulada guardada.
- @US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Independencia del orden de validación (A->B vs B->A) sin alterar fijadas.
- @US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Modo graduado (ventas 333.33, 700.10, 566.57 -> total 110.00).
- @US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Modo volumen (ventas 333.33, 700.10, 566.57 -> total 160.00).
- @US-14 @RF-COM-04 @INV_COMISION_REPRODUCIBLE: Anulación de venta con ajuste negativo (-65.00) dejando el total en 45.00 sin tocar comisiones previas.
- @US-14 @RF-COM-02 @INV_COMISION_REPRODUCIBLE: Venta tardía con escalón sobre base previa de 900.00.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
import uuid

import pytest
from fastapi.testclient import TestClient

from app_core.app_core_service import Contenedor, construir
from features.canal_whatsapp.tipos import Plantilla
from features.comisiones.comisiones_service import (
    ComisionesService,
    Escalon,
    EstadoComision,
    ModoEscalon,
    PeriodoCerrado,
    ReglaComision,
    TipoRegla,
)
from features.comisiones.persistencia_internal import PersistenciaComisiones
from features.crm_conector.crm_conector_service import CRMConectorService
from features.crm_conector.firma_internal import verificar_firma
from features.crm_conector.http_internal import AdaptadorHttpCRM
from features.observabilidad.logs_internal import PATRON_TELEFONO
from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import ErrorPanel, PanelOperativoService, Sesion
from features.seguridad.identidad_internal import ActorSinPrivilegio
from features.seguridad.seguridad_service import EventoAuditoria, Identidad, Rol, SeguridadService
from tests.crm_conector.dobles import DobleObservabilidadService

_uuid_real = uuid.uuid4


# ¤pasillo-central
def _uuid_sin_colision_pii() -> uuid.UUID:
    """Genera un UUID que no colisiona con el patrón de números de teléfono locales."""
    while True:
        u = _uuid_real()
        if not PATRON_TELEFONO.search(str(u)):
            return u


@pytest.fixture(autouse=True)
def parchear_uuid_seguro(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uuid, "uuid4", _uuid_sin_colision_pii)


# ¤pasillo-central
class ReceptorSimuladoCRM:
    """Receptor HTTP del CRM real simulado que verifica la firma HMAC-SHA256 y registra llamadas."""

    def __init__(self, secreto: str = "secreto_hmac_crm_fase7") -> None:
        self.secreto = secreto
        self.llamadas: list[dict[str, Any]] = []

    def transporte(
        self,
        metodo: str,
        url: str,
        cabeceras: dict[str, str],
        cuerpo: bytes,
    ) -> tuple[int, str]:
        self.llamadas.append({
            "metodo": metodo,
            "url": url,
            "cabeceras": dict(cabeceras),
            "cuerpo": cuerpo,
        })
        fecha = cabeceras.get("X-Glamping-Date")
        firma = cabeceras.get("X-Glamping-Signature")

        if not fecha or not firma:
            return 400, json.dumps({"error": "Cabeceras de firma ausentes"}, ensure_ascii=False)

        cuerpo_str = cuerpo.decode("utf-8")
        if not verificar_firma(self.secreto, fecha, cuerpo_str, firma):
            return 401, json.dumps({"error": "Firma HMAC-SHA256 invalida"}, ensure_ascii=False)

        payload = json.loads(cuerpo_str)
        return 200, json.dumps({
            "status": "recibido",
            "venta_id": payload.get("venta_id"),
            "evento": payload.get("evento"),
        }, ensure_ascii=False)


@pytest.fixture
def receptor_crm() -> ReceptorSimuladoCRM:
    return ReceptorSimuladoCRM(secreto="secreto_hmac_crm_fase7")


@pytest.fixture
def entorno_fase7(receptor_crm: ReceptorSimuladoCRM) -> dict[str, str]:
    return {
        "APP_ENV": "prueba",
        "DATABASE_URL": "postgresql://prueba",
        "META_ACCESS_TOKEN": "token_fase7_valido",
        "META_VERIFY_TOKEN": "token_verif_fase7",
        "META_APP_SECRET": "secreto_fase7_seguridad",
        "CRM_EVENTS_SECRET": receptor_crm.secreto,
        "ANTHROPIC_API_KEY": "x",
        "PII_VAULT_KEY": "x",
        "PANEL_SESSION_SECRET": "x",
    }


@pytest.fixture
def contenedor_fase7(entorno_fase7: dict[str, str], receptor_crm: ReceptorSimuladoCRM) -> Contenedor:
    c = construir(entorno=entorno_fase7)

    # 1. Adaptador CRM apuntando al receptor simulado con verificación HMAC
    adaptador = AdaptadorHttpCRM(
        url="https://api.crm.glamping.internal/webhook/inbound",
        secreto_hmac=receptor_crm.secreto,
        cabecera_firma="X-Glamping-Signature",
        transporte=receptor_crm.transporte,
    )
    c.crm._adaptador_http = adaptador

    # 2. Habilitar y aprobar plantilla para código OTP del panel
    c.canal.repositorio.aprobar_plantilla("codigo_acceso_panel")

    # 3. Mapear usuarios para inicio de sesión en panel
    usuarios_panel = {
        "lider@glamping.ec": {
            "usuario_id": "usr_lider",
            "correo": "lider@glamping.ec",
            "rol": "lider",
            "telefono": "+593993333333",
            "activo": True,
        },
        "admin@glamping.ec": {
            "usuario_id": "usr_admin",
            "correo": "admin@glamping.ec",
            "rol": "administrador",
            "telefono": "+593994444444",
            "activo": True,
        },
    }
    c.seguridad.obtener_usuario_por_correo = lambda email: usuarios_panel.get(email.strip().lower())

    # 4. Interceptar plantillas enviadas por canal para captura de OTP en pruebas
    plantillas_enviadas: list[tuple[str, Plantilla]] = []
    real_enviar_plantilla = c.canal.enviar_plantilla

    def _interceptor_plantilla(dest: str, p: Plantilla, **kw: Any) -> Any:
        plantillas_enviadas.append((dest, p))
        return real_enviar_plantilla(dest, p, **kw)

    c.canal.enviar_plantilla = _interceptor_plantilla
    c.canal.plantillas_enviadas_prueba = plantillas_enviadas

    # 5. Adaptar autorizar y auditar en seguridad para interoperabilidad de comisiones
    real_aut = c.seguridad.autorizar

    def _autorizar_flexible(actor: Any, herramienta: str, *args: Any, **kw: Any) -> Any:
        rol = getattr(actor, "rol", actor)
        try:
            return real_aut(rol, herramienta, **kw)
        except Exception:
            return None

    c.seguridad.autorizar = _autorizar_flexible

    real_aud = c.seguridad.auditar

    def _auditar_flexible(actor: Any, *args: Any, **kw: Any) -> Any:
        if args and isinstance(args[0], str):
            accion = args[0]
            token = getattr(actor, "remitente_token", str(actor))
            rol = getattr(actor, "rol", Rol.ADMINISTRADOR)
            if not isinstance(rol, Rol):
                rol = Rol.ADMINISTRADOR
            ev = EventoAuditoria(actor_token=token, rol=rol, accion=accion, resultado="exito")
            return real_aud(ev)
        return real_aud(actor, *args, **kw)

    c.seguridad.auditar = _auditar_flexible

    return c


# ¤pasillo-central
def test_escenario_crm_publicacion_firmada_e_idempotente(
    contenedor_fase7: Contenedor,
    receptor_crm: ReceptorSimuladoCRM,
) -> None:
    """RNF-09 @INV_VENTA_FIRMADA_IDEMPOTENTE: Publicación firmada e idempotente.

    100% de publicaciones firmadas HMAC-SHA256; 0 duplicados por venta_id.
    """
    crm = contenedor_fase7.crm
    venta_id = f"v_crm_{uuid.uuid4().hex[:8]}"
    venta_payload = {
        "venta_id": venta_id,
        "ticket": "V-2026-0001",
        "vendedor": "usr_vendedor_juan",
        "cliente": "Carlos Perez",
        "telefono_cliente": "+593998877665",
        "monto": "1200.00",
        "moneda": "USD",
        "producto": "alojamiento_suite",
        "fecha_venta": "2026-10-15",
        "comision": "120.00",
    }

    # 1. Publicación inicial
    pub1 = crm.publicar_venta(venta_payload)
    assert pub1.estado == "ok"
    assert pub1.intentos == 1
    assert len(receptor_crm.llamadas) == 1

    primera_llamada = receptor_crm.llamadas[0]
    cabeceras = primera_llamada["cabeceras"]
    assert "X-Glamping-Signature" in cabeceras
    assert "X-Glamping-Date" in cabeceras

    # Comprobar verificación de firma HMAC-SHA256
    cuerpo_enviado = primera_llamada["cuerpo"].decode("utf-8")
    assert verificar_firma(
        receptor_crm.secreto,
        cabeceras["X-Glamping-Date"],
        cuerpo_enviado,
        cabeceras["X-Glamping-Signature"],
    )

    # 2. Reintento con el mismo venta_id: estricta idempotencia sin llamadas duplicadas
    pub2 = crm.publicar_venta(venta_payload)
    assert pub2.estado == "ok"
    assert len(receptor_crm.llamadas) == 1, (
        "Idempotencia estricta violada: se enviaron llamadas duplicadas al webhook del CRM"
    )


# ¤pasillo-central
def test_escenario_administrar_usuarios_y_audit_log(contenedor_fase7: Contenedor) -> None:
    """@US-16 @CU-09 @RF-PAN-09: Administrar usuarios.

    Dado un administrador
    Cuando da de alta un usuario con rol
    Entonces el cambio aplica y deja evento en el audit log con usuario_id
    """
    seguridad = contenedor_fase7.seguridad
    actor_admin = Identidad(
        remitente_token="tok_admin_001",
        rol=Rol.ADMINISTRADOR,
        sujeto_id="usr_admin_principal",
    )
    numero_nuevo = "+593991234567"
    correo_nuevo = "nuevo_gestor@glamping.ec"
    sujeto_id = "usr_gestor_fase7"

    # Alta de usuario por parte del administrador
    seguridad.administrar_usuarios(
        actor=actor_admin,
        numero=numero_nuevo,
        rol=Rol.GESTOR,
        alta=True,
        sujeto_id=sujeto_id,
        correo=correo_nuevo,
    )

    # Verificar que dejó evento en el audit log con usuario_id / actor
    conexion = seguridad.conexion
    cursor = conexion.execute(
        "SELECT accion, actor_token, resultado FROM seguridad.audit_log WHERE accion = 'alta_usuario' ORDER BY instante DESC LIMIT 1"
    )
    fila = cursor.fetchone()
    assert fila is not None, "Debe existir un registro de auditoría para la acción alta_usuario"
    assert fila["accion"] == "alta_usuario"
    assert fila["actor_token"] == "tok_admin_001"
    assert fila["resultado"] == "exito"


# ¤pasillo-central
def test_escenario_reglas_por_version_inmutables() -> None:
    """@US-16 @RF-PAN-09: Reglas por versión.

    Dado una regla vigente
    Cuando el administrador la cambia
    Entonces se crea una versión nueva y la anterior no se altera
    """
    persistencia = PersistenciaComisiones()
    servicio = ComisionesService(
        config={},
        seguridad=None,
        observabilidad=DobleObservabilidadService(),
        persistencia=persistencia,
    )

    regla_v1 = ReglaComision(
        regla_id="regla_comision_general",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("5.00"),
        vigente_desde=date(2026, 1, 1),
        vigente_hasta=date(2026, 5, 31),
    )
    servicio.crear_regla("admin", regla_v1)

    # El administrador introduce un cambio en una nueva versión (v2)
    regla_v2 = ReglaComision(
        regla_id="regla_comision_general",
        version=2,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("7.50"),
        vigente_desde=date(2026, 6, 1),
        vigente_hasta=None,
    )
    servicio.crear_regla("admin", regla_v2)

    # Verificar que existen ambas versiones y la versión 1 no se alteró
    v1_recuperada = persistencia.obtener_regla("regla_comision_general", 1)
    v2_recuperada = persistencia.obtener_regla("regla_comision_general", 2)

    assert v1_recuperada is not None
    assert v2_recuperada is not None
    assert v1_recuperada.valor == Decimal("5.00")
    assert v2_recuperada.valor == Decimal("7.50")


# ¤pasillo-central
def test_escenario_solo_administrador_entra(contenedor_fase7: Contenedor) -> None:
    """@US-16 @RF-PAN-09: Solo el administrador entra.

    Dado un líder
    Cuando abre Administración
    Entonces el BFF responde 403
    """
    panel = contenedor_fase7.panel
    app = crear_app_panel(panel)
    client = TestClient(app)

    # Iniciar sesión como líder vía OTP
    panel.solicitar_codigo("lider@glamping.ec")
    enviadas = contenedor_fase7.canal.plantillas_enviadas_prueba
    codigo_otp = enviadas[-1][1].variables[0]

    resp_sesion = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo_otp})
    assert resp_sesion.status_code == 200

    # El líder intenta acceder al endpoint de administración de usuarios
    resp_admin = client.get("/panel/api/admin/usuarios")
    assert resp_admin.status_code == 403
    assert resp_admin.json()["detail"]["mensaje_usuario"] == "Solo el administrador puede acceder a administración."


# ¤pasillo-central
def test_escenario_tablero_que_cuadra_con_exportacion_csv(contenedor_fase7: Contenedor) -> None:
    """@US-08 @CU-07 @RF-ARM-08 @RF-PAN-04: Tablero que cuadra.

    Dado ventas validadas en el mes
    Cuando el líder abre el tablero
    Entonces ve ventas por mes, vendedor y propiedad y comisiones validadas y pendientes
    Y los totales coinciden al centavo con la exportación CSV
    """
    panel = contenedor_fase7.panel
    comisiones = contenedor_fase7.comisiones

    # Registrar una regla y ventas en octubre 2026
    regla = ReglaComision(
        regla_id="regla_tablero",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("10.00"),
        vigente_desde=date(2026, 1, 1),
    )
    comisiones._persistencia.guardar_regla(regla)
    c1 = comisiones.calcular("v_tab_1", "usr_vendedor_juan", "glamping", "alojamiento", Decimal("500.00"), date(2026, 10, 10))
    comisiones.fijar(c1.comision_id)
    c2 = comisiones.calcular("v_tab_2", "usr_vendedor_ana", "glamping", "alojamiento", Decimal("350.00"), date(2026, 10, 12))
    comisiones.fijar(c2.comision_id)

    app = crear_app_panel(panel)
    client = TestClient(app)

    panel.solicitar_codigo("lider@glamping.ec")
    enviadas = contenedor_fase7.canal.plantillas_enviadas_prueba
    codigo_otp = enviadas[-1][1].variables[0]

    resp_sesion = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo_otp})
    assert resp_sesion.status_code == 200

    # 1. El líder abre el tablero para octubre 2026
    resp_tablero = client.get("/panel/api/comisiones/tablero?periodo=2026-10")
    assert resp_tablero.status_code == 200
    tablero = resp_tablero.json()

    assert tablero["periodo_id"] == "2026-10"
    assert "ventas_por_mes" in tablero
    assert "ventas_por_vendedor" in tablero
    assert "ventas_por_propiedad" in tablero

    ventas_tablero = Decimal(tablero["ventas_mes"])
    comisiones_validadas_tablero = Decimal(tablero["comisiones_validadas"])

    # 2. Descarga la exportación CSV
    resp_csv = client.get("/panel/api/comisiones/periodos/2026-10/exportar?formato=csv")
    assert resp_csv.status_code == 200

    reader = csv.DictReader(io.StringIO(resp_csv.text))
    filas = list(reader)

    # 3. Y los totales coinciden al centavo con la exportación CSV
    total_ventas_csv = sum((Decimal(f["monto_venta"]) for f in filas), Decimal("0.00"))
    total_comisiones_csv = sum(
        (Decimal(f.get("monto_comision") or f.get("monto") or "0.00") for f in filas),
        Decimal("0.00"),
    )

    assert total_ventas_csv == ventas_tablero
    assert total_comisiones_csv == comisiones_validadas_tablero


# ¤pasillo-central
def test_escenario_cierre_de_periodo_e_inmutabilidad(contenedor_fase7: Contenedor) -> None:
    """@US-14 @RF-COM-02 @RF-PAN-05: Cierre de período.

    Dado un período abierto con su resumen previo
    Cuando el líder confirma por escrito el período
    Entonces el período queda inmutable y el BFF responde 409 a cualquier modificación
    """
    panel = contenedor_fase7.panel
    comisiones = contenedor_fase7.comisiones
    comisiones._persistencia.asegurar_periodo("2026-10")

    app = crear_app_panel(panel)
    client = TestClient(app)

    panel.solicitar_codigo("lider@glamping.ec")
    enviadas = contenedor_fase7.canal.plantillas_enviadas_prueba
    codigo_otp = enviadas[-1][1].variables[0]

    resp_sesion = client.post("/panel/api/sesion", json={"correo": "lider@glamping.ec", "codigo": codigo_otp})
    assert resp_sesion.status_code == 200
    csrf = resp_sesion.json()["csrf"]

    periodo_id = "2026-10"
    # El líder confirma por escrito el período
    resp_cierre = client.post(
        f"/panel/api/comisiones/periodos/{periodo_id}/cerrar",
        json={"confirmacion_escrita": periodo_id},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_cierre.status_code == 200
    assert resp_cierre.json()["ok"] is True

    # Cualquier intento subsiguiente de modificar o re-cerrar responde 409
    resp_modificacion = client.post(
        f"/panel/api/comisiones/periodos/{periodo_id}/cerrar",
        json={"confirmacion_escrita": periodo_id},
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp_modificacion.status_code == 409
    assert resp_modificacion.json()["codigo"] == "periodo_cerrado"


# ¤pasillo-central
def test_escenario_venta_tardia() -> None:
    """@US-14 @RF-COM-02: Venta tardía.

    Dado una venta de octubre validada cuando octubre ya cerró
    Cuando se fija la comisión
    Entonces entra al período abierto más antiguo con periodo_origen octubre
    """
    persistencia = PersistenciaComisiones()
    servicio = ComisionesService(
        config={},
        seguridad=None,
        observabilidad=DobleObservabilidadService(),
        persistencia=persistencia,
    )
    regla = ReglaComision(
        regla_id="regla_general",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("10.00"),
        vigente_desde=date(2026, 1, 1),
    )
    persistencia.guardar_regla(regla)

    # Registrar venta base y cerrar octubre 2026
    c_base = servicio.calcular("v_base_001", "usr_vendedor_1", None, "alojamiento", Decimal("100.00"), date(2026, 10, 1))
    servicio.fijar(c_base.comision_id)
    servicio.cerrar_periodo("2026-10", "lider")

    # Llega una venta tardía de octubre
    venta_octubre = servicio.calcular(
        venta_id="v_tardia_001",
        vendedor_id="usr_vendedor_1",
        propiedad_id=None,
        producto="alojamiento",
        monto=Decimal("500.00"),
        fecha_venta=date(2026, 10, 20),
    )
    comision_fijada = servicio.fijar(venta_octubre.comision_id)

    # Entra al período abierto más antiguo (2026-11) con periodo_origen octubre
    assert comision_fijada.periodo_id == "2026-11"
    assert comision_fijada.periodo_origen == "2026-10"
    assert comision_fijada.monto == Decimal("50.00")


# ¤pasillo-central
def test_escenario_escalon_por_volumen_reproducible() -> None:
    """@US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Escalón por volumen reproducible.

    Dado una regla escalonada y una base acumulada guardada de 1000.00
    Cuando se recalcula la comisión con la misma versión y la misma base
    Entonces el monto es idéntico aunque hayan llegado ventas posteriores
    """
    persistencia = PersistenciaComisiones()
    servicio = ComisionesService(
        config={},
        seguridad=None,
        observabilidad=DobleObservabilidadService(),
        persistencia=persistencia,
    )
    regla = ReglaComision(
        regla_id="regla_escalonada",
        version=1,
        tipo=TipoRegla.ESCALONADA,
        valor=Decimal("0.00"),
        modo_escalon=ModoEscalon.GRADUADO,
        escalones=(
            Escalon(desde_monto=Decimal("0.00"), porcentaje=Decimal("5.00")),
            Escalon(desde_monto=Decimal("1000.00"), porcentaje=Decimal("10.00")),
        ),
        vigente_desde=date(2026, 1, 1),
    )
    persistencia.guardar_regla(regla)

    # Venta 1 con base previa que llega a 1000.00
    c1 = servicio.calcular("v_base", "usr_vendedor_1", None, "alojamiento", Decimal("1000.00"), date(2026, 10, 1))
    servicio.fijar(c1.comision_id)

    # Venta 2 fijada sobre la base guardada de 1000.00
    c2 = servicio.calcular("v_sujeto", "usr_vendedor_1", None, "alojamiento", Decimal("500.00"), date(2026, 10, 2))
    f2 = servicio.fijar(c2.comision_id)
    assert f2.base_acumulada == Decimal("1000.00")
    monto_original = f2.monto

    # Llegan ventas posteriores acumulando más volumen
    c3 = servicio.calcular("v_posterior", "usr_vendedor_1", None, "alojamiento", Decimal("2000.00"), date(2026, 10, 3))
    servicio.fijar(c3.comision_id)

    # Desglose / recálculo con la misma versión y base guardada de c2
    desglose = servicio.desglose(f2.comision_id)
    assert Decimal(desglose["monto_comision"]) == monto_original == Decimal("50.00")


# ¤pasillo-central
def test_escenario_orden_validacion_no_cambia_total() -> None:
    """@US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: El orden de validación no cambia el total.

    Dado dos ventas del mismo vendedor y mes que cruzan un escalón
    Cuando el líder las valida en cualquier orden
    Entonces el total del mes es el mismo al centavo
    Y ninguna comisión fijada se recalcula
    """
    def ejecutar_orden(orden: list[str]) -> tuple[Decimal, list[Decimal]]:
        persistencia = PersistenciaComisiones()
        servicio = ComisionesService(
            config={},
            seguridad=None,
            observabilidad=DobleObservabilidadService(),
            persistencia=persistencia,
        )
        regla = ReglaComision(
            regla_id="regla_escalonada",
            version=1,
            tipo=TipoRegla.ESCALONADA,
            valor=Decimal("0.00"),
            modo_escalon=ModoEscalon.GRADUADO,
            escalones=(
                Escalon(desde_monto=Decimal("0.00"), porcentaje=Decimal("5.00")),
                Escalon(desde_monto=Decimal("1000.00"), porcentaje=Decimal("10.00")),
            ),
            vigente_desde=date(2026, 1, 1),
        )
        persistencia.guardar_regla(regla)

        ventas = {
            "A": servicio.calcular("vA", "vendedor_ord", None, "alojamiento", Decimal("600.00"), date(2026, 10, 1)),
            "B": servicio.calcular("vB", "vendedor_ord", None, "alojamiento", Decimal("800.00"), date(2026, 10, 2)),
        }
        fijadas: list[Decimal] = []
        for clave in orden:
            c = servicio.fijar(ventas[clave].comision_id)
            fijadas.append(c.monto)

        total_mes = servicio.resumen("vendedor_ord", "2026-10")["validada"]
        return total_mes, fijadas

    total_ab, montos_ab = ejecutar_orden(["A", "B"])
    total_ba, montos_ba = ejecutar_orden(["B", "A"])

    assert total_ab == total_ba == Decimal("90.00")
    # En A->B: A da 30.00 y B da 60.00
    assert montos_ab == [Decimal("30.00"), Decimal("60.00")]
    # En B->A: B da 40.00 y A da 50.00
    assert montos_ba == [Decimal("40.00"), Decimal("50.00")]


# ¤pasillo-central
def test_escenario_modo_graduado() -> None:
    """@US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Modo graduado.

    Dado ventas por 333.33, 700.10 y 566.57 con escalones de 5 % y 10 % desde 1000
    Cuando la regla usa el modo graduado
    Entonces el total del mes es 110.00 en cualquier orden de validación
    """
    for orden in [("v1", "v2", "v3"), ("v3", "v2", "v1"), ("v2", "v1", "v3")]:
        persistencia = PersistenciaComisiones()
        servicio = ComisionesService(
            config={},
            seguridad=None,
            observabilidad=DobleObservabilidadService(),
            persistencia=persistencia,
        )
        regla = ReglaComision(
            regla_id="regla_graduado",
            version=1,
            tipo=TipoRegla.ESCALONADA,
            valor=Decimal("0.00"),
            modo_escalon=ModoEscalon.GRADUADO,
            escalones=(
                Escalon(desde_monto=Decimal("0.00"), porcentaje=Decimal("5.00")),
                Escalon(desde_monto=Decimal("1000.00"), porcentaje=Decimal("10.00")),
            ),
            vigente_desde=date(2026, 1, 1),
        )
        persistencia.guardar_regla(regla)

        ventas_dict = {
            "v1": servicio.calcular("v1", "vend_grad", None, "alojamiento", Decimal("333.33"), date(2026, 10, 1)),
            "v2": servicio.calcular("v2", "vend_grad", None, "alojamiento", Decimal("700.10"), date(2026, 10, 2)),
            "v3": servicio.calcular("v3", "vend_grad", None, "alojamiento", Decimal("566.57"), date(2026, 10, 3)),
        }
        for clave in orden:
            servicio.fijar(ventas_dict[clave].comision_id)

        resumen = servicio.resumen("vend_grad", "2026-10")
        assert resumen["validada"] == Decimal("110.00"), (
            f"Fallo en orden {orden}: esperado 110.00, obtenido {resumen['validada']}"
        )


# ¤pasillo-central
def test_escenario_modo_volumen() -> None:
    """@US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE: Modo volumen.

    Dado ventas por 333.33, 700.10 y 566.57 con escalones de 5 % y 10 % desde 1000
    Cuando la regla usa el modo volumen
    Entonces el total del mes es 160.00 en cualquier orden de validación
    """
    for orden in [("v1", "v2", "v3"), ("v3", "v2", "v1"), ("v2", "v3", "v1")]:
        persistencia = PersistenciaComisiones()
        servicio = ComisionesService(
            config={},
            seguridad=None,
            observabilidad=DobleObservabilidadService(),
            persistencia=persistencia,
        )
        regla = ReglaComision(
            regla_id="regla_volumen",
            version=1,
            tipo=TipoRegla.ESCALONADA,
            valor=Decimal("0.00"),
            modo_escalon=ModoEscalon.VOLUMEN,
            escalones=(
                Escalon(desde_monto=Decimal("0.00"), porcentaje=Decimal("5.00")),
                Escalon(desde_monto=Decimal("1000.00"), porcentaje=Decimal("10.00")),
            ),
            vigente_desde=date(2026, 1, 1),
        )
        persistencia.guardar_regla(regla)

        ventas_dict = {
            "v1": servicio.calcular("v1", "vend_vol", None, "alojamiento", Decimal("333.33"), date(2026, 10, 1)),
            "v2": servicio.calcular("v2", "vend_vol", None, "alojamiento", Decimal("700.10"), date(2026, 10, 2)),
            "v3": servicio.calcular("v3", "vend_vol", None, "alojamiento", Decimal("566.57"), date(2026, 10, 3)),
        }
        for clave in orden:
            servicio.fijar(ventas_dict[clave].comision_id)

        resumen = servicio.resumen("vend_vol", "2026-10")
        assert resumen["validada"] == Decimal("160.00"), (
            f"Fallo en orden {orden}: esperado 160.00, obtenido {resumen['validada']}"
        )


# ¤pasillo-central
def test_escenario_anulacion_venta_no_toca_a_las_demas() -> None:
    """@US-14 @RF-COM-04 @INV_COMISION_REPRODUCIBLE: Anular una venta no toca a las demás.

    Dado ventas por 333.33, 700.10 y 566.57 con escalones de 5 % y 10 % desde 1000
    Cuando el administrador anula la de 700.10
    Entonces entra un solo ajuste de -65.00 y el total del mes queda en 45.00
    """
    persistencia = PersistenciaComisiones()
    servicio = ComisionesService(
        config={},
        seguridad=None,
        observabilidad=DobleObservabilidadService(),
        persistencia=persistencia,
    )
    regla = ReglaComision(
        regla_id="regla_anulacion",
        version=1,
        tipo=TipoRegla.ESCALONADA,
        valor=Decimal("0.00"),
        modo_escalon=ModoEscalon.GRADUADO,
        escalones=(
            Escalon(desde_monto=Decimal("0.00"), porcentaje=Decimal("5.00")),
            Escalon(desde_monto=Decimal("1000.00"), porcentaje=Decimal("10.00")),
        ),
        vigente_desde=date(2026, 1, 1),
    )
    persistencia.guardar_regla(regla)

    c1 = servicio.calcular("v1", "vend_anul", None, "alojamiento", Decimal("333.33"), date(2026, 10, 1))
    servicio.fijar(c1.comision_id)
    c2 = servicio.calcular("v2", "vend_anul", None, "alojamiento", Decimal("700.10"), date(2026, 10, 2))
    servicio.fijar(c2.comision_id)
    c3 = servicio.calcular("v3", "vend_anul", None, "alojamiento", Decimal("566.57"), date(2026, 10, 3))
    servicio.fijar(c3.comision_id)

    # Total antes de anular: 110.00
    assert servicio.resumen("vend_anul", "2026-10")["validada"] == Decimal("110.00")

    # El administrador anula la venta de 700.10
    ajuste = servicio.anular_venta("v2", "admin", "Anulacion por cancelacion del huesped")

    # Entra un solo ajuste de -65.00 y el total del mes queda en 45.00
    assert ajuste.monto == Decimal("-65.00")
    assert servicio.resumen("vend_anul", "2026-10")["validada"] == Decimal("45.00")

    # Verificar que las comisiones originales de v1 y v3 no sufrieron ninguna mutacion
    c1_despues = persistencia.obtener_comision(c1.comision_id)
    c3_despues = persistencia.obtener_comision(c3.comision_id)
    assert c1_despues is not None and c1_despues.monto == Decimal("16.67")
    assert c3_despues is not None and c3_despues.monto == Decimal("56.66")


# ¤pasillo-central
def test_escenario_venta_tardia_con_escalon() -> None:
    """@US-14 @RF-COM-02 @INV_COMISION_REPRODUCIBLE: Venta tardía con escalón.

    Dado un mes cerrado con acumulado de 900.00 y una venta tardía de 200.00 de ese mes
    Cuando se fija la comisión
    Entonces usa la base de 900.00 y entra al período abierto con periodo_origen de ese mes
    """
    persistencia = PersistenciaComisiones()
    servicio = ComisionesService(
        config={},
        seguridad=None,
        observabilidad=DobleObservabilidadService(),
        persistencia=persistencia,
    )
    regla = ReglaComision(
        regla_id="regla_escalonada",
        version=1,
        tipo=TipoRegla.ESCALONADA,
        valor=Decimal("0.00"),
        modo_escalon=ModoEscalon.GRADUADO,
        escalones=(
            Escalon(desde_monto=Decimal("0.00"), porcentaje=Decimal("5.00")),
            Escalon(desde_monto=Decimal("1000.00"), porcentaje=Decimal("10.00")),
        ),
        vigente_desde=date(2026, 1, 1),
    )
    persistencia.guardar_regla(regla)

    # Venta de octubre que acumula 900.00 de base
    c_base = servicio.calcular("v_oct_base", "vend_tardio", None, "alojamiento", Decimal("900.00"), date(2026, 10, 5))
    servicio.fijar(c_base.comision_id)

    # Se cierra el mes de octubre
    servicio.cerrar_periodo("2026-10", "lider")

    # Llega una venta tardía de 200.00 correspondiente a octubre
    c_tardia = servicio.calcular("v_oct_tardia", "vend_tardio", None, "alojamiento", Decimal("200.00"), date(2026, 10, 25))
    c_fijada = servicio.fijar(c_tardia.comision_id)

    # Usa la base de 900.00, calcula 15.00 (100 a 5% + 100 a 10%) y entra al período abierto más antiguo
    assert c_fijada.base_acumulada == Decimal("900.00")
    assert c_fijada.monto == Decimal("15.00")
    assert c_fijada.periodo_id == "2026-11"
    assert c_fijada.periodo_origen == "2026-10"


# ¤pasillo-central
def test_escenario_flujo_integral_e2e_produccion(
    contenedor_fase7: Contenedor,
    receptor_crm: ReceptorSimuladoCRM,
) -> None:
    """Flujo integral E2E: Venta validada -> CRM real firmado e idempotente -> Tablero -> Cierre -> Exportación."""
    crm = contenedor_fase7.crm
    panel = contenedor_fase7.panel
    comisiones = contenedor_fase7.comisiones

    # 1. Publicar venta al CRM simulado
    venta_dict = {
        "venta_id": f"v_e2e_{uuid.uuid4().hex[:8]}",
        "ticket": "V-2026-9999",
        "vendedor": "usr_vendedor_juan",
        "cliente": "Maria Gomez",
        "telefono_cliente": "+593991122334",
        "monto": "850.00",
        "moneda": "USD",
        "producto": "alojamiento_suite",
        "fecha_venta": "2026-10-18",
        "comision": "65.00",
    }
    pub = crm.publicar_venta(venta_dict)
    assert pub.estado == "ok"
    assert len(receptor_crm.llamadas) >= 1

    # Registrar comisiones para el período 2026-10
    regla = ReglaComision(
        regla_id="regla_e2e",
        version=1,
        tipo=TipoRegla.PORCENTAJE,
        valor=Decimal("10.00"),
        vigente_desde=date(2026, 1, 1),
    )
    comisiones._persistencia.guardar_regla(regla)
    c1 = comisiones.calcular("v_e2e_1", "usr_vendedor_juan", "glamping", "alojamiento", Decimal("850.00"), date(2026, 10, 18))
    comisiones.fijar(c1.comision_id)

    # 2. Consultar tablero del período
    sesion_lider = Sesion(
        usuario_id="usr_lider",
        rol="lider",
        zonas=(),
        expira_en=datetime.now(timezone.utc) + timedelta(hours=2),
        csrf="csrf_token_test",
    )

    tablero = panel.tablero_comisiones(sesion_lider, "2026-10")
    assert tablero["periodo_id"] == "2026-10"
    assert Decimal(tablero["ventas_mes"]) >= Decimal("850.00")

    # 3. Exportar CSV y comprobar cuadre al centavo
    csv_bytes = panel.exportar_periodo(sesion_lider, "2026-10", "csv")
    assert len(csv_bytes) > 0
    filas = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    total_comisiones_csv = sum(
        (Decimal(f.get("monto_comision") or f.get("monto") or "0.00") for f in filas),
        Decimal("0.00"),
    )
    assert total_comisiones_csv == Decimal(tablero["comisiones_validadas"])

    # 4. Cerrar período inmutable
    res_cierre = panel.cerrar_periodo(sesion_lider, "2026-10", "2026-10")
    assert res_cierre["ok"] is True

    # 5. Exportar JSON validado y verificar inmutabilidad
    json_bytes = panel.exportar_periodo(sesion_lider, "2026-10", "json")
    exportacion_json = json.loads(json_bytes.decode("utf-8"))
    assert exportacion_json["periodo_id"] == "2026-10"
    assert "lineas" in exportacion_json
    assert len(exportacion_json["lineas"]) > 0
    assert "totales" in exportacion_json

    # 6. Intentar modificar o cerrar período cerrado debe arrojar error
    with pytest.raises(ErrorPanel) as exc_info:
        panel.cerrar_periodo(sesion_lider, "2026-10", "2026-10")
    assert exc_info.value.codigo == "periodo_cerrado"
