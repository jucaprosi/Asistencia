-- ¤inferencia
-- depende: 202611250145_observabilidad_cuota_inferencia.sql
-- K1 del ADR-0021: la aplicación reserva y concilia la cuota; no la borra.
-- © 2026 Juan Carlos Proaño. Todos los derechos reservados.

GRANT SELECT, INSERT, UPDATE ON observabilidad.cuota_inferencia TO app_glamping;
