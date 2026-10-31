-- ¤spec-glamping
-- Prueba negativa de las leyes que viven en la base de datos. Cada bloque debe fallar con el error esperado:
-- si la operación prohibida se ejecuta, el bloque lanza AssertionError y psql termina con Exit Code distinto de 0.
BEGIN;

INSERT INTO arm.vendedores (vendedor_id, telefono_token, nombre)
VALUES ('00000000-0000-0000-0000-000000000001', 'tok', 'Vendedor de prueba');
INSERT INTO arm.ventas (venta_id, ticket, vendedor_id, producto, monto, fecha_venta, texto_original_token, mensaje_id, confianza, huella_duplicado)
VALUES ('00000000-0000-0000-0000-000000000002', 'V-2026-0001', '00000000-0000-0000-0000-000000000001', 'Prueba', 100.00, '2026-10-30', 'tok', 'm1', 0.90, 'h');

DO $$ BEGIN
  BEGIN
    UPDATE arm.ventas SET estado = 'publicada' WHERE venta_id = '00000000-0000-0000-0000-000000000002';
    RAISE EXCEPTION 'AssertionError: por_validar a publicada no debió permitirse' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  UPDATE arm.ventas SET estado = 'validada' WHERE venta_id = '00000000-0000-0000-0000-000000000002';
  UPDATE arm.ventas SET estado = 'no_publicada' WHERE venta_id = '00000000-0000-0000-0000-000000000002';
  UPDATE arm.ventas SET estado = 'publicada' WHERE venta_id = '00000000-0000-0000-0000-000000000002';
  UPDATE arm.ventas SET estado = 'anulada' WHERE venta_id = '00000000-0000-0000-0000-000000000002';
  BEGIN
    UPDATE arm.ventas SET estado = 'validada' WHERE venta_id = '00000000-0000-0000-0000-000000000002';
    RAISE EXCEPTION 'AssertionError: anulada es un estado final' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

DO $$ BEGIN
  BEGIN
    INSERT INTO arm.transiciones (venta_id, de, a, actor_id, rol)
    VALUES ('00000000-0000-0000-0000-000000000002', 'por_validar', 'rechazada', 'x', 'lider');
    RAISE EXCEPTION 'AssertionError: rechazar exige motivo' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO arm.transiciones (venta_id, de, a, actor_id, rol, motivo)
    VALUES ('00000000-0000-0000-0000-000000000002', 'publicada', 'anulada', 'x', 'lider', 'm');
    RAISE EXCEPTION 'AssertionError: solo el administrador anula' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

INSERT INTO agente.envios_programados (codigo_reserva, plantilla, fecha) VALUES ('R1', 'instrucciones_checkin', '2026-10-30');
INSERT INTO pms.propiedades (propiedad_id, tipo, nombre, zona_id, direccion, prompt_variante)
VALUES ('P1', 'glamping', 'Prueba', 'Z1', 'Dir', 'glamping');
DO $$ BEGIN
  BEGIN
    INSERT INTO agente.envios_programados (codigo_reserva, plantilla, fecha) VALUES ('R1', 'instrucciones_checkin', '2026-10-30');
    RAISE EXCEPTION 'AssertionError: un envío programado no se repite' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO pms.incidencias (incidencia_id, propiedad_id, categoria, prioridad, descripcion_token)
    VALUES ('I-2026-0001', 'P1', 'seguridad', 'baja', 'tok');
    RAISE EXCEPTION 'AssertionError: seguridad y acceso son críticas' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
END $$;

INSERT INTO comisiones.reglas (regla_id, version, tipo, valor, vigente_desde, creada_por)
VALUES ('r1', 1, 'porcentaje', 0.1000, '2026-01-01', 'prueba');
INSERT INTO comisiones.periodos (periodo_id) VALUES ('2026-10'), ('2026-11');
INSERT INTO comisiones.comisiones (comision_id, venta_id, regla_id, regla_version, monto, periodo_id, periodo_origen, estado)
VALUES ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000002', 'r1', 1, 10.00, '2026-10', '2026-10', 'fijada');
UPDATE comisiones.periodos SET cerrado_en = now(), cerrado_por = 'prueba' WHERE periodo_id = '2026-10';

DO $$ BEGIN
  BEGIN
    UPDATE comisiones.comisiones SET monto = 99 WHERE comision_id = '00000000-0000-0000-0000-000000000003';
    RAISE EXCEPTION 'AssertionError: un período cerrado es inmutable' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    UPDATE comisiones.reglas SET valor = 0.5 WHERE regla_id = 'r1';
    RAISE EXCEPTION 'AssertionError: una regla no se edita' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO comisiones.comisiones (venta_id, regla_id, regla_version, monto, periodo_id, periodo_origen, estado)
    VALUES ('00000000-0000-0000-0000-000000000002', 'r1', 1, 5.00, '2026-11', '2026-10', 'fijada');
    RAISE EXCEPTION 'AssertionError: una venta solo tiene una comisión base' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
END $$;
INSERT INTO comisiones.comisiones (venta_id, regla_id, regla_version, monto, periodo_id, periodo_origen, estado, ajuste_de, motivo)
VALUES ('00000000-0000-0000-0000-000000000002', 'r1', 1, -10.00, '2026-11', '2026-10', 'ajustada', '00000000-0000-0000-0000-000000000003', 'venta anulada');

INSERT INTO seguridad.audit_log (actor_token, rol, accion, resultado) VALUES ('tok', 'administrador', 'prueba', 'ok');
INSERT INTO conocimiento.documentos (documento_id, ruta, propiedad_id, tipo, dueno, revisado, version_hash)
VALUES ('00000000-0000-0000-0000-000000000004', 'a.md', 'global', 'faq', 'prueba', '2026-10-30', 'v1');
SET LOCAL app.propiedad_id = 'A';
SET LOCAL ROLE app_glamping;
INSERT INTO conocimiento.chunks (documento_id, propiedad_id, encabezado, texto, embedding, orden)
VALUES ('00000000-0000-0000-0000-000000000004', 'A', 'E', 'texto', array_fill(0.1::real, ARRAY[1024])::vector, 0);
SET LOCAL app.propiedad_id = 'B';
INSERT INTO conocimiento.chunks (documento_id, propiedad_id, encabezado, texto, embedding, orden)
VALUES ('00000000-0000-0000-0000-000000000004', 'B', 'E', 'texto', array_fill(0.1::real, ARRAY[1024])::vector, 0);
SET LOCAL app.propiedad_id = 'A';

DO $$
DECLARE
  filas integer;
BEGIN
  SELECT count(*) INTO filas FROM conocimiento.chunks WHERE propiedad_id = 'B';
  IF filas <> 0 THEN
    RAISE EXCEPTION 'AssertionError: fuga entre propiedades, % filas', filas USING ERRCODE = 'raise_exception';
  END IF;
  BEGIN
    UPDATE seguridad.audit_log SET resultado = 'alterado';
    RAISE EXCEPTION 'AssertionError: el audit log es solo INSERT' USING ERRCODE = 'raise_exception';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END $$;

ROLLBACK;
SELECT 'esquema verificado' AS resultado;
