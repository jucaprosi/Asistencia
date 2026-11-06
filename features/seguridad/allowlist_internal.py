# ¤seguridad-canal
# ¤¤security-engineer
"""Mapeo y verificación de allowlist de acciones por rol (RF-SEC-02)."""
from __future__ import annotations

from typing import Mapping

from features.seguridad.tipos import AccionNoAutorizada, Rol, Veredicto

# Allowlist canónica idéntica a docs/spec/contratos/dominio.yaml
ALLOWLIST_CANONICA: dict[str, tuple[str, ...]] = {
    Rol.HUESPED_POTENCIAL.value: (
        "consultar_disponibilidad",
        "cotizar",
        "crear_reserva_preliminar",
        "solicitar_reserva",
        "solicitar_humano",
    ),
    Rol.HUESPED_ACTIVO.value: (
        "consultar_disponibilidad",
        "cotizar",
        "crear_reserva_preliminar",
        "solicitar_reserva",
        "solicitar_humano",
        "obtener_instrucciones_checkin",
        "reportar_incidencia",
    ),
    Rol.VENDEDOR.value: (
        "registrar_venta",
        "consultar_comision_propia",
        "solicitar_humano",
    ),
    Rol.LIDER.value: (
        "validar_venta",
        "rechazar_venta",
        "ver_comisiones_todas",
        "exportar_periodo",
        "cerrar_periodo",
        "preguntar_jarvis",
    ),
    Rol.GESTOR.value: (
        "ver_conversaciones_zona",
        "resolver_incidencia",
        "tomar_handoff",
        "responder_handoff",
        "devolver_handoff",
    ),
    Rol.ADMINISTRADOR.value: ("*",),
    Rol.ANFITRION.value: (
        "responder_solicitud",
        "reportar_resultado_estadia",
        "consultar_estado_cuenta_anfitrion",
        "actualizar_calendario",
    ),
    Rol.SISTEMA.value: (
        "buscar_contacto_crm",
        "crear_oportunidad_crm",
    ),
    Rol.DESCONOCIDO.value: (),
}


# ¤seguridad-canal
def obtener_acciones_permitidas(
    rol: Rol | str, mapa_allowlist: Mapping[str, list[str] | tuple[str, ...]] | None = None
) -> tuple[str, ...]:
    """Retorna las acciones permitidas para el rol dado."""
    clave_rol = rol.value if isinstance(rol, Rol) else str(rol)
    if mapa_allowlist and clave_rol in mapa_allowlist:
        return tuple(mapa_allowlist[clave_rol])
    return ALLOWLIST_CANONICA.get(clave_rol, ())


# ¤seguridad-canal
def evaluar_allowlist(
    rol: Rol | str,
    herramienta: str,
    mapa_allowlist: Mapping[str, list[str] | tuple[str, ...]] | None = None,
) -> Veredicto:
    """Verifica si la herramienta solicitada está autorizada para el rol (INV_ALLOWLIST_POR_ACCION)."""
    clave_rol = rol.value if isinstance(rol, Rol) else str(rol)
    permitidas = obtener_acciones_permitidas(clave_rol, mapa_allowlist)

    if "*" in permitidas or herramienta in permitidas:
        return Veredicto(permitido=True)

    motivo = f"AccionNoAutorizada: herramienta '{herramienta}' prohibida para rol '{clave_rol}'"
    return Veredicto(permitido=False, motivo=motivo)


# ¤seguridad-canal
def exigir_allowlist(
    rol: Rol | str,
    herramienta: str,
    mapa_allowlist: Mapping[str, list[str] | tuple[str, ...]] | None = None,
) -> None:
    """Lanza AccionNoAutorizada si la herramienta no está permitida para el rol."""
    veredicto = evaluar_allowlist(rol, herramienta, mapa_allowlist)
    if not veredicto.permitido:
        raise AccionNoAutorizada(veredicto.motivo or "Acción no autorizada")
