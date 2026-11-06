# Procedimiento de Backup Cifrado y Restauración (RNF-15, S-08)

`¤infra-hibrida`
`¤¤devops-engineer`

## 1. Alcance
Este directorio contiene las herramientas de respaldo y recuperación ante desastres para el despliegue productivo del agente Glamping Imbabura en el servidor propio. Cumple con:
- **RNF-15 (Durabilidad y PITR ≥ 7 días):** Respaldos diarios automatizados con rotación semanal y prueba obligatoria de restauración por fase.
- **S-08 (Servidor Contable y Aislamiento):** Cifrado en reposo simétrico (AES-256-CBC con PBKDF2 y 100.000 iteraciones) sin almacenar claves ni credenciales en el repositorio (`INV_SIN_SECRETOS_EN_REPO`).

## 2. Generación de Respaldo (`backup.sh`)
```bash
# Ejecutar respaldo cifrado en la ruta designada
./infra/backups/backup.sh /var/backups/glamping "clave_secreta_segura"
```
Salida:
- `dump_glamping_YYYYMMDD_HHMMSSZ.sql.enc`: Archivo cifrado con AES-256.
- `dump_glamping_YYYYMMDD_HHMMSSZ.sql.enc.sha256`: Hash criptográfico para verificación de integridad.

## 3. Restauración de Respaldo (`restaurar.sh`)
```bash
# Validar hash, descifrar y restaurar en PostgreSQL
./infra/backups/restaurar.sh /var/backups/glamping/dump_glamping_YYYYMMDD_HHMMSSZ.sql.enc "clave_secreta_segura"
```

## 4. Registro de Ensayos de Recuperación
Conforme a `RNF-15`, cada hito de producción documenta la prueba de restauración en `governance/artefactos/`.
