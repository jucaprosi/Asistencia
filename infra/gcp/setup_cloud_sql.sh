#!/usr/bin/env bash
# ¤infra-cloud
# ¤¤devops-engineer
# Script de aprovisionamiento de Cloud SQL PostgreSQL 16 con extensión pgvector.
# Proyecto: Glamping Imbabura
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-glamping-imbabura}"
REGION="${GCP_LOCATION:-us-central1}"
INSTANCE_NAME="glamping-db"
DB_NAME="glamping_prod"
DB_USER="glamping_app"

echo "=== Configurando Cloud SQL PostgreSQL 16 en ${PROJECT_ID} (${REGION}) ==="

# 1. Habilitar APIs necesarias
gcloud services enable sqladmin.googleapis.com run.googleapis.com secretmanager.googleapis.com --project="${PROJECT_ID}"

# 2. Crear instancia Cloud SQL si no existe (optimizada para el bono gratuito de $300 USD)
if ! gcloud sql instances describe "${INSTANCE_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Creando instancia Cloud SQL: ${INSTANCE_NAME}..."
  gcloud sql instances create "${INSTANCE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --storage-type=SSD \
    --storage-size=10GB \
    --storage-auto-increase \
    --backup-start-time=03:00 \
    --enable-point-in-time-recovery
else
  echo "La instancia ${INSTANCE_NAME} ya existe."
fi

# 3. Crear base de datos
if ! gcloud sql databases describe "${DB_NAME}" --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Creando base de datos: ${DB_NAME}..."
  gcloud sql databases create "${DB_NAME}" --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}"
fi

# 4. Generar contraseña segura y crear usuario de aplicación
DB_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
if ! gcloud sql users describe "${DB_USER}" --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Creando usuario de BD: ${DB_USER}..."
  gcloud sql users create "${DB_USER}" --instance="${INSTANCE_NAME}" --project="${PROJECT_ID}" --password="${DB_PASS}"
fi

# 5. Cadena de conexión para Cloud Run (vía socket UNIX /cloudsql/)
CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"

# 6. Registrar DATABASE_URL en Secret Manager
echo "Guardando DATABASE_URL en Google Secret Manager..."
if ! gcloud secrets describe DATABASE_URL --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud secrets create DATABASE_URL --replication-policy="automatic" --project="${PROJECT_ID}"
fi
echo -n "${DATABASE_URL}" | gcloud secrets versions add DATABASE_URL --data-file=- --project="${PROJECT_ID}"

echo "=== Configuración completada exitosamente ==="
echo "Instancia: ${CONNECTION_NAME}"
echo "Base de datos: ${DB_NAME}"
echo "Secret Manager: DATABASE_URL actualizado."
