# ¤pasillo-central
# ¤¤solutions-architect
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
from features.herramientas_glamping.herramientas_glamping_service import cargar_config as cargar_config_herramientas
from features.observabilidad.observabilidad_service import ObservabilidadService
from features.observabilidad.observabilidad_service import cargar_config as cargar_config_observabilidad
from features.panel_operativo.panel_operativo_service import PanelOperativoService
from features.panel_operativo.panel_operativo_service import cargar_config as cargar_config_panel
from features.web_huespedes.web_huespedes_service import WebHuespedesService
from features.web_huespedes.web_huespedes_service import cargar_config as cargar_config_web
from features.pms_conector.pms_conector_service import PMSConectorService
from features.pms_conector.pms_conector_service import cargar_config as cargar_config_pms
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
    agente: AgenteService
    panel: PanelOperativoService
    web: WebHuespedesService


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
def construir(ruta_config: Path = RUTA_CONFIG, entorno: Mapping[str, str] | None = None) -> Contenedor:
    """Construye las compuertas en el orden declarado y registra los receptores del canal."""
    env = dict(os.environ if entorno is None else entorno)
    config_app = resolver_secretos(cargar_config_app(ruta_config), env)

    def _config(cargador: Any) -> Mapping[str, Any]:
        return resolver_secretos(cargador(), env)

    observabilidad = ObservabilidadService(_config(cargar_config_observabilidad))
    seguridad = SeguridadService(_config(cargar_config_seguridad), observabilidad=observabilidad)
    conocimiento = ConocimientoService(_config(cargar_config_conocimiento), observabilidad=observabilidad)
    pms = PMSConectorService(_config(cargar_config_pms), observabilidad=observabilidad)
    crm = CRMConectorService(_config(cargar_config_crm), observabilidad=observabilidad)
    comisiones = ComisionesService(_config(cargar_config_comisiones), seguridad=seguridad, observabilidad=observabilidad)
    canal = CanalWhatsappService(_config(cargar_config_canal), seguridad=seguridad, observabilidad=observabilidad)
    arm = ArmJarvisService(
        _config(cargar_config_arm), seguridad=seguridad, comisiones=comisiones, crm=crm, canal=canal,
        observabilidad=observabilidad,
    )
    herramientas = HerramientasGlampingService(
        _config(cargar_config_herramientas), seguridad=seguridad, pms=pms, conocimiento=conocimiento, crm=crm,
        arm=arm, comisiones=comisiones, observabilidad=observabilidad,
    )
    agente = AgenteService(
        _config(cargar_config_agente), seguridad=seguridad, herramientas=herramientas, conocimiento=conocimiento,
        canal=canal, observabilidad=observabilidad,
    )
    panel = PanelOperativoService(
        _config(cargar_config_panel), seguridad=seguridad, arm=arm, comisiones=comisiones, agente=agente,
        canal=canal, crm=crm, pms=pms, conocimiento=conocimiento, observabilidad=observabilidad,
    )

    canal.registrar_receptor(Canal.HUESPEDES, agente.atender)
    canal.registrar_receptor(Canal.VENDEDORES, arm.procesar)

    return Contenedor(
        config_app=config_app, observabilidad=observabilidad, seguridad=seguridad, conocimiento=conocimiento,
        pms=pms, crm=crm, comisiones=comisiones, canal=canal, arm=arm, herramientas=herramientas, agente=agente,
        panel=panel,
        web=WebHuespedesService(_config(cargar_config_web), pms=pms, observabilidad=observabilidad),
    )
