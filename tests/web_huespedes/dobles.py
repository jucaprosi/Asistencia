# ¤web-huespedes
# ¤¤frontend-developer
"""Dobles de prueba para compuertas consumidas por la sala web_huespedes (T-405)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from features.anfitriones.anfitriones_service import (
    Anfitrion,
    EstadoAnfitrion,
    EstadoHospedaje,
    Hospedaje,
)


# ¤web-huespedes
class DobleAnfitriones:
    """Doble de anfitriones_service para pruebas de la web pública (RF-ANF-03, INV_SOLO_PUBLICADO)."""

    def __init__(self) -> None:
        self.anfitriones: dict[str, Anfitrion] = {}
        self.hospedajes: dict[str, Hospedaje] = {}

    def registrar_anfitrion(
        self,
        anfitrion: Anfitrion,
        telefono_token: str = "",
        actor_id: str = "admin",
    ) -> Anfitrion:
        self.anfitriones[anfitrion.anfitrion_id] = anfitrion
        return anfitrion

    def guardar_hospedaje(self, hospedaje: Hospedaje, actor_id: str = "admin") -> Hospedaje:
        self.hospedajes[hospedaje.propiedad_id] = hospedaje
        return hospedaje

    def publicar_hospedaje(
        self,
        propiedad_id: str,
        anfitrion_id: str,
        actor_id: str = "admin",
    ) -> Hospedaje:
        h = Hospedaje(
            propiedad_id=propiedad_id,
            anfitrion_id=anfitrion_id,
            estado=EstadoHospedaje.PUBLICADO,
            publicado_por=actor_id,
            publicado_en=datetime.now(timezone.utc),
        )
        self.hospedajes[propiedad_id] = h
        return h

    def pausar_hospedaje(self, propiedad_id: str, actor_id: str = "admin") -> Hospedaje | None:
        h = self.hospedajes.get(propiedad_id)
        if h:
            h_pausado = Hospedaje(
                propiedad_id=h.propiedad_id,
                anfitrion_id=h.anfitrion_id,
                estado=EstadoHospedaje.PAUSADO,
                publicado_por=actor_id,
                publicado_en=h.publicado_en,
            )
            self.hospedajes[propiedad_id] = h_pausado
            return h_pausado
        return None

    def suspender_anfitrion(self, anfitrion_id: str) -> None:
        anf = self.anfitriones.get(anfitrion_id)
        if anf:
            self.anfitriones[anfitrion_id] = Anfitrion(
                anfitrion_id=anf.anfitrion_id,
                nombre_comercial=anf.nombre_comercial,
                comision_porcentaje=anf.comision_porcentaje,
                terminos_version=anf.terminos_version,
                estado=EstadoAnfitrion.SUSPENDIDO,
            )

    def obtener_anfitrion(self, anfitrion_id: str) -> Anfitrion | None:
        return self.anfitriones.get(anfitrion_id)

    def publicados(self) -> tuple[Hospedaje, ...]:
        """INV_SOLO_PUBLICADO: visible(h) => estado(h) = publicado y estado(anfitrion(h)) = activo."""
        resultado: list[Hospedaje] = []
        for h in self.hospedajes.values():
            if h.estado != EstadoHospedaje.PUBLICADO:
                continue
            anf = self.anfitriones.get(h.anfitrion_id)
            if anf is not None and anf.estado != EstadoAnfitrion.ACTIVO:
                continue
            resultado.append(h)
        return tuple(resultado)


# ¤web-huespedes
class DoblePMS:
    """Doble de pms_conector_service para pruebas de disponibilidad y cotización."""

    def __init__(self, total: Decimal = Decimal("180.00"), disponible: bool = True) -> None:
        self.total = total
        self.disponible = disponible

    def consultar_disponibilidad(self, propiedad_id: str, desde: date, hasta: date, huespedes: int) -> Any:
        @dataclass(frozen=True)
        class UnidadDoble:
            unidad_id: str = "U-01"
            capacidad: int = 4

        @dataclass(frozen=True)
        class DispDoble:
            disponible: bool
            unidades: tuple[UnidadDoble, ...] = ()

        if self.disponible:
            return DispDoble(disponible=True, unidades=(UnidadDoble(),))
        return DispDoble(disponible=False)

    def cotizar(self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int) -> Any:
        @dataclass(frozen=True)
        class CotDoble:
            total: Decimal
            moneda: str = "USD"

        return CotDoble(total=self.total, moneda="USD")


# ¤web-huespedes
class DobleObservabilidad:
    """Doble de observabilidad_service para registrar eventos."""

    def __init__(self) -> None:
        self.logs: list[tuple[str, str, dict[str, Any]]] = []

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append((nivel, evento, campos))
