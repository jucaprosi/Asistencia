# ¤agente-enrutador
# ¤¤machine-learning-engineer
"""Enrutador multi-propiedad y evaluador de casos (RF-AG-01)."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping, Sequence

from features.agente.tipos import ContextoConversacion, ModoAgente, ResolucionPropiedad

__all__ = ["EnrutadorPropiedad"]


# ¤agente-enrutador
def _normalizar_texto(texto: str) -> str:
    """Normaliza texto eliminando diacríticos y convirtiendo a minúsculas."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ¤agente-enrutador
class EnrutadorPropiedad:
    """Resuelve la propiedad aplicable según código de reserva, nombre, dirección o contexto (RF-AG-01)."""

    PATRON_RESERVA = re.compile(r"\b(res[-_][a-z0-9_-]+)\b", re.IGNORECASE)

    PALABRAS_AMBIGUAS = (
        "opciones de hospedaje",
        "que opciones tienen",
        "opciones tienen",
        "donde puedo hospedarme",
        "alojamientos tienen",
        "tipos de hospedaje",
        "sus tarifas de alojamiento",
        "habitaciones disponibles",
        "ambas propiedades",
        "glamping o departamento",
        "glamping y departamento",
        "glamping y departamentos",
        "glamping y las suites",
        "suites y el glamping",
        "otavalo como en quito",
        "tanto en otavalo como en quito",
        "comparar el glamping",
    )

    TERMINOS_NOMBRE: Mapping[str, Sequence[str]] = {
        "glamping": (
            "glamping",
            "glamping san pablo",
            "san pablo",
            "domo lago",
            "domo montana",
            "domos",
            "domo",
            "tienda safari",
        ),
        "departamento_centro": (
            "suites centro historico",
            "suites centro",
            "suite colonial",
            "suite balcon",
            "departamento centro",
            "departamentos",
            "departamento",
            "suites",
            "suite",
        ),
    }

    TERMINOS_DIRECCION: Mapping[str, Sequence[str]] = {
        "glamping": (
            "sector cajas",
            "via al lago san pablo",
            "via al lago",
            "lago san pablo",
            "otavalo",
            "imbabura",
        ),
        "departamento_centro": (
            "calle garcia moreno y sucre",
            "garcia moreno y sucre",
            "garcia moreno",
            "sucre",
            "quito colonial",
            "centro historico de quito",
            "centro historico",
            "quito",
        ),
    }

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config = config or {}
        self._propiedades = tuple(self._config.get("propiedades", {}).keys()) or ("glamping", "departamento_centro")

    # ¤agente-enrutador
    def resolver(
        self,
        mensaje: Any,
        contexto: ContextoConversacion | None = None,
    ) -> ResolucionPropiedad:
        """Determina la propiedad siguiendo el orden: código de reserva -> nombre -> dirección -> contexto -> pregunta."""
        texto_crudo = mensaje if isinstance(mensaje, str) else getattr(mensaje, "texto", str(mensaje))
        if hasattr(mensaje, "texto_tokenizado") and mensaje.texto_tokenizado:
            texto_crudo = mensaje.texto_tokenizado
        elif isinstance(mensaje, dict) and "texto" in mensaje:
            texto_crudo = mensaje["texto"]
        elif isinstance(mensaje, dict) and "texto_tokenizado" in mensaje:
            texto_crudo = mensaje["texto_tokenizado"]

        texto_norm = _normalizar_texto(texto_crudo)

        # 1. Código de reserva
        coincidencia_res = self.PATRON_RESERVA.search(texto_norm)
        if coincidencia_res:
            codigo = coincidencia_res.group(1).upper()
            if "GLAMP" in codigo:
                return ResolucionPropiedad(propiedad_id="glamping", metodo="codigo_reserva")
            if "DEP" in codigo:
                return ResolucionPropiedad(propiedad_id="departamento_centro", metodo="codigo_reserva")

        # 2. Detección de ambigüedad explícita o preguntas generales multillocal
        if any(amb in texto_norm for amb in self.PALABRAS_AMBIGUAS):
            return ResolucionPropiedad(
                propiedad_id=None,
                metodo="pregunta",
                candidatas=self._propiedades,
            )

        # 3. Nombre de la propiedad o unidades
        coincidencias_nombre: list[str] = []
        for prop_id, terminos in self.TERMINOS_NOMBRE.items():
            if any(t in texto_norm for t in terminos):
                coincidencias_nombre.append(prop_id)

        if len(coincidencias_nombre) > 1:
            return ResolucionPropiedad(
                propiedad_id=None,
                metodo="pregunta",
                candidatas=self._propiedades,
            )
        if len(coincidencias_nombre) == 1:
            return ResolucionPropiedad(propiedad_id=coincidencias_nombre[0], metodo="nombre")

        # 4. Dirección / Ubicación
        coincidencias_dir: list[str] = []
        for prop_id, terminos in self.TERMINOS_DIRECCION.items():
            if any(t in texto_norm for t in terminos):
                coincidencias_dir.append(prop_id)

        if len(coincidencias_dir) > 1:
            return ResolucionPropiedad(
                propiedad_id=None,
                metodo="pregunta",
                candidatas=self._propiedades,
            )
        if len(coincidencias_dir) == 1:
            return ResolucionPropiedad(propiedad_id=coincidencias_dir[0], metodo="direccion")

        # 5. Contexto previo si no hay conflicto y existe una propiedad resuelta
        if contexto and contexto.propiedad_id:
            return ResolucionPropiedad(propiedad_id=contexto.propiedad_id, metodo="contexto")

        # 6. Sin indicios suficientes en mensaje ni contexto -> Pregunta con opciones
        return ResolucionPropiedad(
            propiedad_id=None,
            metodo="pregunta",
            candidatas=self._propiedades,
        )

    # ¤agente-enrutador
    def evaluar(self, archivo_jsonl: Path) -> dict[str, float]:
        """Evalúa un set de casos etiquetados (.jsonl) y reporta la tasa de aciertos."""
        lineas = [l for l in archivo_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lineas:
            return {"aciertos": 0.0, "total": 0.0}

        aciertos = 0
        total = len(lineas)

        for linea in lineas:
            caso = json.loads(linea)
            mensaje = caso.get("mensaje", "")
            ctx_prop = caso.get("contexto_propiedad_id")
            contexto = None
            if ctx_prop is not None:
                contexto = ContextoConversacion(
                    conversacion_id="eval_conv",
                    identidad_token="usr_eval",
                    rol="huesped_potencial",
                    propiedad_id=ctx_prop,
                    modo=ModoAgente.ACTIVO,
                    ventana_24h_hasta=None,
                )

            res = self.resolver(mensaje, contexto)
            esperado_prop = caso.get("esperado_propiedad_id")
            esperado_metodo = caso.get("esperado_metodo")

            ok_prop = (res.propiedad_id == esperado_prop)
            ok_metodo = (res.metodo == esperado_metodo)

            if ok_prop and ok_metodo:
                aciertos += 1

        tasa = float(aciertos) / float(total) if total > 0 else 0.0
        return {"aciertos": tasa, "total": float(total)}
