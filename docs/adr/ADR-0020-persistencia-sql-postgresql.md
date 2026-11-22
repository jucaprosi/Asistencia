# ADR-0020 — Persistencia real en PostgreSQL con una sala adaptadora común
`¤persistencia-sql`

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado** (implementación pedida por el propietario, 2026-11-22) |
| Fecha | 2026-11-22 |
| Decisores | Propietario del proyecto, CTO |
| Complementa | [ADR-0019](ADR-0019-despliegue-google-cloud-y-gemini.md) (Cloud SQL) |

## Contexto
Las salas persistían en SQLite en memoria. En Cloud Run cada instancia perdía su estado al reiniciar y dos instancias no compartían datos, así que no se cumplían `INV_INGESTA_DURABLE` ni la unicidad de tickets. El esquema canónico `docs/spec/esquema.sql` existía, pero ningún repositorio lo usaba.

## Decisión
1. Nueva sala `features/persistencia_sql/` con la compuerta `persistencia_sql_service.py`. `Conexion` expone la API de `sqlite3` que ya usan las salas. Con `DATABASE_URL=postgresql://…` delega en psycopg 3:
   - convierte `?` a `%s`;
   - aplica `search_path` por esquema;
   - confirma las lecturas cuando no hay una transacción abierta;
   - traduce los errores a sus equivalentes de `sqlite3`.
   
   Sin URL sigue en SQLite y emula los esquemas con `ATTACH`.
2. En PostgreSQL las salas no ejecutan su DDL de SQLite. El esquema lo aplica `scripts/migrar_db.py`, que es idempotente: registra cada archivo en `public.migraciones_aplicadas` con su SHA-256 y aplica `esquema.sql` como línea base y luego `docs/spec/migraciones/*.sql`.
3. El SQL de las salas se reescribe a un dialecto común:
   - `ON CONFLICT` en lugar de `INSERT OR IGNORE/REPLACE`;
   - literales `TRUE`/`FALSE`;
   - `CAST(? AS TEXT)` en parámetros opcionales;
   - rangos de fechas en lugar de `strftime`/`LIKE`;
   - `UPDATE … RETURNING` para contadores atómicos.
4. Las columnas `uuid` del esquema pasan a `text`. Las salas generan identificadores legibles que no son UUID (`wamid.*`, `GI-2026-0001`), y forzar `uuid` habría exigido reescribir los identificadores de dominio.
5. El audit log es de solo inserción también para el dueño de la tabla, mediante un trigger (`INV_AUDIT_APPEND_ONLY`).

## Consecuencias
- La suite corre igual en SQLite y también contra PostgreSQL real: `GLAMPING_SUITE_POSTGRES=<url>` trunca las tablas antes de cada prueba.
- Cada instancia abre alrededor de 16 conexiones (una por repositorio). `db-f1-micro` admite pocas conexiones, así que hace falta un pool o una instancia mayor antes de escalar.
- `canal.medios.mensaje_id` ahora admite nulo: un medio puede descargarse sin un mensaje registrado, en lugar de inventar un identificador.
- Revertir es posible: sin `DATABASE_URL` el sistema vuelve a SQLite sin cambios de código.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
