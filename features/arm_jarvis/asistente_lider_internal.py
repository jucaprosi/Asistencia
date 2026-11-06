# ¤arm-jarvis
# ¤¤backend-developer
"""Asistente en lenguaje natural «Jarvis» para líderes y administradores (RF-ARM-09)."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from features.arm_jarvis.persistencia_internal import RepositorioArm
from features.arm_jarvis.tipos import (
    CambioNoPermitido,
    ConfirmacionRequerida,
    ErrorArm,
    EstadoVenta,
)

__all__ = ["AsistenteLider"]

MESES_MAPA = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04", "mayo": "05", "junio": "06",
    "julio": "07", "agosto": "08", "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}

CAMBIOS_PERMITIDOS = {"notificaciones.al_validar", "notificaciones.al_rechazar"}


# ¤arm-jarvis
class AsistenteLider:
    """Procesa consultas operativas del líder y orquesta cambios de configuración acotados."""

    def __init__(self, repositorio: RepositorioArm, config: Mapping[str, Any] | None = None) -> None:
        self._repo = repositorio
        self._config = config or {}

    # ¤arm-jarvis
    def atender_consulta(
        self,
        actor_id: str,
        actor_rol: str,
        pregunta: str,
        conversacion_id: str = "",
    ) -> str:
        """Atiende preguntas en lenguaje natural sobre ventas y configuraciones operativas."""
        # Verificar permisos de rol (solo líder y administrador)
        if actor_rol not in ("lider", "administrador"):
            raise ErrorArm(
                codigo="acceso_denegado",
                mensaje_usuario="No tienes permisos de líder para consultar al asistente Jarvis.",
                detalle_tecnico=f"Rol {actor_rol} sin acceso a asistente líder",
            )

        p = pregunta.strip().lower()

        # 1. Petición de cambio en regla de comisión: estrictamente reservada al administrador
        if re.search(r"\b(?:regla|comisi[oó]n|porcentaje)\b", p) and re.search(r"\b(?:cambi\w*|modific\w*|sub\w*|baj\w*|crea\w*|edit\w*|actualiz\w*)\b", p):
            return "Solo el administrador puede modificar las reglas de comisión."

        # 2. Petición de cambio de configuración permitido
        if "notificaci" in p and ("activar" in p or "desactivar" in p):
            clave = "notificaciones.al_validar" if "validar" in p else "notificaciones.al_rechazar"
            valor = "activar" in p
            return f"Esto cambiará '{clave}' a {valor}. ¿Confirmas este cambio?"

        # 3. Consulta de ventas por vendedor y período
        # Ej: "¿cuánto vendió Carlos en septiembre?"
        m_cuanto = re.search(r"cu[aá]nto\s+vendi[oó]\s+([a-záéíóú]+)", p)
        if m_cuanto:
            nombre_buscado = m_cuanto.group(1).capitalize()
            # Identificar mes
            mes_num = "09"  # Default septiembre si se menciona
            for nombre_mes, cod in MESES_MAPA.items():
                if nombre_mes in p:
                    mes_num = cod
                    break
            anio = str(date.today().year)
            periodo = f"{anio}-{mes_num}"

            # Buscar al vendedor por nombre
            vendedores = self._repo.listar_vendedores_activos()
            vendedor = next((v for v in vendedores if nombre_buscado.lower() in v.nombre.lower()), None)
            if not vendedor:
                return f"No se encontró al vendedor '{nombre_buscado}' en el registro de vendedores activos."

            ventas = self._repo.listar_ventas(vendedor_id=vendedor.vendedor_id, periodo=periodo)
            ventas_validas = [v for v in ventas if v.estado != EstadoVenta.RECHAZADA and v.estado != EstadoVenta.ANULADA]
            total_monto = sum((v.extraida.monto or Decimal("0")) for v in ventas_validas)
            return (
                f"{vendedor.nombre} vendió un total de {total_monto:.2f} USD en {periodo} "
                f"({len(ventas_validas)} ventas registradas)."
            )

        # 4. Consulta de ventas pendientes de validación
        if "por validar" in p or "pendientes" in p:
            ventas_pv = self._repo.listar_ventas(estado=EstadoVenta.POR_VALIDAR)
            return f"Actualmente hay {len(ventas_pv)} venta(s) pendientes por validar."

        return "Hola, soy el asistente Jarvis. Puedo informarte sobre ventas por vendedor o actualizar notificaciones."

    # ¤arm-jarvis
    def aplicar_cambio(
        self,
        actor_id: str,
        actor_rol: str,
        cambio: Mapping[str, Any],
        confirmado: bool,
    ) -> None:
        """Aplica un cambio de configuración acotado en arm.configuracion requiriendo confirmación."""
        if actor_rol not in ("lider", "administrador"):
            raise CambioNoPermitido("configuracion", actor_rol)

        clave = cambio.get("clave", "")
        valor = cambio.get("valor")

        if clave not in CAMBIOS_PERMITIDOS:
            raise CambioNoPermitido(clave, actor_rol)

        if not confirmado:
            raise ConfirmacionRequerida(
                cambio=cambio,
                pregunta=f"¿Confirmas aplicar el cambio '{clave}' = {valor}?",
            )

        self._repo.guardar_configuracion(clave=clave, valor=valor, autor=actor_id)
