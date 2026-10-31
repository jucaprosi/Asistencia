# ¤infra-hibrida
# ¤¤security-engineer
"""Escáner de secretos (INV_SIN_SECRETOS_EN_REPO, RNF-08). Exit 0 si no hay hallazgos; 1 con la lista en stdout.

Busca tokens de Meta, claves de Anthropic, claves AWS, claves privadas PEM y asignaciones literales largas a
nombres típicos de secreto. Los valores ``${VARIABLE}`` y las líneas vacías de ``.env.example`` no cuentan.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXCLUIDOS = {".git", "transcriptor_tiktok", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "data"}
ARCHIVOS_EXENTOS = {Path("scripts/verificar_secretos.py")}
EXTENSIONES = {".py", ".yaml", ".yml", ".md", ".toml", ".json", ".sh", ".bat", ".txt", ".env", ".example", ".ts", ".tsx", ".js"}
PATRONES = (
    ("clave_anthropic", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("token_meta", re.compile(r"\bEAA[A-Za-z0-9]{40,}\b")),
    ("clave_aws", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("clave_privada_pem", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("asignacion_literal", re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|contrase[nñ]a)\b\s*[:=]\s*[\"'][^\"'${}\s]{16,}[\"']")),
)


# ¤infra-hibrida
def archivos_a_revisar() -> list[Path]:
    rutas: list[Path] = []
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file() or any(parte in EXCLUIDOS for parte in ruta.parts):
            continue
        if ruta.suffix.lower() in EXTENSIONES or ruta.name in {".env.example", "Dockerfile"}:
            if ruta.relative_to(RAIZ) not in ARCHIVOS_EXENTOS and "tests" not in ruta.parts:
                rutas.append(ruta)
    return rutas


# ¤infra-hibrida
def main() -> int:
    hallazgos: list[str] = []
    for ruta in archivos_a_revisar():
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        for numero, linea in enumerate(texto.splitlines(), start=1):
            for nombre, patron in PATRONES:
                if patron.search(linea):
                    hallazgos.append(f"{ruta.relative_to(RAIZ)}:{numero} [{nombre}]")
    if hallazgos:
        print("posibles secretos en el repositorio:")
        print("\n".join(hallazgos))
        return 1
    print("sin secretos detectados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
