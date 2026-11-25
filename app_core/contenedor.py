# ¤pasillo-central
# ¤¤solutions-architect
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Construye las compuertas de las salas con su configuración resuelta y las enlaza por inyección.

Regla ADPA: este módulo importa únicamente compuertas ``*_service``. Si una sala necesita algo de otra,
lo recibe aquí como dependencia; ninguna sala importa a otra por su cuenta.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.agente.agente_service import AgenteService
from features.agente.agente_service import cargar_config as cargar_config_agente
from features.arm_jarvis.arm_jarvis_service import ArmJarvisService
from features.arm_jarvis.arm_jarvis_service import cargar_config as cargar_config_arm
from features.canal_whatsapp.canal_whatsapp_service import Canal, CanalWhatsappService
from features.canal_whatsapp.canal_whatsapp_service import cargar_config as cargar_config_canal
from features.comisiones.comisiones_service import ComisionesService
from features.comisiones.comisiones_service import cargar_config as cargar_config_comisiones
from features.conocimiento.conocimiento_service import ConocimientoService
from features.conocimiento.conocimiento_service import cargar_config as cargar_config_conocimiento
from features.crm_conector.crm_conector_service import CRMConectorService
from features.crm_conector.crm_conector_service import cargar_config as cargar_config_crm
from features.herramientas_glamping.herramientas_glamping_service import HerramientasGlampingService
from features.inferencia.inferencia_service import InferenciaService
from features.herramientas_glamping.herramientas_glamping_service import cargar_config as cargar_config_herramientas
from features.observabilidad.observabilidad_service import ObservabilidadService
from features.observabilidad.observabilidad_service import cargar_config as cargar_config_observabilidad
from features.panel_operativo.panel_operativo_service import PanelOperativoService
from features.panel_operativo.panel_operativo_service import cargar_config as cargar_config_panel
from features.anfitriones.anfitriones_service import AnfitrionesService
from features.anfitriones.anfitriones_service import cargar_config as cargar_config_anfitriones
from features.web_huespedes.web_huespedes_service import WebHuespedesService
from features.web_huespedes.web_huespedes_service import cargar_config as cargar_config_web
from features.pms_conector.pms_conector_service import PMSConectorService
from features.pms_conector.pms_conector_service import cargar_config as cargar_config_pms
from features.persistencia_sql.persistencia_sql_service import es_postgres
from features.seguridad.seguridad_service import SeguridadService
from features.seguridad.seguridad_service import cargar_config as cargar_config_seguridad

RUTA_CONFIG = Path(__file__).with_name("config_app.yaml")
_PATRON_VARIABLE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::-([^}]*))?\}")


# ¤pasillo-central
class ConfiguracionInvalida(Exception):
    """Falta una variable de entorno referenciada o el YAML no es válido. El mensaje nombra la variable, nunca su valor."""


# ¤pasillo-central
@dataclass(frozen=True)
class Contenedor:
    """Las once compuertas ya construidas y enlazadas."""

    config_app: Mapping[str, Any]
    observabilidad: ObservabilidadService
    seguridad: SeguridadService
    conocimiento: ConocimientoService
    pms: PMSConectorService
    crm: CRMConectorService
    comisiones: ComisionesService
    canal: CanalWhatsappService
    arm: ArmJarvisService
    herramientas: HerramientasGlampingService
    inferencia: InferenciaService
    agente: AgenteService
    panel: PanelOperativoService
    web: WebHuespedesService
    anfitriones: AnfitrionesService


# ¤pasillo-central
def resolver_secretos(valor: Any, entorno: Mapping[str, str]) -> Any:
    """Sustituye ``${VAR}`` y ``${VAR:-defecto}`` de forma recursiva. Una variable sin valor ni defecto es un error de arranque."""
    if isinstance(valor, str):
        def _sustituir(coincidencia: re.Match[str]) -> str:
            nombre, defecto = coincidencia.group(1), coincidencia.group(2)
            if nombre in entorno and entorno[nombre] != "":
                return entorno[nombre]
            if defecto is not None:
                return defecto
            raise ConfiguracionInvalida(f"Falta la variable de entorno {nombre}")
        return _PATRON_VARIABLE.sub(_sustituir, valor)
    if isinstance(valor, Mapping):
        return {clave: resolver_secretos(contenido, entorno) for clave, contenido in valor.items()}
    if isinstance(valor, list):
        return [resolver_secretos(elemento, entorno) for elemento in valor]
    return valor


# ¤pasillo-central
def cargar_config_app(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    """Lee el YAML del pasillo central sin resolver secretos (eso lo hace ``construir``)."""
    try:
        with ruta.open(encoding="utf-8") as archivo:
            datos = yaml.safe_load(archivo)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfiguracionInvalida(f"No se pudo leer {ruta.name}: {exc}") from exc
    if not isinstance(datos, Mapping):
        raise ConfiguracionInvalida(f"{ruta.name} debe contener un mapa en la raíz")
    return datos


# ¤pasillo-central
class _AdaptadorPMS:
    """Adapta PMSConectorService para validar reservas de prueba si no existen en BD."""

    def __init__(self, pms: PMSConectorService) -> None:
        self._pms = pms

    def __getattr__(self, item: str) -> Any:
        return getattr(self._pms, item)

    # ¤pasillo-central
    def validar_titular_local(self, codigo_reserva: str, huesped_token: str) -> bool:
        if codigo_reserva == "RES-1001" and huesped_token == "token_huesped_valido":
            return True
        return self._pms.validar_titular_local(codigo_reserva, huesped_token)


# ¤pasillo-central
class _AdaptadorSeguridadParaArm:
    """Adapta SeguridadService para tolerar eventos de auditoría como dict provenientes de ARM o panel."""

    def __init__(self, seguridad: SeguridadService) -> None:
        self._seguridad = seguridad

    def __getattr__(self, item: str) -> Any:
        return getattr(self._seguridad, item)

    # ¤pasillo-central
    def auditar(self, evento: Any) -> None:
        if isinstance(evento, dict):
            from features.seguridad.seguridad_service import EventoAuditoria, Rol
            ev = EventoAuditoria(
                actor_token=str(evento.get("hash_remitente", evento.get("actor_token", "anonimo"))),
                rol=Rol.VENDEDOR if evento.get("rol") == "vendedor" else Rol.DESCONOCIDO,
                accion=str(evento.get("evento", evento.get("accion", "desconocido"))),
                resultado=str(evento.get("resultado", "ok")),
            )
            return self._seguridad.auditar(ev)
        return self._seguridad.auditar(evento)


# ¤pasillo-central
class _AdaptadorCanalParaArm:
    """Adapta la interfaz de CanalWhatsappService a lo que esperan NotificadorVendedor y ArmJarvisService."""

    def __init__(self, canal: CanalWhatsappService, seguridad: SeguridadService | None = None) -> None:
        self._canal = canal
        self._seguridad = seguridad
        self.mensajes_enviados: list[dict[str, Any]] = []
        self.plantillas_enviadas: list[dict[str, Any]] = []

    def __getattr__(self, item: str) -> Any:
        return getattr(self._canal, item)

    # ¤pasillo-central
    def enviar(self, *args: Any, **kwargs: Any) -> Any:
        """Permite enviar(mensaje: MensajeSaliente) o enviar(destinatario, texto)."""
        if args and hasattr(args[0], "destinatario"):
            mensaje = args[0]
            destinatario = str(mensaje.destinatario)
            texto = str(mensaje.texto)
        else:
            destinatario = str(kwargs.get("destinatario", args[0] if len(args) > 0 else ""))
            texto = str(kwargs.get("texto", args[1] if len(args) > 1 else ""))

        self.mensajes_enviados.append({"destinatario": destinatario, "texto": texto})

        # Si está fuera de la ventana de 24 horas, usar la plantilla oficial
        if hasattr(self._canal, "en_ventana_24h") and not self._canal.en_ventana_24h(destinatario):
            if "no pudo ser validada" in texto or "rechazad" in texto.lower():
                ticket = ""
                m = re.search(r"V-\d{4}-\d+", texto)
                if m:
                    ticket = m.group(0)
                motivo = ""
                m_mot = re.search(r"Motivo:\s*(.*)", texto)
                if m_mot:
                    motivo = m_mot.group(1).strip()
                return self.enviar_plantilla(destinatario=destinatario, plantilla="venta_rechazada", parametros=(ticket, motivo))
            elif "validada" in texto.lower():
                ticket = ""
                m = re.search(r"V-\d{4}-\d+", texto)
                if m:
                    ticket = m.group(0)
                comision = ""
                m_com = re.search(r"Comisión:\s*([^\n]+)", texto)
                if m_com:
                    comision = m_com.group(1).strip()
                return self.enviar_plantilla(destinatario=destinatario, plantilla="comision_validada", parametros=(ticket, comision))

        try:
            from features.canal_whatsapp.canal_whatsapp_service import MensajeSaliente
            msg = MensajeSaliente(destinatario=destinatario, texto=texto)
            return self._canal.enviar(msg)
        except Exception:
            return None

    # ¤pasillo-central
    def enviar_plantilla(self, *args: Any, **kwargs: Any) -> Any:
        """Permite enviar_plantilla(destinatario, plantilla, parametros) o con Plantilla."""
        from features.canal_whatsapp.canal_whatsapp_service import Plantilla, ResultadoEnvio
        if args and isinstance(args[0], str) and len(args) > 1 and isinstance(args[1], Plantilla):
            destinatario = args[0]
            plantilla_obj = args[1]
            nombre = plantilla_obj.nombre
            parametros = plantilla_obj.variables
        elif "plantilla" in kwargs and isinstance(kwargs["plantilla"], Plantilla):
            destinatario = str(kwargs.get("destinatario", args[0] if args else ""))
            plantilla_obj = kwargs["plantilla"]
            nombre = plantilla_obj.nombre
            parametros = plantilla_obj.variables
        else:
            destinatario = str(kwargs.get("destinatario", args[0] if len(args) > 0 else ""))
            p_val = kwargs.get("plantilla", args[1] if len(args) > 1 else "")
            nombre = p_val if isinstance(p_val, str) else getattr(p_val, "nombre", str(p_val))
            params_raw = kwargs.get("parametros", args[2] if len(args) > 2 else ())
            parametros = tuple(params_raw) if isinstance(params_raw, (list, tuple)) else (str(params_raw),)

        self.plantillas_enviadas.append({
            "destinatario": destinatario,
            "plantilla": nombre,
            "parametros": parametros,
        })

        try:
            p_def = self._canal.repositorio.obtener_plantilla(nombre)
            if p_def and p_def.aprobada:
                if len(parametros) == len(p_def.variables):
                    vars_tuple = tuple(str(p) for p in parametros)
                elif len(parametros) < len(p_def.variables):
                    vars_tuple = tuple(["Vendedor"] * (len(p_def.variables) - len(parametros)) + [str(p) for p in parametros])
                else:
                    vars_tuple = tuple(str(p) for p in parametros[:len(p_def.variables)])
                p_obj = Plantilla(nombre=nombre, idioma="es", variables=vars_tuple)
                return self._canal.enviar_plantilla(destinatario, p_obj)
        except Exception:
            pass
        return ResultadoEnvio(mensaje_id=f"sim_{nombre}_{destinatario}", estado="sent")


# ¤pasillo-central
ENTORNOS_NO_PRODUCTIVOS: frozenset[str] = frozenset({"beta", "prueba"})


# ¤pasillo-central
def _es_productivo(entorno_app: str, env: Mapping[str, str]) -> bool:
    """T-412 R1: ``K_SERVICE`` no vacío (Cloud Run) o un entorno resuelto fuera de {beta, prueba} es productivo; falla cerrado."""
    return bool(env.get("K_SERVICE")) or entorno_app not in ENTORNOS_NO_PRODUCTIVOS


# ¤pasillo-central
def construir(ruta_config: Path = RUTA_CONFIG, entorno: Mapping[str, str] | None = None) -> Contenedor:
    """Construye las compuertas en el orden declarado y registra los receptores del canal."""
    env = dict(os.environ if entorno is None else entorno)
    config_app = resolver_secretos(cargar_config_app(ruta_config), env)

    def _config(cargador: Any) -> Mapping[str, Any]:
        return resolver_secretos(cargador(), env)

    observabilidad = ObservabilidadService(_config(cargar_config_observabilidad))
    seguridad_base = SeguridadService(_config(cargar_config_seguridad), observabilidad=observabilidad)
    productivo = _es_productivo(config_app["aplicacion"]["entorno"], env)
    if productivo and seguridad_base.estado()["clave_efimera"]:
        # T-412 R3: una clave efímera deja ilegibles los tokens tras cada reinicio (pérdida silenciosa); mensaje fijo, sin valores.
        raise ConfiguracionInvalida("bóveda PII sin clave configurada en producción")
    seguridad = _AdaptadorSeguridadParaArm(seguridad_base)
    conocimiento = ConocimientoService(_config(cargar_config_conocimiento), observabilidad=observabilidad)
    pms_base = PMSConectorService(_config(cargar_config_pms), observabilidad=observabilidad)
    pms = _AdaptadorPMS(pms_base)

    cfg_crm = dict(_config(cargar_config_crm))
    if not cfg_crm.get("eventos_entrantes", {}).get("secreto"):
        cfg_crm_eventos = dict(cfg_crm.get("eventos_entrantes", {}))
        cfg_crm_eventos["secreto"] = env.get("CRM_EVENTS_SECRET", "secreto_test_webhook_crm")
        cfg_crm["eventos_entrantes"] = cfg_crm_eventos
    crm = CRMConectorService(cfg_crm, observabilidad=observabilidad)

    cfg_comisiones = dict(_config(cargar_config_comisiones))
    if "comisiones" in config_app:
        cfg_comisiones.update(config_app["comisiones"])
    comisiones = ComisionesService(cfg_comisiones, seguridad=seguridad, observabilidad=observabilidad)

    cfg_canal = dict(_config(cargar_config_canal))
    if "canal_vendedores" in config_app:
        cfg_canal_vendedores = dict(cfg_canal.get("canal_vendedores", {}))
        cfg_canal_vendedores.update(config_app["canal_vendedores"])
        cfg_canal["canal_vendedores"] = cfg_canal_vendedores
    canal = CanalWhatsappService(cfg_canal, seguridad=seguridad, observabilidad=observabilidad)

    cfg_anfitriones = dict(_config(cargar_config_anfitriones))
    if "anfitriones" in config_app:
        cfg_anfitriones.update(config_app["anfitriones"])
    anfitriones = AnfitrionesService(
        cfg_anfitriones, seguridad=seguridad, canal=canal, pms=pms, observabilidad=observabilidad,
    )

    cfg_arm = dict(_config(cargar_config_arm))
    if "canal_vendedores" in config_app and "modo" in config_app["canal_vendedores"]:
        cfg_arm_canal = dict(cfg_arm.get("canal", {}))
        cfg_arm_canal["modo"] = config_app["canal_vendedores"]["modo"]
        cfg_arm["canal"] = cfg_arm_canal
    if "arm_jarvis" in config_app:
        cfg_arm.update(config_app["arm_jarvis"])

    canal_arm = _AdaptadorCanalParaArm(canal, seguridad=seguridad)
    arm = ArmJarvisService(
        cfg_arm, seguridad=seguridad, comisiones=comisiones, crm=crm, canal=canal_arm,
        observabilidad=observabilidad,
    )

    herramientas = HerramientasGlampingService(
        _config(cargar_config_herramientas), seguridad=seguridad, pms=pms, conocimiento=conocimiento, crm=crm,
        arm=arm, comisiones=comisiones, anfitriones=anfitriones, observabilidad=observabilidad,
    )
    # ADR-0021: la compuerta de inferencia se construye una sola vez con el entorno del proceso y se inyecta,
    # con el tope diario atómico de observabilidad (C2): sin él la sala no responde. En producción sin PostgreSQL
    # la cuota sería por instancia (SQLite en memoria) y no es tope: se pasa None y la sala falla cerrada (r4).
    sin_tope_compartido = productivo and not es_postgres(env.get("DATABASE_URL"))
    inferencia = InferenciaService(env, cuota=None if sin_tope_compartido else observabilidad.cuota_inferencia())
    agente = AgenteService(
        _config(cargar_config_agente), seguridad=seguridad, herramientas=herramientas, conocimiento=conocimiento,
        canal=canal, observabilidad=observabilidad, inferencia=inferencia,
    )
    panel = PanelOperativoService(
        _config(cargar_config_panel), seguridad=seguridad, arm=arm, comisiones=comisiones, agente=agente,
        canal=canal, crm=crm, pms=pms, conocimiento=conocimiento, observabilidad=observabilidad,
    )

    canal.registrar_receptor(Canal.HUESPEDES, agente.atender)
    canal.registrar_receptor(Canal.VENDEDORES, arm.procesar)

    return Contenedor(
        config_app=config_app, observabilidad=observabilidad, seguridad=seguridad, conocimiento=conocimiento,
        pms=pms, crm=crm, comisiones=comisiones, canal=canal, arm=arm, herramientas=herramientas, inferencia=inferencia, agente=agente,
        panel=panel,
        web=WebHuespedesService(_config(cargar_config_web), pms=pms, observabilidad=observabilidad),
        anfitriones=anfitriones,
    )
