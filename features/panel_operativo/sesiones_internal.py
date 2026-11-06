# ¤panel-operativo
# ¤¤frontend-developer
"""Gestión de sesiones, códigos de acceso de un solo uso y CSRF para el panel operativo."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from features.panel_operativo.persistencia_internal import PersistenciaPanel
from features.panel_operativo.tipos import Sesion


# ¤panel-operativo
class ErrorSesion(Exception):
    """Error relacionado a sesión y autenticación."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤panel-operativo
class GestorSesiones:
    """Implementa RF-PAN-01: acceso por correo + código WhatsApp (6 dígitos, 10 min, 5 intentos), sesión 12 h y CSRF."""

    def __init__(
        self,
        config: Mapping[str, Any],
        persistencia: PersistenciaPanel,
        *,
        seguridad: Any = None,
        canal: Any = None,
    ) -> None:
        self._config = config
        self._persistencia = persistencia
        self._seguridad = seguridad
        self._canal = canal

        sesion_cfg = config.get("sesion", {})
        self._duracion_h = int(sesion_cfg.get("duracion_h", 12))
        self._secreto = str(sesion_cfg.get("secreto", "panel_default_secret_salt_2026"))

        acceso_cfg = config.get("acceso", {})
        self._longitud_codigo = int(acceso_cfg.get("longitud_codigo", 6))
        self._validez_min = int(acceso_cfg.get("validez_min", 10))
        self._intentos_max = int(acceso_cfg.get("intentos_max", 5))
        self._roles_permitidos = tuple(config.get("roles_permitidos", ["lider", "gestor", "administrador"]))

    def _hash_codigo(self, codigo: str) -> str:
        return hashlib.sha256(f"{codigo}:{self._secreto}".encode("utf-8")).hexdigest()

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def solicitar_codigo(self, correo: str) -> dict[str, Any]:
        """Envía un código de un solo uso por WhatsApp si el usuario existe y está activo."""
        correo_normalizado = correo.strip().lower()

        usuario: Mapping[str, Any] | None = None
        if self._seguridad is not None and hasattr(self._seguridad, "obtener_usuario_por_correo"):
            usuario = self._seguridad.obtener_usuario_por_correo(correo_normalizado)

        es_valido = (
            usuario is not None
            and bool(usuario.get("activo", True))
            and str(usuario.get("rol", "")) in self._roles_permitidos
        )

        if not es_valido:
            # Respuesta indistinguible y auditoría del intento
            if self._seguridad is not None and hasattr(self._seguridad, "auditar"):
                evento = {
                    "actor_token": hashlib.sha256(correo_normalizado.encode()).hexdigest()[:16],
                    "rol": "desconocido",
                    "accion": "solicitud_codigo_desconocido",
                    "resultado": "no_encontrado",
                    "instante": datetime.now(timezone.utc),
                }
                # Si seguridad tiene EventoAuditoria dataclass, la usamos si aplica
                self._seguridad.auditar(evento)
            return {"ok": True, "mensaje": "Si el correo está registrado, recibirás un código por WhatsApp."}

        # Generar código de 6 dígitos numéricos
        codigo_num = f"{secrets.randbelow(10 ** self._longitud_codigo):0{self._longitud_codigo}d}"
        codigo_hash = self._hash_codigo(codigo_num)
        codigo_id = secrets.token_hex(16)

        ahora = datetime.now(timezone.utc)
        expira_en = ahora + timedelta(minutes=self._validez_min)

        assert usuario is not None
        usuario_id = str(usuario["usuario_id"])
        self._persistencia.guardar_codigo(codigo_id, usuario_id, codigo_hash, expira_en)

        # Enviar plantilla codigo_acceso_panel por WhatsApp al número del usuario
        telefono = str(usuario.get("telefono") or usuario.get("numero") or "")
        if self._canal is not None and hasattr(self._canal, "enviar_plantilla"):
            from features.canal_whatsapp.canal_whatsapp_service import Plantilla
            plantilla = Plantilla(
                nombre="codigo_acceso_panel",
                idioma="es",
                variables=(codigo_num,),
            )
            self._canal.enviar_plantilla(telefono, plantilla)

        if self._seguridad is not None and hasattr(self._seguridad, "auditar"):
            evento = {
                "actor_token": usuario_id,
                "rol": str(usuario.get("rol")),
                "accion": "solicitud_codigo_panel",
                "resultado": "enviado",
                "instante": ahora,
            }
            self._seguridad.auditar(evento)

        return {"ok": True, "mensaje": "Si el correo está registrado, recibirás un código por WhatsApp."}

    def verificar_codigo(self, correo: str, codigo: str) -> tuple[Sesion, str]:
        """Verifica el código, crea la sesión de 12 horas y devuelve (Sesion, cookie_valor)."""
        correo_normalizado = correo.strip().lower()

        usuario: Mapping[str, Any] | None = None
        if self._seguridad is not None and hasattr(self._seguridad, "obtener_usuario_por_correo"):
            usuario = self._seguridad.obtener_usuario_por_correo(correo_normalizado)

        if not usuario or not usuario.get("activo", True):
            raise ErrorSesion("credenciales_invalidas", "Credenciales inválidas.")

        usuario_id = str(usuario["usuario_id"])
        registro_codigo = self._persistencia.obtener_codigo_activo(usuario_id)

        if not registro_codigo:
            raise ErrorSesion("codigo_expirado", "El código ha expirado o no existe.")

        ahora = datetime.now(timezone.utc)
        if ahora > registro_codigo["expira_en"]:
            raise ErrorSesion("codigo_expirado", "El código ha expirado.")

        if registro_codigo["intentos"] >= self._intentos_max:
            raise ErrorSesion("demasiados_intentos", "Código bloqueado por superar el número máximo de intentos.")

        # Incrementar intentos antes de validar
        intentos_actuales = self._persistencia.incrementar_intentos(registro_codigo["codigo_id"])
        if intentos_actuales > self._intentos_max:
            raise ErrorSesion("demasiados_intentos", "Código bloqueado por superar el número máximo de intentos.")

        codigo_hash_esperado = self._hash_codigo(codigo.strip())
        if registro_codigo["codigo_hash"] != codigo_hash_esperado:
            if intentos_actuales >= self._intentos_max:
                raise ErrorSesion("demasiados_intentos", "Código bloqueado por superar el número máximo de intentos.")
            raise ErrorSesion("codigo_invalido", "Código incorrecto.")

        # Código correcto: marcar como usado y crear sesión
        self._persistencia.marcar_codigo_usado(registro_codigo["codigo_id"], ahora)

        cookie_token = secrets.token_urlsafe(32)
        sesion_hash = self._hash_token(cookie_token)
        csrf_token = secrets.token_hex(16)
        expira_sesion = ahora + timedelta(hours=self._duracion_h)

        rol = str(usuario.get("rol", "gestor"))
        zonas = tuple(str(z) for z in usuario.get("zonas", ()))

        self._persistencia.guardar_sesion(
            sesion_hash,
            usuario_id,
            csrf_token,
            rol,
            zonas,
            ahora,
            expira_sesion,
        )

        sesion = Sesion(
            usuario_id=usuario_id,
            rol=rol,
            zonas=zonas,
            expira_en=expira_sesion,
            csrf=csrf_token,
        )

        return sesion, cookie_token

    def validar_sesion(self, cookie_token: str) -> Sesion:
        """Comprueba y devuelve una sesión activa."""
        if not cookie_token:
            raise ErrorSesion("sin_sesion", "No se proporcionó token de sesión.")

        sesion_hash = self._hash_token(cookie_token)
        datos = self._persistencia.obtener_sesion(sesion_hash)
        if not datos or datos.get("cerrada_en") is not None:
            raise ErrorSesion("sesion_invalida", "Sesión inválida o cerrada.")

        ahora = datetime.now(timezone.utc)
        if ahora > datos["expira_en"]:
            raise ErrorSesion("sesion_expirada", "La sesión ha expirado.")

        return Sesion(
            usuario_id=datos["usuario_id"],
            rol=datos["rol"],
            zonas=datos["zonas"],
            expira_en=datos["expira_en"],
            csrf=datos["csrf"],
        )

    def cerrar_sesion(self, cookie_token: str) -> None:
        """Cierra la sesión actual y revoca los dispositivos del usuario (RF-PAN-11)."""
        sesion_hash = self._hash_token(cookie_token)
        datos = self._persistencia.obtener_sesion(sesion_hash)
        ahora = datetime.now(timezone.utc)
        self._persistencia.cerrar_sesion(sesion_hash, ahora)
        if datos and "usuario_id" in datos:
            self._persistencia.revocar_dispositivos_de_usuario(datos["usuario_id"], ahora)
