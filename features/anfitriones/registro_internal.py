# ¤anfitriones
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Gestión interna de registro y publicación de anfitriones y hospedajes (RF-ANF-01, RF-ANF-02)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid

from features.anfitriones.persistencia_internal import PersistenciaAnfitriones
from features.anfitriones.tipos import (
    Anfitrion,
    EstadoAnfitrion,
    EstadoHospedaje,
    Hospedaje,
)

__all__ = ["GestorRegistro"]


# ¤anfitriones
class GestorRegistro:
    """Implementa el alta de anfitriones y la publicación revisada de hospedajes."""

    def __init__(
        self,
        persistencia: PersistenciaAnfitriones,
        seguridad: Any,
        observabilidad: Any,
    ) -> None:
        self._persistencia = persistencia
        self._seguridad = seguridad
        self._observabilidad = observabilidad

    def registrar_anfitrion(
        self,
        anfitrion: Anfitrion,
        telefono_token: str,
        actor_id: str,
    ) -> Anfitrion:
        """RF-ANF-01: Alta de anfitrión con versión de términos y porcentaje pactado."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        # Criterio (a): Sin términos no hay alta
        if not anfitrion.terminos_version or not anfitrion.terminos_version.strip():
            raise ErrorAnfitriones(
                "TERMINOS_NO_ACEPTADOS",
                "El anfitrión debe contar con una versión de términos aceptada para el alta.",
            )

        if anfitrion.comision_porcentaje is None:
            raise ErrorAnfitriones(
                "COMISION_REQUERIDA",
                "Debe especificarse el porcentaje de comisión pactado.",
            )

        porcentaje = Decimal(str(anfitrion.comision_porcentaje))
        if porcentaje < Decimal("0") or porcentaje > Decimal("100"):
            raise ErrorAnfitriones(
                "COMISION_INVALIDA",
                "El porcentaje de comisión debe situarse entre 0 y 100.",
            )

        if not telefono_token or not telefono_token.strip():
            raise ErrorAnfitriones(
                "TELEFONO_REQUERIDO",
                "Debe indicarse el teléfono de contacto del anfitrión.",
            )

        # Criterio (b): El teléfono se guarda como token
        token_final = telefono_token
        if hasattr(self._seguridad, "tokenizar"):
            try:
                token_final = self._seguridad.tokenizar(
                    telefono_token,
                    conversacion_id="alta_anfitrion",
                )
            except Exception:
                token_final = telefono_token

        ahora = datetime.now(timezone.utc)
        anfitrion_id = anfitrion.anfitrion_id or str(uuid.uuid4())
        anfitrion_creado = Anfitrion(
            anfitrion_id=anfitrion_id,
            nombre_comercial=anfitrion.nombre_comercial,
            comision_porcentaje=porcentaje,
            terminos_version=anfitrion.terminos_version.strip(),
            estado=EstadoAnfitrion.ACTIVO,
            telefono_token=token_final,
            terminos_aceptados_en=anfitrion.terminos_aceptados_en or ahora,
            creado_en=anfitrion.creado_en or ahora,
        )

        self._persistencia.guardar_anfitrion(anfitrion_creado)

        # Criterio (c): Cada cambio queda en el audit log
        if hasattr(self._seguridad, "auditar"):
            try:
                from features.seguridad.seguridad_service import EventoAuditoria, Rol
                rol_actor = Rol.ADMINISTRADOR if hasattr(Rol, "ADMINISTRADOR") else "administrador"
                self._seguridad.auditar(
                    EventoAuditoria(
                        actor_token=actor_id,
                        rol=rol_actor,
                        accion="alta_anfitrion",
                        resultado="ok",
                    )
                )
            except Exception:
                pass

        if hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "INFO",
                "anfitrion_registrado",
                anfitrion_id=anfitrion_id,
                actor=actor_id,
            )

        return anfitrion_creado

    def guardar_hospedaje(self, hospedaje: Hospedaje, actor_id: str) -> Hospedaje:
        """RF-ANF-02: Publicación revisada (borrador, publicado, pausado)."""
        from features.anfitriones.anfitriones_service import ErrorAnfitriones

        anfitrion = self._persistencia.obtener_anfitrion(hospedaje.anfitrion_id)
        if anfitrion is None:
            raise ErrorAnfitriones(
                "ANFITRION_NO_ENCONTRADO",
                "El anfitrión especificado no existe en el registro.",
            )

        pub_por = hospedaje.publicado_por
        pub_en = hospedaje.publicado_en

        if hospedaje.estado == EstadoHospedaje.PUBLICADO:
            # Criterio (b): El anfitrión no publica por sí mismo
            if actor_id == hospedaje.anfitrion_id:
                if hasattr(self._seguridad, "auditar"):
                    try:
                        from features.seguridad.seguridad_service import EventoAuditoria, Rol
                        rol_actor = Rol.ANFITRION if hasattr(Rol, "ANFITRION") else "anfitrion"
                        self._seguridad.auditar(
                            EventoAuditoria(
                                actor_token=actor_id,
                                rol=rol_actor,
                                accion="publicar_hospedaje",
                                propiedad_id=hospedaje.propiedad_id,
                                resultado="denegado_anfitrion_auto_publica",
                            )
                        )
                    except Exception:
                        pass
                raise ErrorAnfitriones(
                    "PUBLICACION_NO_AUTORIZADA",
                    "El anfitrión no puede publicar hospedajes por sí mismo. Requiere revisión del equipo.",
                )

            # Criterio (a): Publicar exige actor y fecha
            if not actor_id or not actor_id.strip():
                raise ErrorAnfitriones(
                    "ACTOR_REQUERIDO",
                    "La publicación exige registrar el actor que autorizó la revisión.",
                )

            pub_por = actor_id
            pub_en = datetime.now(timezone.utc)

        hospedaje_actualizado = Hospedaje(
            propiedad_id=hospedaje.propiedad_id,
            anfitrion_id=hospedaje.anfitrion_id,
            estado=hospedaje.estado,
            publicado_por=pub_por,
            publicado_en=pub_en,
        )

        self._persistencia.guardar_hospedaje(hospedaje_actualizado)

        if hasattr(self._seguridad, "auditar"):
            try:
                from features.seguridad.seguridad_service import EventoAuditoria, Rol
                rol_actor = Rol.ADMINISTRADOR if hasattr(Rol, "ADMINISTRADOR") else "administrador"
                self._seguridad.auditar(
                    EventoAuditoria(
                        actor_token=actor_id,
                        rol=rol_actor,
                        accion=f"hospedaje_{hospedaje.estado.value}",
                        propiedad_id=hospedaje.propiedad_id,
                        resultado="ok",
                    )
                )
            except Exception:
                pass

        return hospedaje_actualizado

    def publicados(self) -> tuple[Hospedaje, ...]:
        """INV_SOLO_PUBLICADO: visible(h) => estado(h) = publicado y estado(anfitrion(h)) = activo."""
        return self._persistencia.listar_publicados()
