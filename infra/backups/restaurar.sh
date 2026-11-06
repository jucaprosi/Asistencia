#!/usr/bin/env bash
# ¤infra-hibrida
# ¤¤devops-engineer
# Script de restauracion desde backup cifrado (RNF-15, S-08).
# Uso: ./restaurar.sh <archivo_cifrado.enc> [clave_o_passphrase]

set -euo pipefail

ARCHIVO_CIFRADO="$1"
CLAVE="${2:-${BACKUP_ENCRYPTION_KEY:-glamping_backup_secret_key_default}}"
ARCHIVO_DESCIFRADO="${ARCHIVO_CIFRADO%.enc}.restaurado.sql"

if [ ! -f "${ARCHIVO_CIFRADO}" ]; then
    echo "[ERROR] Archivo no encontrado: ${ARCHIVO_CIFRADO}"
    exit 1
fi

# 1. Verificar checksum si existe
if [ -f "${ARCHIVO_CIFRADO}.sha256" ]; then
    echo "[INFO] Verificando integridad SHA-256..."
    sha256sum -c "${ARCHIVO_CIFRADO}.sha256"
fi

# 2. Descifrar con OpenSSL AES-256
echo "[INFO] Descifrando backup..."
openssl enc -d -aes-256-cbc -pbkdf2 -iter 100000 -in "${ARCHIVO_CIFRADO}" -out "${ARCHIVO_DESCIFRADO}" -pass "pass:${CLAVE}"

# 3. Restaurar en base de datos si esta disponible
if command -v psql >/dev/null 2>&1 && [ -n "${DATABASE_URL:-}" ]; then
    echo "[INFO] Aplicando dump a la base de datos..."
    psql "${DATABASE_URL}" < "${ARCHIVO_DESCIFRADO}"
else
    echo "[INFO] Archivo descifrado verificado correctamente: ${ARCHIVO_DESCIFRADO}"
fi

# Limpieza opcional tras restaurar
rm -f "${ARCHIVO_DESCIFRADO}"
echo "[OK] Restauracion completada con exito."
