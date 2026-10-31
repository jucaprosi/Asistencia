-- ¤spec-glamping
-- Esquema canónico. Un esquema de PostgreSQL por sala; sin claves foráneas entre esquemas: las salas
-- se referencian por identificador y se consultan por compuerta (ADPA). Lo aplica la CI en PostgreSQL real.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_glamping') THEN
    CREATE ROLE app_glamping NOLOGIN NOBYPASSRLS;
  END IF;
END $$;

CREATE SCHEMA canal;
CREATE SCHEMA seguridad;
CREATE SCHEMA agente;
CREATE SCHEMA conocimiento;
CREATE SCHEMA pms;
CREATE SCHEMA crm;
CREATE SCHEMA arm;
CREATE SCHEMA comisiones;
CREATE SCHEMA observabilidad;
CREATE SCHEMA panel;

-- Sala canal_whatsapp
CREATE TABLE canal.eventos_entrantes (
  evento_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mensaje_id       text NOT NULL UNIQUE,            -- deduplicación de reintentos de Meta
  conversacion_clave text NOT NULL,                 -- serializa el procesamiento por remitente
  cuerpo_cifrado   bytea NOT NULL,
  estado           text NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','procesando','procesado','muerto')),
  intentos         integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
  recibido_en      timestamptz NOT NULL DEFAULT now(),
  procesado_en     timestamptz
);
CREATE INDEX eventos_pendientes ON canal.eventos_entrantes (conversacion_clave, recibido_en) WHERE estado IN ('pendiente','procesando');

CREATE TABLE canal.mensajes_meta (
  mensaje_id       text PRIMARY KEY,
  direccion        text NOT NULL CHECK (direccion IN ('in','out')),
  remitente_token  text NOT NULL,
  canal            text NOT NULL CHECK (canal IN ('huespedes','vendedores')),
  tipo             text NOT NULL CHECK (tipo IN ('texto','plantilla','medio','boton','ubicacion')),
  estado           text NOT NULL CHECK (estado IN ('recibido','sent','delivered','read','failed')),
  plantilla        text,
  enviado_en       timestamptz NOT NULL DEFAULT now(),
  actualizado_en   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE canal.plantillas (
  nombre           text PRIMARY KEY,
  idioma           text NOT NULL DEFAULT 'es',
  categoria        text NOT NULL CHECK (categoria IN ('utility','authentication','marketing')),
  aprobada         boolean NOT NULL DEFAULT false,
  actualizada_en   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE canal.medios (
  medio_id         text PRIMARY KEY,
  mensaje_id       text NOT NULL REFERENCES canal.mensajes_meta(mensaje_id),
  medio_ref        text NOT NULL,
  tipo             text NOT NULL CHECK (tipo IN ('imagen','audio','documento','ubicacion')),
  bytes            bigint NOT NULL CHECK (bytes >= 0),
  expira_en        timestamptz NOT NULL
);

-- Sala seguridad
CREATE TABLE seguridad.usuarios (
  usuario_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  correo_hash      text NOT NULL UNIQUE,
  numero_hash      text NOT NULL UNIQUE,
  rol              text NOT NULL CHECK (rol IN ('vendedor','lider','gestor','administrador')),
  sujeto_id        text,
  activo           boolean NOT NULL DEFAULT true,
  alta_por         uuid,
  alta_en          timestamptz NOT NULL DEFAULT now(),
  baja_en          timestamptz
);

CREATE TABLE seguridad.huespedes (
  huesped_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  telefono_token   text NOT NULL UNIQUE,
  nombre_token     text,
  idioma           text NOT NULL DEFAULT 'es',
  crm_ref          text,
  creado_en        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE seguridad.bloqueos (
  numero_hash      text PRIMARY KEY,
  motivo           text NOT NULL,
  bloqueado_por    uuid NOT NULL,
  bloqueado_en     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE seguridad.boveda_tokens (
  token            text PRIMARY KEY,
  titular_hash     text NOT NULL,
  tipo             text NOT NULL CHECK (tipo IN ('nombre','telefono','correo','documento','tarjeta','direccion','clave_wifi','codigo_acceso')),
  valor_cifrado    bytea NOT NULL,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  ultimo_uso_en    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX boveda_por_titular ON seguridad.boveda_tokens (titular_hash);

CREATE TABLE seguridad.rate_limit (
  remitente_hash   text NOT NULL,
  ventana          text NOT NULL CHECK (ventana IN ('segundo','minuto','dia')),
  inicio           timestamptz NOT NULL,
  contador         integer NOT NULL DEFAULT 0 CHECK (contador >= 0),
  aviso_enviado    boolean NOT NULL DEFAULT false,
  PRIMARY KEY (remitente_hash, ventana, inicio)
);

CREATE TABLE seguridad.consentimientos (
  consentimiento_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  titular_hash     text NOT NULL,
  base             text NOT NULL CHECK (base IN ('aviso_primer_contacto','reserva','relacion_laboral')),
  version_aviso    text NOT NULL,
  otorgado_en      timestamptz NOT NULL DEFAULT now(),
  revocado_en      timestamptz
);

CREATE TABLE seguridad.solicitudes_titular (
  solicitud_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  titular_hash     text NOT NULL,
  tipo             text NOT NULL CHECK (tipo IN ('acceso','rectificacion','eliminacion','oposicion','portabilidad')),
  estado           text NOT NULL DEFAULT 'recibida' CHECK (estado IN ('recibida','en_curso','atendida','atendida_parcial','rechazada')),
  recibida_en      timestamptz NOT NULL DEFAULT now(),
  limite_en        timestamptz NOT NULL,
  atendida_en      timestamptz,
  atendida_por     uuid,
  motivo           text
);

CREATE TABLE seguridad.audit_log (
  audit_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  instante         timestamptz NOT NULL DEFAULT now(),
  actor_token      text NOT NULL,
  rol              text NOT NULL,
  accion           text NOT NULL,
  herramienta      text,
  propiedad_id     text,
  resultado        text NOT NULL,
  hash_prompt      text,
  traza_id         text
);

-- Sala agente
CREATE TABLE agente.conversaciones (
  conversacion_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identidad_token  text NOT NULL,
  canal            text NOT NULL CHECK (canal IN ('huespedes','vendedores')),
  propiedad_id     text,
  estado           text NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa','handoff','cerrada')),
  modo             text NOT NULL DEFAULT 'activo' CHECK (modo IN ('activo','silencio')),
  resultado        text CHECK (resultado IN ('resuelta','handoff','abandonada')),
  abstenciones_seguidas integer NOT NULL DEFAULT 0 CHECK (abstenciones_seguidas >= 0),
  ventana_24h_hasta timestamptz,
  creada           timestamptz NOT NULL DEFAULT now(),
  actualizada      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE agente.mensajes (
  mensaje_id       text PRIMARY KEY,
  conversacion_id  uuid NOT NULL REFERENCES agente.conversaciones(conversacion_id),
  direccion        text NOT NULL CHECK (direccion IN ('in','out')),
  tipo             text NOT NULL,
  contenido_token  text NOT NULL,
  traza_id         text,
  instante         timestamptz NOT NULL DEFAULT now()
);

-- Evita repetir un envío programado si el planificador se reinicia
CREATE TABLE agente.envios_programados (
  codigo_reserva   text NOT NULL,
  plantilla        text NOT NULL,
  fecha            date NOT NULL,
  mensaje_id       text,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (codigo_reserva, plantilla, fecha)
);

CREATE TABLE agente.cache_semantico (
  hash_consulta    text PRIMARY KEY,
  embedding        vector(1024) NOT NULL,
  respuesta        text NOT NULL,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  expira_en        timestamptz NOT NULL
);

-- Sala conocimiento
CREATE TABLE conocimiento.documentos (
  documento_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ruta             text NOT NULL UNIQUE,
  propiedad_id     text NOT NULL,                    -- 'global' o identificador de propiedad
  tipo             text NOT NULL CHECK (tipo IN ('politicas','precios','checkin','atractivos','faq','pagos','privacidad')),
  dueno            text NOT NULL,
  revisado         date NOT NULL,
  version_hash     text NOT NULL,
  indexado_en      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE conocimiento.chunks (
  chunk_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  documento_id     uuid NOT NULL REFERENCES conocimiento.documentos(documento_id) ON DELETE CASCADE,
  propiedad_id     text NOT NULL,
  encabezado       text NOT NULL,
  texto            text NOT NULL,
  embedding        vector(1024) NOT NULL,
  tsv              tsvector GENERATED ALWAYS AS (to_tsvector('spanish', texto)) STORED,
  orden            integer NOT NULL
);
CREATE INDEX chunks_hnsw ON conocimiento.chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX chunks_gin ON conocimiento.chunks USING gin (tsv);
ALTER TABLE conocimiento.chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE conocimiento.chunks FORCE ROW LEVEL SECURITY;
CREATE POLICY chunks_por_propiedad ON conocimiento.chunks
  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));

-- Sala pms_conector: catálogo local y referencias; la fuente de verdad de reservas es el PMS
CREATE TABLE pms.propiedades (
  propiedad_id     text PRIMARY KEY,
  tipo             text NOT NULL CHECK (tipo IN ('glamping','departamento')),
  nombre           text NOT NULL,
  zona_id          text NOT NULL,
  direccion        text NOT NULL,
  pms_ref          text,
  prompt_variante  text NOT NULL CHECK (prompt_variante IN ('glamping','departamentos')),
  activa           boolean NOT NULL DEFAULT true
);

CREATE TABLE pms.unidades (
  unidad_id        text PRIMARY KEY,
  propiedad_id     text NOT NULL REFERENCES pms.propiedades(propiedad_id),
  nombre           text NOT NULL,
  capacidad        integer NOT NULL CHECK (capacidad >= 1),
  edificio         text,
  piso             text,
  acceso_ref       text,                              -- token de bóveda; nunca el código en claro
  wifi_ref         text
);

-- Caché declarada: el PMS sigue siendo la fuente de verdad. Permite validar al titular sin llamar al PMS.
CREATE TABLE pms.reservas_ref (
  codigo_reserva   text PRIMARY KEY,
  propiedad_id     text NOT NULL REFERENCES pms.propiedades(propiedad_id),
  unidad_id        text NOT NULL REFERENCES pms.unidades(unidad_id),
  huesped_id       uuid NOT NULL,
  desde            date NOT NULL,
  hasta            date NOT NULL,
  estado           text NOT NULL CHECK (estado IN ('preliminar','confirmada','cancelada','expirada','completada')),
  expira_en        timestamptz,
  pms_ref          text,
  actualizada      timestamptz NOT NULL DEFAULT now(),
  CHECK (hasta > desde)
);
CREATE INDEX reservas_por_llegada ON pms.reservas_ref (desde) WHERE estado = 'confirmada';

-- Si ADR-0007 crea la sala operaciones, esta tabla y su secuencia se mueven a ella sin cambiar de forma
CREATE TABLE pms.incidencias (
  incidencia_id    text PRIMARY KEY CHECK (incidencia_id ~ '^I-[0-9]{4}-[0-9]{4,}$'),
  propiedad_id     text NOT NULL REFERENCES pms.propiedades(propiedad_id),
  unidad_id        text REFERENCES pms.unidades(unidad_id),
  codigo_reserva   text,
  categoria        text NOT NULL CHECK (categoria IN ('agua','electricidad','limpieza','acceso','seguridad','ruido','wifi','otra')),
  prioridad        text NOT NULL CHECK (prioridad IN ('baja','media','alta','critica')),
  estado           text NOT NULL DEFAULT 'abierta' CHECK (estado IN ('abierta','en_curso','resuelta')),
  descripcion_token text NOT NULL,
  gestor_id        uuid,
  creada           timestamptz NOT NULL DEFAULT now(),
  resuelta_en      timestamptz,
  resuelta_por     uuid,
  nota             text,
  CHECK (categoria NOT IN ('acceso','seguridad') OR prioridad = 'critica')
);

CREATE TABLE pms.idempotencia (
  clave            uuid PRIMARY KEY,
  operacion        text NOT NULL,
  resultado_json   jsonb NOT NULL,
  creado_en        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE pms.secuencia_incidencias (
  anio             integer PRIMARY KEY,
  ultimo           integer NOT NULL DEFAULT 0
);

-- Sala crm_conector: asignación humana y publicación. El handoff vive aquí; el inbox externo es un espejo opcional.
CREATE TABLE crm.zonas (
  zona_id          text PRIMARY KEY,
  nombre           text NOT NULL,
  gestor_principal_id uuid NOT NULL,
  gestor_respaldo_id  uuid NOT NULL,
  CHECK (gestor_principal_id <> gestor_respaldo_id)
);

CREATE TABLE crm.handoffs (
  handoff_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversacion_id  uuid NOT NULL,
  motivo           text NOT NULL CHECK (motivo IN ('peticion_explicita','baja_confianza','fuera_alcance','incidencia_critica','inyeccion_repetida','degradacion','limite_iteraciones')),
  zona_id          text REFERENCES crm.zonas(zona_id),
  estado           text NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','tomado','devuelto')),
  asignado_a       uuid,
  resumen_token    text NOT NULL,
  inicio           timestamptz NOT NULL DEFAULT now(),
  tomado_en        timestamptz,
  ultima_actividad timestamptz NOT NULL DEFAULT now(),
  devuelto_en      timestamptz,
  devuelto_por     text CHECK (devuelto_por IN ('gestor','vencimiento'))
);
CREATE UNIQUE INDEX un_handoff_abierto ON crm.handoffs (conversacion_id) WHERE estado <> 'devuelto';

CREATE TABLE crm.publicaciones (
  venta_id         uuid NOT NULL,
  evento           text NOT NULL CHECK (evento IN ('venta_validada','venta_anulada')),
  payload_json     jsonb NOT NULL,
  estado           text NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','ok','error')),
  intentos         integer NOT NULL DEFAULT 0,
  ultima_respuesta text,
  proximo_intento  timestamptz,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (venta_id, evento)
);

CREATE TABLE crm.eventos (
  evento_id        text PRIMARY KEY,
  tipo             text NOT NULL,
  referencia       text NOT NULL,
  datos_json       jsonb NOT NULL,
  recibido_en      timestamptz NOT NULL DEFAULT now(),
  procesado_en     timestamptz
);

CREATE TABLE crm.referencias (
  entidad          text NOT NULL,
  id_local         text NOT NULL,
  crm_ref          text NOT NULL,
  PRIMARY KEY (entidad, id_local)
);

-- Sala arm_jarvis
CREATE TABLE arm.vendedores (
  vendedor_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  telefono_token   text NOT NULL UNIQUE,
  nombre           text NOT NULL,
  activo           boolean NOT NULL DEFAULT true,
  regla_comision_default_id text
);

CREATE TABLE arm.secuencia_tickets (
  anio             integer PRIMARY KEY,
  ultimo           integer NOT NULL DEFAULT 0
);

CREATE TABLE arm.ventas (
  venta_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket           text NOT NULL UNIQUE CHECK (ticket ~ '^V-[0-9]{4}-[0-9]{4,}$'),
  vendedor_id      uuid NOT NULL REFERENCES arm.vendedores(vendedor_id),
  cliente_token    text,
  telefono_cliente_token text,
  producto         text NOT NULL,
  propiedad_id     text,
  noches           integer CHECK (noches >= 1),
  monto            numeric(12,2) NOT NULL CHECK (monto > 0),
  moneda           text NOT NULL DEFAULT 'USD' CHECK (moneda = 'USD'),
  fecha_venta      date NOT NULL,
  fecha_llegada    date,
  texto_original_token text NOT NULL,
  mensaje_id       text NOT NULL,
  indice_en_mensaje integer NOT NULL DEFAULT 0,
  confianza        numeric(3,2) NOT NULL CHECK (confianza BETWEEN 0 AND 1),
  confianza_campos jsonb NOT NULL DEFAULT '{}',
  huella_duplicado text NOT NULL,
  posible_duplicado_de uuid REFERENCES arm.ventas(venta_id),
  estado           text NOT NULL DEFAULT 'por_validar' CHECK (estado IN ('por_validar','validada','rechazada','publicada','no_publicada','anulada')),
  reserva_ref      text,
  creada           timestamptz NOT NULL DEFAULT now(),
  validada_en      timestamptz,
  actualizada      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (mensaje_id, indice_en_mensaje)
);
CREATE INDEX ventas_huella ON arm.ventas (huella_duplicado, creada);

CREATE TABLE arm.transiciones (
  transicion_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venta_id         uuid NOT NULL REFERENCES arm.ventas(venta_id),
  de               text NOT NULL,
  a                text NOT NULL,
  actor_id         text NOT NULL,
  rol              text NOT NULL,
  motivo           text,
  instante         timestamptz NOT NULL DEFAULT now(),
  CHECK (a NOT IN ('rechazada','anulada') OR motivo IS NOT NULL),
  CHECK (a <> 'anulada' OR rol = 'administrador')
);

CREATE TABLE arm.configuracion (
  clave            text PRIMARY KEY,
  valor            jsonb NOT NULL,
  cambiado_por     text NOT NULL,
  cambiado_en      timestamptz NOT NULL DEFAULT now()
);

CREATE FUNCTION arm.validar_transicion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.estado = OLD.estado THEN
    RETURN NEW;
  END IF;
  IF NOT (
       (OLD.estado = 'por_validar'  AND NEW.estado IN ('validada','rechazada','anulada'))
    OR (OLD.estado = 'validada'     AND NEW.estado IN ('publicada','no_publicada','anulada'))
    OR (OLD.estado = 'no_publicada' AND NEW.estado IN ('publicada','anulada'))
    OR (OLD.estado = 'publicada'    AND NEW.estado = 'anulada')
    OR (OLD.estado = 'rechazada'    AND NEW.estado = 'anulada')
  ) THEN
    RAISE EXCEPTION 'TransicionInvalida: % a %', OLD.estado, NEW.estado USING ERRCODE = 'check_violation';
  END IF;
  NEW.actualizada := now();
  RETURN NEW;
END $$;
CREATE TRIGGER ventas_transicion BEFORE UPDATE OF estado ON arm.ventas
  FOR EACH ROW EXECUTE FUNCTION arm.validar_transicion();

-- Sala comisiones
CREATE TABLE comisiones.reglas (
  regla_id         text NOT NULL,
  version          integer NOT NULL CHECK (version >= 1),
  vendedor_id      uuid,
  propiedad_id     text,
  producto_patron  text,
  tipo             text NOT NULL CHECK (tipo IN ('porcentaje','fijo','escalonada')),
  valor            numeric(12,4),
  escalones        jsonb NOT NULL DEFAULT '[]',
  modo_escalon     text NOT NULL DEFAULT 'graduado' CHECK (modo_escalon IN ('graduado','volumen')),
  vigente_desde    date NOT NULL,
  vigente_hasta    date,
  creada_por       text NOT NULL,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (regla_id, version),
  CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
);

CREATE TABLE comisiones.periodos (
  periodo_id       text PRIMARY KEY CHECK (periodo_id ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
  cerrado_en       timestamptz,
  cerrado_por      text,
  resumen_json     jsonb
);

CREATE TABLE comisiones.comisiones (
  comision_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  venta_id         uuid NOT NULL,
  vendedor_id      uuid NOT NULL,
  fecha_venta      date NOT NULL,
  monto_venta      numeric(12,2) NOT NULL,
  regla_id         text NOT NULL,
  regla_version    integer NOT NULL,
  monto            numeric(12,2) NOT NULL,
  base_acumulada   numeric(12,2) NOT NULL DEFAULT 0 CHECK (base_acumulada >= 0),
  periodo_id       text NOT NULL REFERENCES comisiones.periodos(periodo_id),
  periodo_origen   text NOT NULL,
  estado           text NOT NULL CHECK (estado IN ('estimada','fijada','pagada','ajustada')),
  ajuste_de        uuid REFERENCES comisiones.comisiones(comision_id),
  motivo           text,
  FOREIGN KEY (regla_id, regla_version) REFERENCES comisiones.reglas(regla_id, version),
  CHECK (estado <> 'ajustada' OR ajuste_de IS NOT NULL),
  CHECK (estado = 'ajustada' OR monto >= 0),
  CHECK (estado = 'ajustada' OR monto_venta >= 0)
);
CREATE UNIQUE INDEX comision_unica_por_venta ON comisiones.comisiones (venta_id) WHERE ajuste_de IS NULL;

CREATE FUNCTION comisiones.proteger_periodo_cerrado() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  objetivo text;
BEGIN
  objetivo := CASE WHEN TG_OP = 'DELETE' THEN OLD.periodo_id ELSE NEW.periodo_id END;
  IF EXISTS (SELECT 1 FROM comisiones.periodos p WHERE p.periodo_id = objetivo AND p.cerrado_en IS NOT NULL) THEN
    RAISE EXCEPTION 'PeriodoCerrado: %', objetivo USING ERRCODE = 'check_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER comisiones_periodo BEFORE INSERT OR UPDATE OR DELETE ON comisiones.comisiones
  FOR EACH ROW EXECUTE FUNCTION comisiones.proteger_periodo_cerrado();

CREATE FUNCTION comisiones.proteger_regla() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'ReglaInmutable: crea una versión nueva' USING ERRCODE = 'check_violation';
END $$;
CREATE TRIGGER reglas_inmutables BEFORE UPDATE OR DELETE ON comisiones.reglas
  FOR EACH ROW EXECUTE FUNCTION comisiones.proteger_regla();

-- Sala observabilidad
CREATE TABLE observabilidad.trazas (
  traza_id         text PRIMARY KEY,
  mensaje_id       text,
  iniciada         timestamptz NOT NULL DEFAULT now(),
  cerrada          timestamptz
);

CREATE TABLE observabilidad.spans (
  span_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  traza_id         text NOT NULL REFERENCES observabilidad.trazas(traza_id) ON DELETE CASCADE,
  sala             text NOT NULL,
  nombre           text NOT NULL,
  duracion_ms      integer NOT NULL CHECK (duracion_ms >= 0),
  modelo           text,
  tokens_in        integer,
  tokens_out       integer,
  costo_usd        numeric(10,6),
  atributos        jsonb NOT NULL DEFAULT '{}'
);

-- Sala panel_operativo
CREATE TABLE panel.codigos_acceso (
  codigo_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id       uuid NOT NULL,
  codigo_hash      text NOT NULL,
  intentos         integer NOT NULL DEFAULT 0 CHECK (intentos BETWEEN 0 AND 5),
  expira_en        timestamptz NOT NULL,
  usado_en         timestamptz
);

-- Un teléfono por fila; se revoca al cerrar sesión o dar de baja al usuario
CREATE TABLE panel.dispositivos (
  dispositivo_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id       uuid NOT NULL,
  endpoint         text NOT NULL UNIQUE,
  clave_p256dh     text NOT NULL,
  clave_auth       text NOT NULL,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  revocado_en      timestamptz
);

-- Repetir una acción con la misma clave devuelve la respuesta guardada
CREATE TABLE panel.acciones_idempotentes (
  usuario_id       uuid NOT NULL,
  clave            uuid NOT NULL,
  accion           text NOT NULL,
  respuesta        jsonb,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (usuario_id, clave)
);

CREATE TABLE panel.sesiones (
  sesion_id_hash   text PRIMARY KEY,
  usuario_id       uuid NOT NULL,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  expira_en        timestamptz NOT NULL,
  cerrada_en       timestamptz
);

-- Permisos
GRANT USAGE ON SCHEMA canal, seguridad, agente, conocimiento, pms, crm, arm, comisiones, observabilidad, panel TO app_glamping;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA canal, seguridad, agente, conocimiento, pms, crm, arm, comisiones, observabilidad, panel TO app_glamping;
REVOKE UPDATE, DELETE, TRUNCATE ON seguridad.audit_log FROM app_glamping;
REVOKE UPDATE, DELETE, TRUNCATE ON arm.transiciones FROM app_glamping;
