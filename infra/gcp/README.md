# Infraestructura Cloud Native en Google Cloud Platform (GCP)
`¤infra-cloud`

Este directorio contiene la configuración y scripts para el despliegue serverless de Glamping Imbabura en Google Cloud Platform, garantizando **cero pérdida de datos** ante reinicios de Cloud Run mediante la persistencia gestionada en PostgreSQL 16 con `pgvector` ([ADR-0019](../../docs/adr/ADR-0019-despliegue-google-cloud-y-gemini.md)).

---

## 1. Arquitectura de Persistencia Serverless

En Cloud Run, los contenedores son efímeros y stateless: cualquier archivo local o base de datos SQLite en memoria se destruye cuando la instancia escala a cero o se recicla. Para garantizar durabilidad:

```
[Cliente WhatsApp / Panel]
             │
             ▼ HTTPS
    [Google Cloud Run]
  (min-instances: 1, stateless)
             │
             │ Socket UNIX (/cloudsql/PROJECT:REGION:INSTANCE)
             ▼
[Cloud SQL PostgreSQL 16 + pgvector]
  - Esquema canónico: docs/spec/esquema.sql
  - 12 esquemas ADPA aislados
  - Almacén de vectores para RAG
  - Backups diarios automáticos y PITR
```

---

## 2. Aprovisionamiento de Cloud SQL

Para crear la instancia gestionada dentro del bono de \$300 USD de Google Cloud:

```bash
bash infra/gcp/setup_cloud_sql.sh
```

El script:
1. Habilita las APIs necesarias (`sqladmin`, `run`, `secretmanager`).
2. Crea la instancia `glamping-db` (`db-f1-micro` con PostgreSQL 16).
3. Habilita Point-in-Time Recovery (PITR) y backups automatizados.
4. Crea la base de datos `glamping_prod` y el usuario `glamping_app`.
5. Almacena la cadena de conexión en **Google Secret Manager** (`DATABASE_URL`).

---

## 3. Migración y Aplicación de Esquema

Las migraciones se ejecutan de forma idempotente con `scripts/migrar_db.py`:

```bash
# Modo comprobación (dry-run):
python scripts/migrar_db.py --url "$DATABASE_URL" --dry-run

# Aplicación real del esquema:
python scripts/migrar_db.py --url "$DATABASE_URL"

# O mediante la compuerta de app_core:
python -m app_core.main --migrar-db
```

---

## 4. Despliegue en Cloud Run

El despliegue se gestiona a través de Cloud Build (`cloudbuild.yaml`) o con `gcloud`:

```bash
gcloud run services replace infra/gcp/cloudrun.yaml
```

**Parámetros clave de resiliencia:**
- `autoscaling.knative.dev/minScale: "1"`: Contenedor siempre activo para eliminar arranques en frío (Cold Starts) en webhooks de Meta.
- `run.googleapis.com/cloudsql-instances`: Enlace gestionado al socket de Cloud SQL.
- Inyección de credenciales directamente desde Secret Manager sin archivos `.env` en disco.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
