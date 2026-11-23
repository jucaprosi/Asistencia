# ¤canal-whatsapp
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Enrutamiento del canal de vendedores y separación de flujos ARM vs Huéspedes (RF-GW-06).

Parametrizable por modo (grupo o 1:1 según S-01). Garantiza que:
(a) Un mensaje del canal de vendedores nunca se enruta al agente de huéspedes.
(b) Un mensaje del canal de huéspedes nunca llega al ARM.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from features.canal_whatsapp.tipos import Canal, MensajeEntrante, PlantillaMeta

__all__ = [
    "EnrutadorCanal",
    "PLANTILLA_COMISION_VALIDADA",
    "clasificar_canal",
]

# Definición local de la plantilla comision_validada (aprobación en vivo en T-511)
PLANTILLA_COMISION_VALIDADA = PlantillaMeta(
    nombre="comision_validada",
    idioma="es",
    categoria="utility",
    variables=("nombre", "ticket", "comision"),
    aprobada=False,
    actualizada_en=datetime.now(timezone.utc),
)

ROLES_VENDEDORES = {"vendedor", "lider", "administrador"}


# ¤canal-whatsapp
def clasificar_canal(
    remitente: str,
    grupo_id: str | None = None,
    *,
    modo: str = "uno_a_uno",
    grupo_id_configurado: str | None = None,
    seguridad: Any = None,
    vendedores_registrados: set[str] | None = None,
) -> Canal:
    """Clasifica si un mensaje pertenece al canal de huéspedes o de vendedores (RF-GW-06).

    - Modo 'grupo': Si grupo_id coincide con el grupo configurado (o si grupo_id está presente),
      se clasifica como VENDEDORES. De lo contrario, HUESPEDES.
    - Modo 'uno_a_uno' (o '1a1'): Si el remitente es un vendedor registrado o tiene rol de vendedor
      en seguridad_service, se clasifica como VENDEDORES. De lo contrario, HUESPEDES.
    """
    modo_norm = str(modo).lower().replace(":", "").replace("-", "_")

    if modo_norm in {"grupo", "group"}:
        if grupo_id:
            if grupo_id_configurado:
                return Canal.VENDEDORES if grupo_id == grupo_id_configurado else Canal.HUESPEDES
            return Canal.VENDEDORES
        return Canal.HUESPEDES

    # Modo uno_a_uno / 1a1
    if vendedores_registrados and remitente in vendedores_registrados:
        return Canal.VENDEDORES

    if seguridad is not None and hasattr(seguridad, "identificar"):
        try:
            identidad = seguridad.identificar(remitente)
            rol = getattr(identidad, "rol", None)
            rol_str = getattr(rol, "value", str(rol)).lower()
            if rol_str in ROLES_VENDEDORES:
                return Canal.VENDEDORES
        except Exception:
            pass

    return Canal.HUESPEDES


# ¤canal-whatsapp
class EnrutadorCanal:
    """Gestiona la clasificación y el despacho segregado al ARM o al Agente de Huéspedes."""

    def __init__(
        self,
        modo: str = "uno_a_uno",
        grupo_id: str | None = None,
        *,
        seguridad: Any = None,
        observabilidad: Any = None,
        vendedores: set[str] | None = None,
    ) -> None:
        self.modo = modo
        self.grupo_id = grupo_id
        self.seguridad = seguridad
        self.observabilidad = observabilidad
        self._vendedores_registrados: set[str] = set(vendedores or set())

    # ¤canal-whatsapp
    def registrar_vendedor(self, remitente: str) -> None:
        """Registra un número de teléfono o token como vendedor en modo 1a1."""
        self._vendedores_registrados.add(remitente)

    # ¤canal-whatsapp
    def es_vendedor(self, remitente: str) -> bool:
        """Determina si un remitente es un vendedor registrado o verificado."""
        if remitente in self._vendedores_registrados:
            return True
        if self.seguridad is not None and hasattr(self.seguridad, "identificar"):
            try:
                identidad = self.seguridad.identificar(remitente)
                rol = getattr(identidad, "rol", None)
                rol_str = getattr(rol, "value", str(rol)).lower()
                return rol_str in ROLES_VENDEDORES
            except Exception:
                pass
        return False

    # ¤canal-whatsapp
    def clasificar_canal(self, remitente: str, grupo_id: str | None = None) -> Canal:
        """Clasifica el canal correspondiente aplicando la estrategia configurada."""
        return clasificar_canal(
            remitente,
            grupo_id=grupo_id,
            modo=self.modo,
            grupo_id_configurado=self.grupo_id,
            seguridad=self.seguridad,
            vendedores_registrados=self._vendedores_registrados,
        )

    # ¤canal-whatsapp
    def despachar(
        self,
        mensaje: MensajeEntrante,
        receptores: Mapping[Canal, Callable[[MensajeEntrante], Any]],
    ) -> Any:
        """Despacha el mensaje entrante exclusivamente al receptor asignado a su canal.

        Criterios estrictos (RF-GW-06):
        (a) Un mensaje de vendedores NUNCA se entrega al receptor de huéspedes.
        (b) Un mensaje de huéspedes NUNCA se entrega al receptor de ARM / vendedores.
        """
        canal_origen = mensaje.canal
        receptor = receptores.get(canal_origen)

        if receptor is None:
            if self.observabilidad and hasattr(self.observabilidad, "log"):
                self.observabilidad.log(
                    "WARNING",
                    "RECEPTOR_NO_ENCONTRADO",
                    canal=canal_origen.value,
                    mensaje_id=mensaje.mensaje_id,
                )
            return None

        # Verificación explícita de mamparos antes de invocar
        if canal_origen == Canal.VENDEDORES:
            receptor_huespedes = receptores.get(Canal.HUESPEDES)
            if receptor is receptor_huespedes and receptor_huespedes is not None:
                raise RuntimeError("Violación RF-GW-06: Mensaje de vendedores no puede enrutarse a huéspedes")

        if canal_origen == Canal.HUESPEDES:
            receptor_vendedores = receptores.get(Canal.VENDEDORES)
            if receptor is receptor_vendedores and receptor_vendedores is not None:
                raise RuntimeError("Violación RF-GW-06: Mensaje de huéspedes no puede enrutarse a vendedores")

        return receptor(mensaje)
