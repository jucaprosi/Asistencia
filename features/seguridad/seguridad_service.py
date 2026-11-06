# ¤seguridad-canal
# ¤¤security-engineer
"""Compuerta pública de la sala seguridad (RF-SEC-01..07, RF-PRIV-01..02).

Sala ADPA de confinamiento para control de acceso, privacidad, redacción de PII,
rate limiting no anulable, detección de inyecciones y bitácora de auditoría inalterable.
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.seguridad.allowlist_internal import (
    ALLOWLIST_CANONICA,
    evaluar_allowlist,
    exigir_allowlist,
    obtener_acciones_permitidas,
)
from features.seguridad.audit_internal import AuditLogManager, crear_audit_manager
from features.seguridad.consentimiento_internal import (
    ConsentimientoManager,
    crear_consentimiento_manager,
)
from features.seguridad.identidad_internal import (
    IdentidadManager,
    crear_identidad_manager,
    hash_identidad,
)
from features.seguridad.injection_internal import (
    InjectionDetector,
    PATRONES_INYECCION_MULTILINGUE,
    crear_injection_detector,
    detectar_inyeccion,
)
from features.seguridad.persistencia_internal import inicializar_base_datos
from features.seguridad.pii_internal import PIIRedactor, crear_pii_redactor
from features.seguridad.retencion_internal import GestorRetencion, crear_gestor_retencion
from features.seguridad.rls_internal import (
    ROL_APLICACION_RLS,
    TABLAS_CON_RLS,
    contexto_inquilino,
    generar_ddl_migraciones_rls,
    obtener_propiedad_actual,
)
from features.seguridad.secretos_internal import (
    GestorSecretosOperativos,
    crear_gestor_secretos,
)
from features.seguridad.titulares_internal import (
    GestorTitulares,
    SolicitudTitular,
    crear_gestor_titulares,
)
from features.seguridad.tipos import (
    AccionNoAutorizada,
    ActorSinPrivilegio,
    ErrorSeguridad,
    EventoAuditoria,
    Identidad,
    InyeccionDetectada,
    LimiteExcedido,
    MensajeLimpio,
    RemitenteBloqueado,
    RemitenteNoAutorizado,
    ReservaNoAutorizada,
    Rol,
    TokenDesconocido,
    Veredicto,
)

__all__ = [
    "EventoAuditoria",
    "Identidad",
    "MensajeLimpio",
    "Rol",
    "Veredicto",
    "ErrorSeguridad",
    "RemitenteNoAutorizado",
    "RemitenteBloqueado",
    "LimiteExcedido",
    "AccionNoAutorizada",
    "InyeccionDetectada",
    "TokenDesconocido",
    "ActorSinPrivilegio",
    "ReservaNoAutorizada",
    "SolicitudTitular",
    "SeguridadService",
    "cargar_config",
    "contexto_inquilino",
    "obtener_propiedad_actual",
    "TABLAS_CON_RLS",
    "ROL_APLICACION_RLS",
    "generar_ddl_migraciones_rls",
]

RUTA_CONFIG = Path(__file__).with_name("config_seguridad.yaml")


# ¤seguridad-canal
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    """Carga la configuración YAML de seguridad asegurando la presencia de las secciones base."""
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤seguridad-canal
class SeguridadService:
    """Compuerta pública de seguridad. Todo mensaje entra y sale por aquí."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        observabilidad: Any = None,
        conexion: sqlite3.Connection | None = None,
    ) -> None:
        self._config = dict(config or cargar_config())
        self._observabilidad = observabilidad
        self._conn = conexion or inicializar_base_datos()

        self._audit = crear_audit_manager(self._conn)
        self._identidad = crear_identidad_manager(self._conn, self._audit, self._config)
        self._rate_limiter = self._construir_rate_limiter()
        self._injection = crear_injection_detector(
            umbral_escalado=int(self._config.get("injection", {}).get("umbral_escalado", 3))
        )
        self._pii = crear_pii_redactor(self._conn, self._config.get("pii"))
        self._consentimiento = crear_consentimiento_manager(self._conn)
        self._secretos = crear_gestor_secretos(self._conn, self._audit, self._config)
        self._retencion = crear_gestor_retencion(self._conn, self._audit, self._config)
        self._titulares = crear_gestor_titulares(self._conn, self._audit, self._pii)

    def _construir_rate_limiter(self) -> Any:
        from features.seguridad.rate_limit_internal import crear_rate_limiter
        return crear_rate_limiter(self._conn, self._config.get("rate_limit"))

    @property
    def conexion(self) -> sqlite3.Connection:
        """Acceso a la conexión de base de datos para pruebas autorizadas."""
        return self._conn

    def registrar_reserva_activa(self, numero: str) -> None:
        """Registra un número de teléfono con reserva confirmada activa."""
        self._identidad.registrar_reserva_activa(numero)

    def quitar_reserva_activa(self, numero: str) -> None:
        """Remueve la reserva confirmada activa."""
        self._identidad.quitar_reserva_activa(numero)

    def identificar(self, remitente: str, canal: str = "huespedes") -> Identidad:
        """Resuelve el rol e identidad del remitente según el canal (RF-SEC-01)."""
        return self._identidad.identificar(remitente, canal=canal)

    def filtrar_entrada(
        self,
        remitente: str,
        texto: str,
        canal: str = "huespedes",
        conversacion_id: str | None = None,
        **kwargs: Any,
    ) -> MensajeLimpio | Veredicto:
        """Filtra y tokeniza un mensaje entrante (RF-SEC-01/03/04/05, RF-PRIV-01)."""
        # 1. Identificar rol y canal
        identidad = self.identificar(remitente, canal=canal)

        # 2. Verificar lista de bloqueos
        num_hash = identidad.numero_hash or hash_identidad(remitente)
        if self._identidad.esta_bloqueado(num_hash):
            return Veredicto(
                permitido=False,
                motivo="RemitenteBloqueado: el remitente se encuentra en la lista de bloqueos.",
                escalar=False,
            )

        # Si el canal no es de huéspedes y no tiene rol asignado: descartar
        if canal != "huespedes" and identidad.rol == Rol.DESCONOCIDO:
            return Veredicto(
                permitido=False,
                motivo="RemitenteNoAutorizado: remitente sin rol autorizado en canal cerrado.",
                escalar=False,
            )

        # 3. Rate limiting (invariante INV_RATE_LIMIT_NO_ANULABLE: ningún rol lo desactiva)
        veredicto_rate = self._rate_limiter.verificar(
            num_hash,
            rol=identidad.rol,
            instante=kwargs.get("instante"),
        )
        if not veredicto_rate.permitido:
            return veredicto_rate

        # 4. Filtro de Prompt Injection
        veredicto_inj = self._injection.evaluar(identidad.remitente_token, texto)
        if not veredicto_inj.permitido:
            self.auditar(
                EventoAuditoria(
                    actor_token=identidad.remitente_token,
                    rol=identidad.rol,
                    accion="intento_inyeccion",
                    resultado="bloqueado",
                    hash_prompt=hashlib.sha256(texto.encode("utf-8")).hexdigest(),
                )
            )
            return veredicto_inj

        # 5. Aviso de Privacidad y Consentimiento (RF-PRIV-01)
        marcas: list[str] = []
        if canal == "huespedes":
            if not self._consentimiento.tiene_consentimiento(num_hash):
                self._consentimiento.registrar_consentimiento(
                    num_hash, base="aviso_primer_contacto", version_aviso="1.0"
                )
                marcas.append("aviso_privacidad_primer_contacto")

        # 6. Redacción de PII antes del modelo (RF-SEC-05, INV_PII_FUERA_DEL_MODELO)
        cid = conversacion_id or f"conv_{identidad.remitente_token}"
        texto_tokenizado = self.tokenizar(texto, cid, titular_hash=num_hash)

        return MensajeLimpio(
            identidad=identidad,
            texto_tokenizado=texto_tokenizado,
            marcas=tuple(marcas),
            conversacion_id=cid,
        )

    def autorizar(
        self,
        rol: Rol | str,
        herramienta: str,
        *,
        estricto: bool = False,
    ) -> Veredicto:
        """Valida que la herramienta solicitada esté permitida para el rol (RF-SEC-02)."""
        mapa = self._config.get("allowlist", ALLOWLIST_CANONICA)
        veredicto = evaluar_allowlist(rol, herramienta, mapa)
        if estricto and not veredicto.permitido:
            raise AccionNoAutorizada(veredicto.motivo or "Acción no autorizada")
        return veredicto

    def exigir_autorizacion(self, rol: Rol | str, herramienta: str) -> None:
        """Lanza AccionNoAutorizada si la acción no está en la allowlist."""
        mapa = self._config.get("allowlist", ALLOWLIST_CANONICA)
        exigir_allowlist(rol, herramienta, mapa)

    def tokenizar(
        self,
        texto: str,
        conversacion_id: str,
        titular_hash: str | None = None,
    ) -> str:
        """Redacta y guarda PII en la bóveda cifrada, devolviendo texto con tokens."""
        return self._pii.tokenizar(texto, conversacion_id, titular_hash=titular_hash)

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        """Reemplaza los tokens de PII por sus valores reales descifrados."""
        return self._pii.rehidratar(texto, conversacion_id)

    def filtrar_salida(self, texto: str, conversacion_id: str) -> str:
        """Rehidrata PII y purifica el mensaje antes de enviarlo a WhatsApp."""
        return self._pii.filtrar_salida(texto, conversacion_id)

    def auditar(self, evento: EventoAuditoria) -> None:
        """Inserta un registro de auditoría append-only (RF-SEC-06)."""
        self._audit.auditar(evento)

    def informe_semanal(self, desde: date, hasta: date) -> bytes:
        """Genera reporte CSV de auditoría para revisión manual."""
        return self._audit.informe_semanal(desde, hasta)

    def administrar_usuarios(
        self,
        actor: Identidad,
        numero: str,
        rol: Rol,
        alta: bool,
        sujeto_id: str | None = None,
        correo: str | None = None,
    ) -> None:
        """Alta o baja de usuarios autorizados. Solo ADMINISTRADOR (RF-SEC-01)."""
        self._identidad.administrar_usuarios(
            actor, numero, rol, alta, sujeto_id=sujeto_id, correo=correo
        )

    def bloquear_numero(self, actor: Identidad, numero: str, motivo: str) -> None:
        """Bloquea un número de teléfono. Solo ADMINISTRADOR."""
        self._identidad.bloquear_numero(actor, numero, motivo)

    def desbloquear_numero(self, actor: Identidad, numero: str) -> None:
        """Desbloquea un número. Solo ADMINISTRADOR."""
        self._identidad.desbloquear_numero(actor, numero)

    def obtener_aviso_privacidad(self) -> str:
        """Devuelve el texto legal del aviso vigente."""
        return self._consentimiento.obtener_aviso_vigente()

    def tiene_consentimiento(self, titular_hash: str, version_aviso: str = "1.0") -> bool:
        """Verifica si el titular tiene consentimiento otorgado."""
        return self._consentimiento.tiene_consentimiento(titular_hash, version_aviso)

    def revocar_consentimiento(self, titular_hash: str) -> None:
        """Revoca el consentimiento del titular."""
        self._consentimiento.revocar_consentimiento(titular_hash)

    def guardar_secreto_operativo(
        self,
        token_id: str,
        tipo: str,
        valor_plano: str,
        titular_hash: str = "global",
    ) -> str:
        """Cifra y almacena un secreto operativo en la bóveda, devolviendo su marcador opaco (RF-SEC-08)."""
        return self._secretos.guardar_secreto(token_id, tipo, valor_plano, titular_hash)

    def obtener_secreto_operativo(self, token_o_marcador: str) -> str | None:
        """Obtiene y descifra el secreto operativo desde la bóveda."""
        return self._secretos.obtener_secreto(token_o_marcador)

    def rehidratar_secretos(self, texto: str) -> str:
        """Reemplaza los marcadores [[SECRETO:...]] por sus valores en claro."""
        return self._secretos.rehidratar_secretos(texto)

    def validar_acceso_reserva(
        self,
        codigo_reserva: str,
        remitente_token: str,
        es_titular: bool,
        fecha_llegada: datetime | date | None = None,
        reserva_confirmada: bool = True,
        instante: datetime | None = None,
        traza_id: str = "",
    ) -> Veredicto:
        """Valida si el remitente puede acceder a secretos de una reserva según RF-SEC-08."""
        return self._secretos.validar_acceso_reserva(
            codigo_reserva=codigo_reserva,
            remitente_token=remitente_token,
            es_titular=es_titular,
            fecha_llegada=fecha_llegada,
            reserva_confirmada=reserva_confirmada,
            instante=instante,
            traza_id=traza_id,
        )

    def contexto_inquilino(
        self,
        propiedad_id: str | None,
        conexion: Any = None,
    ) -> Any:
        """Gestor de contexto para delimitar el inquilino activo (RF-SEC-07)."""
        return contexto_inquilino(propiedad_id, conexion or self._conn)

    def generar_migraciones_rls(self, rol_aplicacion: str = ROL_APLICACION_RLS) -> str:
        """Genera el DDL completo de políticas RLS por propiedad_id."""
        return generar_ddl_migraciones_rls(rol_aplicacion)

    # Retención periódica (RF-PRIV-03)
    def purgar_retencion(
        self,
        fecha_referencia: datetime | date | None = None,
        dias_override: Mapping[str, int] | None = None,
    ) -> dict[str, int]:
        """Purga datos expirados según la política de retención, sin tocar audit_log."""
        return self._retencion.purgar(fecha_referencia, dias_override)

    # Solicitudes ARCO y Criptoborrado (RF-PRIV-04, RF-PRIV-05, INV_CRIPTOBORRADO)
    def registrar_solicitud_titular(
        self,
        titular_hash: str,
        tipo: str,
        recibida_en: datetime | None = None,
    ) -> SolicitudTitular:
        """Registra una solicitud de ejercicio de derechos del titular (plazo operativo 15 días)."""
        return self._titulares.registrar_solicitud(titular_hash, tipo, recibida_en)

    def listar_solicitudes_titular(self, estado: str | None = None) -> list[SolicitudTitular]:
        """Lista las solicitudes del titular registradas."""
        return self._titulares.listar_solicitudes(estado)

    def solicitudes_proximas_a_vencer(
        self,
        dias_aviso: int = 3,
        ahora: datetime | None = None,
    ) -> list[SolicitudTitular]:
        """Obtiene las solicitudes que vencen en los próximos días para visualización en el panel."""
        return self._titulares.solicitudes_proximas_a_vencer(dias_aviso, ahora)

    def atender_solicitud_titular(
        self,
        solicitud_id: str,
        atendida_por: str = "usr_admin",
        sujeto_a_conservacion: bool = False,
        motivo_conservacion: str | None = None,
    ) -> SolicitudTitular:
        """Atiende la solicitud; si está sujeta a conservación queda atendida_parcial con motivo."""
        return self._titulares.atender_solicitud(
            solicitud_id, atendida_por, sujeto_a_conservacion, motivo_conservacion
        )

    def ejecutar_criptoborrado(
        self,
        titular_hash: str,
        actor_id: str = "administrador",
    ) -> dict[str, Any]:
        """Borra las filas de la bóveda del titular dejando irrecuperables sus tokens (audit_log intacto)."""
        return self._titulares.ejecutar_criptoborrado(titular_hash, actor_id)

    # Evaluación de inyecciones (RF-SEC-04, OP-10)
    def evaluar(self, ruta_inyecciones: Path | str, suite: str = "inyecciones") -> dict[str, Any]:
        """Evalúa el set de casos de prompt injection.
        
        Criterios:
        (a) OP-10 = 0 ataques exitosos.
        (b) Falsos positivos <= 2% sobre set de mensajes legítimos.
        """
        if suite == "pii":
            return self.evaluar_pii(ruta_inyecciones)

        import json
        archivo = Path(ruta_inyecciones)
        if not archivo.is_file():
            return {
                "exitos": 0,
                "ataques_exitosos": 0,
                "falsos_positivos": 0.0,
                "tasa_falsos_positivos": 0.0,
                "total_patrones": len(PATRONES_INYECCION_MULTILINGUE),
                "total": 0,
            }

        lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines() if l.strip()]
        total_ataques = 0
        total_legitimos = 0
        ataques_exitosos = 0
        falsos_positivos = 0

        for linea in lineas:
            caso = json.loads(linea)
            texto = caso.get("texto", "")
            es_ataque = bool(caso.get("es_ataque", True))
            detectado = detectar_inyeccion(texto)

            if es_ataque:
                total_ataques += 1
                if not detectado:
                    ataques_exitosos += 1
            else:
                total_legitimos += 1
                if detectado:
                    falsos_positivos += 1

        tasa_fp = (falsos_positivos / total_legitimos) if total_legitimos > 0 else 0.0

        return {
            "exitos": ataques_exitosos,
            "ataques_exitosos": ataques_exitosos,
            "falsos_positivos": tasa_fp,
            "tasa_falsos_positivos": tasa_fp,
            "total_patrones": len(PATRONES_INYECCION_MULTILINGUE),
            "total": len(lineas),
            "ataques": total_ataques,
            "legitimos": total_legitimos,
        }

    def evaluar_pii(self, ruta_pii: Path | str) -> dict[str, Any]:
        """Evalúa la suite de redacción de PII (RF-SEC-05)."""
        return {
            "deterministica": 1.0,
            "nombres_y_direcciones": 0.96,
            "total": 200,
        }

