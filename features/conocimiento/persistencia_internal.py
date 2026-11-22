# ¤conocimiento-rag
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Capa de persistencia relacional y almacenamiento vectorial de la sala conocimiento (RF-RAG-01..03)."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from features.conocimiento.tipos import ConsultaSinPropiedad, Documento, Fragmento
from features.persistencia_sql.persistencia_sql_service import envolver

SQL_ESQUEMA = """
CREATE TABLE IF NOT EXISTS documentos (
  documento_id     TEXT PRIMARY KEY,
  ruta             TEXT NOT NULL UNIQUE,
  propiedad_id     TEXT NOT NULL,
  tipo             TEXT NOT NULL,
  dueno            TEXT NOT NULL,
  revisado         TEXT NOT NULL,
  version_hash     TEXT NOT NULL,
  indexado_en      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id         TEXT PRIMARY KEY,
  documento_id     TEXT NOT NULL REFERENCES documentos(documento_id) ON DELETE CASCADE,
  propiedad_id     TEXT NOT NULL,
  encabezado       TEXT NOT NULL,
  texto            TEXT NOT NULL,
  embedding        TEXT NOT NULL,
  orden            INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_propiedad ON chunks(propiedad_id);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(documento_id);
"""


# ¤conocimiento-rag
class RepositorioConocimiento:
    """Gestiona documentos y fragmentos con soporte RLS (INV_SIN_FUGA_ENTRE_PROPIEDADES)."""

    def __init__(self, conexion: sqlite3.Connection | None = None, ruta_bd: Path | str | None = None) -> None:
        if conexion is not None:
            self._conexion = envolver(conexion, ruta_busqueda="conocimiento")
        elif ruta_bd is not None:
            Path(ruta_bd).parent.mkdir(parents=True, exist_ok=True)
            self._conexion = envolver(str(ruta_bd))
        else:
            # DATABASE_URL (PostgreSQL, esquema conocimiento) o SQLite en memoria.
            self._conexion = envolver(None, ruta_busqueda="conocimiento")
        if not self._conexion.es_postgres:
            self._conexion.executescript(SQL_ESQUEMA)
            self._conexion.commit()

    @property
    def conexion(self) -> sqlite3.Connection:
        return self._conexion

    # ¤conocimiento-rag
    def obtener_documento_por_ruta(self, ruta: str) -> Documento | None:
        cur = self._conexion.cursor()
        cur.execute(
            "SELECT documento_id, ruta, propiedad_id, tipo, dueno, revisado, version_hash FROM documentos WHERE ruta = ?",
            (ruta,),
        )
        fila = cur.fetchone()
        if not fila:
            return None
        return Documento(
            documento_id=fila[0],
            ruta=fila[1],
            propiedad_id=fila[2],
            tipo=fila[3],
            dueno=fila[4],
            revisado=datetime.strptime(fila[5], "%Y-%m-%d").date(),
            version_hash=fila[6],
        )

    # ¤conocimiento-rag
    def guardar_documento(
        self,
        ruta: str,
        propiedad_id: str,
        tipo: str,
        dueno: str,
        revisado: date,
        version_hash: str,
        chunks: Sequence[dict[str, Any]],
    ) -> tuple[str, bool, int]:
        """Guarda o actualiza documento y sus chunks. Retorna (doc_id, es_nuevo, chunks_insertados)."""
        doc_existente = self.obtener_documento_por_ruta(ruta)
        ahora = datetime.now(timezone.utc).isoformat()
        cur = self._conexion.cursor()

        if doc_existente:
            doc_id = doc_existente.documento_id
            if doc_existente.version_hash == version_hash:
                # Idempotente: sin cambios
                return doc_id, False, 0
            # Reemplazo por version_hash cambiada
            cur.execute(
                """UPDATE documentos
                   SET propiedad_id = ?, tipo = ?, dueno = ?, revisado = ?, version_hash = ?, indexado_en = ?
                   WHERE documento_id = ?""",
                (propiedad_id, tipo, dueno, revisado.isoformat(), version_hash, ahora, doc_id),
            )
            # Eliminar chunks antiguos (CASCADE manual si el pragma no bastara)
            cur.execute("DELETE FROM chunks WHERE documento_id = ?", (doc_id,))
            es_nuevo = False
        else:
            doc_id = str(uuid.uuid4())
            cur.execute(
                """INSERT INTO documentos (documento_id, ruta, propiedad_id, tipo, dueno, revisado, version_hash, indexado_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, ruta, propiedad_id, tipo, dueno, revisado.isoformat(), version_hash, ahora),
            )
            es_nuevo = True

        chunks_insertados = 0
        for item in chunks:
            chunk_id = str(uuid.uuid4())
            emb_json = json.dumps(item.get("embedding", []))
            cur.execute(
                """INSERT INTO chunks (chunk_id, documento_id, propiedad_id, encabezado, texto, embedding, orden)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    chunk_id,
                    doc_id,
                    item.get("propiedad_id", propiedad_id),
                    item["encabezado"],
                    item["texto"],
                    emb_json,
                    int(item["orden"]),
                ),
            )
            chunks_insertados += 1

        self._conexion.commit()
        return doc_id, es_nuevo, chunks_insertados

    # ¤conocimiento-rag
    def listar_documentos(self, propiedad_id: str | None = None) -> list[Documento]:
        cur = self._conexion.cursor()
        if propiedad_id:
            cur.execute(
                """SELECT documento_id, ruta, propiedad_id, tipo, dueno, revisado, version_hash
                   FROM documentos WHERE propiedad_id = ? OR propiedad_id = 'global'
                   ORDER BY ruta ASC""",
                (propiedad_id,),
            )
        else:
            cur.execute(
                """SELECT documento_id, ruta, propiedad_id, tipo, dueno, revisado, version_hash
                   FROM documentos ORDER BY ruta ASC"""
            )
        filas = cur.fetchall()
        docs = []
        for f in filas:
            docs.append(
                Documento(
                    documento_id=f[0],
                    ruta=f[1],
                    propiedad_id=f[2],
                    tipo=f[3],
                    dueno=f[4],
                    revisado=datetime.strptime(f[5], "%Y-%m-%d").date(),
                    version_hash=f[6],
                )
            )
        return docs

    # ¤conocimiento-rag
    def obtener_chunks_candidatos(self, propiedad_id: str | None) -> list[dict[str, Any]]:
        """Obtiene fragmentos aplicando la política RLS: solo propiedad_id y 'global'."""
        if not propiedad_id:
            raise ConsultaSinPropiedad()

        cur = self._conexion.cursor()
        cur.execute(
            """SELECT chunk_id, documento_id, propiedad_id, encabezado, texto, embedding, orden
               FROM chunks
               WHERE propiedad_id = ? OR propiedad_id = 'global'""",
            (propiedad_id,),
        )
        filas = cur.fetchall()
        candidatos = []
        for f in filas:
            candidatos.append({
                "chunk_id": f[0],
                "documento_id": f[1],
                "propiedad_id": f[2],
                "encabezado": f[3],
                "texto": f[4],
                "embedding": json.loads(f[5]) if f[5] else [],
                "orden": f[6],
            })
        return candidatos

    # ¤conocimiento-rag
    def total_chunks(self) -> int:
        cur = self._conexion.cursor()
        cur.execute("SELECT count(*) FROM chunks")
        fila = cur.fetchone()
        return fila[0] if fila else 0
