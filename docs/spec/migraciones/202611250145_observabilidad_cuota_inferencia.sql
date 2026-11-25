-- ¤inferencia
-- K1 del ADR-0021: tope diario del gasto en inferencia en PostgreSQL. Lo usa cuota_internal.py con un único
-- UPDATE ... WHERE gastado_micro + costo <= tope RETURNING; el día es el día UTC en formato AAAA-MM-DD.
-- El permiso de app_glamping lo da la migración de seguridad que depende de esta.
-- Sin esta tabla la cuota niega toda inferencia (falla cerrada).
-- © 2026 Juan Carlos Proaño. Todos los derechos reservados.

CREATE TABLE IF NOT EXISTS observabilidad.cuota_inferencia (
  dia            text   PRIMARY KEY CHECK (dia ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
  gastado_micro  bigint NOT NULL DEFAULT 0 CHECK (gastado_micro >= 0)
);
