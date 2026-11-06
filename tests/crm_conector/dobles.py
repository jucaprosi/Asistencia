# ¤crm-conector
# ¤¤integration-engineer
"""Dobles de prueba para la sala crm_conector."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from features.crm_conector.base_internal import CRMConnector
from features.crm_conector.tipos import (
    Contacto,
    ContactoDuplicado,
    Oportunidad,
    OportunidadInexistente,
    PublicacionVenta,
)


# ¤crm-conector
class DobleObservabilidadService:
    """Doble de observabilidad para registrar logs y trazas de crm_conector."""

    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []
        self.alertas: list[dict[str, Any]] = []

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, "campos": campos})
        if nivel in {"WARN", "ERROR"}:
            self.alertas.append({"nivel": nivel, "evento": evento, "campos": campos})

    def disparar_alerta(self, tipo: str, severidad: str, detalle: str) -> None:
        self.alertas.append({"tipo": tipo, "severidad": severidad, "detalle": detalle})

    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str = "huespedes") -> str:
        return f"traza_{uuid4().hex[:8]}"

    def cerrar_traza(self, traza_id: str, resultado: str) -> None:
        pass


# ¤crm-conector
class DobleCRMAlternativo(CRMConnector):
    """Segunda implementación del contrato para verificar parametrización (RF-CRM-01)."""

    def __init__(self) -> None:
        self.contactos: dict[str, Contacto] = {}
        self.oportunidades: dict[str, Oportunidad] = {}

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
        for c in self.contactos.values():
            if tok_tel and c.telefono_token == tok_tel:
                return c
            if tok_em and c.email_token == tok_em:
                return c
        return None

    def crear_contacto(self, contacto: Contacto) -> Contacto:
        if contacto.contacto_id in self.contactos:
            raise ContactoDuplicado(f"Ya existe {contacto.contacto_id}")
        cid = contacto.contacto_id or f"alt_{uuid4().hex[:8]}"
        persisted = Contacto(
            contacto_id=cid,
            nombre_token=contacto.nombre_token,
            telefono_token=contacto.telefono_token,
            email_token=contacto.email_token,
            crm_ref=f"alt_crm_{cid}",
        )
        self.contactos[cid] = persisted
        return persisted

    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        op_id = oportunidad.oportunidad_id or f"alt_opp_{uuid4().hex[:8]}"
        persisted = Oportunidad(
            oportunidad_id=op_id,
            contacto_id=oportunidad.contacto_id,
            propiedad_id=oportunidad.propiedad_id,
            etapa=oportunidad.etapa,
            monto=oportunidad.monto,
            crm_ref=f"alt_crm_opp_{op_id}",
        )
        self.oportunidades[op_id] = persisted
        return persisted

    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad:
        if oportunidad_id not in self.oportunidades:
            raise OportunidadInexistente(f"No existe {oportunidad_id}")
        actual = self.oportunidades[oportunidad_id]
        monto = datos.get("monto", actual.monto)
        if isinstance(monto, (int, float, str)):
            monto = Decimal(str(monto))
        actualizada = Oportunidad(
            oportunidad_id=actual.oportunidad_id,
            contacto_id=datos.get("contacto_id", actual.contacto_id),
            propiedad_id=datos.get("propiedad_id", actual.propiedad_id),
            etapa=datos.get("etapa", actual.etapa),
            monto=monto,
            crm_ref=datos.get("crm_ref", actual.crm_ref),
        )
        self.oportunidades[oportunidad_id] = actualizada
        return actualizada

    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        return PublicacionVenta(
            venta_id=str(venta.get("venta_id", uuid4())),
            estado="ok",
            intentos=1,
            ultima_respuesta="200 OK (alt)",
        )

    def publicar_anulacion(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        return PublicacionVenta(
            venta_id=str(venta.get("venta_id", uuid4())),
            estado="ok",
            intentos=1,
            ultima_respuesta="200 OK (alt anulacion)",
        )

    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        return f"alt_msg_{uuid4().hex[:6]}"
