# ¤observabilidad
# ¤¤devops-engineer
"""Gestión, cálculo de tokens/costo y persistencia de trazas y spans (RF-OBS-02, INV_TRAZA_POR_MENSAJE)."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from features.observabilidad.tipos import Metrica, Span, Traza, TrazaDesconocida

__all__ = ["GestorTrazas", "AlmacenTrazas", "calcular_costo_tokens"]

# Precios por millón de tokens en USD por defecto
PRECIOS_MILLON_DEFECTO: dict[str, tuple[Decimal, Decimal]] = {
    "claude-opus-5-5": (Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-5-5": (Decimal("0.80"), Decimal("4.00")),
    "claude-sonnet-5-5": (Decimal("3.00"), Decimal("15.00")),
}
PRECIO_ESTANDAR = (Decimal("3.00"), Decimal("15.00"))


# ¤observabilidad
def calcular_costo_tokens(
    modelo: str | None,
    tokens_in: int | None,
    tokens_out: int | None,
    tabla_precios: Mapping[str, Mapping[str, float]] | None = None,
) -> Decimal:
    """Calcula el costo en USD de una invocación de modelo redondeado a 6 decimales (numeric(10,6))."""
    if not tokens_in and not tokens_out:
        return Decimal("0.000000")

    t_in = tokens_in or 0
    t_out = tokens_out or 0

    if tabla_precios and modelo and modelo in tabla_precios:
        p_in = Decimal(str(tabla_precios[modelo].get("in", 3.0)))
        p_out = Decimal(str(tabla_precios[modelo].get("out", 15.0)))
    else:
        p_in, p_out = PRECIOS_MILLON_DEFECTO.get(modelo or "", PRECIO_ESTANDAR)

    costo_in = (Decimal(t_in) / Decimal("1000000")) * p_in
    costo_out = (Decimal(t_out) / Decimal("1000000")) * p_out
    return (costo_in + costo_out).quantize(Decimal("0.000001"))


# ¤observabilidad
class AlmacenTrazas:
    """Persistencia de trazas y spans en SQLite según el esquema observabilidad."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None or str(db_path) == ":memory:":
            self._ruta_db = ":memory:"
            self._con_memoria: sqlite3.Connection | None = sqlite3.connect(":memory:", check_same_thread=False)
            self._con_memoria.execute("PRAGMA foreign_keys = ON;")
        else:
            self._ruta_db = str(db_path)
            self._con_memoria = None
            Path(self._ruta_db).parent.mkdir(parents=True, exist_ok=True)
        self._inicializar_tablas()

    # ¤observabilidad
    @contextmanager
    def _obtener_conexion(self) -> Iterator[sqlite3.Connection]:
        if self._con_memoria is not None:
            with self._con_memoria:
                yield self._con_memoria
        else:
            con = sqlite3.connect(self._ruta_db)
            con.execute("PRAGMA foreign_keys = ON;")
            try:
                with con:
                    yield con
            finally:
                con.close()

    # ¤observabilidad
    def cerrar(self) -> None:
        if self._con_memoria is not None:
            self._con_memoria.close()
            self._con_memoria = None

    def _inicializar_tablas(self) -> None:
        with self._obtener_conexion() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS observabilidad_trazas (
                  traza_id         TEXT PRIMARY KEY,
                  mensaje_id       TEXT,
                  conversacion_id  TEXT,
                  canal            TEXT NOT NULL DEFAULT 'huespedes',
                  resultado        TEXT,
                  iniciada         TEXT NOT NULL,
                  cerrada          TEXT
                );

                CREATE TABLE IF NOT EXISTS observabilidad_spans (
                  span_id          TEXT PRIMARY KEY,
                  traza_id         TEXT NOT NULL REFERENCES observabilidad_trazas(traza_id) ON DELETE CASCADE,
                  sala             TEXT NOT NULL,
                  nombre           TEXT NOT NULL,
                  inicio           TEXT NOT NULL,
                  duracion_ms      INTEGER NOT NULL CHECK (duracion_ms >= 0),
                  modelo           TEXT,
                  tokens_in        INTEGER,
                  tokens_out       INTEGER,
                  costo_usd        NUMERIC(10,6),
                  atributos        TEXT NOT NULL DEFAULT '{}'
                );
                """
            )

    # ¤observabilidad
    def crear_traza(
        self,
        traza_id: str,
        mensaje_id: str | None,
        conversacion_id: str | None,
        canal: str,
        iniciada: datetime,
    ) -> None:
        iniciada_str = iniciada.isoformat()
        with self._obtener_conexion() as con:
            con.execute(
                """
                INSERT INTO observabilidad_trazas (
                    traza_id, mensaje_id, conversacion_id, canal, resultado, iniciada, cerrada
                ) VALUES (?, ?, ?, ?, NULL, ?, NULL);
                """,
                (traza_id, mensaje_id, conversacion_id, canal, iniciada_str),
            )

    # ¤observabilidad
    def existe_traza(self, traza_id: str) -> bool:
        with self._obtener_conexion() as con:
            cur = con.execute("SELECT 1 FROM observabilidad_trazas WHERE traza_id = ?;", (traza_id,))
            return cur.fetchone() is not None

    # ¤observabilidad
    def cerrar_traza(self, traza_id: str, resultado: str, cerrada: datetime) -> None:
        cerrada_str = cerrada.isoformat()
        with self._obtener_conexion() as con:
            cur = con.execute(
                "UPDATE observabilidad_trazas SET resultado = ?, cerrada = ? WHERE traza_id = ?;",
                (resultado, cerrada_str, traza_id),
            )
            if cur.rowcount == 0:
                raise TrazaDesconocida(traza_id)

    # ¤observabilidad
    def guardar_span(self, span: Span) -> None:
        inicio_str = span.inicio.isoformat()
        costo_str = str(span.costo_usd) if span.costo_usd is not None else None
        atributos_str = json.dumps(dict(span.atributos), ensure_ascii=False)

        with self._obtener_conexion() as con:
            con.execute(
                """
                INSERT INTO observabilidad_spans (
                    span_id, traza_id, sala, nombre, inicio, duracion_ms, modelo, tokens_in, tokens_out, costo_usd, atributos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    span.span_id,
                    span.traza_id,
                    span.sala,
                    span.nombre,
                    inicio_str,
                    span.duracion_ms,
                    span.modelo,
                    span.tokens_in,
                    span.tokens_out,
                    costo_str,
                    atributos_str,
                ),
            )

    # ¤observabilidad
    def obtener_traza(self, traza_id: str) -> Traza:
        with self._obtener_conexion() as con:
            cur_t = con.execute(
                "SELECT traza_id, mensaje_id, conversacion_id, canal, iniciada, cerrada, resultado FROM observabilidad_trazas WHERE traza_id = ?;",
                (traza_id,),
            )
            fila_t = cur_t.fetchone()
            if not fila_t:
                raise TrazaDesconocida(traza_id)

            tid, mid, cid, canal, ini_str, fin_str, res = fila_t

            cur_s = con.execute(
                """
                SELECT span_id, traza_id, sala, nombre, inicio, duracion_ms, modelo, tokens_in, tokens_out, costo_usd, atributos
                FROM observabilidad_spans
                WHERE traza_id = ?
                ORDER BY inicio ASC;
                """,
                (traza_id,),
            )
            filas_s = cur_s.fetchall()

        spans: list[Span] = []
        for sid, trid, sala, nom, s_ini, dur, mod, t_in, t_out, costo, atrs in filas_s:
            costo_dec = Decimal(str(costo)).quantize(Decimal("0.000001")) if costo is not None else None
            spans.append(
                Span(
                    span_id=sid,
                    traza_id=trid,
                    sala=sala,
                    nombre=nom,
                    inicio=datetime.fromisoformat(s_ini),
                    duracion_ms=dur,
                    modelo=mod,
                    tokens_in=t_in,
                    tokens_out=t_out,
                    costo_usd=costo_dec,
                    atributos=json.loads(atrs) if atrs else {},
                )
            )

        return Traza(
            traza_id=tid,
            mensaje_id=mid,
            conversacion_id=cid,
            canal=canal,
            inicio=datetime.fromisoformat(ini_str),
            fin=datetime.fromisoformat(fin_str) if fin_str else None,
            resultado=res,
            spans=tuple(spans),
        )

    # ¤observabilidad
    def listar_trazas(self) -> tuple[Traza, ...]:
        with self._obtener_conexion() as con:
            cur = con.execute("SELECT traza_id FROM observabilidad_trazas ORDER BY iniciada ASC;")
            ids = [fila[0] for fila in cur.fetchall()]
        return tuple(self.obtener_traza(tid) for tid in ids)


# ¤observabilidad
class ContextoSpan:
    """Objeto mutable durante la ejecución del span para registrar telemetría y atributos."""

    def __init__(self, span_id: str, traza_id: str, sala: str, nombre: str, inicio: datetime, **atributos: Any) -> None:
        self.span_id = span_id
        self.traza_id = traza_id
        self.sala = sala
        self.nombre = nombre
        self.inicio = inicio
        self.atributos: dict[str, Any] = dict(atributos)
        self.modelo: str | None = atributos.get("modelo")
        self.tokens_in: int | None = atributos.get("tokens_in")
        self.tokens_out: int | None = atributos.get("tokens_out")
        self.costo_usd: Decimal | None = atributos.get("costo_usd")


# ¤observabilidad
class GestorTrazas:
    """Orquestador de ciclo de vida de trazas y spans."""

    def __init__(self, config: Mapping[str, Any], almacen: AlmacenTrazas | None = None) -> None:
        self._config = config
        self._almacen = almacen or AlmacenTrazas(db_path=config.get("db_path"))
        self._precios_config = config.get("costos", {}).get("tabla_precios_por_modelo", {})

    # ¤observabilidad
    def iniciar_traza(self, mensaje_id: str | None, conversacion_id: str | None, canal: str = "huespedes") -> str:
        """Inicia una traza persistida asociada al mensaje entrante (INV_TRAZA_POR_MENSAJE)."""
        traza_id = str(uuid.uuid4())
        iniciada = datetime.now(timezone.utc)
        self._almacen.crear_traza(
            traza_id=traza_id,
            mensaje_id=mensaje_id,
            conversacion_id=conversacion_id,
            canal=canal,
            iniciada=iniciada,
        )
        return traza_id

    # ¤observabilidad
    @contextmanager
    def span(self, traza_id: str, sala: str, nombre: str, **atributos: Any) -> Iterator[ContextoSpan]:
        """Context manager para instrumentar un span con medición de tiempo, tokens y costo."""
        if not self._almacen.existe_traza(traza_id):
            raise TrazaDesconocida(traza_id)

        span_id = str(uuid.uuid4())
        inicio = datetime.now(timezone.utc)
        ctx = ContextoSpan(span_id, traza_id, sala, nombre, inicio, **atributos)
        t0 = time.time()

        try:
            yield ctx
        finally:
            duracion_ms = max(0, int((time.time() - t0) * 1000))
            modelo = ctx.modelo or ctx.atributos.get("modelo")
            tokens_in = ctx.tokens_in if ctx.tokens_in is not None else ctx.atributos.get("tokens_in")
            tokens_out = ctx.tokens_out if ctx.tokens_out is not None else ctx.atributos.get("tokens_out")
            costo = ctx.costo_usd if ctx.costo_usd is not None else ctx.atributos.get("costo_usd")

            if costo is None and (tokens_in is not None or tokens_out is not None):
                costo = calcular_costo_tokens(modelo, tokens_in, tokens_out, self._precios_config)
            elif costo is not None and not isinstance(costo, Decimal):
                costo = Decimal(str(costo)).quantize(Decimal("0.000001"))

            span_final = Span(
                span_id=span_id,
                traza_id=traza_id,
                sala=sala,
                nombre=nombre,
                inicio=inicio,
                duracion_ms=duracion_ms,
                modelo=modelo,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                costo_usd=costo,
                atributos=ctx.atributos,
            )
            self._almacen.guardar_span(span_final)

    # ¤observabilidad
    def cerrar_traza(self, traza_id: str, resultado: str) -> Traza:
        """Cierra la traza en almacenamiento y la retorna completa con todos sus spans."""
        ahora = datetime.now(timezone.utc)
        self._almacen.cerrar_traza(traza_id, resultado, ahora)
        return self._almacen.obtener_traza(traza_id)

    # ¤observabilidad
    def obtener_traza(self, traza_id: str) -> Traza:
        return self._almacen.obtener_traza(traza_id)

    # ¤observabilidad
    def todas_las_trazas(self) -> tuple[Traza, ...]:
        return self._almacen.listar_trazas()

    # ¤observabilidad
    def calcular_metricas_operativas(self) -> tuple[Metrica, ...]:
        """Calcula OP-01..OP-10 exclusivamente a partir de las trazas (RF-OBS-02)."""
        from features.observabilidad.metricas_internal import calcular_metricas_prd
        return calcular_metricas_prd(self.todas_las_trazas())
