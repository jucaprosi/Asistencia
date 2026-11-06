# ¤observabilidad
# ¤¤devops-engineer
"""Motor y detectores de alertas operativas (RF-OBS-04)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from features.observabilidad.tipos import Alerta, Traza

__all__ = ["DetectorAlertas"]


# ¤observabilidad
class DetectorAlertas:
    """Evalúa anomalías operativas sobre logs, trazas, colas y estados del sistema."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        self._config = config
        cfg_alertas = config.get("alertas", {})
        self.silencio_webhook_horas = int(cfg_alertas.get("silencio_webhook_horas", 2))
        self.tasa_errores_15m = float(cfg_alertas.get("tasa_errores_15m", 0.05))
        self.cola_crm_max = int(cfg_alertas.get("cola_crm_max", 10))
        costo_cfg = cfg_alertas.get("costo_diario_usd", 20)
        try:
            self.costo_diario_max = float(costo_cfg)
        except (ValueError, TypeError):
            self.costo_diario_max = 20.0

    # ¤observabilidad
    def verificar_silencio_webhook(
        self,
        ahora: datetime,
        ultimo_mensaje: datetime | None,
        hora_apertura: int = 8,
        hora_cierre: int = 20,
    ) -> Alerta | None:
        """Dispara si en horario operativo (08:00 - 20:00) pasan > 2h sin mensajes."""
        hora_actual = ahora.hour
        if hora_actual < hora_apertura or hora_actual >= hora_cierre:
            return None

        if ultimo_mensaje is None:
            return Alerta(
                nombre="silencio_webhook",
                severidad="critica",
                mensaje="Sin mensajes en el webhook durante horario operativo.",
                disparada_en=ahora,
            )

        diferencia_horas = (ahora - ultimo_mensaje).total_seconds() / 3600.0
        if diferencia_horas > self.silencio_webhook_horas:
            return Alerta(
                nombre="silencio_webhook",
                severidad="critica",
                mensaje=(
                    f"Webhook sin mensajes en {diferencia_horas:.1f} h en horario operativo "
                    f"(límite: {self.silencio_webhook_horas} h)."
                ),
                disparada_en=ahora,
            )
        return None

    # ¤observabilidad
    def verificar_tasa_errores(
        self,
        trazas: Sequence[Traza],
        ahora: datetime,
    ) -> Alerta | None:
        """Dispara si la tasa de errores en los últimos 15 min supera el 5 %."""
        inicio_ventana = ahora - timedelta(minutes=15)
        recientes = [t for t in trazas if t.inicio >= inicio_ventana]
        if not recientes:
            return None

        errores = 0
        for t in recientes:
            if t.resultado in ("error", "fallo", "excepcion", "fallido"):
                errores += 1
            elif any(s.atributos.get("error") for s in t.spans):
                errores += 1

        tasa = errores / len(recientes)
        if tasa > self.tasa_errores_15m:
            return Alerta(
                nombre="tasa_errores_alta",
                severidad="critica",
                mensaje=f"Tasa de errores ({tasa:.1%}) supera el umbral ({self.tasa_errores_15m:.1%}) en 15 min.",
                disparada_en=ahora,
            )
        return None

    # ¤observabilidad
    def verificar_cola_crm(self, tamano_cola: int, ahora: datetime) -> Alerta | None:
        """Dispara si la cola de publicaciones al CRM supera el máximo configurado."""
        if tamano_cola > self.cola_crm_max:
            return Alerta(
                nombre="cola_crm_congestionada",
                severidad="aviso",
                mensaje=f"Cola CRM con {tamano_cola} elementos (máximo permitido: {self.cola_crm_max}).",
                disparada_en=ahora,
            )
        return None

    # ¤observabilidad
    def verificar_costo_diario(
        self,
        costo_acumulado_usd: float | Decimal,
        ahora: datetime,
    ) -> Alerta | None:
        """Dispara si el costo diario de modelos excede el umbral configurado."""
        costo_num = float(costo_acumulado_usd)
        if costo_num > self.costo_diario_max:
            return Alerta(
                nombre="costo_diario_excedido",
                severidad="aviso",
                mensaje=f"Costo diario acumulado ({costo_num:.2f} USD) excede límite ({self.costo_diario_max:.2f} USD).",
                disparada_en=ahora,
            )
        return None

    # ¤observabilidad
    def verificar_evento_muerto(
        self,
        eventos: Sequence[Mapping[str, Any]],
        ahora: datetime,
    ) -> Alerta | None:
        """Dispara si existe algún evento con estado 'muerto' en canal.eventos_entrantes."""
        muertos = [e for e in eventos if e.get("estado") == "muerto"]
        if muertos:
            return Alerta(
                nombre="evento_muerto_canal",
                severidad="critica",
                mensaje=f"Se detectaron {len(muertos)} evento(s) en estado 'muerto' en canal.eventos_entrantes.",
                disparada_en=ahora,
            )
        return None

    # ¤observabilidad
    def verificar_handoff_desatendido(
        self,
        handoffs: Sequence[Mapping[str, Any]],
        ahora: datetime,
    ) -> Alerta | None:
        """Dispara si un handoff lleva > 15 minutos sin tomar en crm.handoffs."""
        for h in handoffs:
            estado = h.get("estado")
            creado_en = h.get("creado_en")
            if estado in ("pendiente", "sin_tomar") and isinstance(creado_en, datetime):
                demora = (ahora - creado_en).total_seconds()
                if demora > 900:  # 15 minutos
                    minutos = int(demora // 60)
                    return Alerta(
                        nombre="handoff_desatendido",
                        severidad="critica",
                        mensaje=f"Handoff sin tomar durante {minutos} minutos en crm.handoffs.",
                        disparada_en=ahora,
                    )
        return None

    # ¤observabilidad
    def verificar_venta_no_publicada(
        self,
        ventas: Sequence[Mapping[str, Any]],
        ahora: datetime,
    ) -> Alerta | None:
        """Dispara si una venta sigue en 'no_publicada' o 'pendiente' tras 24 horas."""
        for v in ventas:
            estado = v.get("estado")
            creado_en = v.get("creado_en")
            if estado in ("no_publicada", "pendiente") and isinstance(creado_en, datetime):
                demora = (ahora - creado_en).total_seconds()
                if demora > 86400:  # 24 horas
                    horas = int(demora // 3600)
                    return Alerta(
                        nombre="venta_no_publicada_24h",
                        severidad="aviso",
                        mensaje=f"Venta con estado '{estado}' tras {horas} horas sin publicarse.",
                        disparada_en=ahora,
                    )
        return None

    # ¤observabilidad
    def verificar_todas(
        self,
        ahora: datetime | None = None,
        fuente_datos: Mapping[str, Any] | None = None,
    ) -> tuple[Alerta, ...]:
        """Ejecuta todas las reglas de alerta y devuelve las que se hayan disparado."""
        instante = ahora or datetime.now(timezone.utc)
        datos = fuente_datos or {}
        alertas: list[Alerta] = []

        # 1. Silencio webhook
        if "ultimo_mensaje_at" in datos or "silencio_webhook" in datos:
            ultimo = datos.get("ultimo_mensaje_at")
            a1 = self.verificar_silencio_webhook(instante, ultimo)
            if a1:
                alertas.append(a1)

        # 2. Tasa de errores 15m
        if "trazas" in datos:
            a2 = self.verificar_tasa_errores(datos["trazas"], instante)
            if a2:
                alertas.append(a2)

        # 3. Cola CRM
        if "cola_crm" in datos or "tamano_cola_crm" in datos:
            tamano = int(datos.get("tamano_cola_crm", datos.get("cola_crm", 0)))
            a3 = self.verificar_cola_crm(tamano, instante)
            if a3:
                alertas.append(a3)

        # 4. Costo diario acumulado
        if "costo_diario" in datos or "costo_diario_usd" in datos:
            costo = float(datos.get("costo_diario_usd", datos.get("costo_diario", 0.0)))
            a4 = self.verificar_costo_diario(costo, instante)
            if a4:
                alertas.append(a4)

        # 5. Evento muerto en canal
        if "eventos" in datos or "eventos_entrantes" in datos:
            eventos = datos.get("eventos_entrantes", datos.get("eventos", ()))
            a5 = self.verificar_evento_muerto(eventos, instante)
            if a5:
                alertas.append(a5)

        # 6. Handoff desatendido
        if "handoffs" in datos:
            a6 = self.verificar_handoff_desatendido(datos["handoffs"], instante)
            if a6:
                alertas.append(a6)

        # 7. Venta no publicada > 24h
        if "ventas" in datos:
            a7 = self.verificar_venta_no_publicada(datos["ventas"], instante)
            if a7:
                alertas.append(a7)

        return tuple(alertas)
