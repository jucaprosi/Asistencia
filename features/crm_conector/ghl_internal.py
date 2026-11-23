# ¤crm-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Implementación del conector GoHighLevel (GHL) mediante webhooks y API REST (RF-CRM-02)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from features.crm_conector.base_internal import CRMConnector
from features.crm_conector.http_internal import AdaptadorHttpCRM
from features.crm_conector.tipos import (
    Contacto,
    ContactoDuplicado,
    Oportunidad,
    OportunidadInexistente,
    PublicacionVenta,
)

__all__ = ["GHLConnector"]


# ¤crm-conector
class GHLConnector(CRMConnector):
    """Conector GoHighLevel que implementa el contrato de CRM."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        adaptador: AdaptadorHttpCRM | None = None,
    ) -> None:
        self.config = dict(config or {})
        self.adaptador = adaptador or AdaptadorHttpCRM(
            url=self.config.get("webhook_ventas", {}).get("url", ""),
            secreto_hmac=self.config.get("webhook_ventas", {}).get("secreto_hmac", ""),
            cabecera_firma=self.config.get("webhook_ventas", {}).get("cabecera_firma", "X-Glamping-Signature"),
        )
        # Memoria interna para cachear / sincronizar contactos y oportunidades en el conector
        self._contactos: dict[str, Contacto] = {}
        self._oportunidades: dict[str, Oportunidad] = {}
        self._mensajes: dict[str, list[dict[str, Any]]] = {}

    def buscar_contacto(
        self,
        email: str | None = None,
        telefono: str | None = None,
        *,
        email_token: str | None = None,
        telefono_token: str | None = None,
    ) -> Contacto | None:
        tok_tel = telefono_token or telefono
        tok_em = email_token or email

        for c in self._contactos.values():
            if tok_tel and (c.telefono_token == tok_tel or c.telefono_token.endswith(tok_tel)):
                return c
            if tok_em and c.email_token == tok_em:
                return c
        return None

    def crear_contacto(self, contacto: Contacto) -> Contacto:
        if contacto.contacto_id in self._contactos:
            raise ContactoDuplicado(f"Ya existe un contacto con id {contacto.contacto_id}")
        for c in self._contactos.values():
            if c.telefono_token == contacto.telefono_token:
                raise ContactoDuplicado(f"Ya existe un contacto con teléfono {contacto.telefono_token}")

        cid = contacto.contacto_id or f"ghl_cnt_{uuid4().hex[:8]}"
        cref = contacto.crm_ref or f"ghl_ref_{uuid4().hex[:8]}"
        nuevo = Contacto(
            contacto_id=cid,
            nombre_token=contacto.nombre_token,
            telefono_token=contacto.telefono_token,
            email_token=contacto.email_token,
            crm_ref=cref,
        )
        self._contactos[cid] = nuevo
        return nuevo

    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        op_id = oportunidad.oportunidad_id or f"ghl_opp_{uuid4().hex[:8]}"
        cref = oportunidad.crm_ref or f"ghl_opp_ref_{uuid4().hex[:8]}"
        nueva = Oportunidad(
            oportunidad_id=op_id,
            contacto_id=oportunidad.contacto_id,
            propiedad_id=oportunidad.propiedad_id,
            etapa=oportunidad.etapa,
            monto=oportunidad.monto,
            crm_ref=cref,
        )
        self._oportunidades[op_id] = nueva
        return nueva

    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad:
        actual = self._oportunidades.get(oportunidad_id)
        if not actual:
            raise OportunidadInexistente(f"Oportunidad {oportunidad_id} no encontrada en GHL.")

        monto_nuevo = datos.get("monto", actual.monto)
        if isinstance(monto_nuevo, (int, float, str)):
            monto_nuevo = Decimal(str(monto_nuevo))

        actualizada = Oportunidad(
            oportunidad_id=actual.oportunidad_id,
            contacto_id=datos.get("contacto_id", actual.contacto_id),
            propiedad_id=datos.get("propiedad_id", actual.propiedad_id),
            etapa=datos.get("etapa", actual.etapa),
            monto=monto_nuevo,
            crm_ref=datos.get("crm_ref", actual.crm_ref),
        )
        self._oportunidades[oportunidad_id] = actualizada
        return actualizada

    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        venta_id = str(venta["venta_id"])
        codigo, respuesta = self.adaptador.enviar_publicacion(venta)
        return PublicacionVenta(
            venta_id=venta_id,
            estado="ok",
            intentos=1,
            ultima_respuesta=f"{codigo} OK: {respuesta}",
            proximo_intento=None,
        )

    def publicar_anulacion(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        venta_id = str(venta["venta_id"])
        codigo, respuesta = self.adaptador.enviar_publicacion(venta)
        return PublicacionVenta(
            venta_id=venta_id,
            estado="ok",
            intentos=1,
            ultima_respuesta=f"{codigo} OK: {respuesta}",
            proximo_intento=None,
        )

    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        msg_id = f"ghl_msg_{uuid4().hex[:8]}"
        self._mensajes.setdefault(conversacion_id, []).append({
            "mensaje_id": msg_id,
            "texto": texto,
            "enviado_en": datetime.now(timezone.utc),
        })
        return msg_id
