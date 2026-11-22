# ¤conocimiento-rag
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Evaluación continua del motor RAG frente al set dorado (RF-RAG-04, RF-RAG-06, INV_NO_LO_SE)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from features.conocimiento.recuperador_internal import RecuperadorHibrido


# ¤conocimiento-rag
class EvaluadorSetDorado:
    """Evalúa fidelidad, tasa de abstención y alucinaciones de precios/políticas."""

    def __init__(self, recuperador: RecuperadorHibrido) -> None:
        self._recuperador = recuperador

    # ¤conocimiento-rag
    def evaluar_archivo(self, ruta_set_dorado: Path) -> dict[str, float]:
        """Ejecuta todos los casos de prueba del set dorado y compila las métricas de calidad."""
        if not ruta_set_dorado.is_file():
            return {
                "fidelidad": 0.0,
                "abstencion": 0.0,
                "alucinaciones_precio_politica": 0.0,
                "p95_latencia_ms": 0.0,
            }

        lineas = [l.strip() for l in ruta_set_dorado.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lineas:
            return {
                "fidelidad": 0.0,
                "abstencion": 0.0,
                "alucinaciones_precio_politica": 0.0,
                "p95_latencia_ms": 0.0,
            }

        casos_positivos = 0
        aciertos_positivos = 0
        casos_trampa = 0
        aciertos_abstencion = 0
        alucinaciones = 0
        latencias_ms: list[float] = []

        for linea in lineas:
            try:
                caso = json.loads(linea)
            except json.JSONDecodeError:
                continue

            pregunta = caso.get("pregunta", "")
            propiedad_id = caso.get("propiedad_id", "glamping")
            espera_abstencion = bool(caso.get("espera_abstencion", False))
            respuesta_esperada = caso.get("respuesta_esperada", "")
            tipo_caso = caso.get("tipo", "")

            t0 = time.time()
            resultado = self._recuperador.recuperar(pregunta, propiedad_id)
            latencia = (time.time() - t0) * 1000.0
            latencias_ms.append(latencia)

            if espera_abstencion:
                casos_trampa += 1
                if not resultado.suficiente:
                    aciertos_abstencion += 1
                else:
                    # Sobre umbral en pregunta trampa
                    if tipo_caso in ("precios", "politicas", "trampa_precio", "trampa_politica"):
                        alucinaciones += 1
            else:
                casos_positivos += 1
                if resultado.suficiente and resultado.fragmentos:
                    # Verificar si la respuesta o fragmento contiene palabras clave de la respuesta esperada
                    textos_recuperados = " ".join(f"{f.encabezado} {f.texto}".lower() for f in resultado.fragmentos)
                    tokens_esperados = [t for t in respuesta_esperada.lower().split() if len(t) > 3]
                    if not tokens_esperados or any(t in textos_recuperados for t in tokens_esperados):
                        aciertos_positivos += 1
                    else:
                        # Si es suficiente pero no contiene tokens clave, considerar si la similitud fue alta
                        if resultado.mejor_puntuacion >= 0.60:
                            aciertos_positivos += 1

        fidelidad = (aciertos_positivos / casos_positivos) if casos_positivos > 0 else 1.0
        abstencion = (aciertos_abstencion / casos_trampa) if casos_trampa > 0 else 1.0

        latencias_ms.sort()
        if latencias_ms:
            idx_p95 = int(len(latencias_ms) * 0.95)
            p95 = latencias_ms[min(idx_p95, len(latencias_ms) - 1)]
        else:
            p95 = 0.0

        return {
            "fidelidad": round(fidelidad, 4),
            "abstencion": round(abstencion, 4),
            "alucinaciones_precio_politica": float(alucinaciones),
            "p95_latencia_ms": round(p95, 2),
        }
