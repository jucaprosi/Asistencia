# ¤persistencia-sql
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala persistencia_sql: conexión única a SQLite o PostgreSQL según DATABASE_URL.

Las salas escriben SQL portable (esquemas ``canal.tabla``, ``INSERT ... ON CONFLICT``, parámetros ``?``) y
reciben aquí una :class:`Conexion` con la interfaz mínima de DB-API que ya usaban con ``sqlite3``:
``execute``, ``executemany``, ``executescript``, ``commit``, ``rollback`` y filas accesibles por nombre e
índice. Con SQLite (pruebas y desarrollo) cada esquema se emula con ``ATTACH``. Con PostgreSQL el esquema
lo gobierna ``docs/spec/esquema.sql`` (``scripts/migrar_db.py``), por lo que ``asegurar_esquema`` no
ejecuta el DDL propio de la sala.
"""
from __future__ import annotations

import os
import re
import sqlite3
import threading
import weakref
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import yaml

__all__ = [
    "Conexion",
    "Fila",
    "PersistenciaSqlService",
    "abrir_conexion",
    "cargar_config",
    "cerrar_conexiones_postgres",
    "envolver",
    "es_postgres",
    "url_desde_entorno",
]

RUTA_CONFIG = Path(__file__).with_name("config_persistencia_sql.yaml")
_PREFIJOS_POSTGRES = ("postgresql://", "postgres://")
_PATRON_ESQUEMA = re.compile(r"\b([a-z_]+)\.[a-z_]+\b")
_PALABRAS_LECTURA = ("select", "with", "show", "explain")
_ABIERTAS_POSTGRES: "weakref.WeakSet[Conexion]" = weakref.WeakSet()


# ¤persistencia-sql
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤persistencia-sql
def es_postgres(url: str | None) -> bool:
    return bool(url) and str(url).startswith(_PREFIJOS_POSTGRES)


# ¤persistencia-sql
def url_desde_entorno(entorno: Mapping[str, str] | None = None) -> str:
    """Devuelve DATABASE_URL o cadena vacía (SQLite en memoria)."""
    env = os.environ if entorno is None else entorno
    return str(env.get("DATABASE_URL", "") or "").strip()


# ¤persistencia-sql
class Fila(Sequence[Any]):
    """Fila inmutable accesible por índice y por nombre de columna, como ``sqlite3.Row``."""

    __slots__ = ("_columnas", "_valores", "_indices")

    def __init__(self, columnas: Sequence[str], valores: Sequence[Any]) -> None:
        self._columnas = tuple(columnas)
        self._valores = tuple(valores)
        self._indices = {nombre: i for i, nombre in enumerate(self._columnas)}

    def __getitem__(self, clave: Any) -> Any:  # type: ignore[override]
        if isinstance(clave, str):
            return self._valores[self._indices[clave]]
        return self._valores[clave]

    def __len__(self) -> int:
        return len(self._valores)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._valores)

    def keys(self) -> list[str]:
        return list(self._columnas)

    def __repr__(self) -> str:
        return f"Fila({dict(zip(self._columnas, self._valores))!r})"


# ¤persistencia-sql
class _CursorPostgres:
    """Cursor con resultados ya leídos: sobrevive al ``commit`` automático de las lecturas."""

    def __init__(self, filas: list[Fila], rowcount: int) -> None:
        self._filas = filas
        self._posicion = 0
        self.rowcount = rowcount

    def fetchone(self) -> Fila | None:
        if self._posicion >= len(self._filas):
            return None
        fila = self._filas[self._posicion]
        self._posicion += 1
        return fila

    def fetchall(self) -> list[Fila]:
        restantes = self._filas[self._posicion:]
        self._posicion = len(self._filas)
        return restantes

    def fetchmany(self, tamano: int = 1) -> list[Fila]:
        lote = self._filas[self._posicion:self._posicion + tamano]
        self._posicion += len(lote)
        return lote

    def __iter__(self) -> Iterator[Fila]:
        return iter(self.fetchall())


# ¤persistencia-sql
def _a_formato_psycopg(sql: str) -> str:
    """Convierte ``?`` en ``%s`` y escapa ``%`` literal, respetando cadenas entre comillas."""
    salida: list[str] = []
    comilla: str | None = None
    for caracter in sql:
        if comilla:
            salida.append("%%" if caracter == "%" else caracter)
            if caracter == comilla:
                comilla = None
            continue
        if caracter in ("'", '"'):
            comilla = caracter
            salida.append(caracter)
        elif caracter == "?":
            salida.append("%s")
        elif caracter == "%":
            salida.append("%%")
        else:
            salida.append(caracter)
    return "".join(salida)


# ¤persistencia-sql
def _error_equivalente(exc: Exception) -> Exception:
    """Traduce errores de psycopg a las clases de ``sqlite3`` que las salas ya capturan."""
    try:
        import psycopg
    except ImportError:  # pragma: no cover
        return exc
    if isinstance(exc, psycopg.IntegrityError):
        return sqlite3.IntegrityError(str(exc))
    if isinstance(exc, psycopg.OperationalError):
        return sqlite3.OperationalError(str(exc))
    if isinstance(exc, psycopg.Error):
        return sqlite3.DatabaseError(str(exc))
    return exc


# ¤persistencia-sql
def _es_lectura(sql: str) -> bool:
    texto = sql.lstrip().lower()
    return texto.startswith(_PALABRAS_LECTURA) and not re.search(r"\b(insert|update|delete)\b", texto)


# ¤persistencia-sql
class Conexion:
    """Conexión de una sala: misma interfaz para SQLite y PostgreSQL."""

    def __init__(self, url: str = "", *, esquemas: Iterable[str] = (), ruta_busqueda: str | None = None) -> None:
        self.url = url
        self.dialecto = "postgresql" if es_postgres(url) else "sqlite"
        self._lock = threading.RLock()
        self._en_transaccion = False
        if self.dialecto == "postgresql":
            self._crudo = self._conectar_postgres(url, ruta_busqueda)
            _ABIERTAS_POSTGRES.add(self)
        else:
            ruta = url.replace("sqlite:///", "").replace("sqlite://", "") if url else ":memory:"
            self._crudo = sqlite3.connect(ruta or ":memory:", check_same_thread=False)
            self._crudo.row_factory = sqlite3.Row
            self._crudo.execute("PRAGMA foreign_keys = ON;")
            for esquema in esquemas:
                self.adjuntar_esquema(esquema)

    @classmethod
    def desde_sqlite(cls, crudo: sqlite3.Connection, *, esquemas: Iterable[str] = ()) -> "Conexion":
        """Envuelve una conexión ``sqlite3`` ya abierta (pruebas que comparten una base entre salas)."""
        envoltura = cls.__new__(cls)
        envoltura.url = ""
        envoltura.dialecto = "sqlite"
        envoltura._lock = threading.RLock()
        envoltura._en_transaccion = False
        envoltura._crudo = crudo
        crudo.row_factory = sqlite3.Row
        for esquema in esquemas:
            envoltura.adjuntar_esquema(esquema)
        return envoltura

    @staticmethod
    def _conectar_postgres(url: str, ruta_busqueda: str | None = None) -> Any:
        import psycopg
        from psycopg.types.string import TextLoader

        conexion = psycopg.connect(url, autocommit=False)
        # Fechas como texto ISO: las salas ya serializan y parsean ISO-8601 (datetime.fromisoformat).
        # uuid también como texto: las salas comparan identificadores como cadenas.
        # json/jsonb como texto: las salas guardan json.dumps(...) y leen con json.loads(...).
        for tipo in ("timestamptz", "timestamp", "date", "time", "timetz", "uuid", "json", "jsonb"):
            conexion.adapters.register_loader(tipo, TextLoader)
        conexion.execute("SET TIME ZONE 'UTC'")
        if ruta_busqueda:
            # La sala usa nombres sin esquema (``reglas``) que en PostgreSQL viven en su esquema (``comisiones.reglas``).
            if not re.fullmatch(r"[a-z_]+", ruta_busqueda):
                raise ValueError(f"esquema inválido: {ruta_busqueda!r}")
            conexion.execute(f"SET search_path TO {ruta_busqueda}, public")
        conexion.commit()
        return conexion

    @property
    def es_postgres(self) -> bool:
        return self.dialecto == "postgresql"

    def adjuntar_esquema(self, esquema: str) -> None:
        """SQLite: emula el esquema ``<esquema>.tabla`` con una base adjunta en memoria (idempotente)."""
        if self.es_postgres:
            return
        with self._lock:
            adjuntas = {fila[1] for fila in self._crudo.execute("PRAGMA database_list").fetchall()}
            if esquema not in adjuntas:
                self._crudo.execute(f"ATTACH DATABASE ':memory:' AS {esquema}")
                self._crudo.execute(f"PRAGMA {esquema}.foreign_keys = ON;")

    def asegurar_esquema(self, ddl_sqlite: str) -> None:
        """Crea las tablas de la sala en SQLite; en PostgreSQL el esquema ya lo aplicó la migración."""
        if self.es_postgres:
            return
        with self._lock:
            for esquema in sorted(set(_PATRON_ESQUEMA.findall(ddl_sqlite)) - {"sqlite_master"}):
                if not esquema.startswith(("excluded", "new", "old")):
                    self.adjuntar_esquema(esquema)
            self._crudo.executescript(ddl_sqlite)
            self._crudo.commit()

    def execute(self, sql: str, parametros: Sequence[Any] | Mapping[str, Any] = ()) -> Any:
        with self._lock:
            if not self.es_postgres:
                return self._crudo.execute(sql, parametros)
            try:
                if parametros:
                    cursor = self._crudo.execute(_a_formato_psycopg(sql), parametros)
                else:
                    cursor = self._crudo.execute(sql)
            except Exception as exc:
                self._crudo.rollback()
                self._en_transaccion = False
                raise _error_equivalente(exc) from exc
            filas: list[Fila] = []
            if cursor.description is not None:
                columnas = [col.name for col in cursor.description]
                filas = [Fila(columnas, valores) for valores in cursor.fetchall()]
            if _es_lectura(sql) and not self._en_transaccion:
                self._crudo.commit()
            else:
                self._en_transaccion = True
            return _CursorPostgres(filas, cursor.rowcount)

    def executemany(self, sql: str, lotes: Iterable[Sequence[Any]]) -> Any:
        with self._lock:
            if not self.es_postgres:
                return self._crudo.executemany(sql, lotes)
            with self._crudo.cursor() as cursor:
                cursor.executemany(_a_formato_psycopg(sql), list(lotes))
                self._en_transaccion = True
                return _CursorPostgres([], cursor.rowcount)

    def executescript(self, script: str) -> None:
        with self._lock:
            if self.es_postgres:
                self._crudo.execute(script)
                self._crudo.commit()
                self._en_transaccion = False
            else:
                self._crudo.executescript(script)

    def commit(self) -> None:
        with self._lock:
            self._crudo.commit()
            self._en_transaccion = False

    def rollback(self) -> None:
        with self._lock:
            self._crudo.rollback()
            self._en_transaccion = False

    def __enter__(self) -> "Conexion":
        """``with conexion:`` confirma al salir sin error y revierte si hubo excepción (semántica de sqlite3)."""
        return self

    def __exit__(self, tipo: Any, valor: Any, traza: Any) -> bool:
        if tipo is None:
            self.commit()
        else:
            self.rollback()
        return False

    def cursor(self) -> "_CursorConexion":
        return _CursorConexion(self)

    def close(self) -> None:
        with self._lock:
            self._crudo.close()

    @property
    def row_factory(self) -> Any:
        return getattr(self._crudo, "row_factory", None)

    @row_factory.setter
    def row_factory(self, valor: Any) -> None:
        if not self.es_postgres:
            self._crudo.row_factory = valor


# ¤persistencia-sql
class _CursorConexion:
    """Cursor mínimo sobre :class:`Conexion` para el código que usa ``conexion.cursor().execute(...)``."""

    def __init__(self, conexion: Conexion) -> None:
        self._conexion = conexion
        self._ultimo: Any = None
        self.rowcount = -1

    def execute(self, sql: str, parametros: Sequence[Any] | Mapping[str, Any] = ()) -> "_CursorConexion":
        self._ultimo = self._conexion.execute(sql, parametros)
        self.rowcount = self._ultimo.rowcount
        return self

    def executemany(self, sql: str, lotes: Iterable[Sequence[Any]]) -> "_CursorConexion":
        self._ultimo = self._conexion.executemany(sql, lotes)
        self.rowcount = self._ultimo.rowcount
        return self

    def fetchone(self) -> Any:
        return self._ultimo.fetchone() if self._ultimo is not None else None

    def fetchall(self) -> list[Any]:
        return self._ultimo.fetchall() if self._ultimo is not None else []

    def close(self) -> None:
        self._ultimo = None


# ¤persistencia-sql
def abrir_conexion(
    url: str | None = None, *, esquemas: Iterable[str] = (), ruta_busqueda: str | None = None
) -> Conexion:
    """Abre la conexión de una sala. ``url`` vacía o ``None`` usa DATABASE_URL; si tampoco hay, SQLite en memoria."""
    destino = url_desde_entorno() if url is None else url
    return Conexion(destino, esquemas=esquemas, ruta_busqueda=ruta_busqueda)


# ¤persistencia-sql
def cerrar_conexiones_postgres() -> int:
    """Cierra las conexiones PostgreSQL abiertas en el proceso (pruebas y apagado ordenado)."""
    cerradas = 0
    for conexion in list(_ABIERTAS_POSTGRES):
        try:
            conexion.close()
            cerradas += 1
        except Exception:
            pass
    _ABIERTAS_POSTGRES.clear()
    return cerradas


# ¤persistencia-sql
def envolver(origen: Any = None, *, esquemas: Iterable[str] = (), ruta_busqueda: str | None = None) -> Conexion:
    """Normaliza lo que recibe un repositorio: ``None`` (DATABASE_URL o memoria), URL/ruta, ``sqlite3`` o Conexion."""
    if isinstance(origen, Conexion):
        for esquema in esquemas:
            origen.adjuntar_esquema(esquema)
        return origen
    if isinstance(origen, sqlite3.Connection):
        return Conexion.desde_sqlite(origen, esquemas=esquemas)
    if origen is None or isinstance(origen, (str, Path)):
        return abrir_conexion(None if origen is None else str(origen), esquemas=esquemas, ruta_busqueda=ruta_busqueda)
    raise TypeError(f"origen de conexión no soportado: {type(origen).__name__}")


# ¤persistencia-sql
class PersistenciaSqlService:
    """Fábrica de conexiones para el pasillo central y las salas."""

    def __init__(self, config: Mapping[str, Any] | None = None, *, url: str | None = None) -> None:
        self._config = dict(config or cargar_config())
        self.url = url_desde_entorno() if url is None else url

    @property
    def es_postgres(self) -> bool:
        return es_postgres(self.url)

    def abrir(self, *, esquemas: Iterable[str] = ()) -> Conexion:
        return Conexion(self.url, esquemas=esquemas)
