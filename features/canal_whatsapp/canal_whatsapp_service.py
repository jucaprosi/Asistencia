# ¤canal-whatsapp
# ¤¤integration-engineer
"""Compuerta pública de la sala canal_whatsapp para Meta WhatsApp Cloud API (RF-GW-01..06).

Recepción y verificación por webhook, ingesta durable, ventana de 24 h, envío con reintentos,
plantillas del catálogo y gestión de medios.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from features.canal_whatsapp.enrutamiento_canal_internal import (
    EnrutadorCanal,
    PLANTILLA_COMISION_VALIDADA,
    clasificar_canal as clasificar_canal_fn,
)
from features.canal_whatsapp.envio_internal import GestorEnvio
from features.canal_whatsapp.medios_internal import AlmacenamientoMedios, GestorMedios
from features.canal_whatsapp.persistencia_internal import RepositorioCanal
from features.canal_whatsapp.tipos import (
    ApiMetaNoDisponible, Boton, Canal, ErrorCanalWhatsapp, EventoEntrante,
    FirmaInvalida, FueraDeVentana, MedioMeta, MedioNoPermitido, MensajeDuplicado,
    MensajeEntrante, MensajeMeta, MensajeSaliente, OpcionLista, Plantilla,
    PlantillaMeta, PlantillaNoAprobada, ResultadoEnvio, TipoContenido,
    VariablesPlantillaInvalidas,
)
from features.canal_whatsapp.trabajador_internal import TrabajadorIngesta
from features.canal_whatsapp.webhook_internal import (
    convertir_mensaje_meta, parsear_payload_webhook, validar_firma_webhook,
    verificar_desafio,
)

__all__ = [
    "Canal", "TipoContenido", "MensajeEntrante", "Boton", "OpcionLista", "MensajeSaliente",
    "Plantilla", "ResultadoEnvio", "EventoEntrante", "MensajeMeta", "MedioMeta", "PlantillaMeta",
    "ErrorCanalWhatsapp", "FirmaInvalida", "MensajeDuplicado", "FueraDeVentana",
    "PlantillaNoAprobada", "VariablesPlantillaInvalidas", "ApiMetaNoDisponible", "MedioNoPermitido",
    "EnrutadorCanal", "PLANTILLA_COMISION_VALIDADA", "clasificar_canal_fn",
    "CanalWhatsappService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_canal_whatsapp.yaml")
Receptor = Callable[[MensajeEntrante], Any]


# ¤canal-whatsapp
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    """Lee ``config_canal_whatsapp.yaml``; los secretos ``${VAR}`` los resuelve el pasillo central."""
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤canal-whatsapp
def _tipo_meta_a_sql(tipo_raw: str) -> str:
    tipo_l = tipo_raw.lower()
    if tipo_l in {"text", "texto"}:
        return "texto"
    if tipo_l in {"image", "audio", "document", "video", "medio", "imagen", "documento"}:
        return "medio"
    if tipo_l in {"button", "interactive", "boton", "lista"}:
        return "boton"
    if tipo_l in {"location", "ubicacion"}:
        return "ubicacion"
    if tipo_l in {"template", "plantilla"}:
        return "plantilla"
    return "texto"


# ¤canal-whatsapp
class CanalWhatsappService:
    """Compuerta de la sala canal_whatsapp que conecta con la Meta WhatsApp Cloud API oficial."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any = None,
        observabilidad: Any = None,
        cliente_http: Any = None,
        repositorio: RepositorioCanal | None = None,
        almacenamiento: AlmacenamientoMedios | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._config = dict(config)
        self._seguridad = seguridad
        self._observabilidad = observabilidad
        self._receptores: dict[Canal, Receptor] = {}

        self._verify_token = str(self._resolver_env(self._config.get("verify_token", "")))
        self._secreto_app = str(self._resolver_env(self._config.get("secreto_app", "")))
        self._ventana_horas = float(self._config.get("ventana_servicio_horas", 24))

        self._repositorio = repositorio or RepositorioCanal()
        self._almacenamiento = almacenamiento or AlmacenamientoMedios(
            bucket=str(self._resolver_env(self._config.get("medios", {}).get("bucket", "glamping-medios"))),
            prefijo=self._config.get("medios", {}).get("prefijo", "whatsapp/"),
        )
        self._gestor_medios = GestorMedios(self._almacenamiento, self._config.get("medios"))
        self._cliente_meta = cliente_http
        self._gestor_envio = GestorEnvio(
            self._config,
            self._repositorio,
            self._cliente_meta,
            observabilidad=self._observabilidad,
            sleep_fn=sleep_fn,
        )

        canal_vendedores_cfg = self._config.get("canal_vendedores", {})
        modo_vendedores = str(self._resolver_env(canal_vendedores_cfg.get("modo", "uno_a_uno")))
        grupo_id_vendedores = self._resolver_env(canal_vendedores_cfg.get("grupo_id", None))
        if not grupo_id_vendedores:
            grupo_id_vendedores = None
        else:
            grupo_id_vendedores = str(grupo_id_vendedores)

        self._enrutador = EnrutadorCanal(
            modo=modo_vendedores,
            grupo_id=grupo_id_vendedores,
            seguridad=self._seguridad,
            observabilidad=self._observabilidad,
        )

        ingesta_cfg = self._config.get("ingesta", {})
        self._trabajador = TrabajadorIngesta(
            self._repositorio,
            observabilidad=self._observabilidad,
            max_reintentos=int(ingesta_cfg.get("reintentos_evento", 5)),
            agrupacion_segundos=int(ingesta_cfg.get("agrupacion_segundos", 3)),
            clasificador_canal=self.clasificar_canal,
            enrutador=self._enrutador,
        )

        self._sembrar_plantillas()

    def _resolver_env(self, valor: Any) -> Any:
        if isinstance(valor, str) and valor.startswith("${") and valor.endswith("}"):
            interior = valor[2:-1]
            if ":-" in interior:
                nombre, defecto = interior.split(":-", 1)
                return os.environ.get(nombre, defecto)
            return os.environ.get(interior, "")
        return valor

    def _sembrar_plantillas(self) -> None:
        plantillas_cfg = self._config.get("plantillas", [])
        for p in plantillas_cfg:
            self._repositorio.guardar_plantilla(
                nombre=p["nombre"],
                categoria=p.get("categoria", "utility"),
                variables=p.get("variables", []),
                idioma=p.get("idioma", "es"),
                aprobada=p.get("aprobada", False),
            )

    @property
    def repositorio(self) -> RepositorioCanal:
        return self._repositorio

    @property
    def trabajador(self) -> TrabajadorIngesta:
        return self._trabajador

    def aprobar_plantilla(self, nombre: str, aprobada: bool = True) -> None:
        """Permite aprobar o desaprobar una plantilla en el catálogo de persistencia."""
        self._repositorio.aprobar_plantilla(nombre, aprobada)

    def registrar_receptor(self, canal: Canal, receptor: Receptor) -> None:
        """El pasillo central enlaza aquí al agente (huéspedes) y al ARM (vendedores). Un receptor por canal."""
        if canal in self._receptores:
            raise ErrorCanalWhatsapp("RECEPTOR_DUPLICADO", "Canal ya enlazado", f"canal={canal.value}")
        self._receptores[canal] = receptor

    def receptores(self) -> Mapping[Canal, Receptor]:
        return dict(self._receptores)

    def verificar_webhook(self, modo: str, token: str, desafio: str) -> str | None:
        """RF-GW-01 (a): Responde con hub.challenge si las credenciales de suscripción coinciden."""
        return verificar_desafio(modo, token, desafio, self._verify_token)

    def recibir(self, cuerpo: bytes, firma_sha256: str) -> list[MensajeEntrante]:
        """RF-GW-01 (b-d) y RF-GW-07: Valida firma HMAC, persiste evento durablemente y deduplica."""
        validar_firma_webhook(cuerpo, firma_sha256, self._secreto_app)

        mensajes_raw, estados_raw = parsear_payload_webhook(cuerpo)

        for st in estados_raw:
            mensaje_id = st.get("id")
            estado = st.get("status")
            if mensaje_id and estado:
                self.actualizar_estado(mensaje_id, estado)

        mensajes_procesados: list[MensajeEntrante] = []
        for rm in mensajes_raw:
            mensaje_id = rm.get("id")
            remitente = rm.get("from")
            if not mensaje_id or not remitente:
                continue

            insertado = self._repositorio.guardar_evento(
                mensaje_id=mensaje_id,
                conversacion_clave=remitente,
                cuerpo_cifrado=cuerpo,
                estado="pendiente",
            )
            if not insertado:
                # Duplicado de Meta: respondio_200 de forma idempotente sin re-procesar
                continue

            grupo_id = rm.get("group_id") or rm.get("chat_id") or rm.get("grupo_id")
            canal = self.clasificar_canal(remitente, grupo_id)
            tipo_sql = _tipo_meta_a_sql(rm.get("type", "texto"))
            self._repositorio.guardar_mensaje_meta(
                mensaje_id=mensaje_id,
                direccion="in",
                remitente_token=remitente,
                canal=canal,
                tipo=tipo_sql,
                estado="recibido",
            )
            msg_entrante = convertir_mensaje_meta(rm, canal)
            mensajes_procesados.append(msg_entrante)

        return mensajes_procesados

    def clasificar_canal(self, remitente: str, grupo_id: str | None = None) -> Canal:
        """Clasifica si el mensaje pertenece al canal de huéspedes o de vendedores (RF-GW-06)."""
        return self._enrutador.clasificar_canal(remitente, grupo_id)

    def registrar_vendedor(self, remitente: str) -> None:
        """Registra un remitente como vendedor para el enrutamiento 1:1."""
        self._enrutador.registrar_vendedor(remitente)

    def despachar(self, mensaje: MensajeEntrante) -> Any:
        """Despacha un mensaje entrante a su receptor correspondiente asegurando mamparos (RF-GW-06)."""
        return self._enrutador.despachar(mensaje, self._receptores)

    def en_ventana_24h(self, destinatario: str) -> bool:
        """RF-GW-03: Verifica si han transcurrido menos de 24 horas desde el último mensaje del usuario."""
        ultimo = self._repositorio.ultimo_mensaje_entrante(destinatario)
        if ultimo is None:
            return False
        ahora = datetime.now(timezone.utc)
        delta_horas = (ahora - ultimo).total_seconds() / 3600.0
        return delta_horas < self._ventana_horas

    def enviar(self, mensaje: MensajeSaliente) -> ResultadoEnvio:
        """RF-GW-02, RF-GW-03: Envía mensaje libre respetando la ventana de 24 horas."""
        en_ventana = self.en_ventana_24h(mensaje.destinatario)
        canal = self.clasificar_canal(mensaje.destinatario, None)
        return self._gestor_envio.enviar_mensaje(mensaje, en_ventana=en_ventana, canal=canal)

    def enviar_plantilla(self, destinatario: str, plantilla: Plantilla) -> ResultadoEnvio:
        """RF-GW-04: Envía una plantilla aprobada con validación estricta de variables."""
        canal = self.clasificar_canal(destinatario, None)
        return self._gestor_envio.enviar_plantilla(destinatario, plantilla, canal=canal)

    def actualizar_estado(self, mensaje_id: str, estado: str) -> None:
        """RF-GW-02 (a): Actualiza el estado (sent, delivered, read, failed) del mensaje."""
        self._repositorio.actualizar_estado_mensaje(mensaje_id, estado)

    def descargar_medio(
        self, medio_id: str, remitente: str | None = None, mensaje_id: str | None = None
    ) -> str:
        """RF-GW-05: Descarga un medio respetando bloqueo de seguridad y devuelve medio_ref (nunca bytes).

        ``mensaje_id`` enlaza el medio con su mensaje en ``canal.mensajes_meta``; sin él el medio queda sin
        mensaje asociado (la clave foránea no admite un identificador inventado).
        """
        medio = self._repositorio.obtener_medio(medio_id)
        if medio:
            return medio.medio_ref

        return self._gestor_medios.descargar_medio(
            medio_id,
            mensaje_id=mensaje_id,
            remitente=remitente,
            cliente_meta=self._cliente_meta,
            repositorio=self._repositorio,
            seguridad=self._seguridad,
            observabilidad=self._observabilidad,
        )

    def procesar_ingesta(self) -> int:
        """Dispara el procesamiento de eventos pendientes en segundo plano."""
        return self._trabajador.procesar_pendientes(self._receptores)

    def recuperar_caidas(self) -> int:
        """Recupera eventos que quedaron en estado procesando tras una caída del servicio."""
        return self._trabajador.recuperar_caidas()
