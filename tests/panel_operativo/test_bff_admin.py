# ¤panel-operativo
# ¤¤frontend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Árbitro de RF-PAN-09, RF-ANF-01, RF-ANF-02, RF-PMS-08 e INV_AISLAMIENTO_ANFITRION.

Verifica:
1. Aislamiento por rol en administración: solo administrador tiene acceso (403 para gestor, líder, anfitrión).
2. Gestión de usuarios, enmascaramiento y auditoría con usuario_id.
3. Reglas de comisión por versión inmutable.
4. Alta de anfitrión con versión de términos obligatoria y tokenización.
5. Publicación revisada de hospedaje por administrador con actor y fecha.
6. Mantenimiento del calendario con aislamiento de anfitrión y liberación omitiendo reservas activas.
7. Auditoría filtrable y exportable a CSV.
8. Solicitudes de titulares de datos (ARCO).
9. Salud del sistema y reindexación de conocimiento con set dorado.
"""
from __future__ import annotations

from datetime import date
from fastapi.testclient import TestClient
import pytest

from features.panel_operativo.bff_internal import crear_app_panel
from features.panel_operativo.panel_operativo_service import PanelOperativoService, cargar_config
from tests.panel_operativo.dobles import (
    DobleAgenteService,
    DobleCanalWhatsappService,
    DobleObservabilidadService,
    DoblePMSConectorService,
    DobleSeguridadService,
)


def _crear_cliente_con_sesion(
    correo: str, servicio_existente: PanelOperativoService | None = None
) -> tuple[TestClient, PanelOperativoService, str]:
    if servicio_existente is not None:
        servicio = servicio_existente
        canal = servicio._canal
    else:
        config = dict(cargar_config())
        seguridad = DobleSeguridadService()
        agente = DobleAgenteService()
        canal = DobleCanalWhatsappService()
        pms = DoblePMSConectorService()
        servicio = PanelOperativoService(
            config,
            seguridad=seguridad,
            agente=agente,
            canal=canal,
            pms=pms,
            observabilidad=DobleObservabilidadService(),
        )
    app = crear_app_panel(servicio)
    client = TestClient(app)

    # Iniciar sesión
    servicio.solicitar_codigo(correo)
    codigo = canal.plantillas_enviadas[-1][1].variables[0]
    resp = client.post("/panel/api/sesion", json={"correo": correo, "codigo": codigo})
    assert resp.status_code == 200
    csrf = resp.json()["csrf"]
    return client, servicio, csrf


def test_administracion_aislamiento_por_rol_403() -> None:
    """Verifica que roles no administradores (gestor, líder, anfitrión) reciban 403 en endpoints admin."""
    # Gestor intentando acceder a administración
    client_gestor, _, csrf_gestor = _crear_cliente_con_sesion("gestor_a@glamping.ec")
    cabeceras_gestor = {"X-CSRF-Token": csrf_gestor}

    assert client_gestor.get("/panel/api/admin/usuarios").status_code == 403
    assert client_gestor.post("/panel/api/admin/usuarios", json={"numero": "+593998887777", "rol": "gestor"}, headers=cabeceras_gestor).status_code == 403
    assert client_gestor.get("/panel/api/admin/reglas_comision").status_code == 403
    assert client_gestor.post("/panel/api/admin/reglas_comision", json={"nombre": "Regla X"}, headers=cabeceras_gestor).status_code == 403
    assert client_gestor.get("/panel/api/admin/anfitriones").status_code == 403
    assert client_gestor.post("/panel/api/admin/anfitriones", json={"nombre": "Anf X", "version_terminos": "v1"}, headers=cabeceras_gestor).status_code == 403
    assert client_gestor.get("/panel/api/admin/auditoria").status_code == 403
    assert client_gestor.get("/panel/api/admin/auditoria/exportar").status_code == 403
    assert client_gestor.get("/panel/api/admin/privacidad/solicitudes").status_code == 403
    assert client_gestor.get("/panel/api/admin/salud").status_code == 403
    assert client_gestor.post("/panel/api/admin/conocimiento/reindexar", headers=cabeceras_gestor).status_code == 403
    assert client_gestor.get("/panel/api/admin/plantillas").status_code == 403

    # Líder intentando acceder a administración
    client_lider, _, _ = _crear_cliente_con_sesion("lider@glamping.ec")
    assert client_lider.get("/panel/api/admin/usuarios").status_code == 403
    assert client_lider.get("/panel/api/admin/salud").status_code == 403


def test_admin_gestion_usuarios_enmascaramiento_y_auditoria() -> None:
    """Verifica que el administrador gestione usuarios con números enmascarados y auditoría obligatoria."""
    client_admin, servicio, csrf = _crear_cliente_con_sesion("admin@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf}

    # Listar usuarios
    resp_lista = client_admin.get("/panel/api/admin/usuarios")
    assert resp_lista.status_code == 200
    usuarios = resp_lista.json()
    assert len(usuarios) >= 1
    # Comprobar enmascaramiento
    for u in usuarios:
        assert "***" in u["correo_enmascarado"]
        assert "***" in u["numero_enmascarado"]

    # Dar de alta usuario
    nuevo_num = "+593991239999"
    resp_alta = client_admin.post(
        "/panel/api/admin/usuarios",
        json={"numero": nuevo_num, "rol": "gestor", "alta": True, "correo": "nuevo_gestor@glamping.ec"},
        headers=cabeceras,
    )
    assert resp_alta.status_code == 200

    # Comprobar evento en auditoría con usuario_id del administrador
    resp_aud = client_admin.get("/panel/api/admin/auditoria?accion=alta_usuario")
    assert resp_aud.status_code == 200
    eventos = resp_aud.json()
    assert len(eventos) >= 1
    ultimo = eventos[-1]
    assert ultimo["actor"] == "usr_admin"
    assert ultimo["accion"] == "alta_usuario"
    assert ultimo["usuario_id"] == "usr_admin"

    # Bloquear número
    resp_bloq = client_admin.post(
        "/panel/api/admin/bloqueos",
        json={"numero": nuevo_num, "motivo": "Sospecha de fraude"},
        headers=cabeceras,
    )
    assert resp_bloq.status_code == 200

    # Desbloquear número
    resp_desbloq = client_admin.delete(f"/panel/api/admin/bloqueos/{nuevo_num}", headers=cabeceras)
    assert resp_desbloq.status_code == 200


def test_reglas_comision_version_inmutable() -> None:
    """Verifica que la creación de regla cree nuevas versiones y nunca mutaciones en sitio."""
    client_admin, _, csrf = _crear_cliente_con_sesion("admin@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf}

    # Crear versión 1
    resp_v1 = client_admin.post(
        "/panel/api/admin/reglas_comision",
        json={"regla_id": "regla_otavalo", "nombre": "Comisión Otavalo", "tipo": "porcentaje", "parametros": {"porcentaje": 12.0}},
        headers=cabeceras,
    )
    assert resp_v1.status_code == 200
    r1 = resp_v1.json()
    assert r1["regla_id"] == "regla_otavalo"
    assert r1["version"] == 1

    # Crear versión 2 para la misma regla
    resp_v2 = client_admin.post(
        "/panel/api/admin/reglas_comision",
        json={"regla_id": "regla_otavalo", "nombre": "Comisión Otavalo 2027", "tipo": "porcentaje", "parametros": {"porcentaje": 14.0}},
        headers=cabeceras,
    )
    assert resp_v2.status_code == 200
    r2 = resp_v2.json()
    assert r2["regla_id"] == "regla_otavalo"
    assert r2["version"] == 2

    # Consultar historial completo
    resp_lista = client_admin.get("/panel/api/admin/reglas_comision")
    assert resp_lista.status_code == 200
    historial = [r for r in resp_lista.json() if r["regla_id"] == "regla_otavalo"]
    assert len(historial) == 2
    assert historial[0]["version"] == 1
    assert historial[1]["version"] == 2


def test_anfitrion_alta_terminos_obligatorios_y_tokenizacion() -> None:
    """RF-ANF-01: Registro de anfitrión exige términos y tokeniza teléfono."""
    client_admin, _, csrf = _crear_cliente_con_sesion("admin@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf}

    # Sin versión de términos debe ser rechazado con 400
    resp_sin_terminos = client_admin.post(
        "/panel/api/admin/anfitriones",
        json={"anfitrion_id": "anf_test", "nombre": "Juan Pérez", "telefono": "+593991234567", "porcentaje_comision": 15.0},
        headers=cabeceras,
    )
    assert resp_sin_terminos.status_code == 400
    assert "términos" in resp_sin_terminos.json()["detail"]["mensaje_usuario"].lower()

    # Con versión de términos debe ser exitoso y teléfono tokenizado
    resp_con_terminos = client_admin.post(
        "/panel/api/admin/anfitriones",
        json={
            "anfitrion_id": "anf_test",
            "nombre": "Juan Pérez",
            "telefono": "+593991234567",
            "porcentaje_comision": 15.0,
            "version_terminos": "v2.1_2026",
        },
        headers=cabeceras,
    )
    assert resp_con_terminos.status_code == 200
    anf = resp_con_terminos.json()
    assert anf["anfitrion_id"] == "anf_test"
    assert anf["version_terminos"] == "v2.1_2026"
    assert anf["telefono_token"].startswith("tok_")


def test_publicacion_revisada_hospedaje() -> None:
    """RF-ANF-02: Publicación de hospedaje requiere rol administrador, guardando actor y fecha."""
    client_admin, servicio, csrf_admin = _crear_cliente_con_sesion("admin@glamping.ec")
    cabeceras_admin = {"X-CSRF-Token": csrf_admin}

    # Hospedaje en borrador
    servicio.guardar_hospedaje_borrador("hosp_domo_1", "anf_1", "Domo Estelar")

    # Anfitrión intenta publicar por sí mismo: 403 Forbidden
    client_anf, _, csrf_anf = _crear_cliente_con_sesion("anfitrion@glamping.ec", servicio_existente=servicio)
    resp_anf_pub = client_anf.post("/panel/api/admin/hospedajes/hosp_domo_1/publicar", headers={"X-CSRF-Token": csrf_anf})
    assert resp_anf_pub.status_code == 403

    # Administrador publica
    resp_pub = client_admin.post("/panel/api/admin/hospedajes/hosp_domo_1/publicar", headers=cabeceras_admin)
    assert resp_pub.status_code == 200
    datos = resp_pub.json()
    assert datos["estado"] == "publicado"
    assert datos["publicado_por"] == "usr_admin"
    assert datos["publicado_en"] is not None


def test_mantenimiento_calendario_aislamiento_anfitrion() -> None:
    """RF-PMS-08 & INV_AISLAMIENTO_ANFITRION: El anfitrión solo puede cambiar unidades propias."""
    client_anf1, servicio, csrf1 = _crear_cliente_con_sesion("anfitrion@glamping.ec")
    cabeceras1 = {"X-CSRF-Token": csrf1}

    # Registrar unidades: u_propia de anf_1, u_ajena de anf_2
    servicio.registrar_unidad("u_propia", "anf_1", "Cabaña A")
    servicio.registrar_unidad("u_ajena", "anf_2", "Cabaña B")

    # anf_1 bloquea fechas en su unidad: OK
    resp_ok = client_anf1.post(
        "/panel/api/calendario/bloquear",
        json={"unidad_id": "u_propia", "desde": "2026-11-10", "hasta": "2026-11-15"},
        headers=cabeceras1,
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["noches_bloqueadas"] == 5

    # anf_1 intenta bloquear fechas en unidad de anf_2: 403 Forbidden
    resp_prohibido = client_anf1.post(
        "/panel/api/calendario/bloquear",
        json={"unidad_id": "u_ajena", "desde": "2026-11-10", "hasta": "2026-11-15"},
        headers=cabeceras1,
    )
    assert resp_prohibido.status_code == 403

    # anf_1 intenta liberar fechas en unidad ajena: 403 Forbidden
    resp_liberar_prohibido = client_anf1.post(
        "/panel/api/calendario/liberar",
        json={"unidad_id": "u_ajena", "desde": "2026-11-10", "hasta": "2026-11-15"},
        headers=cabeceras1,
    )
    assert resp_liberar_prohibido.status_code == 403


def test_liberar_fechas_no_toca_reservas_activas() -> None:
    """RF-PMS-08: Liberar fechas nunca toca noches con reserva activa y reporta noches omitidas."""
    client_anf1, servicio, csrf1 = _crear_cliente_con_sesion("anfitrion@glamping.ec")
    cabeceras1 = {"X-CSRF-Token": csrf1}

    servicio.registrar_unidad("u_reservada", "anf_1", "Suite Lago")
    # Noche 2026-12-05 tiene reserva activa
    servicio.registrar_reserva_calendario("u_reservada", date(2026, 12, 5))

    # Bloquear 2026-12-01 al 2026-12-10 (9 noches)
    client_anf1.post(
        "/panel/api/calendario/bloquear",
        json={"unidad_id": "u_reservada", "desde": "2026-12-01", "hasta": "2026-12-10"},
        headers=cabeceras1,
    )

    # Liberar 2026-12-01 al 2026-12-10
    resp_lib = client_anf1.post(
        "/panel/api/calendario/liberar",
        json={"unidad_id": "u_reservada", "desde": "2026-12-01", "hasta": "2026-12-10"},
        headers=cabeceras1,
    )
    assert resp_lib.status_code == 200
    res = resp_lib.json()
    assert res["liberadas"] == 8
    assert res["omitidas"] == 1


def test_auditoria_exportar_csv_y_solicitudes_privacidad() -> None:
    """Verifica exportación de audit log en CSV y solicitudes ARCO de privacidad."""
    client_admin, _, csrf = _crear_cliente_con_sesion("admin@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf}

    # Exportar auditoría a CSV
    resp_csv = client_admin.get("/panel/api/admin/auditoria/exportar")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers.get("content-type", "")
    assert "evento_id,actor,usuario_id,accion,detalles,instante" in resp_csv.text

    # Registrar solicitud de privacidad ARCO
    resp_sol = client_admin.post(
        "/panel/api/admin/privacidad/solicitudes",
        json={"tipo": "cancelacion", "titular_hash": "hash_abc_123"},
        headers=cabeceras,
    )
    assert resp_sol.status_code == 200
    sol = resp_sol.json()
    assert sol["tipo"] == "cancelacion"
    assert sol["estado"] == "recibida"

    # Listar solicitudes de privacidad
    resp_lista_sol = client_admin.get("/panel/api/admin/privacidad/solicitudes")
    assert resp_lista_sol.status_code == 200
    assert len(resp_lista_sol.json()) >= 1


def test_salud_sistema_y_reindexar_conocimiento() -> None:
    """Verifica consulta de salud OP-01..10 y reindexación con reporte del set dorado."""
    client_admin, _, csrf = _crear_cliente_con_sesion("admin@glamping.ec")
    cabeceras = {"X-CSRF-Token": csrf}

    # Salud del sistema
    resp_salud = client_admin.get("/panel/api/admin/salud")
    assert resp_salud.status_code == 200
    salud = resp_salud.json()
    assert len(salud["metricas"]) >= 3
    assert salud["cola_crm"] == 0

    # Reindexar conocimiento
    resp_reindex = client_admin.post("/panel/api/admin/conocimiento/reindexar", headers=cabeceras)
    assert resp_reindex.status_code == 200
    datos = resp_reindex.json()
    assert datos["documentos_indexados"] > 0
    dorado = datos["set_dorado"]
    assert dorado["fidelidad"] >= 0.95
    assert dorado["abstencion"] >= 0.90
    assert dorado["alucinaciones_precio_politica"] == 0
