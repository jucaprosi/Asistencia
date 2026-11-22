# ¤infra-cloud
# ¤¤devops-engineer
"""Herramienta de migración y verificación de persistencia en PostgreSQL (Cloud SQL / pgvector).

Aplica docs/spec/esquema.sql (línea base) y docs/spec/migraciones/*.sql a DATABASE_URL, una sola vez cada
archivo, registrándolos en public.migraciones_aplicadas.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
RUTA_ESQUEMA_DEFECTO = RAIZ / "docs" / "spec" / "esquema.sql"


# ¤infra-cloud
def normalizar_url_db(url: str) -> str:
    """Normaliza cadenas postgres:// a postgresql:// para compatibilidad con psycopg3."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


# ¤infra-cloud
def verificar_conexion(db_url: str | None = None, timeout: float = 5.0) -> dict[str, Any]:
    """Verifica si la base de datos PostgreSQL está accesible."""
    url = normalizar_url_db(db_url or os.environ.get("DATABASE_URL", ""))
    if not url:
        return {"conectado": False, "error": "DATABASE_URL no configurada"}
    try:
        import psycopg
        with psycopg.connect(url, connect_timeout=int(timeout)) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
                fila_vector = cur.fetchone()
                tiene_vector = fila_vector is not None
            return {
                "conectado": True,
                "version": version,
                "vector": tiene_vector,
            }
    except Exception as exc:
        return {"conectado": False, "error": str(exc)}


# ¤infra-cloud
def aplicar_esquema(
    db_url: str | None = None,
    ruta_esquema: Path | str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Lee y ejecuta el esquema canónico docs/spec/esquema.sql sobre PostgreSQL."""
    url = normalizar_url_db(db_url or os.environ.get("DATABASE_URL", ""))
    if not url:
        raise ValueError("DATABASE_URL no configurada. Defina DATABASE_URL o pase --url.")

    ruta = Path(ruta_esquema or RUTA_ESQUEMA_DEFECTO)
    if not ruta.is_file():
        raise FileNotFoundError(f"Archivo de esquema no encontrado: {ruta}")

    contenido_sql = ruta.read_text(encoding="utf-8")

    if dry_run:
        bloques = [b.strip() for b in re.split(r";\s*\n", contenido_sql) if b.strip()]
        return {
            "exito": True,
            "dry_run": True,
            "archivo": str(ruta),
            "bytes": len(contenido_sql),
            "bloques": len(bloques),
        }

    try:
        import psycopg
        with psycopg.connect(url) as conn:
            aplicadas = _aplicar_pendientes(conn, ruta, contenido_sql)
        return {
            "exito": True,
            "dry_run": False,
            "archivo": str(ruta),
            "bytes": len(contenido_sql),
            "aplicadas": aplicadas,
        }
    except Exception as exc:
        return {
            "exito": False,
            "dry_run": False,
            "archivo": str(ruta),
            "error": str(exc),
        }


# ¤infra-cloud
def _aplicar_pendientes(conn: Any, ruta_base: Path, contenido_base: str) -> list[str]:
    """Aplica la línea base y luego ``docs/spec/migraciones/*.sql`` una sola vez cada una, en orden.

    Cada archivo corre en su propia transacción y queda registrado con su SHA-256 en
    ``public.migraciones_aplicadas``. Repetir la orden no hace nada; un archivo ya aplicado cuyo
    contenido cambió es un error (la corrección va en una migración nueva, nunca editando la anterior).
    """
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS public.migraciones_aplicadas ("
            " nombre text PRIMARY KEY, sha256 text NOT NULL, aplicada_en timestamptz NOT NULL DEFAULT now())"
        )
    registradas = {
        nombre: sha for nombre, sha in conn.execute("SELECT nombre, sha256 FROM public.migraciones_aplicadas")
    }
    if not registradas and conn.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = 'canal'"
    ).fetchone():
        raise RuntimeError(
            "La base ya tiene el esquema pero no el registro de migraciones: no se puede saber qué versión "
            "tiene. Restaure desde una base vacía o registre la línea base a mano tras verificarla."
        )
    archivos = [("000_linea_base.sql", contenido_base)]
    carpeta = RAIZ / "docs" / "spec" / "migraciones"
    if ruta_base == RUTA_ESQUEMA_DEFECTO and carpeta.is_dir():
        archivos += [(p.name, p.read_text(encoding="utf-8")) for p in sorted(carpeta.glob("*.sql"))]
    aplicadas: list[str] = []
    for nombre, sql in archivos:
        sha = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        if nombre in registradas:
            if registradas[nombre] != sha:
                raise RuntimeError(f"La migración {nombre} ya aplicada cambió de contenido; cree una nueva.")
            continue
        with conn.transaction():
            conn.execute(sql)
            conn.execute(
                "INSERT INTO public.migraciones_aplicadas (nombre, sha256) VALUES (%s, %s)", (nombre, sha)
            )
        aplicadas.append(nombre)
    return aplicadas


# ¤infra-cloud
def main(argumentos: list[str] | None = None) -> int:
    """Punto de entrada CLI para la migración de la base de datos."""
    analizador = argparse.ArgumentParser(description="Migrador de persistencia PostgreSQL (Glamping Imbabura)")
    analizador.add_argument("--url", default=None, help="Cadena de conexión DATABASE_URL")
    analizador.add_argument("--esquema", type=Path, default=None, help="Ruta alternativa a esquema.sql")
    analizador.add_argument("--check", action="store_true", help="Solo verifica la conectividad sin aplicar cambios")
    analizador.add_argument("--dry-run", action="store_true", help="Valida el archivo SQL sin ejecutarlo")
    opciones = analizador.parse_args(argumentos)

    if opciones.check:
        res = verificar_conexion(opciones.url)
        if res.get("conectado"):
            print(f"[OK] Conexión exitosa a PostgreSQL: {res.get('version')} (pgvector: {res.get('vector')})")
            return 0
        else:
            print(f"[ERROR] No se pudo conectar a PostgreSQL: {res.get('error')}", file=sys.stderr)
            return 1

    try:
        res = aplicar_esquema(opciones.url, opciones.esquema, dry_run=opciones.dry_run)
        if res.get("exito"):
            modo = "Simulación (dry-run)" if res.get("dry_run") else "Migración completada"
            detalle = ", ".join(res.get("aplicadas", [])) or "nada pendiente"
            print(f"[OK] {modo}: {res.get('archivo')} ({detalle})")
            return 0
        else:
            print(f"[ERROR] Falló la migración: {res.get('error')}", file=sys.stderr)
            return 1
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
