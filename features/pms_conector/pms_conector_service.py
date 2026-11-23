# ¤pms-conector
# ¤¤integration-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala pms_conector (RF-PMS-01..06, INV_ESCRITURA_PMS_EXPLICITA).

Provee acceso desacoplado a disponibilidad, tarifas, reservas y contingencias locales.
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.pms_conector.base_internal import PMSConnector
from features.pms_conector.fake_internal import FakePMS
from features.pms_conector.persistencia_internal import inicializar_base_datos
from features.pms_conector.plataforma_internal import PlataformaPMS
from features.pms_conector.tipos import (
    AislamientoAnfitrionError,
    CapacidadExcedida,
    Cotizacion,
    Disponibilidad,
    ErrorPMS,
    EscrituraDeshabilitada,
    EstadoReserva,
    FechasInvalidas,
    IdempotenciaRequerida,
    Incidencia,
    InstruccionesCheckin,
    PMSNoDisponible,
    Propiedad,
    PropiedadInexistente,
    Reserva,
    ReservaInexistente,
    SinDisponibilidad,
    TipoPropiedad,
    Unidad,
    UnidadInexistente,
)

__all__ = [
    "Cotizacion",
    "Disponibilidad",
    "EstadoReserva",
    "Incidencia",
    "InstruccionesCheckin",
    "Propiedad",
    "Reserva",
    "TipoPropiedad",
    "Unidad",
    "ErrorPMS",
    "PMSNoDisponible",
    "PropiedadInexistente",
    "UnidadInexistente",
    "FechasInvalidas",
    "SinDisponibilidad",
    "EscrituraDeshabilitada",
    "ReservaInexistente",
    "IdempotenciaRequerida",
    "CapacidadExcedida",
    "AislamientoAnfitrionError",
    "PMSConnector",
    "FakePMS",
    "PlataformaPMS",
    "PMSConectorService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_pms_conector.yaml")


# ¤pms-conector
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    """Carga la configuración YAML del conector PMS."""
    if not ruta.is_file():
        return {}
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤pms-conector
def _resolver_valor(valor: Any) -> Any:
    """Resuelve variables de entorno con valor por defecto de la forma ${VAR:-defecto}."""
    if isinstance(valor, str) and valor.startswith("${") and valor.endswith("}"):
        contenido = valor[2:-1]
        if ":-" in contenido:
            var, defecto = contenido.split(":-", 1)
            import os
            return os.environ.get(var, defecto)
        import os
        return os.environ.get(contenido, "")
    return valor


# ¤pms-conector
class PMSConectorService:
    """Compuerta pública del conector PMS. Lecturas libres; escrituras deshabilitadas por defecto."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        observabilidad: Any = None,
        conector: PMSConnector | None = None,
        conexion: sqlite3.Connection | None = None,
    ) -> None:
        cfg = cargar_config() if config is None else config
        self._config = dict(cfg)
        self._observabilidad = observabilidad
        self._conn = conexion or inicializar_base_datos()

        self._timeout_s = float(_resolver_valor(self._config.get("timeout_s", 8.0)))
        self._reintentos_lectura = int(_resolver_valor(self._config.get("reintentos_lectura", 2)))
        self._escrituras = dict(self._config.get("escrituras_habilitadas", {}))

        if conector is not None:
            self._conector = conector
        else:
            self._conector = self._seleccionar_proveedor()

        # Cache de idempotencia en memoria si aplica
        self._cache_idempotencia: dict[str, Any] = {}

    def _seleccionar_proveedor(self) -> PMSConnector:
        nombre = str(_resolver_valor(self._config.get("proveedor", "fake"))).lower()
        if nombre == "fake":
            return FakePMS()
        if nombre == "plataforma":
            return PlataformaPMS(conexion=self._conn)
        return FakePMS()

    @property
    def conector(self) -> PMSConnector:
        """Acceso al conector subyacente para pruebas de contrato."""
        return self._conector

    @property
    def conexion(self) -> sqlite3.Connection:
        """Acceso a la base de datos interna para auditoría de esquemas."""
        return self._conn

    def proveedor(self) -> str:
        """Retorna el identificador del proveedor PMS activo."""
        return str(_resolver_valor(self._config.get("proveedor", "fake")))

    def _verificar_escritura(self, operacion: str, clave_idempotencia: str | None) -> None:
        """Valida que la operación de escritura esté explícitamente permitida y tenga clave de idempotencia."""
        if not clave_idempotencia or not str(clave_idempotencia).strip():
            raise IdempotenciaRequerida(f"La operación '{operacion}' requiere clave de idempotencia obligatoria")

        habilitada = bool(self._escrituras.get(operacion, False))
        if not habilitada:
            raise EscrituraDeshabilitada(
                f"La operación de escritura '{operacion}' no está habilitada en config_pms_conector.yaml"
            )

    def _ejecutar_lectura(self, accion: str, func, *args, **kwargs) -> Any:
        """Ejecuta una lectura con política de reintentos configurada (RF-PMS-03)."""
        intentos = 0
        ultimo_error: Exception | None = None

        while intentos <= self._reintentos_lectura:
            t0 = time.time()
            try:
                res = func(*args, **kwargs)
                duracion = time.time() - t0
                if duracion > self._timeout_s:
                    raise TimeoutError(f"PMS superó tiempo máximo de {self._timeout_s}s (t={duracion:.2f}s)")
                return res
            except (TimeoutError, PMSNoDisponible) as exc:
                ultimo_error = exc
                intentos += 1
                if intentos <= self._reintentos_lectura:
                    time.sleep(0.05 * intentos)
            except ErrorPMS:
                raise
            except Exception as exc:
                raise PMSNoDisponible(f"Error inesperado de comunicación con el PMS en {accion}: {exc}") from exc

        raise PMSNoDisponible(f"PMS no disponible en {accion} tras {intentos} reintentos", detalle_tecnico=str(ultimo_error))

    def listar_propiedades(self) -> tuple[Propiedad, ...]:
        return self._ejecutar_lectura("listar_propiedades", self._conector.listar_propiedades)

    def consultar_disponibilidad(
        self, propiedad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Disponibilidad:
        return self._ejecutar_lectura(
            "consultar_disponibilidad",
            self._conector.consultar_disponibilidad,
            propiedad_id,
            desde,
            hasta,
            huespedes,
        )

    def cotizar(
        self, propiedad_id: str, unidad_id: str, desde: date, hasta: date, huespedes: int
    ) -> Cotizacion:
        return self._ejecutar_lectura(
            "cotizar", self._conector.cotizar, propiedad_id, unidad_id, desde, hasta, huespedes
        )

    def crear_reserva_preliminar(
        self,
        propiedad_id: str,
        unidad_id: str,
        desde: date,
        hasta: date,
        huespedes: int,
        huesped_token: str,
        clave_idempotencia: str,
    ) -> Reserva:
        self._verificar_escritura("crear_reserva_preliminar", clave_idempotencia)

        if clave_idempotencia in self._cache_idempotencia:
            return self._cache_idempotencia[clave_idempotencia]

        reserva = self._conector.crear_reserva_preliminar(
            propiedad_id,
            unidad_id,
            desde,
            hasta,
            huespedes,
            huesped_token,
            clave_idempotencia,
        )

        # Guardar en referencia local pms.reservas_ref (RF-PMS-06)
        self._guardar_referencia_local(reserva)
        self._cache_idempotencia[clave_idempotencia] = reserva
        return reserva

    def confirmar_reserva(self, codigo: str, clave_idempotencia: str) -> Reserva:
        self._verificar_escritura("confirmar_reserva", clave_idempotencia)
        if clave_idempotencia in self._cache_idempotencia:
            return self._cache_idempotencia[clave_idempotencia]

        reserva = self._conector.confirmar_reserva(codigo, clave_idempotencia)
        self._guardar_referencia_local(reserva)
        self._cache_idempotencia[clave_idempotencia] = reserva
        return reserva

    def obtener_reserva(self, codigo: str) -> Reserva:
        reserva = self._ejecutar_lectura("obtener_reserva", self._conector.obtener_reserva, codigo)
        self._guardar_referencia_local(reserva)
        return reserva

    def reservas_con_llegada(self, fecha: date) -> tuple[Reserva, ...]:
        return self._ejecutar_lectura("reservas_con_llegada", self._conector.reservas_con_llegada, fecha)

    def cancelar_reserva(self, codigo: str, motivo: str, clave_idempotencia: str) -> Reserva:
        self._verificar_escritura("cancelar_reserva", clave_idempotencia)
        if clave_idempotencia in self._cache_idempotencia:
            return self._cache_idempotencia[clave_idempotencia]

        reserva = self._conector.cancelar_reserva(codigo, motivo, clave_idempotencia)
        self._guardar_referencia_local(reserva)
        self._cache_idempotencia[clave_idempotencia] = reserva
        return reserva

    def obtener_instrucciones_checkin(self, codigo_reserva: str) -> InstruccionesCheckin:
        return self._ejecutar_lectura(
            "obtener_instrucciones_checkin", self._conector.obtener_instrucciones_checkin, codigo_reserva
        )

    def registrar_incidencia(self, incidencia: Incidencia, clave_idempotencia: str) -> Incidencia:
        self._verificar_escritura("registrar_incidencia", clave_idempotencia)
        if clave_idempotencia in self._cache_idempotencia:
            return self._cache_idempotencia[clave_idempotencia]

        creada = self._conector.registrar_incidencia(incidencia, clave_idempotencia)
        self._cache_idempotencia[clave_idempotencia] = creada
        return creada

    def registrar_tarea_housekeeping(
        self,
        propiedad_id: str,
        unidad_id: str,
        fecha: date,
        nota: str,
        clave_idempotencia: str,
    ) -> str:
        self._verificar_escritura("housekeeping", clave_idempotencia)
        if clave_idempotencia in self._cache_idempotencia:
            return self._cache_idempotencia[clave_idempotencia]

        tarea_id = self._conector.registrar_tarea_housekeeping(
            propiedad_id, unidad_id, fecha, nota, clave_idempotencia
        )
        self._cache_idempotencia[clave_idempotencia] = tarea_id
        return tarea_id

    def guardar_tarifas(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        precio: Decimal,
        minimo_noches: int,
        actor_id: str,
    ) -> int:
        return self._conector.guardar_tarifas(unidad_id, desde, hasta, precio, minimo_noches, actor_id)

    def actualizar_calendario(
        self,
        unidad_id: str,
        desde: date,
        hasta: date,
        accion: str,
        actor_id: str,
    ) -> tuple[int, int]:
        afectadas, omitidas = self._conector.actualizar_calendario(unidad_id, desde, hasta, accion, actor_id)
        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "INFO",
                "calendario_actualizado",
                unidad_id=unidad_id,
                desde=desde.isoformat(),
                hasta=hasta.isoformat(),
                accion=accion,
                actor_id=actor_id,
                afectadas=afectadas,
                omitidas=omitidas,
            )
        return afectadas, omitidas

    def _guardar_referencia_local(self, reserva: Reserva) -> None:
        """Almacena o actualiza la reserva en la tabla local pms.reservas_ref (RF-PMS-06)."""
        expira_str = reserva.expira_en.isoformat() if reserva.expira_en else None
        self._conn.execute(
            """
            INSERT INTO pms.reservas_ref (
                codigo_reserva, propiedad_id, unidad_id, huesped_token, desde, hasta,
                huespedes, total, estado, expira_en, pms_ref, actualizada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(codigo_reserva) DO UPDATE SET
                estado = excluded.estado,
                expira_en = excluded.expira_en,
                actualizada = CURRENT_TIMESTAMP
            """,
            (
                reserva.codigo,
                reserva.propiedad_id,
                reserva.unidad_id,
                reserva.huesped_token,
                reserva.desde.isoformat(),
                reserva.hasta.isoformat(),
                reserva.huespedes,
                str(reserva.total),
                reserva.estado.value,
                expira_str,
                reserva.pms_ref,
            ),
        )
        self._conn.commit()

    def validar_titular_local(self, codigo_reserva: str, huesped_token: str) -> bool:
        """RF-PMS-06: Valida al titular contra la referencia local sin consultar al PMS remoto."""
        cursor = self._conn.execute(
            """
            SELECT codigo_reserva, estado FROM pms.reservas_ref
            WHERE codigo_reserva = ? AND huesped_token = ?
            """,
            (codigo_reserva, huesped_token),
        )
        fila = cursor.fetchone()
        if fila and fila["estado"] in ("confirmada", "preliminar"):
            return True
        return False

    def obtener_referencia_local(self, codigo_reserva: str) -> Reserva | None:
        """Recupera la reserva almacenada localmente en pms.reservas_ref sin consultar al PMS."""
        cursor = self._conn.execute(
            """
            SELECT codigo_reserva, propiedad_id, unidad_id, huesped_token, desde, hasta,
                   huespedes, total, estado, expira_en, pms_ref
            FROM pms.reservas_ref
            WHERE codigo_reserva = ?
            """,
            (codigo_reserva,),
        )
        fila = cursor.fetchone()
        if not fila:
            return None

        expira_dt = datetime.fromisoformat(fila["expira_en"]) if fila["expira_en"] else None
        return Reserva(
            codigo=fila["codigo_reserva"],
            propiedad_id=fila["propiedad_id"],
            unidad_id=fila["unidad_id"],
            huesped_token=fila["huesped_token"],
            desde=date.fromisoformat(fila["desde"]),
            hasta=date.fromisoformat(fila["hasta"]),
            huespedes=int(fila["huespedes"]),
            estado=EstadoReserva(fila["estado"]),
            total=Decimal(fila["total"]),
            expira_en=expira_dt,
            pms_ref=fila["pms_ref"],
        )
