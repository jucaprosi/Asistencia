# ¤crm-conector
# ¤¤integration-engineer
"""Implementación FakeCRM en memoria para desarrollo Clean-Room y tests de contrato (RF-CRM-01)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from features.crm_conector.base_internal import CRMConnector
from features.crm_conector.tipos import (
    Contacto,
    ContactoDuplicado,
    EventoCRM,
    Oportunidad,
    OportunidadInexistente,
    PublicacionVenta,
)


# ¤crm-conector
class FakeCRM(CRMConnector):
    """Proveedor en memoria de CRM que simula contactos, oportunidades, eventos y publicaciones."""

    def __init__(self) -> None:
        self.contactos: dict[str, Contacto] = {}
        self.oportunidades: dict[str, Oportunidad] = {}
        self.publicaciones: dict[str, PublicacionVenta] = {}
        self.mensajes: dict[str, list[dict[str, Any]]] = {}
        self.eventos: list[EventoCRM] = []
        self.llamadas: list[tuple[str, dict[str, Any]]] = []
        self._inicializar_datos_semilla()

    def _inicializar_datos_semilla(self) -> None:
        c1 = Contacto(
            contacto_id="cnt_semilla_001",
            nombre_token="tok_nombre_juan",
            telefono_token="tok_tel_593991112233",
            email_token="tok_email_juan@ejemplo.com",
            crm_ref="crm_ref_cnt_001",
        )
        self.contactos[c1.contacto_id] = c1

        op1 = Oportunidad(
            oportunidad_id="opp_semilla_001",
            contacto_id=c1.contacto_id,
            propiedad_id="glamping_imbabura",
            etapa="Por validar",
            monto=Decimal("150.00"),
            crm_ref="crm_ref_opp_001",
        )
        self.oportunidades[op1.oportunidad_id] = op1

    def buscar_contacto(
        self,
        email: str | None = None,
        telefono: str | None = None,
        *,
        email_token: str | None = None,
        telefono_token: str | None = None,
    ) -> Contacto | None:
        self.llamadas.append((
            "buscar_contacto",
            {"email": email, "telefono": telefono, "email_token": email_token, "telefono_token": telefono_token},
        ))
        tok_tel = telefono_token or telefono
        tok_em = email_token or email

        for c in self.contactos.values():
            if tok_tel and (c.telefono_token == tok_tel or c.telefono_token.endswith(tok_tel)):
                return c
            if tok_em and (c.email_token == tok_em):
                return c
        return None

    def crear_contacto(self, contacto: Contacto) -> Contacto:
        self.llamadas.append(("crear_contacto", {"contacto_id": contacto.contacto_id}))
        # Validar duplicados por contacto_id o telefono_token
        if contacto.contacto_id in self.contactos:
            raise ContactoDuplicado(f"Ya existe un contacto con id {contacto.contacto_id}")
        for c in self.contactos.values():
            if c.telefono_token == contacto.telefono_token:
                raise ContactoDuplicado(f"Ya existe un contacto con teléfono {contacto.telefono_token}")

        cid = contacto.contacto_id or f"cnt_{uuid4().hex[:8]}"
        cref = contacto.crm_ref or f"crm_cnt_{uuid4().hex[:8]}"
        persisted = Contacto(
            contacto_id=cid,
            nombre_token=contacto.nombre_token,
            telefono_token=contacto.telefono_token,
            email_token=contacto.email_token,
            crm_ref=cref,
        )
        self.contactos[cid] = persisted
        return persisted

    def crear_oportunidad(self, oportunidad: Oportunidad) -> Oportunidad:
        self.llamadas.append(("crear_oportunidad", {"oportunidad_id": oportunidad.oportunidad_id}))
        op_id = oportunidad.oportunidad_id or f"opp_{uuid4().hex[:8]}"
        cref = oportunidad.crm_ref or f"crm_opp_{uuid4().hex[:8]}"
        persisted = Oportunidad(
            oportunidad_id=op_id,
            contacto_id=oportunidad.contacto_id,
            propiedad_id=oportunidad.propiedad_id,
            etapa=oportunidad.etapa,
            monto=oportunidad.monto,
            crm_ref=cref,
        )
        self.oportunidades[op_id] = persisted
        return persisted

    def actualizar_oportunidad(self, oportunidad_id: str, datos: Mapping[str, Any]) -> Oportunidad:
        self.llamadas.append(("actualizar_oportunidad", {"oportunidad_id": oportunidad_id, "datos": dict(datos)}))
        if oportunidad_id not in self.oportunidades:
            raise OportunidadInexistente(f"No existe oportunidad con id {oportunidad_id}")

        actual = self.oportunidades[oportunidad_id]
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
        self.oportunidades[oportunidad_id] = actualizada
        return actualizada

    def publicar_venta(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        self.llamadas.append(("publicar_venta", dict(venta)))
        venta_id = str(venta.get("venta_id", uuid4()))
        pub = PublicacionVenta(
            venta_id=venta_id,
            estado="ok",
            intentos=1,
            ultima_respuesta="200 OK (venta_validada)",
            proximo_intento=None,
        )
        self.publicaciones[venta_id] = pub
        return pub

    def publicar_anulacion(self, venta: Mapping[str, Any]) -> PublicacionVenta:
        self.llamadas.append(("publicar_anulacion", dict(venta)))
        venta_id = str(venta.get("venta_id", uuid4()))
        pub = PublicacionVenta(
            venta_id=venta_id,
            estado="ok",
            intentos=1,
            ultima_respuesta="200 OK (venta_anulada)",
            proximo_intento=None,
        )
        self.publicaciones[venta_id] = pub
        return pub

    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        self.llamadas.append(("enviar_mensaje", {"conversacion_id": conversacion_id, "texto": texto}))
        msg_id = f"msg_{uuid4().hex[:8]}"
        self.mensajes.setdefault(conversacion_id, []).append({
            "mensaje_id": msg_id,
            "texto": texto,
            "enviado_en": datetime.now(timezone.utc),
        })
        return msg_id
