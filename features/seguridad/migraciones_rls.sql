-- ¤seguridad-canal
-- ¤¤security-engineer
-- Migraciones de Row-Level Security por propiedad_id (RF-SEC-07, T-304)
-- Rol de aplicación NOBYPASSRLS e invariantes de aislamiento multi-inquilino.
-- © 2026 Juan Carlos Proaño. Todos los derechos reservados.

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_glamping') THEN
    CREATE ROLE app_glamping NOLOGIN NOBYPASSRLS;
  ELSE
    ALTER ROLE app_glamping NOBYPASSRLS;
  END IF;
END $$;

GRANT USAGE ON SCHEMA agente TO app_glamping;
GRANT USAGE ON SCHEMA anfitriones TO app_glamping;
GRANT USAGE ON SCHEMA arm TO app_glamping;
GRANT USAGE ON SCHEMA comisiones TO app_glamping;
GRANT USAGE ON SCHEMA conocimiento TO app_glamping;
GRANT USAGE ON SCHEMA pms TO app_glamping;
GRANT USAGE ON SCHEMA seguridad TO app_glamping;
GRANT USAGE ON SCHEMA web TO app_glamping;

-- RLS para conocimiento.chunks
ALTER TABLE conocimiento.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE conocimiento.chunks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_chunks_por_propiedad ON conocimiento.chunks;
CREATE POLICY rls_chunks_por_propiedad ON conocimiento.chunks
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON conocimiento.chunks TO app_glamping;

-- RLS para conocimiento.documentos
ALTER TABLE conocimiento.documentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE conocimiento.documentos FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_documentos_por_propiedad ON conocimiento.documentos;
CREATE POLICY rls_documentos_por_propiedad ON conocimiento.documentos
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON conocimiento.documentos TO app_glamping;

-- RLS para pms.propiedades
ALTER TABLE pms.propiedades ENABLE ROW LEVEL SECURITY;
ALTER TABLE pms.propiedades FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_propiedades_por_propiedad ON pms.propiedades;
CREATE POLICY rls_propiedades_por_propiedad ON pms.propiedades
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON pms.propiedades TO app_glamping;

-- RLS para pms.unidades
ALTER TABLE pms.unidades ENABLE ROW LEVEL SECURITY;
ALTER TABLE pms.unidades FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_unidades_por_propiedad ON pms.unidades;
CREATE POLICY rls_unidades_por_propiedad ON pms.unidades
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON pms.unidades TO app_glamping;

-- RLS para pms.reservas_ref
ALTER TABLE pms.reservas_ref ENABLE ROW LEVEL SECURITY;
ALTER TABLE pms.reservas_ref FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_reservas_ref_por_propiedad ON pms.reservas_ref;
CREATE POLICY rls_reservas_ref_por_propiedad ON pms.reservas_ref
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON pms.reservas_ref TO app_glamping;

-- RLS para pms.incidencias
ALTER TABLE pms.incidencias ENABLE ROW LEVEL SECURITY;
ALTER TABLE pms.incidencias FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_incidencias_por_propiedad ON pms.incidencias;
CREATE POLICY rls_incidencias_por_propiedad ON pms.incidencias
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON pms.incidencias TO app_glamping;

-- RLS para agente.conversaciones
ALTER TABLE agente.conversaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE agente.conversaciones FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_conversaciones_por_propiedad ON agente.conversaciones;
CREATE POLICY rls_conversaciones_por_propiedad ON agente.conversaciones
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON agente.conversaciones TO app_glamping;

-- RLS para arm.ventas
ALTER TABLE arm.ventas ENABLE ROW LEVEL SECURITY;
ALTER TABLE arm.ventas FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_ventas_por_propiedad ON arm.ventas;
CREATE POLICY rls_ventas_por_propiedad ON arm.ventas
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON arm.ventas TO app_glamping;

-- RLS para web.enlaces_contacto
ALTER TABLE web.enlaces_contacto ENABLE ROW LEVEL SECURITY;
ALTER TABLE web.enlaces_contacto FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_enlaces_contacto_por_propiedad ON web.enlaces_contacto;
CREATE POLICY rls_enlaces_contacto_por_propiedad ON web.enlaces_contacto
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON web.enlaces_contacto TO app_glamping;

-- RLS para anfitriones.solicitudes
ALTER TABLE anfitriones.solicitudes ENABLE ROW LEVEL SECURITY;
ALTER TABLE anfitriones.solicitudes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_solicitudes_por_propiedad ON anfitriones.solicitudes;
CREATE POLICY rls_solicitudes_por_propiedad ON anfitriones.solicitudes
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON anfitriones.solicitudes TO app_glamping;

-- RLS para anfitriones.hospedajes
ALTER TABLE anfitriones.hospedajes ENABLE ROW LEVEL SECURITY;
ALTER TABLE anfitriones.hospedajes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_hospedajes_por_propiedad ON anfitriones.hospedajes;
CREATE POLICY rls_hospedajes_por_propiedad ON anfitriones.hospedajes
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON anfitriones.hospedajes TO app_glamping;

-- RLS para comisiones.reglas
ALTER TABLE comisiones.reglas ENABLE ROW LEVEL SECURITY;
ALTER TABLE comisiones.reglas FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_reglas_por_propiedad ON comisiones.reglas;
CREATE POLICY rls_reglas_por_propiedad ON comisiones.reglas
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT, UPDATE, DELETE ON comisiones.reglas TO app_glamping;

-- RLS para seguridad.audit_log
ALTER TABLE seguridad.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE seguridad.audit_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_audit_log_por_propiedad ON seguridad.audit_log;
CREATE POLICY rls_audit_log_por_propiedad ON seguridad.audit_log
  FOR ALL
  TO app_glamping
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))
  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

GRANT SELECT, INSERT ON seguridad.audit_log TO app_glamping;
REVOKE UPDATE, DELETE, TRUNCATE ON seguridad.audit_log FROM app_glamping;
