# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala crm_conector (RF-CRM-01..06, RF-MCP-06)."""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

import yaml

from features.crm_conector.base_internal import CRMConnector
from features.crm_conector.chatwoot_internal import ChatwootAttioConnector
from features.crm_conector.cola_internal import (
    calcular_proximo_intento,
    obtener_publicacion,
    procesar_cola_reintentos,
    registrar_o_recuperar_publicacion,
    reintentar_publicacion_manual,
)
from features.crm_conector.eventos_internal import procesar_evento_entrante
from features.crm_conector.fake_internal import FakeCRM
from features.crm_conector.firma_internal import (
    calcular_firma,
    generar_cuerpo_canonico,
    validar_firma,
    verificar_firma,
)
from features.crm_conector.ghl_internal import GHLConnector
from features.crm_conector.http_internal import AdaptadorHttpCRM
from features.crm_conector.persistencia_internal import (
    actualizar_handoff,
    crear_handoff,
    guardar_referencia,
    inicializar_base_datos,
    insertar_zona,
    listar_handoffs as db_listar_handoffs,
    listar_zonas as db_listar_zonas,
    obtener_handoff as db_obtener_handoff,
    obtener_handoff_abierto_por_conversacion,
    obtener_referencia,
    obtener_zona as db_obtener_zona,
)
from features.crm_conector.tipos import (
    BandejaHandoffInactiva,
    Contacto,
    ContactoDuplicado,
    ContactoNoEncontrado,
    CRMNoDisponible,
    ErrorCRM,
    EventoCRM,
    FirmaEventoInvalida,
    Handoff,
    HandoffExistente,
    HandoffInexistente,
    LimiteDeTasa,
    Oportunidad,
    OportunidadInexistente,
    PublicacionVenta,
    ReferenciaCRM,
    ResultadoHandoff,
    WebhookRechazado,
    Zona,
    ZonaInexistente,
)

__all__ = [
    "Contacto",
    "EventoCRM",
    "Oportunidad",
    "PublicacionVenta",
    "Zona",
    "Handoff",
    "ResultadoHandoff",
    "ReferenciaCRM",
    "ErrorCRM",
    "CRMNoDisponible",
    "ContactoDuplicado",
    "ContactoNoEncontrado",
    "OportunidadInexistente",
    "WebhookRechazado",
    "LimiteDeTasa",
    "FirmaEventoInvalida",
    "HandoffExistente",
    "HandoffInexistente",
    "ZonaInexistente",
    "BandejaHandoffInactiva",
    "CRMConectorService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_crm_conector.yaml")
ReceptorEvento = Callable[[EventoCRM], Any]
_PATRON_ENV = re.compile(r"^\$\{([A-Z0-9_]+)(?::-(.*))?\}$")


# ¤crm-conector
def _resolver_valor(valor: Any) -> Any:
    if isinstance(valor, str):
        coincidencia = _PATRON_ENV.match(valor.strip())
        if coincidencia:
            var_nombre, por_defecto = coincidencia.groups()
            return os.getenv(var_nombre, por_defecto if por_defecto is not None else "")
        return valor
    if isinstance(valor, dict):
        return {k: _resolver_valor(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_resolver_valor(v) for v in valor]
    return valor


# ¤crm-conector
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        datos = yaml.safe_load(archivo) or {}
    return _resolver_valor(datos)


# ¤crm-conector
class CRMConectorService:
    """Publica ventas e idempotencia, gestiona contactos/oportunidades y atiende handoffs por zona."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        observabilidad: Any = None,
        conector: CRMConnector | None = None,
        conexion_bd: sqlite3.Connection | None = None,
        adaptador_http: AdaptadorHttpCRM | None = None,
    ) -> None:
        if config is None:
            self._config = dict(cargar_config())
        else:
            self._config = dict(_resolver_valor(dict(config)))

        self._observabilidad = observabilidad
        self._receptores: dict[str, list[ReceptorEvento]] = {}
        self._conexion_bd = inicializar_base_datos(conexion_bd)

        # Inicializar adaptador HTTP configurable
        if adaptador_http is not None:
            self._adaptador_http = adaptador_http
        else:
            webhook_cfg = self._config.get("webhook_ventas", {})
            self._adaptador_http = AdaptadorHttpCRM(
                url=str(webhook_cfg.get("url", "")),
                secreto_hmac=str(webhook_cfg.get("secreto_hmac", "")),
                cabecera_firma=str(webhook_cfg.get("cabecera_firma", "X-Glamping-Signature")),
            )

        # Resolver conector según proveedor (RF-CRM-02)
        if conector is not None:
            self._conector: CRMConnector = conector
        else:
            proveedor = str(self._config.get("proveedor", "fake")).lower()
            if proveedor == "fake":
                self._conector = FakeCRM()
            elif proveedor == "ghl":
                self._conector = GHLConnector(self._config, self._adaptador_http)
            elif proveedor == "chatwoot_attio":
                self._conector = ChatwootAttioConnector(self._config, self._adaptador_http)
            else:
                raise CRMNoDisponible(f"Proveedor desconocido '{proveedor}'.")

    # --- Gestión de receptores de eventos ---

    # ¤crm-conector
    def registrar_receptor(self, tipo: str, receptor: ReceptorEvento) -> None:
        """El pasillo central enlaza aquí a arm_jarvis, agente y panel_operativo."""
        self._receptores.setdefault(tipo, []).append(receptor)

    # ¤crm-conector
    def despachar_evento(self, evento: EventoCRM) -> None:
        for receptor in self._receptores.get(evento.tipo, []):
            receptor(evento)
        for receptor in self._receptores.get("*", []):
            receptor(evento)

    # --- Contactos y Oportunidades (RF-CRM-01, RF-MCP-07) ---

    # ¤crm-conector
    def buscar_contacto(
        self,
        telefono_token: str | None = None,
        email_token: str | None = None,
        *,
        telefono: str | None = None,
        email: str | None = None,
    ) -> Contacto | None:
        tok_tel = telefono_token or telefono
        tok_em = email_token or email
        return self._conector.buscar_contacto(
            email=tok_em,
            telefono=tok_tel,
            email_token=tok_em,
            telefono_token=tok_tel,
        )

    # ¤crm-conector
    def crear_contacto(self, contacto: Contacto) -> Contacto:
        return self._conector.crear_contacto(contacto)

    # ¤crm-conector
    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        return self._conector.crear_oportunidad(oportunidad)

    # ¤crm-conector
    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad:
        return self._conector.actualizar_oportunidad(oportunidad_id, datos)

    # --- Herramientas MCP para el agente ---

    # ¤crm-conector
    def buscar_contacto_crm(
        self,
        telefono_token: str | None = None,
        email_token: str | None = None,
    ) -> dict[str, Any]:
        """Herramienta MCP buscar_contacto_crm."""
        contacto = self.buscar_contacto(telefono_token=telefono_token, email_token=email_token)
        if contacto:
            return {"encontrado": True, "contacto_id": contacto.contacto_id}
        return {"encontrado": False}

    # ¤crm-conector
    def crear_oportunidad_crm(
        self,
        contacto_id: str,
        propiedad_id: str,
        etapa: str,
        monto: Decimal | float | None = None,
    ) -> dict[str, Any]:
        """Herramienta MCP crear_oportunidad_crm."""
        monto_dec = Decimal(str(monto)) if monto is not None else None
        op = Oportunidad(
            oportunidad_id=str(uuid4()),
            contacto_id=contacto_id,
            propiedad_id=propiedad_id,
            etapa=etapa,
            monto=monto_dec,
        )
        guardada = self.crear_oportunidad(op)
        return {"oportunidad_id": guardada.oportunidad_id}

    # --- Ventas y publicaciones (RF-CRM-01, RF-CRM-03, INV_VENTA_FIRMADA_IDEMPOTENTE) ---

    # ¤crm-conector
    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        """Publica una venta al CRM de forma firmada e idempotente (RF-CRM-03)."""
        venta_id = str(venta["venta_id"])
        evento = "venta_validada"

        payload = {
            "venta_id": venta_id,
            "evento": evento,
            "ticket": str(venta.get("ticket", "")),
            "vendedor": str(venta.get("vendedor", "")),
            "cliente": str(venta.get("cliente", "")),
            "telefono_cliente": venta.get("telefono_cliente"),
            "monto": str(venta.get("monto", "0.00")),
            "moneda": str(venta.get("moneda", "USD")),
            "producto": str(venta.get("producto", "")),
            "fecha_venta": str(venta.get("fecha_venta", "")),
            "comision": str(venta.get("comision", "0.00")),
        }

        pub_existente, es_nueva = registrar_o_recuperar_publicacion(
            self._conexion_bd, venta_id, evento, payload
        )

        # Criterio idempotencia: Si ya está 'ok', no reenviar ni duplicar contacto/oportunidad
        if not es_nueva and pub_existente.estado == "ok":
            return pub_existente

        try:
            codigo, respuesta = self._adaptador_http.enviar_publicacion(payload)
            intentos = pub_existente.intentos + 1
            with self._conexion_bd:
                self._conexion_bd.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'ok', intentos = ?, ultima_respuesta = ?, proximo_intento = NULL
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, f"{codigo} OK: {respuesta}", venta_id, evento),
                )
            if hasattr(self._conector, "publicar_venta"):
                try:
                    self._conector.publicar_venta(payload)
                except Exception:
                    pass
            return obtener_publicacion(self._conexion_bd, venta_id, evento) or pub_existente
        except Exception as exc:
            intentos = pub_existente.intentos + 1
            prox = calcular_proximo_intento(intentos, self._config.get("cola", {}).get("backoff_s"))
            with self._conexion_bd:
                self._conexion_bd.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'pendiente', intentos = ?, ultima_respuesta = ?, proximo_intento = ?
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, str(exc), prox.isoformat(), venta_id, evento),
                )
            return obtener_publicacion(self._conexion_bd, venta_id, evento) or pub_existente

    # ¤crm-conector
    def publicar_anulacion(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        """Publica la anulación de una venta de forma firmada e idempotente (RF-CRM-03, RF-COM-04)."""
        venta_id = str(venta["venta_id"])
        evento = "venta_anulada"

        payload = {
            "venta_id": venta_id,
            "evento": evento,
            "ticket": str(venta.get("ticket", "")),
            "vendedor": str(venta.get("vendedor", "")),
            "cliente": str(venta.get("cliente", "")),
            "telefono_cliente": venta.get("telefono_cliente"),
            "monto": str(venta.get("monto", "0.00")),
            "moneda": str(venta.get("moneda", "USD")),
            "producto": str(venta.get("producto", "")),
            "fecha_venta": str(venta.get("fecha_venta", "")),
            "comision": str(venta.get("comision", "0.00")),
        }

        pub_existente, es_nueva = registrar_o_recuperar_publicacion(
            self._conexion_bd, venta_id, evento, payload
        )

        if not es_nueva and pub_existente.estado == "ok":
            return pub_existente

        try:
            codigo, respuesta = self._adaptador_http.enviar_publicacion(payload)
            intentos = pub_existente.intentos + 1
            with self._conexion_bd:
                self._conexion_bd.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'ok', intentos = ?, ultima_respuesta = ?, proximo_intento = NULL
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, f"{codigo} OK: {respuesta}", venta_id, evento),
                )
            if hasattr(self._conector, "publicar_anulacion"):
                try:
                    self._conector.publicar_anulacion(payload)
                except Exception:
                    pass
            return obtener_publicacion(self._conexion_bd, venta_id, evento) or pub_existente
        except Exception as exc:
            intentos = pub_existente.intentos + 1
            prox = calcular_proximo_intento(intentos, self._config.get("cola", {}).get("backoff_s"))
            with self._conexion_bd:
                self._conexion_bd.execute(
                    """
                    UPDATE crm.publicaciones
                    SET estado = 'pendiente', intentos = ?, ultima_respuesta = ?, proximo_intento = ?
                    WHERE venta_id = ? AND evento = ?
                    """,
                    (intentos, str(exc), prox.isoformat(), venta_id, evento),
                )
            return obtener_publicacion(self._conexion_bd, venta_id, evento) or pub_existente

    # ¤crm-conector
    def procesar_cola(self, ahora: datetime | None = None) -> int:
        """Procesa cola persistente de publicaciones fallidas con backoff (RF-CRM-04)."""
        return procesar_cola_reintentos(
            conexion=self._conexion_bd,
            adaptador=self._adaptador_http,
            observabilidad=self._observabilidad,
            config=self._config,
            ahora=ahora,
        )

    # ¤crm-conector
    def reintentar_publicacion(self, venta_id: str, evento: str = "venta_validada") -> PublicacionVenta:
        """Reintenta manualmente una publicación desde el panel (RF-CRM-04)."""
        return reintentar_publicacion_manual(
            conexion=self._conexion_bd,
            venta_id=venta_id,
            evento=evento,
            adaptador=self._adaptador_http,
        )

    # ¤crm-conector
    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        return self._conector.enviar_mensaje(conversacion_id, texto)

    # ¤crm-conector
    def recibir_evento(self, cuerpo: bytes, firma: str, fecha_iso: str | None = None) -> EventoCRM:
        """Recibe y valida un evento entrante del CRM verificando firma HMAC-SHA256 (RF-CRM-03)."""
        secreto = str(self._config.get("eventos_entrantes", {}).get("secreto", ""))
        evento = procesar_evento_entrante(
            cuerpo=cuerpo,
            firma=firma,
            secreto=secreto,
            conexion=self._conexion_bd,
            fecha_iso=fecha_iso,
            observabilidad=self._observabilidad,
        )
        self.despachar_evento(evento)
        return evento

    # --- Handoffs por zona (RF-CRM-06, RF-MCP-06, INV_HANDOFF_UNICO) ---

    # ¤crm-conector
    def solicitar_handoff(
        self,
        conversacion_id: str,
        zona_id: str | None = None,
        resumen: str = "",
        motivo: str = "peticion_explicita",
        propiedad_id: str | None = None,
    ) -> str:
        """Crea un handoff en crm.handoffs asignado al gestor de la zona o al administrador."""
        # 1. Verificar INV_HANDOFF_UNICO: no permitir segundo handoff abierto
        existente = obtener_handoff_abierto_por_conversacion(self._conexion_bd, conversacion_id)
        if existente:
            raise HandoffExistente(
                f"La conversación {conversacion_id} ya tiene un handoff abierto con id {existente.handoff_id}."
            )

        # 2. Resolver zona_id
        zona_resuelt_id = zona_id
        if not zona_resuelt_id and propiedad_id:
            mapeo = self._config.get("propiedades_zonas", {})
            zona_resuelt_id = mapeo.get(propiedad_id)

        # 3. Determinar asignatario
        admin_id = str(self._config.get("admin_id", "00000000-0000-0000-0000-000000000001"))
        asignado_a: str = admin_id
        zona_final: str | None = None

        if zona_resuelt_id:
            zona = db_obtener_zona(self._conexion_bd, zona_resuelt_id)
            if zona:
                asignado_a = zona.gestor_principal_id
                zona_final = zona.zona_id
            else:
                # Si la zona especificada no existe en la base, asignar a admin con zona vacía
                asignado_a = admin_id
                zona_final = None
        else:
            # Handoff sin zona resuelta: asigna al administrador con zona vacía
            asignado_a = admin_id
            zona_final = None

        # 4. Registrar handoff en persistencia
        handoff_id = str(uuid4())
        ahora = datetime.now(timezone.utc)
        nuevo_handoff = Handoff(
            handoff_id=handoff_id,
            conversacion_id=conversacion_id,
            motivo=motivo,
            zona_id=zona_final,
            estado="pendiente",
            asignado_a=asignado_a,
            resumen_token=resumen or "Solicitud de asistencia humana",
            inicio=ahora,
            tomado_en=None,
            ultima_actividad=ahora,
            devuelto_en=None,
            devuelto_por=None,
        )
        crear_handoff(self._conexion_bd, nuevo_handoff)

        # 5. Notificar por observabilidad y eventos
        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "INFO",
                "handoff_solicitado",
                conversacion_id=conversacion_id,
                handoff_id=handoff_id,
                zona_id=zona_final,
                asignado_a=asignado_a,
                motivo=motivo,
                plantilla="handoff_asignado",
            )

        self.despachar_evento(
            EventoCRM(
                tipo="mensaje_gestor",
                referencia=handoff_id,
                actor="sistema",
                datos={
                    "evento": "handoff_asignado",
                    "asignado_a": asignado_a,
                    "conversacion_id": conversacion_id,
                    "zona_id": zona_final,
                    "plantilla": "handoff_asignado",
                },
                recibido_en=ahora,
            )
        )

        return handoff_id

    # ¤crm-conector
    def solicitar_humano(
        self,
        motivo: str,
        resumen: str,
        propiedad_id: str | None = None,
        conversacion_id: str | None = None,
    ) -> dict[str, Any]:
        """Herramienta MCP solicitar_humano (RF-MCP-06)."""
        conv_id = conversacion_id or str(uuid4())
        bandeja_activa = bool(self._config.get("bandeja_handoff_activa", True))

        # Escenario: Escalamiento antes de la fase 4 (instalación sin bandeja activa)
        if not bandeja_activa:
            contacto_configurado = str(
                self._config.get("contacto_humano_escalamiento", "+593999999999")
            )
            if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                self._observabilidad.log(
                    "WARN",
                    "escalamiento_sin_bandeja",
                    conversacion_id=conv_id,
                    motivo=motivo,
                    contacto_entregado=contacto_configurado,
                )
            return {
                "contacto_humano": contacto_configurado,
                "motivo": motivo,
                "bandeja_activa": False,
                "canal": "whatsapp",
            }

        # Bandeja activa: procede con handoff normal
        handoff_id = self.solicitar_handoff(
            conversacion_id=conv_id,
            propiedad_id=propiedad_id,
            resumen=resumen,
            motivo=motivo,
        )
        h = db_obtener_handoff(self._conexion_bd, handoff_id)
        asignado_a = h.asignado_a if h else str(self._config.get("admin_id", "admin"))
        minutos_estimados = int(self._config.get("minutos_estimados_atencion", 15))

        return {
            "handoff_id": handoff_id,
            "asignado_a": asignado_a,
            "canal": "panel",
            "minutos_estimados": minutos_estimados,
        }

    # ¤crm-conector
    def tomar_handoff(self, handoff_id: str, gestor_id: str) -> None:
        """Marca un handoff como tomado por el gestor."""
        h = db_obtener_handoff(self._conexion_bd, handoff_id)
        if not h:
            raise HandoffInexistente(f"Handoff {handoff_id} no encontrado.")

        ahora = datetime.now(timezone.utc)
        actualizado = Handoff(
            handoff_id=h.handoff_id,
            conversacion_id=h.conversacion_id,
            motivo=h.motivo,
            zona_id=h.zona_id,
            estado="tomado",
            asignado_a=gestor_id,
            resumen_token=h.resumen_token,
            inicio=h.inicio,
            tomado_en=ahora,
            ultima_actividad=ahora,
            devuelto_en=None,
            devuelto_por=None,
        )
        actualizar_handoff(self._conexion_bd, actualizado)

        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "INFO",
                "handoff_tomado",
                handoff_id=handoff_id,
                gestor_id=gestor_id,
                conversacion_id=h.conversacion_id,
            )

    # ¤crm-conector
    def devolver_al_asistente(
        self,
        handoff_id: str,
        gestor_id: str | None = None,
        devuelto_por: str = "gestor",
        reanudar_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Devuelve el handoff al asistente inteligente y libera la conversación."""
        h = db_obtener_handoff(self._conexion_bd, handoff_id)
        if not h:
            raise HandoffInexistente(f"Handoff {handoff_id} no encontrado.")

        ahora = datetime.now(timezone.utc)
        actualizado = Handoff(
            handoff_id=h.handoff_id,
            conversacion_id=h.conversacion_id,
            motivo=h.motivo,
            zona_id=h.zona_id,
            estado="devuelto",
            asignado_a=h.asignado_a,
            resumen_token=h.resumen_token,
            inicio=h.inicio,
            tomado_en=h.tomado_en,
            ultima_actividad=ahora,
            devuelto_en=ahora,
            devuelto_por=devuelto_por,  # type: ignore[arg-type]
        )
        actualizar_handoff(self._conexion_bd, actualizado)

        # Reanudar al agente si se proporcionó callback
        if reanudar_callback is not None:
            reanudar_callback(h.conversacion_id)

        # Notificar a receptores
        self.despachar_evento(
            EventoCRM(
                tipo="handoff_devuelto",
                referencia=handoff_id,
                actor=gestor_id or devuelto_por,
                datos={
                    "conversacion_id": h.conversacion_id,
                    "devuelto_por": devuelto_por,
                },
                recibido_en=ahora,
            )
        )

        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "INFO",
                "handoff_devuelto",
                handoff_id=handoff_id,
                conversacion_id=h.conversacion_id,
                devuelto_por=devuelto_por,
                gestor_id=gestor_id,
            )

    # ¤crm-conector
    def revisar_plazos_handoffs(self, ahora: datetime | None = None) -> dict[str, int]:
        """
        Revisa las condiciones temporales de handoffs:
        (a) Si lleva 15 min sin tomar en 'pendiente', reasigna a gestor_respaldo_id y dispara alerta.
        (b) Si lleva 24 h en 'tomado' sin actividad, lo devuelve al asistente con devuelto_por='vencimiento'.
        """
        tiempo_actual = ahora or datetime.now(timezone.utc)
        limite_sin_tomar_min = int(self._config.get("tiempo_limite_sin_tomar_minutos", 15))
        limite_abandono_horas = int(self._config.get("tiempo_limite_abandono_horas", 24))

        reasignados_respaldo = 0
        devueltos_vencimiento = 0

        # Revisar pendientes
        pendientes = db_listar_handoffs(self._conexion_bd, estado="pendiente")
        for h in pendientes:
            inicio_utc = h.inicio if h.inicio.tzinfo else h.inicio.replace(tzinfo=timezone.utc)
            t_actual_utc = tiempo_actual if tiempo_actual.tzinfo else tiempo_actual.replace(tzinfo=timezone.utc)
            delta_min = (t_actual_utc - inicio_utc).total_seconds() / 60.0

            if delta_min >= limite_sin_tomar_min and h.zona_id:
                zona = db_obtener_zona(self._conexion_bd, h.zona_id)
                if zona and h.asignado_a != zona.gestor_respaldo_id:
                    # Reasignar a gestor de respaldo
                    actualizado = Handoff(
                        handoff_id=h.handoff_id,
                        conversacion_id=h.conversacion_id,
                        motivo=h.motivo,
                        zona_id=h.zona_id,
                        estado="pendiente",
                        asignado_a=zona.gestor_respaldo_id,
                        resumen_token=h.resumen_token,
                        inicio=h.inicio,
                        tomado_en=None,
                        ultima_actividad=tiempo_actual,
                        devuelto_en=None,
                        devuelto_por=None,
                    )
                    actualizar_handoff(self._conexion_bd, actualizado)
                    reasignados_respaldo += 1

                    if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                        self._observabilidad.log(
                            "WARN",
                            "alerta_handoff_no_tomado",
                            handoff_id=h.handoff_id,
                            zona_id=h.zona_id,
                            gestor_anterior=h.asignado_a,
                            gestor_respaldo=zona.gestor_respaldo_id,
                            minutos_esperando=round(delta_min, 1),
                        )

        # Revisar tomados sin actividad
        tomados = db_listar_handoffs(self._conexion_bd, estado="tomado")
        for h in tomados:
            ult_act = h.ultima_actividad or h.tomado_en or h.inicio
            ult_act_utc = ult_act if ult_act.tzinfo else ult_act.replace(tzinfo=timezone.utc)
            t_actual_utc = tiempo_actual if tiempo_actual.tzinfo else tiempo_actual.replace(tzinfo=timezone.utc)
            delta_horas = (t_actual_utc - ult_act_utc).total_seconds() / 3600.0

            if delta_horas >= limite_abandono_horas:
                self.devolver_al_asistente(
                    h.handoff_id,
                    devuelto_por="vencimiento",
                )
                devueltos_vencimiento += 1

                if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                    self._observabilidad.log(
                        "INFO",
                        "handoff_vencido_por_abandono",
                        handoff_id=h.handoff_id,
                        conversacion_id=h.conversacion_id,
                        horas_inactivo=round(delta_horas, 1),
                    )

        return {
            "reasignados_respaldo": reasignados_respaldo,
            "devueltos_vencimiento": devueltos_vencimiento,
        }

    # --- Consultas de persistencia de apoyo ---

    # ¤crm-conector
    def obtener_handoff(self, handoff_id: str) -> Handoff | None:
        return db_obtener_handoff(self._conexion_bd, handoff_id)

    # ¤crm-conector
    def listar_handoffs(self, zona_id: str | None = None, estado: str | None = None) -> list[Handoff]:
        return db_listar_handoffs(self._conexion_bd, zona_id=zona_id, estado=estado)

    # ¤crm-conector
    def obtener_zona(self, zona_id: str) -> Zona | None:
        return db_obtener_zona(self._conexion_bd, zona_id)

    # ¤crm-conector
    def listar_zonas(self) -> list[Zona]:
        return db_listar_zonas(self._conexion_bd)

    # ¤crm-conector
    def registrar_zona(self, zona: Zona) -> None:
        insertar_zona(self._conexion_bd, zona)

    # ¤crm-conector
    def guardar_referencia(self, entidad: str, id_local: str, crm_ref: str) -> None:
        guardar_referencia(self._conexion_bd, ReferenciaCRM(entidad, id_local, crm_ref))

    # ¤crm-conector
    def obtener_referencia(self, entidad: str, id_local: str) -> str | None:
        return obtener_referencia(self._conexion_bd, entidad, id_local)
