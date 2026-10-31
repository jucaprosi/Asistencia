# ¤canal-whatsapp
# ¤¤integration-engineer
"""Compuerta pública de la sala canal_whatsapp (RF-GW-01..06).

Fase 0: interfaz declarada e importable; la lógica llega en TASK-001 (RF-GW-01..05) y TASK-006 (RF-GW-06).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

from features.canal_whatsapp.tipos import (
    Canal, MensajeEntrante, MensajeSaliente, Plantilla, ResultadoEnvio, TipoContenido,
)

__all__ = [
    "Canal", "MensajeEntrante", "MensajeSaliente", "Plantilla", "ResultadoEnvio", "TipoContenido",
    "ErrorCanalWhatsapp", "CanalWhatsappService", "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_canal_whatsapp.yaml")
Receptor = Callable[[MensajeEntrante], Any]


# ¤canal-whatsapp
class ErrorCanalWhatsapp(Exception):
    """Error tipado de la sala: ``codigo`` estable, ``mensaje_usuario`` apto para mostrar, detalle técnico aparte."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(f"{codigo}: {mensaje_usuario}")
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤canal-whatsapp
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    """Lee ``config_canal_whatsapp.yaml``; los secretos ``${VAR}`` los resuelve el pasillo central."""
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤canal-whatsapp
class CanalWhatsappService:
    """Recepción y envío por la Cloud API oficial; ventana de 24 h; plantillas; medios; separación de canales."""

    def __init__(self, config: Mapping[str, Any], *, seguridad: Any, observabilidad: Any) -> None:
        self._config = config
        self._seguridad = seguridad
        self._observabilidad = observabilidad
        self._receptores: dict[Canal, Receptor] = {}

    def registrar_receptor(self, canal: Canal, receptor: Receptor) -> None:
        """El pasillo central enlaza aquí al agente (huéspedes) y al ARM (vendedores). Un receptor por canal."""
        if canal in self._receptores:
            raise ErrorCanalWhatsapp("RECEPTOR_DUPLICADO", "Canal ya enlazado", f"canal={canal.value}")
        self._receptores[canal] = receptor

    def receptores(self) -> Mapping[Canal, Receptor]:
        return dict(self._receptores)

    def verificar_webhook(self, modo: str, token: str, desafio: str) -> str | None:
        raise NotImplementedError("TASK-001 RF-GW-01")

    def recibir(self, cuerpo: bytes, firma_sha256: str) -> list[MensajeEntrante]:
        raise NotImplementedError("TASK-001 RF-GW-01")

    def clasificar_canal(self, remitente: str, grupo_id: str | None) -> Canal:
        raise NotImplementedError("TASK-006 RF-GW-06")

    def en_ventana_24h(self, destinatario: str) -> bool:
        raise NotImplementedError("TASK-001 RF-GW-03")

    def enviar(self, mensaje: MensajeSaliente) -> ResultadoEnvio:
        raise NotImplementedError("TASK-001 RF-GW-02")

    def enviar_plantilla(self, destinatario: str, plantilla: Plantilla) -> ResultadoEnvio:
        raise NotImplementedError("TASK-001 RF-GW-04")

    def actualizar_estado(self, mensaje_id: str, estado: str) -> None:
        raise NotImplementedError("TASK-001 RF-GW-02")

    def descargar_medio(self, medio_id: str) -> str:
        raise NotImplementedError("TASK-001 RF-GW-05")
