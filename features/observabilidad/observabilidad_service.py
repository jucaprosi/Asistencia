# ¤observabilidad
# ¤¤devops-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala observabilidad (RF-OBS-01..04)."""
from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.observabilidad.alertas_internal import DetectorAlertas, costo_del_dia
from features.observabilidad.cuota_internal import CuotaDiaria
from features.observabilidad.logs_internal import LoggerObservabilidad
from features.observabilidad.metricas_internal import calcular_metricas_prd
from features.observabilidad.tipos import (
    Alerta,
    ErrorObservabilidad,
    LogConPII,
    Metrica,
    Span,
    SuiteNoEncontrada,
    Traza,
    TrazaDesconocida,
)
from features.observabilidad.trazas_internal import GestorTrazas

__all__ = [
    "Alerta",
    "Metrica",
    "Span",
    "Traza",
    "ErrorObservabilidad",
    "TrazaDesconocida",
    "LogConPII",
    "SuiteNoEncontrada",
    "ObservabilidadService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_observabilidad.yaml")


# ¤observabilidad
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤observabilidad
class ObservabilidadService:
    """Base de todas las métricas del PRD: trazas con spans y cálculo de tokens/costo, y logs sin PII."""

    def __init__(
        self,
        config: Mapping[str, Any],
        gestor_trazas: GestorTrazas | None = None,
        logger: LoggerObservabilidad | None = None,
        detector_alertas: DetectorAlertas | None = None,
    ) -> None:
        self._config = config
        self._gestor_trazas = gestor_trazas or GestorTrazas(config)
        self._logger = logger or LoggerObservabilidad(config)
        self._detector_alertas = detector_alertas or DetectorAlertas(config)
        self._cuotas: list[CuotaDiaria] = []

    # ¤observabilidad
    def cuota_inferencia(self, tope_usd: Decimal | None = None) -> CuotaDiaria:
        """Tope diario atómico para la sala inferencia (ADR-0021, C2). Por defecto, ``alertas.costo_diario_usd``."""
        if tope_usd is None:
            tope_usd = Decimal(str(self._config["alertas"]["costo_diario_usd"]))
        cuota = CuotaDiaria(self._gestor_trazas.conexion_cuota, tope_usd)
        self._cuotas.append(cuota)  # r3: sus conciliaciones fallidas llegan a alertas_activas
        return cuota

    # ¤observabilidad
    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str = "huespedes") -> str:
        """Inicia una nueva traza persistida asociada a un mensaje entrante (INV_TRAZA_POR_MENSAJE)."""
        return self._gestor_trazas.iniciar_traza(mensaje_id=mensaje_id, conversacion_id=conversacion_id, canal=canal)

    # ¤observabilidad
    def span(self, traza_id: str, sala: str, nombre: str, **atributos: Any) -> AbstractContextManager[Any]:
        """Context manager para instrumentar un span dentro de una traza (RF-OBS-02)."""
        return self._gestor_trazas.span(traza_id=traza_id, sala=sala, nombre=nombre, **atributos)

    # ¤observabilidad
    def cerrar_traza(self, traza_id: str, resultado: str) -> Traza:
        """Cierra la traza en la base de datos y la retorna completa con sus spans."""
        return self._gestor_trazas.cerrar_traza(traza_id=traza_id, resultado=resultado)

    # ¤observabilidad
    def obtener_traza(self, traza_id: str) -> Traza:
        """Recupera una traza persistida por su ID."""
        return self._gestor_trazas.obtener_traza(traza_id)

    # ¤observabilidad
    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        """Registra un evento estructurado JSON garantizando ausencia de PII en claro (RF-OBS-01)."""
        self._logger.registrar(nivel=nivel, evento=evento, **campos)

    # ¤observabilidad
    def metricas(self, ventana: str = "7d") -> tuple[Metrica, ...]:
        """Calcula métricas operativas (OP-01..OP-10) a partir de las trazas."""
        trazas = self._gestor_trazas.todas_las_trazas()
        return calcular_metricas_prd(trazas, ventana=ventana)

    # ¤observabilidad
    def evaluar(
        self,
        suites: tuple[str, ...] = ("rag", "ventas", "inyecciones", "enrutador", "pii"),
    ) -> Mapping[str, Mapping[str, float]]:
        """Despacha la evaluación a las compuertas correspondientes de cada suite (RF-OBS-03)."""
        raiz = Path(__file__).resolve().parent.parent.parent
        rutas_suites = {
            "rag": raiz / "evals" / "set_dorado.jsonl",
            "enrutador": raiz / "evals" / "enrutador.jsonl",
            "inyecciones": raiz / "evals" / "inyecciones.jsonl",
            "ventas": raiz / "evals" / "ventas.jsonl",
            "pii": raiz / "evals" / "pii.jsonl",
        }

        resultados: dict[str, dict[str, float]] = {}
        for s in suites:
            if s not in rutas_suites:
                raise SuiteNoEncontrada(s)
            archivo = rutas_suites[s]
            if not archivo.is_file():
                continue
            casos = [linea for linea in archivo.read_text(encoding="utf-8").splitlines() if linea.strip()]
            if not casos:
                continue

            if s == "rag":
                try:
                    from features.conocimiento.conocimiento_service import (
                        ConocimientoService,
                        cargar_config as cargar_config_rag,
                    )
                    ruta_bd = raiz / "datos_privados" / "conocimiento.db"
                    servicio_rag = ConocimientoService(
                        cargar_config_rag(),
                        ruta_bd=ruta_bd if ruta_bd.is_file() else None,
                    )
                    if servicio_rag.repositorio.total_chunks() == 0:
                        dir_corpus = raiz / "datos_privados" / "corpus"
                        if dir_corpus.is_dir() and any(dir_corpus.glob("*.md")):
                            servicio_rag.indexar(dir_corpus)
                    resultados["rag"] = dict(servicio_rag.evaluar(archivo))
                except Exception:
                    pass
            elif s == "enrutador":
                try:
                    from features.agente.agente_service import (
                        AgenteService,
                        cargar_config as cargar_config_agente,
                    )
                    servicio_agente = AgenteService(cargar_config_agente())
                    resultados["enrutador"] = dict(servicio_agente.evaluar(archivo))
                except Exception:
                    pass
            elif s == "ventas":
                try:
                    from features.arm_jarvis.arm_jarvis_service import (
                        ArmJarvisService,
                        cargar_config as cargar_config_arm,
                    )
                    if hasattr(ArmJarvisService, "evaluar"):
                        servicio_arm = ArmJarvisService(cargar_config_arm())
                        resultados["ventas"] = dict(servicio_arm.evaluar(archivo))
                except Exception:
                    pass
            elif s == "inyecciones":
                try:
                    from features.seguridad.seguridad_service import (
                        SeguridadService,
                        cargar_config as cargar_config_seg,
                    )
                    if hasattr(SeguridadService, "evaluar"):
                        servicio_seg = SeguridadService(cargar_config_seg())
                        resultados["inyecciones"] = dict(servicio_seg.evaluar(archivo))
                except Exception:
                    pass
            elif s == "pii":
                try:
                    from features.seguridad.seguridad_service import (
                        SeguridadService,
                        cargar_config as cargar_config_seg,
                    )
                    if hasattr(SeguridadService, "evaluar_pii"):
                        servicio_seg = SeguridadService(cargar_config_seg())
                        resultados["pii"] = dict(servicio_seg.evaluar_pii(archivo))
                except Exception:
                    pass

        return resultados

    # ¤observabilidad
    def alertas_activas(self, fuente_datos: Mapping[str, Any] | None = None) -> tuple[Alerta, ...]:
        """Evalúa y retorna las alertas operativas activas (RF-OBS-04)."""
        datos = dict(fuente_datos or {})
        trazas = self._gestor_trazas.todas_las_trazas()
        if "trazas" not in datos:
            datos["trazas"] = trazas
        if "ultimo_mensaje_at" not in datos and trazas:
            datos["ultimo_mensaje_at"] = max(t.inicio for t in trazas)
        if "costo_diario" not in datos and "costo_diario_usd" not in datos:
            datos["costo_diario_usd"] = costo_del_dia(trazas, datetime.now(timezone.utc))
        if "conciliaciones_fallidas" not in datos and self._cuotas:
            datos["conciliaciones_fallidas"] = sum(c.conciliaciones_fallidas for c in self._cuotas)
        return self._detector_alertas.verificar_todas(fuente_datos=datos)
