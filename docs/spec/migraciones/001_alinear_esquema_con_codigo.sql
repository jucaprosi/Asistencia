-- ¤persistencia-sql
-- Alinea el esquema canónico con las columnas y tablas que las salas ya usan (comparación automática
-- SQLite ↔ PostgreSQL del 2026-11-22, ADR-0020). Solo agrega; no borra datos.

-- pms_conector: la reserva guarda el token del huésped, el número de huéspedes y el total cotizado.
ALTER TABLE pms.reservas_ref ADD COLUMN IF NOT EXISTS huesped_token text;
ALTER TABLE pms.reservas_ref ADD COLUMN IF NOT EXISTS huespedes integer NOT NULL DEFAULT 1;
ALTER TABLE pms.reservas_ref ADD COLUMN IF NOT EXISTS total numeric(12,2);
ALTER TABLE pms.reservas_ref ALTER COLUMN huesped_id DROP NOT NULL;

-- arm_jarvis: comisión estimada al registrar y fijada al validar.
ALTER TABLE arm.ventas ADD COLUMN IF NOT EXISTS comision_estimada numeric(12,2);
ALTER TABLE arm.ventas ADD COLUMN IF NOT EXISTS comision_fijada numeric(12,2);

-- anfitriones: contadores para identificadores legibles.
CREATE TABLE IF NOT EXISTS anfitriones.secuencias (
  nombre           text PRIMARY KEY,
  valor            integer NOT NULL
);

-- panel_operativo: la sesión guarda token CSRF, rol y zonas; etiquetas y notas de conversación.
ALTER TABLE panel.sesiones ADD COLUMN IF NOT EXISTS csrf text NOT NULL DEFAULT '';
ALTER TABLE panel.sesiones ADD COLUMN IF NOT EXISTS rol text NOT NULL DEFAULT '';
ALTER TABLE panel.sesiones ADD COLUMN IF NOT EXISTS zonas text NOT NULL DEFAULT '';
CREATE TABLE IF NOT EXISTS panel.conversaciones_etiquetas (
  conversacion_id  text NOT NULL,
  etiqueta         text NOT NULL,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (conversacion_id, etiqueta)
);
CREATE TABLE IF NOT EXISTS panel.conversaciones_notas (
  nota_id          text PRIMARY KEY,
  conversacion_id  text NOT NULL,
  autor_id         text NOT NULL,
  autor_nombre     text NOT NULL,
  texto            text NOT NULL,
  creada_en        timestamptz NOT NULL DEFAULT now()
);

-- agente: rol del interlocutor en la conversación.
ALTER TABLE agente.conversaciones ADD COLUMN IF NOT EXISTS rol text NOT NULL DEFAULT 'huesped_potencial';

-- observabilidad: la traza registra canal, conversación y resultado; el span su instante de inicio.
ALTER TABLE observabilidad.trazas ADD COLUMN IF NOT EXISTS conversacion_id text;
ALTER TABLE observabilidad.trazas ADD COLUMN IF NOT EXISTS canal text NOT NULL DEFAULT 'huespedes';
ALTER TABLE observabilidad.trazas ADD COLUMN IF NOT EXISTS resultado text;
ALTER TABLE observabilidad.spans ADD COLUMN IF NOT EXISTS inicio timestamptz NOT NULL DEFAULT now();

-- agente: la caché semántica se separa por propiedad (la consulta filtra por propiedad_id).
ALTER TABLE agente.cache_semantico ADD COLUMN IF NOT EXISTS propiedad_id text NOT NULL DEFAULT 'glamping';

-- pms_conector: reservas_ref es una caché del PMS (externo o propio); un proveedor externo puede referir
-- propiedades y unidades que la plataforma no replica, así que la caché no exige claves foráneas.
ALTER TABLE pms.reservas_ref DROP CONSTRAINT IF EXISTS reservas_ref_propiedad_id_fkey;
ALTER TABLE pms.reservas_ref DROP CONSTRAINT IF EXISTS reservas_ref_unidad_id_fkey;

-- seguridad: el audit log es de solo inserción también para el dueño de la tabla (INV_AUDIT_APPEND_ONLY).
-- Los permisos de app_glamping no bastan si la aplicación se conecta con el usuario propietario.
CREATE OR REPLACE FUNCTION seguridad.audit_log_solo_insercion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'REVOKE: operacion % denegada sobre seguridad.audit_log', TG_OP;
END $$;
DROP TRIGGER IF EXISTS audit_log_solo_insercion ON seguridad.audit_log;
CREATE TRIGGER audit_log_solo_insercion BEFORE UPDATE OR DELETE ON seguridad.audit_log
  FOR EACH ROW EXECUTE FUNCTION seguridad.audit_log_solo_insercion();
