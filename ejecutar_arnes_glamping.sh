#!/usr/bin/env bash
# Arnés físico de glamping-imbabura-agent: único árbitro de «fase completada».
# Escribe governance/artefactos/data/.test_verdict.json y devuelve el Exit Code global.
set -u
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python
exec "$PYTHON" scripts/arnes_glamping.py "$@"
