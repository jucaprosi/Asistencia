# ¤crm-conector
# ¤¤integration-engineer
"""Interfaz abstracta base del conector CRM (RF-CRM-01)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from features.crm_conector.tipos import Contacto, Oportunidad, PublicacionVenta


# ¤crm-conector
class CRMConnector(ABC):
    """Contrato abstracto del conector CRM con tipos propios de dominio."""

    @abstractmethod
    def buscar_contacto(
        self,
        email: str | None = None,
        telefono: str | None = None,
        *,
        email_token: str | None = None,
        telefono_token: str | None = None,
    ) -> Contacto | None:
        """Busca un contacto por correo, teléfono o sus tokens asociados."""

    @abstractmethod
    def crear_contacto(self, contacto: Contacto) -> Contacto:
        """Crea un contacto en el CRM y devuelve la entidad persistida."""

    @abstractmethod
    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        """Crea una oportunidad de venta o reserva en el pipeline del CRM."""

    @abstractmethod
    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad:
        """Actualiza la etapa, monto u otros campos de la oportunidad."""

    @abstractmethod
    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        """Publica una venta confirmada de forma firmada e idempotente."""

    @abstractmethod
    def publicar_anulacion(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        """Publica la anulación de una venta en el CRM."""

    @abstractmethod
    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        """Envía un mensaje saliente a través del inbox del CRM si está activo."""
