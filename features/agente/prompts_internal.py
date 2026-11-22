# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Carga, inyección y versionado con hash de prompts por propiedad (RF-AG-02)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from features.agente.tipos import ErrorAgente

__all__ = ["PromptsManager", "calcular_hash_prompt"]

RAIZ_DEFAULT = Path(__file__).resolve().parent.parent.parent


# ¤agente-enrutador
def calcular_hash_prompt(texto: str) -> str:
    """Calcula el hash SHA-256 canónico del prompt para trazabilidad."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ¤agente-enrutador
class PromptsManager:
    """Carga plantillas en arranque y las renderiza aisladamente por propiedad."""

    def __init__(self, config: Mapping[str, Any], raiz: Path | None = None) -> None:
        self._config = config
        self._raiz = raiz or RAIZ_DEFAULT
        self._plantillas_cache: dict[str, str] = {}
        self._precargar_plantillas()

    def _precargar_plantillas(self) -> None:
        prompts_cfg = self._config.get("prompts", {})
        for variante, ruta_relativa in prompts_cfg.items():
            ruta_archivo = self._raiz / ruta_relativa
            if ruta_archivo.is_file():
                self._plantillas_cache[variante] = ruta_archivo.read_text(encoding="utf-8")

    # ¤agente-enrutador
    def obtener_plantilla_cruda(self, variante: str = "glamping") -> str:
        if variante in self._plantillas_cache:
            return self._plantillas_cache[variante]
        prompts_cfg = self._config.get("prompts", {})
        ruta_relativa = prompts_cfg.get(variante)
        if ruta_relativa:
            ruta_archivo = self._raiz / ruta_relativa
            if ruta_archivo.is_file():
                contenido = ruta_archivo.read_text(encoding="utf-8")
                self._plantillas_cache[variante] = contenido
                return contenido
        raise ErrorAgente("plantilla_no_encontrada", f"No se encontró plantilla para {variante}")

    # ¤agente-enrutador
    def armar_prompt(self, propiedad_id: str, variante: str | None = None) -> tuple[str, str]:
        """Inyecta solo los datos de la propiedad resuelta y calcula su hash (INV_SIN_FUGA_ENTRE_PROPIEDADES)."""
        propiedades = self._config.get("propiedades", {})
        if propiedad_id not in propiedades:
            raise ErrorAgente(
                "propiedad_desconocida",
                f"No existen datos de configuración para la propiedad '{propiedad_id}'.",
            )

        if variante is None:
            if propiedad_id.startswith("dep") or "departamento" in propiedad_id:
                variante = "departamentos"
            else:
                variante = "glamping"

        datos_propiedad = dict(propiedades[propiedad_id])
        plantilla = self.obtener_plantilla_cruda(variante)

        # Mapeo unificado de placeholders a datos de la propiedad
        reemplazos: dict[str, str] = {
            "ubicacion_glamping": str(datos_propiedad.get("ubicacion") or datos_propiedad.get("ubicacion_glamping", "")),
            "nombre_glamping": str(datos_propiedad.get("nombre") or datos_propiedad.get("nombre_glamping", "")),
            "direccion_glamping": str(datos_propiedad.get("direccion") or datos_propiedad.get("direccion_glamping", "")),
            "hora_checkin": str(datos_propiedad.get("hora_checkin", "")),
            "hora_checkout": str(datos_propiedad.get("hora_checkout", "")),
            "unidades_glamping": str(datos_propiedad.get("unidades") or datos_propiedad.get("unidades_glamping", "")),
            "resumen_politicas": str(datos_propiedad.get("resumen_politicas", "")),
            "nombre_gestor_glamping": str(datos_propiedad.get("nombre_gestor") or datos_propiedad.get("nombre_gestor_glamping", "")),
            "contacto_humano": str(datos_propiedad.get("contacto_humano", "")),
            "nombre_departamento": str(datos_propiedad.get("nombre") or datos_propiedad.get("nombre_departamento", "")),
            "zona": str(datos_propiedad.get("ubicacion") or datos_propiedad.get("zona", "")),
            "direccion_departamento": str(datos_propiedad.get("direccion") or datos_propiedad.get("direccion_departamento", "")),
            "edificio": str(datos_propiedad.get("edificio", "Edificio Colonial Plaza")),
            "piso": str(datos_propiedad.get("piso", "Piso 2")),
            "capacidad": str(datos_propiedad.get("capacidad", "2 a 4 huéspedes")),
            "resumen_normas": str(datos_propiedad.get("resumen_normas") or datos_propiedad.get("resumen_politicas", "")),
            "nombre_gestor_zona": str(datos_propiedad.get("nombre_gestor") or datos_propiedad.get("nombre_gestor_zona", "")),
            "nombre_comercial": str(self._config.get("nombre_comercial", "Glamping Imbabura y Suites")),
            "ciudad": str(self._config.get("ciudad", "Quito e Imbabura")),
            "lista_propiedades": ", ".join(f"{p.get('nombre', k)} ({p.get('ubicacion', '')})" for k, p in propiedades.items()),
        }

        # Inyectar cualquier otra propiedad personalizada aislada
        for k, v in datos_propiedad.items():
            reemplazos[k] = str(v)

        # Renderizar reemplazando solo las variables de esta propiedad
        def _reemplazar(match: re.Match[str]) -> str:
            clave = match.group(1).strip()
            return reemplazos.get(clave, match.group(0))

        prompt_renderizado = re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", _reemplazar, plantilla)
        hash_prompt = calcular_hash_prompt(prompt_renderizado)
        return prompt_renderizado, hash_prompt
