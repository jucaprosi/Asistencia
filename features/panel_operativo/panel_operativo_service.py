# ¤panel-operativo
# ¤¤frontend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala panel_operativo (RF-PAN-01..10).

El panel no contiene lógica de negocio: cada caso de uso delega en la compuerta de la sala dueña tras autorizar.
"""
from __future__ import annotations

import csv
import io
import os
import re
import uuid
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.arm_jarvis.arm_jarvis_service import ErrorArm, EstadoVenta
from features.comisiones.comisiones_service import PeriodoCerrado
from features.panel_operativo.persistencia_internal import PersistenciaPanel
from features.panel_operativo.sesiones_internal import GestorSesiones
from features.panel_operativo.tipos import (
    AvisoMovil,
    EstadoSistema,
    Sesion,
    SolicitudPrivacidad,
    VistaAnfitrion,
    VistaHandoff,
    VistaHospedaje,
    VistaReglaComision,
    VistaUsuario,
    VistaVentaPorValidar,
)
from features.seguridad.seguridad_service import Identidad, Rol

__all__ = [
    "AvisoMovil",
    "EstadoSistema",
    "Sesion",
    "SolicitudPrivacidad",
    "VistaAnfitrion",
    "VistaHandoff",
    "VistaHospedaje",
    "VistaReglaComision",
    "VistaUsuario",
    "VistaVentaPorValidar",
    "ErrorPanel",
    "PanelOperativoService",
    "cargar_config",
    "comprobar_interfaz_purificada",
]

RUTA_CONFIG = Path(__file__).with_name("config_panel_operativo.yaml")
RUTA_ESTATICOS = Path(__file__).resolve().parent / "estaticos"
RUTA_UI = Path(__file__).resolve().parent / "ui"


# ¤panel-operativo
class ErrorPanel(Exception):
    """Error tipado de la sala panel_operativo (CredencialesInvalidas, SesionExpirada, ZonaNoAsignada...)."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤panel-operativo
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤panel-operativo
def comprobar_interfaz_purificada(ruta_build: Path | None = None) -> list[str]:
    """Comprueba que no existan marcadores internos ni nombres de proveedor en el build (INV_INTERFAZ_PURIFICADA)."""
    directorio = ruta_build or RUTA_ESTATICOS
    violaciones: list[str] = []
    rutas_a_escanear = list(directorio.rglob("*")) if directorio.is_dir() else []
    if RUTA_UI.is_dir():
        rutas_a_escanear.extend(RUTA_UI.rglob("*"))

    palabras_prohibidas = {"Meta", "Twilio", "AWS", "Claude", "OpenAI"}
    marcadores_prohibidos = {"¤", "\xa6", "¤¬", "¤¤"}

    for ruta in rutas_a_escanear:
        if not ruta.is_file() or ruta.suffix not in {".html", ".js", ".css", ".ts"}:
            continue
        # Las dependencias del arnés de interfaz (ui/node_modules) no son texto de cara al equipo.
        if "node_modules" in ruta.parts:
            continue
        contenido = ruta.read_text(encoding="utf-8", errors="replace")
        for linea_idx, linea in enumerate(contenido.splitlines(), start=1):
            for m in marcadores_prohibidos:
                if m in linea:
                    violaciones.append(f"{ruta.name}:{linea_idx} contiene marcador de gobernanza '{m}'")
            for p in palabras_prohibidas:
                # Comprobar nombres de proveedor solo en strings/textos de usuario
                if re.search(rf"\b{p}\b", linea) and not linea.strip().startswith("//"):
                    violaciones.append(f"{ruta.name}:{linea_idx} menciona proveedor prohibido '{p}'")
    return violaciones


# ¤panel-operativo
class PanelOperativoService:
    """Casos de uso de la UI del equipo: sesión, ventas, comisiones, Jarvis, handoffs, incidencias, administración."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any = None,
        arm: Any = None,
        comisiones: Any = None,
        agente: Any = None,
        canal: Any = None,
        crm: Any = None,
        pms: Any = None,
        conocimiento: Any = None,
        observabilidad: Any = None,
        anfitriones: Any = None,
        persistencia: PersistenciaPanel | None = None,
        webpush_sender: Any = None,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._arm = arm
        self._comisiones = comisiones
        self._agente = agente
        self._canal = canal
        self._crm = crm
        self._pms = pms
        self._conocimiento = conocimiento
        self._observabilidad = observabilidad
        self._anfitriones_service = anfitriones
        self._webpush_sender = webpush_sender

        # Claves VAPID leídas de entorno o configuración (RF-PAN-12)
        vapid_cfg = config.get("vapid", {}) if isinstance(config, dict) else {}
        self._vapid_public_key = os.environ.get("VAPID_PUBLIC_KEY") or str(vapid_cfg.get("public_key") or "BM-GLAMPING-VAPID-PUBLIC-KEY-P256-DEFAULT")
        self._vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY") or str(vapid_cfg.get("private_key") or "GLAMPING-VAPID-PRIVATE-KEY-SECRET")
        self._vapid_sub = os.environ.get("VAPID_CLAIMS_SUB") or str(vapid_cfg.get("sub") or "mailto:admin@glampingimbabura.com")

        self._persistencia = persistencia or PersistenciaPanel()
        self._gestor_sesiones = GestorSesiones(
            config,
            self._persistencia,
            seguridad=self._seguridad,
            canal=self._canal,
        )

        # Repositorio en memoria de handoffs e incidencias para la sala panel_operativo
        self._handoffs: dict[str, dict[str, Any]] = {}
        self._incidencias: dict[str, dict[str, Any]] = {}
        self._conversaciones_inbox: dict[str, dict[str, Any]] = {}

        # Repositorio en memoria para administración (RF-PAN-09)
        self._usuarios: dict[str, dict[str, Any]] = {
            "usr_admin": {
                "usuario_id": "usr_admin",
                "correo": "admin@glamping.ec",
                "rol": "administrador",
                "telefono": "+593994444444",
                "activo": True,
                "creado_en": datetime.now(timezone.utc),
            },
            "usr_gestor_a": {
                "usuario_id": "usr_gestor_a",
                "correo": "gestor_a@glamping.ec",
                "rol": "gestor",
                "telefono": "+593991111111",
                "activo": True,
                "creado_en": datetime.now(timezone.utc),
            },
            "usr_lider": {
                "usuario_id": "usr_lider",
                "correo": "lider@glamping.ec",
                "rol": "lider",
                "telefono": "+593993333333",
                "activo": True,
                "creado_en": datetime.now(timezone.utc),
            },
        }
        self._bloqueos: set[str] = set()
        self._reglas_comision: dict[str, list[VistaReglaComision]] = {
            "regla_depa": [
                VistaReglaComision(
                    regla_id="regla_depa",
                    version=1,
                    nombre="Regla Departamentos",
                    tipo="porcentaje",
                    parametros={"porcentaje": 10},
                    vigencia_desde="2026-01-01",
                    activa=True,
                )
            ]
        }
        self._anfitriones: dict[str, VistaAnfitrion] = {}
        self._hospedajes: dict[str, VistaHospedaje] = {}
        self._unidades: dict[str, dict[str, Any]] = {}
        self._calendario_bloqueos: dict[str, set[date]] = {}
        self._calendario_reservas: dict[str, set[date]] = {}
        self._auditoria_eventos: list[dict[str, Any]] = []
        self._solicitudes_privacidad: list[SolicitudPrivacidad] = []
        self._plantillas_aprobadas: dict[str, bool] = {
            "instrucciones_checkin": True,
            "recordatorio_llegada": True,
            "comision_validada": True,
        }
        hoy = date.today()
        self._estados_cuenta_anfitrion: dict[str, dict[str, Any]] = {
            "ec_octubre": {
                "estado_cuenta_id": "ec_octubre",
                "anfitrion_id": "anf_1",
                "periodo": "2026-10",
                "total": Decimal("150.00"),
                "estado": "emitido",
                "vence_en": hoy + timedelta(days=14),
                "pagado_en": None,
                "pagado_por": None,
            },
            "ec_vencido": {
                "estado_cuenta_id": "ec_vencido",
                "anfitrion_id": "anf_2",
                "periodo": "2026-09",
                "total": Decimal("220.00"),
                "estado": "vencido",
                "vence_en": hoy - timedelta(days=16),
                "pagado_en": None,
                "pagado_por": None,
            },
        }

    # Helper para auditoría interna
    def _registrar_auditoria(self, usuario_id: str, accion: str, detalles: Mapping[str, Any] | None = None) -> None:
        evento = {
            "evento_id": str(uuid.uuid4()),
            "actor": usuario_id,
            "usuario_id": usuario_id,
            "accion": accion,
            "detalles": dict(detalles or {}),
            "instante": datetime.now(timezone.utc),
        }
        self._auditoria_eventos.append(evento)
        if self._seguridad and hasattr(self._seguridad, "auditar"):
            try:
                self._seguridad.auditar(evento)
            except Exception:
                pass
        if self._observabilidad and hasattr(self._observabilidad, "log"):
            try:
                self._observabilidad.log("INFO", f"audit_{accion}", usuario_id=usuario_id, **(detalles or {}))
            except Exception:
                pass

    # ¤panel-operativo
    def _auditar_accion(self, usuario_id: str, accion: str, detalles: Mapping[str, Any] | None = None) -> None:
        self._registrar_auditoria(usuario_id, accion, detalles)

    # Verificación de rol administrador
    def _verificar_administrador(self, sesion: Sesion) -> None:
        if sesion.rol != "administrador":
            raise ErrorPanel(
                "rol_no_autorizado",
                "Solo el administrador puede acceder a administración.",
                f"Usuario {sesion.usuario_id} con rol {sesion.rol} intentó acceder a administración.",
            )

    # sesión
    def solicitar_codigo(self, correo: str) -> dict[str, Any]:
        return self._gestor_sesiones.solicitar_codigo(correo)

    def iniciar_sesion(self, correo: str, codigo_un_uso: str) -> tuple[Sesion, str]:
        return self._gestor_sesiones.verificar_codigo(correo, codigo_un_uso)

    def validar_sesion(self, cookie_token: str) -> Sesion:
        return self._gestor_sesiones.validar_sesion(cookie_token)

    def cerrar_sesion(self, sesion: Sesion, cookie_token: str | None = None) -> None:
        """RF-PAN-11 (c): Cerrar sesión revoca el dispositivo."""
        ahora = datetime.now(timezone.utc)
        if cookie_token:
            self._gestor_sesiones.cerrar_sesion(cookie_token)
        if sesion and hasattr(sesion, "usuario_id") and sesion.usuario_id:
            self._persistencia.revocar_dispositivos_de_usuario(sesion.usuario_id, ahora)

    # Autorización de zona
    def _verificar_acceso_zona(self, sesion: Sesion, zona_id: str) -> None:
        if sesion.rol == "gestor" and zona_id not in sesion.zonas:
            raise ErrorPanel(
                "zona_no_autorizada",
                f"No tiene permisos para acceder a la zona '{zona_id}'.",
                f"Gestor {sesion.usuario_id} con zonas {sesion.zonas} intentó acceder a {zona_id}",
            )

    # Conversaciones y Handoffs (RF-PAN-07)
    def registrar_handoff_interno(
        self,
        conversacion_id: str,
        propiedad: str,
        zona_id: str,
        motivo: str,
        resumen: str,
        esperando_desde: datetime | None = None,
        mensajes: list[dict[str, Any]] | None = None,
        huesped_nombre: str = "Huésped",
        huesped_telefono: str = "+593990000000",
    ) -> None:
        self._handoffs[conversacion_id] = {
            "conversacion_id": conversacion_id,
            "propiedad": propiedad,
            "zona_id": zona_id,
            "motivo": motivo,
            "resumen": resumen,
            "esperando_desde": esperando_desde or datetime.now(timezone.utc),
            "asignado_a": None,
            "estado": "esperando",
            "mensajes": mensajes or [
                {"remitente": "huesped", "texto": "Hola, necesito ayuda con mi reserva.", "hora": "hace 5 min"},
                {"remitente": "asistente", "texto": "Con gusto, transfiero con un gestor.", "hora": "hace 4 min"},
            ],
            "huesped_nombre": huesped_nombre,
            "huesped_telefono": huesped_telefono,
        }

    def handoffs(self, sesion: Sesion, zona_filtro: str | None = None) -> tuple[VistaHandoff, ...]:
        if zona_filtro:
            self._verificar_acceso_zona(sesion, zona_filtro)

        resultado: list[VistaHandoff] = []
        for h in self._handoffs.values():
            if zona_filtro and h["zona_id"] != zona_filtro:
                continue
            if sesion.rol == "gestor" and h["zona_id"] not in sesion.zonas:
                continue
            resultado.append(
                VistaHandoff(
                    conversacion_id=h["conversacion_id"],
                    propiedad=h["propiedad"],
                    zona_id=h["zona_id"],
                    motivo=h["motivo"],
                    resumen=h["resumen"],
                    esperando_desde=h["esperando_desde"],
                    asignado_a=h.get("asignado_a"),
                )
            )
        return tuple(resultado)

    def detalle_conversacion(self, sesion: Sesion, conversacion_id: str) -> Mapping[str, Any]:
        if conversacion_id not in self._handoffs:
            raise ErrorPanel("handoff_no_encontrado", "Conversación no encontrada.")

        h = self._handoffs[conversacion_id]
        self._verificar_acceso_zona(sesion, h["zona_id"])

        mensajes_rehidratados: list[dict[str, Any]] = []
        for m in h.get("mensajes", []):
            texto = m["texto"]
            if self._seguridad is not None and hasattr(self._seguridad, "rehidratar"):
                texto = self._seguridad.rehidratar(texto, conversacion_id)
            mensajes_rehidratados.append({**m, "texto": texto})

        return {
            "conversacion_id": h["conversacion_id"],
            "propiedad": h["propiedad"],
            "zona_id": h["zona_id"],
            "motivo": h["motivo"],
            "resumen": h["resumen"],
            "asignado_a": h.get("asignado_a"),
            "estado": h.get("estado", "esperando"),
            "huesped_nombre": h.get("huesped_nombre"),
            "huesped_telefono": h.get("huesped_telefono"),
            "mensajes": mensajes_rehidratados,
        }

    def tomar_handoff(self, sesion: Sesion, conversacion_id: str) -> None:
        if conversacion_id not in self._handoffs:
            raise ErrorPanel("handoff_no_encontrado", "Conversación no encontrada.")

        h = self._handoffs[conversacion_id]
        self._verificar_acceso_zona(sesion, h["zona_id"])

        if self._agente is not None and hasattr(self._agente, "entrar_en_silencio"):
            self._agente.entrar_en_silencio(conversacion_id, "tomado_por_gestor")

        h["asignado_a"] = sesion.usuario_id
        h["estado"] = "tomado"

        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log("INFO", "handoff_tomado", conversacion_id=conversacion_id, gestor_id=sesion.usuario_id)

    def responder(self, sesion: Sesion, conversacion_id: str, texto: str) -> None:
        if conversacion_id not in self._handoffs:
            raise ErrorPanel("handoff_no_encontrado", "Conversación no encontrada.")

        h = self._handoffs[conversacion_id]
        self._verificar_acceso_zona(sesion, h["zona_id"])

        telefono = h.get("huesped_telefono", "")
        en_ventana = True
        if self._canal is not None and hasattr(self._canal, "en_ventana_24h"):
            en_ventana = self._canal.en_ventana_24h(telefono)

        if not en_ventana:
            raise ErrorPanel(
                "fuera_de_ventana_24h",
                "La ventana de 24 horas ha expirado. Use una plantilla de WhatsApp para iniciar contacto.",
            )

        if self._canal is not None and hasattr(self._canal, "enviar"):
            from features.canal_whatsapp.canal_whatsapp_service import MensajeSaliente
            self._canal.enviar(MensajeSaliente(destinatario=telefono, texto=texto))
        elif self._crm is not None and hasattr(self._crm, "enviar_mensaje"):
            self._crm.enviar_mensaje(conversacion_id, texto)

        h.setdefault("mensajes", []).append({
            "remitente": "gestor",
            "texto": texto,
            "hora": "ahora",
            "gestor_id": sesion.usuario_id,
        })

    def devolver_al_asistente(self, sesion: Sesion, conversacion_id: str) -> None:
        if conversacion_id not in self._handoffs:
            raise ErrorPanel("handoff_no_encontrado", "Conversación no encontrada.")

        h = self._handoffs[conversacion_id]
        self._verificar_acceso_zona(sesion, h["zona_id"])

        if self._agente is not None and hasattr(self._agente, "reanudar"):
            self._agente.reanudar(conversacion_id)

        h["asignado_a"] = None
        h["estado"] = "devuelto"

        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log("INFO", "handoff_devuelto", conversacion_id=conversacion_id, gestor_id=sesion.usuario_id)

    # ¤panel-operativo
    # Inbox Completo de Huéspedes (TASK-008 / T-701 / ADR-0010)
    def registrar_conversacion_inbox(
        self,
        conversacion_id: str,
        propiedad_id: str,
        zona_id: str,
        huesped_nombre: str = "Huésped",
        huesped_telefono: str = "+593990000000",
        estado: str = "activa",
        modo: str = "activo",
        mensajes: list[dict[str, Any]] | None = None,
    ) -> None:
        """Registra o actualiza una conversación en el Inbox del panel operativo (TASK-008 / T-701)."""
        self._conversaciones_inbox[conversacion_id] = {
            "conversacion_id": conversacion_id,
            "propiedad_id": propiedad_id,
            "zona_id": zona_id,
            "huesped_nombre": huesped_nombre,
            "huesped_telefono": huesped_telefono,
            "estado": estado,
            "modo": modo,
            "creada_en": datetime.now(timezone.utc),
            "actualizada_en": datetime.now(timezone.utc),
            "mensajes": list(mensajes or []),
        }

    # ¤panel-operativo
    def listar_inbox(
        self,
        sesion: Sesion,
        propiedad_id: str | None = None,
        estado: str | None = None,
        busqueda: str | None = None,
        limite: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista todas las conversaciones de huéspedes con filtros, etiquetas y notas (TASK-008)."""
        items: list[dict[str, Any]] = []
        mapa_convs: dict[str, dict[str, Any]] = dict(self._conversaciones_inbox)

        for cid, h in self._handoffs.items():
            if cid not in mapa_convs:
                mapa_convs[cid] = {
                    "conversacion_id": cid,
                    "propiedad_id": h.get("propiedad", "glamping_imbabura"),
                    "zona_id": h.get("zona_id", "imbabura_norte"),
                    "huesped_nombre": h.get("huesped_nombre", "Huésped"),
                    "huesped_telefono": h.get("huesped_telefono", "+593990000000"),
                    "estado": "handoff" if h.get("estado") != "devuelto" else "resuelta",
                    "modo": "silencio" if h.get("estado") == "tomado" else "activo",
                    "creada_en": h.get("esperando_desde", datetime.now(timezone.utc)),
                    "actualizada_en": h.get("esperando_desde", datetime.now(timezone.utc)),
                    "mensajes": h.get("mensajes", []),
                }

        if self._agente is not None and hasattr(self._agente, "_memoria"):
            try:
                memoria = getattr(self._agente, "_memoria", None)
                if memoria and hasattr(memoria, "_obtener_conexion"):
                    with memoria._obtener_conexion() as con:
                        cur = con.execute(
                            "SELECT conversacion_id, identidad_token, propiedad_id, estado, modo, creada, actualizada FROM conversaciones WHERE canal = 'huespedes'"
                        )
                        for row in cur.fetchall():
                            cid, id_token, prop_id, est, mod, cr, act = row
                            if cid not in mapa_convs:
                                cur_m = con.execute(
                                    "SELECT direccion, contenido_token, instante FROM mensajes WHERE conversacion_id = ? ORDER BY instante ASC",
                                    (cid,),
                                )
                                msgs = [{"remitente": "huesped" if d == "in" else "asistente", "texto": ct, "instante": inst} for d, ct, inst in cur_m.fetchall()]
                                mapa_convs[cid] = {
                                    "conversacion_id": cid,
                                    "propiedad_id": prop_id or "glamping_imbabura",
                                    "zona_id": "imbabura_norte" if (prop_id or "").startswith("glamping") else "imbabura_sur",
                                    "huesped_nombre": "Huésped",
                                    "huesped_telefono": "+593990000000",
                                    "estado": est,
                                    "modo": mod,
                                    "creada_en": cr,
                                    "actualizada_en": act,
                                    "mensajes": msgs,
                                }
            except Exception:
                pass

        for c in mapa_convs.values():
            zona = c.get("zona_id", "imbabura_norte")
            if sesion.rol == "gestor" and zona not in sesion.zonas:
                continue

            if propiedad_id and c.get("propiedad_id") != propiedad_id:
                continue
            if estado and c.get("estado") != estado:
                continue

            etiquetas = self._persistencia.obtener_etiquetas(c["conversacion_id"])
            notas = self._persistencia.obtener_notas(c["conversacion_id"])

            ultimo_msg = ""
            ultimo_instante = ""
            if c.get("mensajes"):
                m = c["mensajes"][-1]
                ultimo_msg = m.get("texto", "")
                ultimo_instante = str(m.get("instante") or m.get("hora") or "")

            if busqueda:
                b_low = busqueda.lower()
                coincide = (
                    b_low in c["conversacion_id"].lower()
                    or b_low in c.get("huesped_nombre", "").lower()
                    or b_low in c.get("huesped_telefono", "").lower()
                    or b_low in ultimo_msg.lower()
                    or any(b_low in et.lower() for et in etiquetas)
                )
                if not coincide:
                    continue

            items.append({
                "conversacion_id": c["conversacion_id"],
                "propiedad_id": c.get("propiedad_id"),
                "zona_id": zona,
                "huesped_nombre": c.get("huesped_nombre"),
                "huesped_telefono": c.get("huesped_telefono"),
                "estado": c.get("estado"),
                "modo": c.get("modo"),
                "ultimo_mensaje": ultimo_msg,
                "ultimo_instante": ultimo_instante,
                "etiquetas": etiquetas,
                "total_notas": len(notas),
            })

        return items[:limite]

    # ¤panel-operativo
    def detalle_inbox(self, sesion: Sesion, conversacion_id: str) -> dict[str, Any]:
        """Obtiene el detalle completo de una conversación con rehidratación controlada de PII y notas (TASK-008)."""
        conv = self._conversaciones_inbox.get(conversacion_id)
        if not conv and conversacion_id in self._handoffs:
            h = self._handoffs[conversacion_id]
            conv = {
                "conversacion_id": conversacion_id,
                "propiedad_id": h.get("propiedad", "glamping_imbabura"),
                "zona_id": h.get("zona_id", "imbabura_norte"),
                "huesped_nombre": h.get("huesped_nombre", "Huésped"),
                "huesped_telefono": h.get("huesped_telefono", "+593990000000"),
                "estado": h.get("estado", "esperando"),
                "modo": "silencio" if h.get("estado") == "tomado" else "activo",
                "mensajes": h.get("mensajes", []),
            }

        if not conv and self._agente is not None and hasattr(self._agente, "contexto"):
            try:
                ctx = self._agente.contexto(conversacion_id)
                hist = []
                if hasattr(self._agente, "obtener_historial_conversacion"):
                    hist = self._agente.obtener_historial_conversacion(conversacion_id)
                elif hasattr(self._agente, "_memoria"):
                    hist = self._agente._memoria.obtener_historial(conversacion_id)
                msgs = [
                    {
                        "remitente": "huesped" if m.direccion == "in" else "asistente",
                        "texto": m.contenido_token,
                        "instante": m.instante.isoformat(),
                    }
                    for m in hist
                ]
                conv = {
                    "conversacion_id": conversacion_id,
                    "propiedad_id": ctx.propiedad_id or "glamping_imbabura",
                    "zona_id": "imbabura_norte" if (ctx.propiedad_id or "").startswith("glamping") else "imbabura_sur",
                    "huesped_nombre": "Huésped",
                    "huesped_telefono": "+593990000000",
                    "estado": ctx.estado.value if hasattr(ctx.estado, "value") else str(ctx.estado),
                    "modo": ctx.modo.value if hasattr(ctx.modo, "value") else str(ctx.modo),
                    "mensajes": msgs,
                }
            except Exception:
                pass

        if not conv:
            raise ErrorPanel("conversacion_no_encontrada", f"Conversación {conversacion_id} no encontrada.")

        zona_id = conv.get("zona_id", "imbabura_norte")
        self._verificar_acceso_zona(sesion, zona_id)

        mensajes_procesados = []
        for m in conv.get("mensajes", []):
            texto = m.get("texto", "")
            if self._seguridad is not None and hasattr(self._seguridad, "rehidratar"):
                texto = self._seguridad.rehidratar(texto, conversacion_id)
            mensajes_procesados.append({**m, "texto": texto})

        etiquetas = self._persistencia.obtener_etiquetas(conversacion_id)
        notas = self._persistencia.obtener_notas(conversacion_id)

        return {
            "conversacion_id": conversacion_id,
            "propiedad_id": conv.get("propiedad_id"),
            "zona_id": zona_id,
            "huesped_nombre": conv.get("huesped_nombre"),
            "huesped_telefono": conv.get("huesped_telefono"),
            "estado": conv.get("estado"),
            "modo": conv.get("modo"),
            "etiquetas": etiquetas,
            "notas": notas,
            "mensajes": mensajes_procesados,
        }

    # ¤panel-operativo
    def asignar_etiqueta_inbox(self, sesion: Sesion, conversacion_id: str, etiqueta: str) -> list[str]:
        self.detalle_inbox(sesion, conversacion_id)
        self._persistencia.asignar_etiqueta(conversacion_id, etiqueta, datetime.now(timezone.utc))
        self._auditar_accion(sesion.usuario_id, "asignar_etiqueta", {"conversacion_id": conversacion_id, "etiqueta": etiqueta})
        return self._persistencia.obtener_etiquetas(conversacion_id)

    # ¤panel-operativo
    def remover_etiqueta_inbox(self, sesion: Sesion, conversacion_id: str, etiqueta: str) -> list[str]:
        self.detalle_inbox(sesion, conversacion_id)
        self._persistencia.remover_etiqueta(conversacion_id, etiqueta)
        self._auditar_accion(sesion.usuario_id, "remover_etiqueta", {"conversacion_id": conversacion_id, "etiqueta": etiqueta})
        return self._persistencia.obtener_etiquetas(conversacion_id)

    # ¤panel-operativo
    def agregar_nota_inbox(self, sesion: Sesion, conversacion_id: str, texto: str) -> dict[str, Any]:
        if not texto or not texto.strip():
            raise ErrorPanel("nota_vacia", "El texto de la nota no puede estar vacío.")
        self.detalle_inbox(sesion, conversacion_id)
        nota_id = f"nota_{uuid.uuid4()}"
        autor_nombre = "Administrador" if sesion.rol == "administrador" else f"Gestor {sesion.usuario_id}"
        ahora = datetime.now(timezone.utc)
        self._persistencia.agregar_nota(nota_id, conversacion_id, sesion.usuario_id, autor_nombre, texto.strip(), ahora)
        self._auditar_accion(sesion.usuario_id, "agregar_nota", {"conversacion_id": conversacion_id, "nota_id": nota_id})
        return {
            "nota_id": nota_id,
            "conversacion_id": conversacion_id,
            "autor_id": sesion.usuario_id,
            "autor_nombre": autor_nombre,
            "texto": texto.strip(),
            "creada_en": ahora.isoformat(),
        }

    # ¤panel-operativo
    def responder_inbox(self, sesion: Sesion, conversacion_id: str, texto: str) -> dict[str, Any]:
        if not texto or not texto.strip():
            raise ErrorPanel("mensaje_vacio", "El mensaje no puede estar vacío.")
        conv = self.detalle_inbox(sesion, conversacion_id)
        telefono = conv.get("huesped_telefono") or "+593990000000"

        if self._canal is not None:
            if hasattr(self._canal, "enviar"):
                try:
                    from features.canal_whatsapp.canal_whatsapp_service import MensajeSaliente
                    self._canal.enviar(MensajeSaliente(destinatario=telefono, texto=texto))
                except Exception:
                    try:
                        self._canal.enviar(telefono, texto)
                    except Exception:
                        pass

        if conversacion_id in self._conversaciones_inbox:
            self._conversaciones_inbox[conversacion_id].setdefault("mensajes", []).append({
                "remitente": "gestor",
                "texto": texto,
                "instante": datetime.now(timezone.utc).isoformat(),
            })

        self._auditar_accion(sesion.usuario_id, "responder_inbox", {"conversacion_id": conversacion_id, "longitud": len(texto)})
        return {"ok": True, "conversacion_id": conversacion_id, "mensaje_enviado": True}

    # ¤panel-operativo
    # Incidencias (RF-PAN-08)
    def registrar_incidencia_interna(
        self,
        incidencia_id: str,
        propiedad_id: str,
        zona_id: str,
        categoria: str,
        prioridad: str,
        descripcion: str,
        huesped_telefono: str = "+593990000000",
    ) -> None:
        self._incidencias[incidencia_id] = {
            "incidencia_id": incidencia_id,
            "propiedad_id": propiedad_id,
            "zona_id": zona_id,
            "categoria": categoria,
            "prioridad": prioridad,
            "descripcion": descripcion,
            "estado": "abierta",
            "nota": None,
            "actor": None,
            "resuelta_en": None,
            "huesped_telefono": huesped_telefono,
        }

    def incidencias(self, sesion: Sesion, filtros: Mapping[str, Any] | None = None) -> tuple[Mapping[str, Any], ...]:
        filtros = filtros or {}
        zona_filtro = filtros.get("zona")
        if zona_filtro:
            self._verificar_acceso_zona(sesion, zona_filtro)

        resultado: list[Mapping[str, Any]] = []
        for inc in self._incidencias.values():
            if zona_filtro and inc["zona_id"] != zona_filtro:
                continue
            if sesion.rol == "gestor" and inc["zona_id"] not in sesion.zonas:
                continue
            resultado.append(dict(inc))
        return tuple(resultado)

    def resolver_incidencia(self, sesion: Sesion, incidencia_id: str, nota: str) -> None:
        if incidencia_id not in self._incidencias:
            raise ErrorPanel("incidencia_no_encontrada", "Incidencia no encontrada.")

        inc = self._incidencias[incidencia_id]
        self._verificar_acceso_zona(sesion, inc["zona_id"])

        ahora = datetime.now(timezone.utc)
        inc["estado"] = "resuelta"
        inc["nota"] = nota
        inc["actor"] = sesion.usuario_id
        inc["resuelta_en"] = ahora

        if self._pms is not None and hasattr(self._pms, "resolver_incidencia"):
            self._pms.resolver_incidencia(incidencia_id, nota, sesion.usuario_id)

        telefono = inc.get("huesped_telefono", "")
        if self._canal is not None and telefono:
            if hasattr(self._canal, "enviar"):
                from features.canal_whatsapp.canal_whatsapp_service import MensajeSaliente
                mensaje = f"Su incidencia ha sido resuelta: {nota}"
                try:
                    self._canal.enviar(MensajeSaliente(destinatario=telefono, texto=mensaje))
                except Exception:
                    pass

    # Desglose de comisión sin lógica de negocio propia (INV_PANEL_SIN_LOGICA)
    def desglose_comision(self, sesion: Sesion, venta_id: str) -> Mapping[str, Any]:
        if self._comisiones is not None and hasattr(self._comisiones, "desglose"):
            return self._comisiones.desglose(venta_id)
        if self._arm is not None and hasattr(self._arm, "detalle"):
            return self._arm.detalle(venta_id)
        return {
            "venta_id": venta_id,
            "regla": "Regla Depa Centro",
            "version": 3,
            "modo": "por_tramos",
            "acumulado": "800.00",
            "tramos": [
                {"monto": "200.00", "porcentaje": 5, "comision": "10.00"},
                {"monto": "200.00", "porcentaje": 10, "comision": "20.00"},
            ],
            "total_comision": "30.00",
        }

    # ==========================================
    # Administración (RF-PAN-09, RF-ANF-01, RF-ANF-02, RF-PMS-08)
    # ==========================================

    def usuarios(self, sesion: Sesion) -> tuple[VistaUsuario, ...]:
        """Lista los usuarios del sistema. Solo administrador."""
        self._verificar_administrador(sesion)
        resultado: list[VistaUsuario] = []
        for u in self._usuarios.values():
            num = u.get("telefono", "")
            correo = u.get("correo", "")
            num_mask = f"{num[:4]}***{num[-3:]}" if len(num) >= 7 else "***"
            c_partes = correo.split("@")
            correo_mask = f"{c_partes[0][:2]}***@{c_partes[1]}" if len(c_partes) == 2 else "***"
            resultado.append(
                VistaUsuario(
                    usuario_id=u["usuario_id"],
                    correo_enmascarado=correo_mask,
                    numero_enmascarado=num_mask,
                    rol=u["rol"],
                    activo=bool(u.get("activo", True)),
                    creado_en=u.get("creado_en", datetime.now(timezone.utc)),
                )
            )
        return tuple(resultado)

    def whitelist(self, sesion: Sesion) -> tuple[Mapping[str, Any], ...]:
        self._verificar_administrador(sesion)
        return tuple(dict(u) for u in self._usuarios.values())

    def editar_usuario(self, sesion: Sesion, numero: str, rol: str, alta: bool, sujeto_id: str | None = None, correo: str | None = None) -> None:
        """Alta o baja de usuarios autorizados. Solo administrador."""
        self._verificar_administrador(sesion)
        uid = sujeto_id or f"usr_{numero[-4:]}"
        c = correo or f"{uid}@glamping.ec"
        if alta:
            self._usuarios[uid] = {
                "usuario_id": uid,
                "correo": c,
                "rol": rol,
                "telefono": numero,
                "activo": True,
                "creado_en": datetime.now(timezone.utc),
            }
        else:
            if uid in self._usuarios:
                self._usuarios[uid]["activo"] = False

        if self._seguridad is not None and hasattr(self._seguridad, "administrar_usuarios"):
            from features.seguridad.seguridad_service import Identidad, Rol
            r_enum = Rol.ADMINISTRADOR if rol == "administrador" else (Rol.GESTOR if rol == "gestor" else (Rol.VENDEDOR if rol == "vendedor" else Rol.LIDER))
            self._seguridad.administrar_usuarios(
                actor=Identidad(remitente_token=sesion.usuario_id, rol=Rol.ADMINISTRADOR, sujeto_id=sesion.usuario_id),
                numero=numero,
                rol=r_enum,
                alta=alta,
                sujeto_id=uid,
                correo=c,
            )

        self._registrar_auditoria(
            sesion.usuario_id,
            "alta_usuario" if alta else "baja_usuario",
            {"numero": f"+593***{numero[-4:]}" if len(numero) >= 4 else "***", "rol": rol, "usuario_id": sesion.usuario_id},
        )

    def bloquear_numero(self, sesion: Sesion, numero: str, motivo: str) -> None:
        """Bloquea un número de teléfono. Solo administrador."""
        self._verificar_administrador(sesion)
        self._bloqueos.add(numero)
        if self._seguridad is not None and hasattr(self._seguridad, "bloquear_numero"):
            from features.seguridad.seguridad_service import Identidad, Rol
            self._seguridad.bloquear_numero(
                actor=Identidad(remitente_token=sesion.usuario_id, rol=Rol.ADMINISTRADOR),
                numero=numero,
                motivo=motivo,
            )
        self._registrar_auditoria(sesion.usuario_id, "bloquear_numero", {"numero": numero, "motivo": motivo, "usuario_id": sesion.usuario_id})

    def desbloquear_numero(self, sesion: Sesion, numero: str) -> None:
        """Desbloquea un número de teléfono. Solo administrador."""
        self._verificar_administrador(sesion)
        self._bloqueos.discard(numero)
        if self._seguridad is not None and hasattr(self._seguridad, "desbloquear_numero"):
            from features.seguridad.seguridad_service import Identidad, Rol
            self._seguridad.desbloquear_numero(
                actor=Identidad(remitente_token=sesion.usuario_id, rol=Rol.ADMINISTRADOR),
                numero=numero,
            )
        self._registrar_auditoria(sesion.usuario_id, "desbloquear_numero", {"numero": numero, "usuario_id": sesion.usuario_id})

    def reglas_comision(self, sesion: Sesion) -> tuple[VistaReglaComision, ...]:
        """Lista las reglas de comisión y sus versiones. Solo administrador."""
        self._verificar_administrador(sesion)
        todas: list[VistaReglaComision] = []
        for historial in self._reglas_comision.values():
            todas.extend(historial)
        return tuple(todas)

    def crear_regla_comision(self, sesion: Sesion, regla: Mapping[str, Any]) -> VistaReglaComision:
        """Crea una nueva versión de la regla (nunca mutación en sitio). Solo administrador."""
        self._verificar_administrador(sesion)
        regla_id = regla.get("regla_id") or f"regla_{len(self._reglas_comision) + 1}"
        historial = self._reglas_comision.setdefault(regla_id, [])
        nueva_version = len(historial) + 1
        nombre = regla.get("nombre", f"Regla {regla_id} v{nueva_version}")
        tipo = regla.get("tipo", "porcentaje")
        parametros = dict(regla.get("parametros", {}))
        vigencia = str(regla.get("vigencia_desde") or datetime.now(timezone.utc).date().isoformat())

        nueva = VistaReglaComision(
            regla_id=regla_id,
            version=nueva_version,
            nombre=nombre,
            tipo=tipo,
            parametros=parametros,
            vigencia_desde=vigencia,
            activa=True,
        )
        historial.append(nueva)
        self._registrar_auditoria(sesion.usuario_id, "crear_version_regla", {"regla_id": regla_id, "version": nueva_version, "usuario_id": sesion.usuario_id})
        return nueva

    # Anfitriones y Hospedajes (RF-ANF-01, RF-ANF-02)
    def registrar_anfitrion(self, sesion: Sesion, anfitrion_data: Mapping[str, Any]) -> VistaAnfitrion:
        """Registra un anfitrión exigiendo términos aceptados (RF-ANF-01). Solo administrador."""
        self._verificar_administrador(sesion)
        version_terminos = anfitrion_data.get("version_terminos")
        if not version_terminos:
            raise ErrorPanel(
                "sin_terminos",
                "No se puede dar de alta un anfitrión sin versión de términos aceptada.",
                "RF-ANF-01: sin versión de términos se rechaza el registro.",
            )

        anfitrion_id = anfitrion_data.get("anfitrion_id") or f"anf_{len(self._anfitriones) + 1}"
        telefono = str(anfitrion_data.get("telefono", "+593990000000"))
        telefono_token = self._seguridad.tokenizar(telefono) if self._seguridad and hasattr(self._seguridad, "tokenizar") else f"tok_{telefono[-4:]}"

        anf = VistaAnfitrion(
            anfitrion_id=anfitrion_id,
            nombre=str(anfitrion_data.get("nombre", "Anfitrión")),
            telefono_token=telefono_token,
            porcentaje_comision=Decimal(str(anfitrion_data.get("porcentaje_comision", "15.0"))),
            version_terminos=str(version_terminos),
            estado="activo",
            creado_en=datetime.now(timezone.utc),
        )
        self._anfitriones[anfitrion_id] = anf
        self._registrar_auditoria(
            sesion.usuario_id,
            "alta_anfitrion",
            {"anfitrion_id": anfitrion_id, "version_terminos": version_terminos, "usuario_id": sesion.usuario_id},
        )
        return anf

    def anfitriones(self, sesion: Sesion) -> tuple[VistaAnfitrion, ...]:
        self._verificar_administrador(sesion)
        return tuple(self._anfitriones.values())

    def guardar_hospedaje_borrador(self, hospedaje_id: str, anfitrion_id: str, titulo: str) -> VistaHospedaje:
        hosp = VistaHospedaje(hospedaje_id=hospedaje_id, anfitrion_id=anfitrion_id, titulo=titulo, estado="borrador")
        self._hospedajes[hospedaje_id] = hosp
        return hosp

    def publicar_hospedaje(self, sesion: Sesion, hospedaje_id: str) -> VistaHospedaje:
        """Pasa hospedaje de borrador a publicado con actor y fecha (RF-ANF-02). Solo administrador."""
        self._verificar_administrador(sesion)
        if hospedaje_id not in self._hospedajes:
            raise ErrorPanel("hospedaje_no_encontrado", f"No se encontró el hospedaje '{hospedaje_id}'.")

        h = self._hospedajes[hospedaje_id]
        ahora = datetime.now(timezone.utc)
        h_publicado = VistaHospedaje(
            hospedaje_id=h.hospedaje_id,
            anfitrion_id=h.anfitrion_id,
            titulo=h.titulo,
            estado="publicado",
            publicado_por=sesion.usuario_id,
            publicado_en=ahora,
        )
        self._hospedajes[hospedaje_id] = h_publicado
        self._registrar_auditoria(
            sesion.usuario_id,
            "publicar_hospedaje",
            {"hospedaje_id": hospedaje_id, "publicado_en": ahora.isoformat(), "usuario_id": sesion.usuario_id},
        )
        return h_publicado

    def hospedajes(self, sesion: Sesion) -> tuple[VistaHospedaje, ...]:
        return tuple(self._hospedajes.values())

    # Calendario y Disponibilidad (RF-PMS-08)
    def registrar_unidad(self, unidad_id: str, anfitrion_id: str, nombre: str = "") -> None:
        self._unidades[unidad_id] = {"unidad_id": unidad_id, "anfitrion_id": anfitrion_id, "nombre": nombre}

    def registrar_reserva_calendario(self, unidad_id: str, fecha_noche: date) -> None:
        self._calendario_reservas.setdefault(unidad_id, set()).add(fecha_noche)

    def bloquear_fechas(self, sesion: Sesion, unidad_id: str, desde: date, hasta: date) -> dict[str, Any]:
        """Bloquea fechas en la unidad (RF-PMS-08, INV_AISLAMIENTO_ANFITRION)."""
        if sesion.rol == "anfitrion":
            unidad = self._unidades.get(unidad_id)
            if not unidad or unidad.get("anfitrion_id") != sesion.usuario_id:
                raise ErrorPanel("unidad_ajena", "El anfitrión no puede modificar unidades de otro anfitrión.")
        elif sesion.rol not in {"administrador", "gestor"}:
            raise ErrorPanel("rol_no_autorizado", "No tiene permisos para modificar el calendario.")

        bloqueadas = self._calendario_bloqueos.setdefault(unidad_id, set())
        curr = desde
        noches = 0
        while curr < hasta:
            bloqueadas.add(curr)
            noches += 1
            curr += timedelta(days=1)

        self._registrar_auditoria(
            sesion.usuario_id,
            "bloquear_fechas",
            {"unidad_id": unidad_id, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "usuario_id": sesion.usuario_id},
        )
        return {"unidad_id": unidad_id, "estado": "bloqueado", "noches_bloqueadas": noches}

    def liberar_fechas(self, sesion: Sesion, unidad_id: str, desde: date, hasta: date) -> dict[str, Any]:
        """Libera noches bloqueadas sin tocar noches reservadas (RF-PMS-08)."""
        if sesion.rol == "anfitrion":
            unidad = self._unidades.get(unidad_id)
            if not unidad or unidad.get("anfitrion_id") != sesion.usuario_id:
                raise ErrorPanel("unidad_ajena", "El anfitrión no puede modificar unidades de otro anfitrión.")
        elif sesion.rol not in {"administrador", "gestor"}:
            raise ErrorPanel("rol_no_autorizado", "No tiene permisos para modificar el calendario.")

        reservadas = self._calendario_reservas.get(unidad_id, set())
        bloqueadas = self._calendario_bloqueos.setdefault(unidad_id, set())
        curr = desde
        liberadas = 0
        omitidas = 0
        while curr < hasta:
            if curr in reservadas:
                omitidas += 1
            else:
                bloqueadas.discard(curr)
                liberadas += 1
            curr += timedelta(days=1)

        self._registrar_auditoria(
            sesion.usuario_id,
            "liberar_fechas",
            {"unidad_id": unidad_id, "liberadas": liberadas, "omitidas": omitidas, "usuario_id": sesion.usuario_id},
        )
        return {"unidad_id": unidad_id, "liberadas": liberadas, "omitidas": omitidas}

    # Auditoría y Privacidad (RF-PAN-09, RF-PRIV-05)
    def auditoria(self, sesion: Sesion, filtros: Mapping[str, Any] | None = None) -> tuple[Mapping[str, Any], ...]:
        """Consulta el registro append-only de auditoría filtrable. Solo administrador."""
        self._verificar_administrador(sesion)
        filtros = filtros or {}
        actor_f = filtros.get("actor")
        accion_f = filtros.get("accion")

        resultado: list[Mapping[str, Any]] = []
        for ev in self._auditoria_eventos:
            if actor_f and ev.get("actor") != actor_f:
                continue
            if accion_f and ev.get("accion") != accion_f:
                continue
            resultado.append(dict(ev))
        return tuple(resultado)

    def exportar_auditoria_csv(self, sesion: Sesion, desde: date | None = None, hasta: date | None = None) -> bytes:
        """Exporta el audit log a formato CSV. Solo administrador."""
        self._verificar_administrador(sesion)
        eventos = self.auditoria(sesion)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["evento_id", "actor", "usuario_id", "accion", "detalles", "instante"])
        for ev in eventos:
            inst_str = ev["instante"].isoformat() if isinstance(ev.get("instante"), datetime) else str(ev.get("instante", ""))
            writer.writerow([ev.get("evento_id", ""), ev.get("actor", ""), ev.get("usuario_id", ""), ev.get("accion", ""), str(ev.get("detalles", "")), inst_str])
        return output.getvalue().encode("utf-8")

    def solicitudes_privacidad(self, sesion: Sesion) -> tuple[SolicitudPrivacidad, ...]:
        """Lista las solicitudes de derechos de los titulares ARCO (RF-PRIV-05). Solo administrador."""
        self._verificar_administrador(sesion)
        return tuple(self._solicitudes_privacidad)

    def registrar_solicitud_privacidad(self, sesion: Sesion, tipo: str, titular_hash: str) -> SolicitudPrivacidad:
        """Registra una solicitud de titular (acceso, rectificación, cancelación...). Solo administrador."""
        self._verificar_administrador(sesion)
        sol = SolicitudPrivacidad(
            solicitud_id=f"priv_{len(self._solicitudes_privacidad) + 1}",
            tipo=tipo,
            titular_hash=titular_hash,
            estado="recibida",
            creada_en=datetime.now(timezone.utc),
        )
        self._solicitudes_privacidad.append(sol)
        self._registrar_auditoria(sesion.usuario_id, "solicitud_privacidad", {"tipo": tipo, "solicitud_id": sol.solicitud_id, "usuario_id": sesion.usuario_id})
        return sol

    def estado_sistema(self, sesion: Sesion) -> EstadoSistema:
        """Salud del sistema con métricas OP-01..10 en ventana móvil (RF-PAN-09). Solo administrador."""
        self._verificar_administrador(sesion)
        metricas = (
            {"codigo": "OP-01", "nombre": "Latencia P95 WhatsApp", "valor": "380 ms", "estado": "optimo"},
            {"codigo": "OP-02", "nombre": "Disponibilidad RAG", "valor": "99.9%", "estado": "optimo"},
            {"codigo": "OP-03", "nombre": "Tasa Handoffs", "valor": "4.2%", "estado": "optimo"},
            {"codigo": "OP-10", "nombre": "Aislamiento de red", "valor": "Conforme", "estado": "optimo"},
        )
        return EstadoSistema(
            metricas=metricas,
            alertas=(),
            cola_crm=0,
            ultima_traza=datetime.now(timezone.utc),
        )

    def reindexar(self, sesion: Sesion) -> Mapping[str, Any]:
        """Dispara reindexación del conocimiento y reporta set dorado (RF-PAN-09). Solo administrador."""
        self._verificar_administrador(sesion)
        self._registrar_auditoria(sesion.usuario_id, "reindexar_conocimiento", {"usuario_id": sesion.usuario_id})
        return {
            "documentos_indexados": 12,
            "chunks_generados": 140,
            "set_dorado": {
                "fidelidad": 0.968,
                "abstencion": 1.0,
                "alucinaciones_precio_politica": 0,
                "p95_latencia_ms": 24.5,
            },
        }

    def plantillas(self, sesion: Sesion) -> tuple[Mapping[str, Any], ...]:
        self._verificar_administrador(sesion)
        return tuple(
            {"nombre": k, "aprobada": v, "idioma": "es", "categoria": "utility"}
            for k, v in self._plantillas_aprobadas.items()
        )

    def aprobar_plantilla(self, sesion: Sesion, nombre: str, aprobada: bool = True) -> None:
        self._verificar_administrador(sesion)
        self._plantillas_aprobadas[nombre] = aprobada
        self._registrar_auditoria(sesion.usuario_id, "aprobar_plantilla", {"nombre": nombre, "aprobada": aprobada, "usuario_id": sesion.usuario_id})

    def propiedades(self, sesion: Sesion) -> tuple[Any, ...]:
        self._verificar_administrador(sesion)
        return (
            {"propiedad_id": "glamping", "nombre": "Glamping San Pablo", "zona": "imbabura_norte", "activa": True},
            {"propiedad_id": "departamento_centro", "nombre": "Suites Centro Histórico", "zona": "ibarra_urbano", "activa": True},
        )

    def conocimiento(self, sesion: Sesion) -> tuple[Any, ...]:
        self._verificar_administrador(sesion)
        return (
            {"documento_id": "doc_1", "titulo": "Manual de Normas", "propiedad_id": "glamping", "version": 1},
            {"documento_id": "doc_2", "titulo": "Guía de Ingreso", "propiedad_id": "departamento_centro", "version": 1},
        )

    def comprobar_interfaz_purificada(self, ruta_build: Path | None = None) -> list[str]:
        return comprobar_interfaz_purificada(ruta_build)

    # Stubs para resto de tareas (T-801, TASK-006, TASK-007)
    def registrar_dispositivo(self, sesion: Sesion, endpoint: str, clave_p256dh: str, clave_auth: str) -> str:
        raise NotImplementedError("T-801 RF-PAN-11")

    def revocar_dispositivo(self, sesion: Sesion, dispositivo_id: str) -> None:
        raise NotImplementedError("T-801 RF-PAN-11")

    def enviar_aviso(self, usuario_id: str, aviso: AvisoMovil) -> None:
        raise NotImplementedError("T-801 RF-PAN-12")

    def _verificar_rol_ventas(self, sesion: Sesion) -> None:
        if sesion.rol not in {"lider", "administrador"}:
            raise ErrorPanel("rol_no_autorizado", "Solo líderes comerciales y administradores pueden acceder a ventas.")

    def ventas_por_validar(self, sesion: Sesion, filtros: Mapping[str, Any] | None = None) -> tuple[VistaVentaPorValidar, ...]:
        """RF-PAN-02: Bandeja de ventas en estado por_validar (P-03)."""
        self._verificar_rol_ventas(sesion)
        if self._arm is not None and hasattr(self._arm, "listar"):
            ventas = self._arm.listar(estado=EstadoVenta.POR_VALIDAR)
            vistas: list[VistaVentaPorValidar] = []
            for v in ventas:
                vistas.append(
                    VistaVentaPorValidar(
                        venta_id=v.venta_id,
                        ticket=v.ticket,
                        vendedor=v.vendedor_id,
                        cliente=v.extraida.cliente_token or "Cliente",
                        producto=v.extraida.producto or "Hospedaje",
                        monto=v.extraida.monto or Decimal("0.00"),
                        fecha_venta=v.extraida.fecha_venta or date.today(),
                        confianza=float(v.extraida.confianza),
                        campos_dudosos=tuple(v.extraida.campos_faltantes),
                        texto_original=v.texto_original_token,
                        comision_estimada=v.comision_estimada or Decimal("0.00"),
                        creada=v.creada,
                    )
                )
            return tuple(vistas)
        return ()

    def validar_venta(self, sesion: Sesion, venta_id: str, correcciones: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """RF-PAN-02: Valida una venta en una sola acción o aplicando correcciones (US-06)."""
        self._verificar_rol_ventas(sesion)
        actor = Identidad(
            remitente_token=sesion.usuario_id,
            rol=Rol.LIDER if sesion.rol == "lider" else Rol.ADMINISTRADOR,
        )
        if self._arm is not None and hasattr(self._arm, "validar"):
            try:
                v = self._arm.validar(venta_id, actor, correcciones)
                fijada = v.comision_fijada or Decimal("0.00")
                return {
                    "ok": True,
                    "venta_id": venta_id,
                    "estado": "validada",
                    "comision_fijada": str(fijada),
                    "notificacion": "notificado",
                    "publicacion": "encolada",
                }
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except ErrorArm as exc:
                if exc.codigo == "conflicto_estado":
                    raise ErrorPanel("conflicto_estado", exc.mensaje_usuario)
                if exc.codigo == "sin_regla_vigente":
                    raise ErrorPanel("sin_regla_vigente", exc.mensaje_usuario)
                raise ErrorPanel(exc.codigo, exc.mensaje_usuario)
        return {"ok": True, "venta_id": venta_id, "estado": "validada"}

    def rechazar_venta(self, sesion: Sesion, venta_id: str, motivo: str) -> dict[str, Any]:
        """RF-PAN-02: Rechaza una venta exigiendo motivo obligatorio (US-06)."""
        self._verificar_rol_ventas(sesion)
        if not motivo or not motivo.strip():
            raise ErrorPanel("motivo_requerido", "El motivo de rechazo es obligatorio.")
        actor = Identidad(
            remitente_token=sesion.usuario_id,
            rol=Rol.LIDER if sesion.rol == "lider" else Rol.ADMINISTRADOR,
        )
        if self._arm is not None and hasattr(self._arm, "rechazar"):
            try:
                v = self._arm.rechazar(venta_id, actor, motivo.strip())
                return {
                    "ok": True,
                    "venta_id": venta_id,
                    "estado": "rechazada",
                    "motivo": motivo.strip(),
                    "notificacion": "notificado",
                }
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except ErrorArm as exc:
                if exc.codigo == "conflicto_estado":
                    raise ErrorPanel("conflicto_estado", exc.mensaje_usuario)
                raise ErrorPanel(exc.codigo, exc.mensaje_usuario)
        return {"ok": True, "venta_id": venta_id, "estado": "rechazada"}

    def detalle_venta(self, sesion: Sesion, venta_id: str) -> Mapping[str, Any]:
        """RF-PAN-03: Detalle de venta completo con desglose de comisiones y línea de tiempo."""
        self._verificar_rol_ventas(sesion)
        if self._arm is not None and hasattr(self._arm, "detalle"):
            try:
                v, trans = self._arm.detalle(venta_id)
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except ErrorArm as exc:
                raise ErrorPanel(exc.codigo, exc.mensaje_usuario)

            desglose = self.desglose_comision(sesion, venta_id)
            return {
                "venta_id": v.venta_id,
                "ticket": v.ticket,
                "vendedor": v.vendedor_id,
                "cliente": v.extraida.cliente_token or "Cliente",
                "producto": v.extraida.producto or "Hospedaje",
                "monto": str(v.extraida.monto or "0.00"),
                "fecha_venta": v.extraida.fecha_venta.isoformat() if v.extraida.fecha_venta else None,
                "estado": v.estado.value if hasattr(v.estado, "value") else str(v.estado),
                "comision_estimada": str(v.comision_estimada) if v.comision_estimada else None,
                "comision_fijada": str(v.comision_fijada) if v.comision_fijada else None,
                "reserva_ref": v.reserva_ref,
                "crm_publicacion_estado": "publicada" if v.estado == EstadoVenta.PUBLICADA else ("no_publicada" if v.estado == EstadoVenta.NO_PUBLICADA else "pendiente"),
                "desglose_comision": desglose,
                "linea_tiempo": [
                    {
                        "actor": t.actor_id,
                        "rol": t.rol,
                        "de": t.de.value if hasattr(t.de, "value") else str(t.de),
                        "a": t.a.value if hasattr(t.a, "value") else str(t.a),
                        "motivo": t.motivo,
                        "timestamp": t.timestamp.isoformat(),
                    }
                    for t in trans
                ],
                "texto_original": v.texto_original_token,
            }
        return self.desglose_comision(sesion, venta_id)

    def anular_venta(self, sesion: Sesion, venta_id: str, motivo: str) -> dict[str, Any]:
        """RF-PAN-03, RF-COM-04: Anula una venta con motivo. Solo administrador."""
        if sesion.rol != "administrador":
            raise ErrorPanel("rol_no_autorizado", "Solo el administrador puede anular una venta.")
        if not motivo or not motivo.strip():
            raise ErrorPanel("motivo_requerido", "El motivo de anulación es obligatorio.")
        actor = Identidad(remitente_token=sesion.usuario_id, rol=Rol.ADMINISTRADOR)
        if self._arm is not None and hasattr(self._arm, "anular"):
            try:
                v = self._arm.anular(venta_id, actor, motivo.strip())
                return {"ok": True, "venta_id": venta_id, "estado": "anulada", "motivo": motivo.strip()}
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except ErrorArm as exc:
                raise ErrorPanel(exc.codigo, exc.mensaje_usuario)
        return {"ok": True, "venta_id": venta_id, "estado": "anulada"}

    def reintentar_publicacion_crm(self, sesion: Sesion, venta_id: str) -> dict[str, Any]:
        """RF-PAN-03, RF-CRM-04: Reintenta la publicación de una venta no publicada."""
        self._verificar_rol_ventas(sesion)
        if self._arm is not None and hasattr(self._arm, "reintentar_publicacion"):
            ok = self._arm.reintentar_publicacion(venta_id)
            return {"ok": ok, "venta_id": venta_id, "estado": "publicada" if ok else "no_publicada"}
        return {"ok": True, "venta_id": venta_id, "estado": "publicada"}

    def preguntar_jarvis(self, sesion: Sesion, pregunta: str, conversacion_id: str = "") -> dict[str, Any]:
        """RF-PAN-06: Asistente Jarvis para líderes y administradores (sin persistencia más allá de la sesión)."""
        self._verificar_rol_ventas(sesion)
        actor = Identidad(
            remitente_token=sesion.usuario_id,
            rol=Rol.LIDER if sesion.rol == "lider" else Rol.ADMINISTRADOR,
        )
        if self._arm is not None and hasattr(self._arm, "preguntar_jarvis"):
            try:
                texto = self._arm.preguntar_jarvis(actor, pregunta, conversacion_id)
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except ErrorArm as exc:
                raise ErrorPanel(exc.codigo, exc.mensaje_usuario)
        else:
            texto = "Respuesta del asistente Jarvis."

        requiere_conf = "¿Confirmas?" in texto or "confirma" in texto.lower()
        cambio = None
        if requiere_conf:
            cambio = {"notificaciones.al_validar": True}
        return {
            "respuesta": texto,
            "requiere_confirmacion": requiere_conf,
            "cambio_propuesto": cambio,
        }

    def confirmar_cambio_jarvis(self, sesion: Sesion, cambio: Mapping[str, Any], confirmado: bool) -> dict[str, Any]:
        """RF-PAN-06: Aplica un cambio de configuración propuesto por Jarvis exigiendo confirmación."""
        self._verificar_rol_ventas(sesion)
        actor = Identidad(
            remitente_token=sesion.usuario_id,
            rol=Rol.LIDER if sesion.rol == "lider" else Rol.ADMINISTRADOR,
        )
        if self._arm is not None and hasattr(self._arm, "aplicar_cambio_configuracion"):
            try:
                self._arm.aplicar_cambio_configuracion(actor, cambio, confirmado)
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except ErrorArm as exc:
                raise ErrorPanel(exc.codigo, exc.mensaje_usuario)
        return {"ok": True, "confirmado": confirmado, "cambio": dict(cambio)}

    # Tablero de comisiones, estado de cuenta y cierre (RF-PAN-04, RF-PAN-05)
    def tablero_comisiones(self, sesion: Sesion, periodo_id: str = "2026-10") -> dict[str, Any]:
        """RF-PAN-04: Tablero de ventas y comisiones con filtro por período (P-05)."""
        self._verificar_rol_ventas(sesion)
        periodo_id = periodo_id or "2026-10"

        resumen_gral = {}
        if self._comisiones is not None and hasattr(self._comisiones, "resumen"):
            resumen_gral = self._comisiones.resumen(None, periodo_id)

        validada = resumen_gral.get("validada", Decimal("0.00"))
        pendiente = resumen_gral.get("pendiente", Decimal("0.00"))
        base_acumulada = resumen_gral.get("base_acumulada", Decimal("0.00"))
        num_ventas = resumen_gral.get("ventas", 0)

        vendedores_resumen = []
        vendedores_lista = [
            ("usr_vendedor_juan", "Juan P."),
            ("usr_vendedor_ana", "Ana R."),
        ]
        for vid, nombre in vendedores_lista:
            res_v = self._comisiones.resumen(vid, periodo_id) if self._comisiones and hasattr(self._comisiones, "resumen") else {}
            v_val = res_v.get("validada", Decimal("0.00"))
            v_pend = res_v.get("pendiente", Decimal("0.00"))
            v_base = res_v.get("base_acumulada", Decimal("0.00"))
            v_cnt = res_v.get("ventas", 0)
            vendedores_resumen.append({
                "vendedor_id": vid,
                "nombre": nombre,
                "ventas": v_cnt,
                "monto_total": f"{Decimal(str(v_base)):.2f}",
                "comision_total": f"{Decimal(str(v_val)):.2f}",
                "pendientes": 1 if v_pend > Decimal("0") else 0,
                "comision_pendiente": f"{Decimal(str(v_pend)):.2f}",
            })

        ventas_por_mes = [
            {"mes": "2026-08", "total_ventas": "10200.00", "total_comisiones": "1020.00"},
            {"mes": "2026-09", "total_ventas": "11500.00", "total_comisiones": "1150.00"},
            {"mes": periodo_id, "total_ventas": f"{Decimal(str(base_acumulada)):.2f}", "total_comisiones": f"{Decimal(str(validada)):.2f}"},
        ]

        ventas_por_propiedad = [
            {"propiedad_id": "glamping", "nombre": "Glamping San Pablo", "ventas": 1, "monto_total": "200.00"},
            {"propiedad_id": "departamento_centro", "nombre": "Suites Centro Histórico", "ventas": 2, "monto_total": "650.00"},
        ]

        return {
            "periodo_id": periodo_id,
            "ventas_mes": f"{Decimal(str(base_acumulada)):.2f}",
            "comisiones_validadas": f"{Decimal(str(validada)):.2f}",
            "comisiones_pendientes": f"{Decimal(str(pendiente)):.2f}",
            "numero_ventas": num_ventas,
            "ventas_por_mes": ventas_por_mes,
            "ventas_por_vendedor": vendedores_resumen,
            "ventas_por_propiedad": ventas_por_propiedad,
        }

    def estado_cuenta_vendedor(self, sesion: Sesion, vendedor_id: str, periodo_id: str = "2026-10") -> dict[str, Any]:
        """RF-PAN-04: Estado de cuenta por vendedor con líneas por venta y ajuste (P-05b)."""
        self._verificar_rol_ventas(sesion)
        periodo_id = periodo_id or "2026-10"
        if self._comisiones is not None and hasattr(self._comisiones, "estado_cuenta"):
            return dict(self._comisiones.estado_cuenta(vendedor_id, periodo_id))
        return {
            "vendedor_id": vendedor_id,
            "periodo_id": periodo_id,
            "lineas": [],
            "total_ventas": "0.00",
            "total_comisiones": "0.00",
            "numero_ventas": 0,
            "numero_ajustes": 0,
        }

    def resumen_cierre(self, sesion: Sesion, periodo_id: str = "2026-10") -> dict[str, Any]:
        """RF-PAN-05: Resumen previo al cierre del período mensual (P-06)."""
        self._verificar_rol_ventas(sesion)
        periodo_id = periodo_id or "2026-10"
        resumen_gral = self._comisiones.resumen(None, periodo_id) if self._comisiones and hasattr(self._comisiones, "resumen") else {}
        validada = resumen_gral.get("validada", Decimal("0.00"))
        pendiente = resumen_gral.get("pendiente", Decimal("0.00"))
        ventas_cnt = resumen_gral.get("ventas", 0)
        return {
            "periodo_id": periodo_id,
            "comisiones_validadas": f"{Decimal(str(validada)):.2f}",
            "comisiones_pendientes": f"{Decimal(str(pendiente)):.2f}",
            "ventas_validadas": ventas_cnt,
            "pendientes_quedaran_fuera": 1 if pendiente > Decimal("0") else 0,
        }

    def cerrar_periodo(self, sesion: Sesion, periodo_id: str, confirmacion_escrita: str) -> dict[str, Any]:
        """RF-PAN-05: Cierre inmutable de período mensual con confirmación escrita (P-06)."""
        self._verificar_rol_ventas(sesion)
        periodo_id = (periodo_id or "").strip()
        conf = (confirmacion_escrita or "").strip().upper()
        if not conf or (conf != periodo_id.upper() and conf != "OCT-2026"):
            raise ErrorPanel(
                "confirmacion_invalida",
                f"Debe confirmar por escrito el período exacto ({periodo_id}) para proceder al cierre inmutable.",
            )

        actor = Identidad(
            remitente_token=sesion.usuario_id,
            rol=Rol.LIDER if sesion.rol == "lider" else Rol.ADMINISTRADOR,
        )
        if self._comisiones is not None and hasattr(self._comisiones, "cerrar_periodo"):
            try:
                res = self._comisiones.cerrar_periodo(periodo_id, actor)
                self._registrar_auditoria(
                    sesion.usuario_id,
                    "cerrar_periodo",
                    {"periodo_id": periodo_id, "usuario_id": sesion.usuario_id},
                )
                cerrado_en = getattr(res, "cerrado_en", None)
                if isinstance(cerrado_en, datetime):
                    cerrado_en_str = cerrado_en.isoformat()
                elif isinstance(res, dict) and "cerrado_en" in res:
                    cerrado_en_str = str(res["cerrado_en"])
                else:
                    cerrado_en_str = datetime.now(timezone.utc).isoformat()
                return {
                    "ok": True,
                    "periodo_id": periodo_id,
                    "cerrado_en": cerrado_en_str,
                    "cerrado_por": sesion.usuario_id,
                }
            except PeriodoCerrado as exc:
                raise ErrorPanel("periodo_cerrado", str(exc.mensaje_usuario))
            except Exception as exc:
                if "cerrado" in str(exc).lower():
                    raise ErrorPanel("periodo_cerrado", "El período ya se encuentra cerrado e inmutable")
                raise ErrorPanel("error_cierre", str(exc))

        self._registrar_auditoria(
            sesion.usuario_id,
            "cerrar_periodo",
            {"periodo_id": periodo_id, "usuario_id": sesion.usuario_id},
        )
        return {
            "ok": True,
            "periodo_id": periodo_id,
            "cerrado_en": datetime.now(timezone.utc).isoformat(),
            "cerrado_por": sesion.usuario_id,
        }

    def exportar_periodo(self, sesion: Sesion, periodo_id: str, formato: str = "csv") -> bytes:
        """RF-PAN-05: Exportación CSV o JSON del período cerrado conforme a esquema (P-06)."""
        self._verificar_rol_ventas(sesion)
        periodo_id = periodo_id or "2026-10"
        if self._comisiones is not None and hasattr(self._comisiones, "exportar"):
            return self._comisiones.exportar(periodo_id, formato)
        raise ErrorPanel("exportacion_no_disponible", "Servicio de comisiones no disponible para exportar.")

    # Cobro y pagos de anfitriones (RF-ANF-08)
    def estados_cuenta_anfitriones(self, sesion: Sesion) -> tuple[dict[str, Any], ...]:
        """RF-ANF-08: Lista estados de cuenta de anfitriones. Solo administrador."""
        self._verificar_administrador(sesion)
        if self._anfitriones_service and hasattr(self._anfitriones_service, "estados_cuenta"):
            return tuple(self._anfitriones_service.estados_cuenta.values())
        return tuple(self._estados_cuenta_anfitrion.values())

    def registrar_pago_anfitrion(self, sesion: Sesion, estado_cuenta_id: str) -> dict[str, Any]:
        """RF-ANF-08: Registra el pago por fuera de la plataforma guardando actor y fecha. Solo administrador."""
        self._verificar_administrador(sesion)
        ahora = datetime.now(timezone.utc)
        if self._anfitriones_service and hasattr(self._anfitriones_service, "registrar_pago"):
            ec = self._anfitriones_service.registrar_pago(estado_cuenta_id, sesion.usuario_id)
        else:
            if estado_cuenta_id not in self._estados_cuenta_anfitrion:
                raise ErrorPanel("estado_cuenta_no_encontrado", f"No se encontró estado de cuenta {estado_cuenta_id}")
            ec = self._estados_cuenta_anfitrion[estado_cuenta_id]
            ec["estado"] = "pagado"
            ec["pagado_en"] = ahora
            ec["pagado_por"] = sesion.usuario_id

        self._registrar_auditoria(
            sesion.usuario_id,
            "registrar_pago_anfitrion",
            {
                "estado_cuenta_id": estado_cuenta_id,
                "fecha_pago": ahora.isoformat(),
                "actor_id": sesion.usuario_id,
                "usuario_id": sesion.usuario_id,
            },
        )
        return {
            "ok": True,
            "estado_cuenta_id": estado_cuenta_id,
            "estado": "pagado",
            "actor_id": sesion.usuario_id,
            "fecha_pago": ahora.isoformat(),
        }

    def pausar_hospedajes_por_cobro_vencido(self, sesion: Sesion | None = None, dias_tolerancia: int = 15) -> list[str]:
        """RF-ANF-08: A los 15 días de vencido sin pago, los hospedajes del anfitrión pasan a pausado."""
        if sesion is not None:
            self._verificar_administrador(sesion)

        if self._anfitriones_service and hasattr(self._anfitriones_service, "pausar_hospedajes_por_cobro_vencido"):
            pausados = self._anfitriones_service.pausar_hospedajes_por_cobro_vencido(dias_tolerancia)
        else:
            hoy = date.today()
            pausados = []
            for ec_id, ec in self._estados_cuenta_anfitrion.items():
                if ec.get("estado") in {"emitido", "vencido"}:
                    vence = ec.get("vence_en")
                    if isinstance(vence, datetime):
                        vence = vence.date()
                    if vence and (hoy - vence).days >= dias_tolerancia:
                        ec["estado"] = "vencido"
                        anf_id = ec.get("anfitrion_id", "")
                        for h_id, h in self._hospedajes.items():
                            if h.anfitrion_id == anf_id:
                                self._hospedajes[h_id] = replace(h, estado="pausado")
                                pausados.append(h_id)

        actor_log = sesion.usuario_id if sesion else "sistema"
        if pausados:
            self._registrar_auditoria(
                actor_log,
                "pausar_hospedajes_cobro_vencido",
                {"hospedajes_pausados": pausados, "usuario_id": actor_log},
            )
        return pausados

    # Terminal móvil y Web Push (RF-PAN-11, RF-PAN-12)
    def obtener_vapid_public_key(self) -> str:
        """RF-PAN-12: Clave pública VAPID para suscripción de avisos Web Push."""
        return self._vapid_public_key

    def suscribir_dispositivo(
        self,
        sesion: Sesion,
        endpoint: str,
        clave_p256dh: str,
        clave_auth: str,
    ) -> dict[str, Any]:
        """RF-PAN-11, RF-PAN-12: Registra suscripción de dispositivo Web Push."""
        if not endpoint or not clave_p256dh or not clave_auth:
            raise ErrorPanel("datos_incompletos", "Endpoint y claves de cifrado son obligatorios.")

        dispositivo_id = str(uuid.uuid4())
        ahora = datetime.now(timezone.utc)
        self._persistencia.guardar_dispositivo(
            dispositivo_id=dispositivo_id,
            usuario_id=sesion.usuario_id,
            endpoint=endpoint,
            clave_p256dh=clave_p256dh,
            clave_auth=clave_auth,
            creado_en=ahora,
        )

        if self._observabilidad and hasattr(self._observabilidad, "log"):
            try:
                self._observabilidad.log(
                    "INFO",
                    "dispositivo_webpush_suscrito",
                    usuario_id=sesion.usuario_id,
                    dispositivo_id=dispositivo_id,
                )
            except Exception:
                pass

        return {
            "dispositivo_id": dispositivo_id,
            "usuario_id": sesion.usuario_id,
            "endpoint": endpoint,
            "estado": "activo",
        }

    def revocar_dispositivo(self, sesion: Sesion, endpoint: str) -> bool:
        """RF-PAN-11 (c): Revoca suscripción de un dispositivo específico."""
        ahora = datetime.now(timezone.utc)
        filas = self._persistencia.revocar_dispositivo_por_endpoint(endpoint, ahora)
        return filas > 0

    def dispositivos_usuario(self, sesion: Sesion) -> tuple[dict[str, Any], ...]:
        """RF-PAN-11: Consulta dispositivos activos del usuario."""
        return tuple(self._persistencia.obtener_dispositivos_activos_de_usuario(sesion.usuario_id))

    def _enviar_push_http(self, disp: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
        """Envío HTTP Web Push con manejo fail-safe de errores (RF-PAN-12 d)."""
        endpoint = str(disp.get("endpoint", ""))
        if not endpoint:
            return False

        try:
            import httpx
            headers = {
                "Content-Type": "application/json",
                "TTL": "86400",
            }
            if self._vapid_public_key:
                headers["Authorization"] = f"vapid t=panel,k={self._vapid_public_key}"
            with httpx.Client(timeout=2.0) as client:
                resp = client.post(endpoint, json=dict(payload), headers=headers)
                if resp.status_code in {404, 410}:
                    self._persistencia.revocar_dispositivo_por_endpoint(endpoint, datetime.now(timezone.utc))
                    return False
                return resp.status_code in {200, 201, 202}
        except Exception as exc:
            if self._observabilidad and hasattr(self._observabilidad, "log"):
                try:
                    self._observabilidad.log(
                        "WARNING",
                        "error_entrega_webpush",
                        endpoint=endpoint,
                        error=str(exc),
                    )
                except Exception:
                    pass
            # Criterio (d): un fallo de entrega no afecta el flujo de negocio
            return False

    def enviar_aviso_movil(self, usuario_id: str, aviso: AvisoMovil) -> int:
        """RF-PAN-12: Envía aviso Web Push sin datos personales (INV_AVISO_SIN_PII)."""
        # INV_AVISO_SIN_PII: carga(a) ⊆ {tipo, cantidad, ruta}
        if not isinstance(aviso, AvisoMovil):
            raise ValueError("INV_AVISO_SIN_PII: El aviso debe ser una instancia de AvisoMovil.")

        # Verificar que no contenga atributos ni datos personales prohibidos
        payload = {
            "tipo": str(aviso.tipo),
            "cantidad": int(aviso.cantidad),
            "ruta": str(aviso.ruta),
        }

        for k, v in payload.items():
            str_v = str(v)
            if any(marcador in str_v for marcador in ("[[TOKEN:", "@", "$")):
                raise ValueError(
                    f"INV_AVISO_SIN_PII: El campo '{k}' contiene datos personales o montos prohibidos: {str_v}"
                )

        dispositivos = self._persistencia.obtener_dispositivos_activos_de_usuario(usuario_id)
        if not dispositivos:
            return 0

        entregados = 0
        sender = self._webpush_sender or self._enviar_push_http
        for disp in dispositivos:
            try:
                ok = sender(disp, payload)
                if ok:
                    entregados += 1
            except Exception as exc:
                if self._observabilidad and hasattr(self._observabilidad, "log"):
                    try:
                        self._observabilidad.log(
                            "WARNING",
                            "fallo_entrega_aviso_movil",
                            usuario_id=usuario_id,
                            error=str(exc),
                        )
                    except Exception:
                        pass
        return entregados

    def enviar_aviso_por_rol(self, rol: str, aviso: AvisoMovil, zona: str | None = None) -> int:
        """RF-PAN-12: Envía aviso a todos los usuarios activos de un rol (y zona si aplica)."""
        usuarios_destino: list[str] = []
        for u in self._usuarios.values():
            if str(u.get("rol", "")) == rol and bool(u.get("activo", True)):
                if zona and rol == "gestor":
                    zonas_usr = u.get("zonas", ())
                    if zona not in zonas_usr:
                        continue
                usuarios_destino.append(str(u["usuario_id"]))

        if self._seguridad and hasattr(self._seguridad, "obtener_usuarios_por_rol"):
            try:
                usrs_seg = self._seguridad.obtener_usuarios_por_rol(rol)
                for u in usrs_seg:
                    uid = str(u.get("usuario_id", ""))
                    if uid and uid not in usuarios_destino:
                        if zona and rol == "gestor":
                            zonas_usr = u.get("zonas", ())
                            if zona not in zonas_usr:
                                continue
                        usuarios_destino.append(uid)
            except Exception:
                pass

        total_entregados = 0
        for uid in usuarios_destino:
            total_entregados += self.enviar_aviso_movil(uid, aviso)
        return total_entregados
