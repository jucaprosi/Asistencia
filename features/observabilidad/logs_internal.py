# ¤observabilidad
# ¤¤devops-engineer
"""Manejo de logs estructurados en JSON por línea sin PII (RF-OBS-01, INV_PII_FUERA_DEL_MODELO)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from features.observabilidad.tipos import LogConPII

__all__ = ["LoggerObservabilidad", "detectar_pii", "redactar_pii"]

# Patrones canónicos de PII: números telefónicos (Ecuador / internacionales) y correos electrónicos
PATRON_TELEFONO = re.compile(
    r"(?:\+?593\s?|0)(?:9\d{8}|[2-7]\d{7})\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|\b\+?\d{9,15}\b"
)
PATRON_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)
PATRON_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


# ¤observabilidad
def detectar_pii(valor: Any) -> tuple[bool, str | None]:
    """Detecta la presencia de números de teléfono o correos electrónicos en cualquier estructura."""
    if isinstance(valor, str):
        # Excluir UUIDs canónicos antes de evaluar dígitos telefónicos
        texto_limpio = PATRON_UUID.sub("", valor)
        if PATRON_TELEFONO.search(texto_limpio):
            return True, f"Número telefónico detectado en '{valor}'"
        if PATRON_EMAIL.search(texto_limpio):
            return True, f"Correo electrónico detectado en '{valor}'"
    elif isinstance(valor, Mapping):
        for k, v in valor.items():
            detectado, motivo = detectar_pii(v)
            if detectado:
                return True, f"Campo '{k}': {motivo}"
    elif isinstance(valor, (list, tuple, set)):
        for elemento in valor:
            detectado, motivo = detectar_pii(elemento)
            if detectado:
                return True, motivo
    return False, None


# ¤observabilidad
def redactar_pii(valor: Any) -> Any:
    """Reemplaza teléfonos y correos en cadenas y estructuras recursivas por marcadores seguros."""
    if isinstance(valor, str):
        uuids: dict[str, str] = {}

        def _proteger_uuid(match: re.Match[str]) -> str:
            clave = f"__UUID_SAFE_{len(uuids)}__"
            uuids[clave] = match.group(0)
            return clave

        texto = PATRON_UUID.sub(_proteger_uuid, valor)
        texto = PATRON_TELEFONO.sub("[REDACTADO_TEL]", texto)
        texto = PATRON_EMAIL.sub("[REDACTADO_EMAIL]", texto)
        for clave, uuid_orig in uuids.items():
            texto = texto.replace(clave, uuid_orig)
        return texto
    elif isinstance(valor, Mapping):
        return {k: redactar_pii(v) for k, v in valor.items()}
    elif isinstance(valor, (list, tuple)):
        return type(valor)(redactar_pii(v) for v in valor)
    return valor


# ¤observabilidad
class LoggerObservabilidad:
    """Emite logs estructurados JSON por línea verificando ausencia absoluta de PII."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self._config = config
        self._cfg_logs = config.get("logs", {})
        self._nivel = str(self._cfg_logs.get("nivel", "INFO")).upper()
        self._destino = str(self._cfg_logs.get("destino", "stdout")).lower()
        self._ruta = str(self._cfg_logs.get("ruta", "/var/log/glamping"))
        self._redaccion_verificada = bool(self._cfg_logs.get("redaccion_verificada", True))
        self._buffer: list[str] = []

    # ¤observabilidad
    def registrar(self, nivel: str, evento: str, redactar: bool = False, **campos: Any) -> str:
        """Registra un evento JSON. Si redactar=False y hay PII, lanza LogConPII (rechazo estricto)."""
        nivel_str = str(nivel).upper()

        if redactar:
            evento_limpio = redactar_pii(evento)
            campos_limpios = {k: redactar_pii(v) for k, v in campos.items()}
        else:
            # Validación de ausencia de PII en evento y campos
            if self._redaccion_verificada:
                pii_evento, motivo_ev = detectar_pii(evento)
                if pii_evento:
                    raise LogConPII(motivo=motivo_ev or "PII en evento")
                for k, v in campos.items():
                    pii_campo, motivo_c = detectar_pii(v)
                    if pii_campo:
                        raise LogConPII(motivo=f"Campo '{k}': {motivo_c}")

            evento_limpio = evento
            campos_limpios = dict(campos)

        # Construcción del registro estándar RF-OBS-01
        registro: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "nivel": nivel_str,
            "evento": evento_limpio,
            "conversacion_id": campos_limpios.pop("conversacion_id", None),
            "propiedad_id": campos_limpios.pop("propiedad_id", None),
            "rol": campos_limpios.pop("rol", None),
            "sala": campos_limpios.pop("sala", None),
            "duracion_ms": campos_limpios.pop("duracion_ms", None),
        }
        registro.update(campos_limpios)

        linea_json = json.dumps(registro, ensure_ascii=False)
        self._buffer.append(linea_json)

        # Emisión al destino configurado
        if self._destino == "stdout":
            sys.stdout.write(linea_json + "\n")
            sys.stdout.flush()
        elif self._destino == "archivo":
            self._escribir_en_archivo(linea_json)

        return linea_json

    def _escribir_en_archivo(self, linea: str) -> None:
        try:
            ruta_dir = Path(self._ruta)
            if ruta_dir.suffix:
                archivo = ruta_dir
                archivo.parent.mkdir(parents=True, exist_ok=True)
            else:
                ruta_dir.mkdir(parents=True, exist_ok=True)
                archivo = ruta_dir / "observabilidad.log"
            with archivo.open("a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except OSError:
            # Si el volumen del sistema no es accesible en pruebas locales, conserva en buffer
            pass

    # ¤observabilidad
    def lineas(self) -> tuple[str, ...]:
        """Devuelve las líneas JSON registradas en memoria."""
        return tuple(self._buffer)

    # ¤observabilidad
    def limpiar_buffer(self) -> None:
        self._buffer.clear()
