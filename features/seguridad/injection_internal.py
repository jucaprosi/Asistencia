# ¤seguridad-canal
# ¤¤security-engineer
"""Filtro de inyecciones de prompt y heurísticas base (RF-SEC-04, INV_INYECCION_CERO)."""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Mapping

import yaml

from features.seguridad.tipos import Veredicto

RUTA_PATRONES_YAML = Path(__file__).with_name("patrones_inyeccion.yaml")


# ¤seguridad-canal
def cargar_patrones_desde_yaml(ruta: Path = RUTA_PATRONES_YAML) -> tuple[str, ...]:
    """Carga los patrones multilingües desde YAML asegurando al menos 40 patrones."""
    if ruta.is_file():
        try:
            with ruta.open(encoding="utf-8") as f:
                datos = yaml.safe_load(f)
                if datos and "patrones" in datos:
                    lista = [item["patron"] for item in datos["patrones"] if "patron" in item]
                    if len(lista) >= 40:
                        return tuple(lista)
        except Exception:
            pass
    return PATRONES_INYECCION_FALLBACK


PATRONES_INYECCION_FALLBACK = (
    # Español
    r"\bignora\s+(?:todas\s+)?(?:las\s+)?(?:instrucciones|reglas|directivas)\b",
    r"\bolvida\s+(?:todas\s+)?(?:las\s+)?(?:instrucciones|reglas)\b",
    r"\brevela\s+(?:tu\s+)?(?:prompt|system\s*prompt|instrucciones|directivas)\b",
    r"\bmuestra\s+(?:el\s+|tu\s+)?(?:prompt|system\s*prompt|instrucciones)\b",
    r"\bcu[aá]les\s+son\s+tus\s+(?:instrucciones|directivas|reglas)(?:\s+de\s+sistema|\s+iniciales)?\b",
    r"\bact[uú]a\s+como\b",
    r"\bahora\s+eres\s+(?:un\s+|una\s+)?(?:hacker|asistente\s+sin\s+restricciones|dan)\b",
    r"\bmodo\s+desarrollador\b",
    r"\bomite\s+(?:las\s+)?restricciones\b",
    r"\bsaltar\s+(?:los\s+)?filtros\s+de\s+seguridad\b",
    r"\bpretende\s+que\s+no\s+tienes\s+l[ií]mites\b",
    r"\bdesactiva\s+(?:tus\s+)?(?:salvaguardas|filtros|reglas)\b",
    r"\bdame\s+acceso\s+al\s+sistema\s+como\s+root\b",
    r"\brepite\s+el\s+texto\s+anterior\s+al\s+primer\s+mensaje\b",
    # English
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?instructions\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)\b",
    r"\breveal\s+(?:your\s+)?(?:system\s+prompt|prompt|instructions)\b",
    r"\bshow\s+(?:me\s+)?(?:your\s+)?(?:system\s+prompt|initial\s+prompt)\b",
    r"\bwhat\s+are\s+your\s+(?:system\s+)?instructions\b",
    r"\bact\s+as\b",
    r"\byou\s+are\s+now\b",
    r"\bjailbreak\b",
    r"\bdan\s+mode\b",
    r"\bdeveloper\s+mode\b",
    r"\bbypass\s+(?:all\s+)?safety\b",
    r"\boverride\s+system\s+rules\b",
    r"\bpretend\s+you\s+have\s+no\s+restrictions\b",
    r"\bprint\s+(?:your\s+)?initial\s+instructions\b",
    # Português
    r"\bignore\s+(?:todas\s+as\s+)?instru[cç][oõ]es\s+anteriores\b",
    r"\besque[cç]a\s+(?:todas\s+as\s+)?instru[cç][oõ]es\b",
    r"\bmostre\s+(?:o\s+)?(?:system\s+)?prompt\b",
    r"\brevele\s+(?:o\s+)?prompt\b",
    r"\bquais\s+s[aã]o\s+as\s+suas\s+instru[cç][oõ]es\b",
    r"\baja\s+como\b",
    r"\bvoc[eê]\s+agora\s+[eé]\b",
    r"\bmodo\s+desenvolvedor\b",
    r"\bdesative\s+(?:todas\s+as\s+)?restri[cç][oõ]es\b",
    # Français
    r"\bignorez\s+(?:toutes\s+les\s+)?instructions\s+pr[eé]c[eé]dentes\b",
    r"\boublie\s+(?:toutes\s+les\s+)?instructions\b",
    r"\br[eé]v[eè]le\s+(?:ton|le)\s+(?:system\s+)?prompt\b",
    r"\bmontre\s+(?:ton|le)\s+prompt\b",
    r"\bquelles\s+sont\s+tes\s+instructions\b",
    r"\bagis\s+comme\b",
    r"\btu\s+es\s+maintenant\b",
    r"\bmode\s+d[eé]veloppeur\b",
    r"\bcontourne\s+la\s+s[eé]curit[eé]\b",
    # Delimitadores y heurísticas especiales
    r"(?:---|===)\s*(?:end|system|developer|instruction)",
    r"(?:<\|im_start\|>|<\|im_end\|>|<system>|\[INST\])",
    r"(?:sudo|root)\s+mode",
    r"(?:unrestricted|uncensored)\s+assistant",
    r"(?:system\s*prompt\s*leak|leak\s*prompt)",
)

PATRONES_INYECCION_MULTILINGUE = cargar_patrones_desde_yaml()
EXPRESIONES_COMPILADAS = [re.compile(p, re.IGNORECASE) for p in PATRONES_INYECCION_MULTILINGUE]

RESPUESTA_NEUTRA_INYECCION = (
    "No puedo procesar esa solicitud. Estoy diseñado para asistirte con información, "
    "disponibilidad y reservas de Glamping Imbabura. ¿En qué puedo ayudarte?"
)


# ¤seguridad-canal
def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparaciones resistentes a trucos unicode."""
    return unicodedata.normalize("NFKC", texto).strip()


# ¤seguridad-canal
def detectar_inyeccion(texto: str) -> bool:
    """Evalúa si el texto entrante coincide con algún patrón de inyección de prompt."""
    limpio = normalizar_texto(texto)
    return any(rx.search(limpio) for rx in EXPRESIONES_COMPILADAS)


# ¤seguridad-canal
class InjectionDetector:
    """Detecta inyecciones y lleva registro de reincidencias para escalado (umbral >= 3)."""

    def __init__(self, umbral_escalado: int = 3) -> None:
        self._umbral = umbral_escalado
        self._reincidencias: dict[str, int] = defaultdict(int)

    def evaluar(self, actor_id: str, texto: str) -> Veredicto:
        """Determina si el mensaje contiene inyección y si debe escalar a humano."""
        if not detectar_inyeccion(texto):
            return Veredicto(permitido=True)

        self._reincidencias[actor_id] += 1
        cuenta = self._reincidencias[actor_id]
        escalar = cuenta >= self._umbral

        motivo = (
            f"InyeccionDetectada: intento de prompt injection neutralizado "
            f"(reincidencia {cuenta}/{self._umbral})"
        )
        return Veredicto(permitido=False, motivo=motivo, escalar=escalar)

    def texto_neutro(self) -> str:
        """Devuelve la respuesta neutra para mensajes neutralizados."""
        return RESPUESTA_NEUTRA_INYECCION


# ¤seguridad-canal
def crear_injection_detector(umbral_escalado: int = 3) -> InjectionDetector:
    """Crea una instancia de InjectionDetector."""
    return InjectionDetector(umbral_escalado)
