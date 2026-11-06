# ¤canal-whatsapp
# ¤¤integration-engineer
"""Validación y armado de plantillas para Meta Cloud API (RF-GW-04)."""
from __future__ import annotations

from typing import Any

from features.canal_whatsapp.tipos import (
    Plantilla, PlantillaMeta, PlantillaNoAprobada, VariablesPlantillaInvalidas,
)


# ¤canal-whatsapp
def validar_plantilla(plantilla: Plantilla, definicion: PlantillaMeta | None) -> None:
    """Valida estado de aprobación, cantidad y tipos de las variables antes de enviar a Meta."""
    if definicion is None:
        raise PlantillaNoAprobada(plantilla.nombre, f"Plantilla '{plantilla.nombre}' no registrada en catálogo")

    if not definicion.aprobada:
        raise PlantillaNoAprobada(plantilla.nombre, f"Plantilla '{plantilla.nombre}' no está aprobada por Meta")

    if len(plantilla.variables) != len(definicion.variables):
        raise VariablesPlantillaInvalidas(
            plantilla.nombre,
            f"Plantilla '{plantilla.nombre}' esperaba {len(definicion.variables)} variables, "
            f"recibió {len(plantilla.variables)}",
        )

    for i, var in enumerate(plantilla.variables):
        if not isinstance(var, str):
            raise VariablesPlantillaInvalidas(
                plantilla.nombre,
                f"Variable en posición {i} debe ser de tipo texto (recibido {type(var).__name__})",
            )


# ¤canal-whatsapp
def armar_payload_plantilla(destinatario: str, plantilla: Plantilla) -> dict[str, Any]:
    """Genera la estructura JSON requerida por Meta Cloud API para enviar una plantilla."""
    componentes: list[dict[str, Any]] = []
    if plantilla.variables:
        componentes.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(v)} for v in plantilla.variables],
        })

    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destinatario,
        "type": "template",
        "template": {
            "name": plantilla.nombre,
            "language": {"code": plantilla.idioma},
            "components": componentes,
        },
    }
