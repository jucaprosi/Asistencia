# ADR-0023 — Migraciones por sala y línea base congelada
`¤persistencia-sql`

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado** (el propietario ordenó empezar por las migraciones, 2026-11-24) |
| Fecha | 2026-11-24 |
| Decisores | Propietario del proyecto, CTO |
| Revisores | Arquitecto ADPA G.I. (dictamen P3 + M0); asesoría externa de CTO Evydentia (convención CI-28 adaptada a SQL plano) |
| Complementa | [ADR-0020](ADR-0020-persistencia-sql-postgresql.md) |

## Contexto
`scripts/migrar_db.py` aplica `docs/spec/esquema.sql` como línea base (registrada como `000_linea_base.sql`) y después `docs/spec/migraciones/NNN_*.sql`. Cada archivo se registra con su SHA-256. Hay dos problemas:

1. **M0: la CI no prueba las migraciones.** La CI aplica `esquema.sql` directo con `psql`, como esquema vivo, y nunca aplica las migraciones: la `001` no se ha probado nunca en CI. Además, si `esquema.sql` cambia, cualquier base ya migrada falla con «ya aplicada cambió de contenido».
2. **Choque entre ramas.** Dos ramas que crean una migración con el mismo número (`002_…`) chocan al fusionarse, o se aplican en un orden distinto en cada base.

## Decisión
1. **Línea base congelada.** `docs/spec/esquema.sql` no se edita más; todo cambio de esquema va en una migración nueva. Ninguna migración ya fusionada en `main` se edita: se agrega otra.
2. **La CI aplica como producción.** Ejecuta `python scripts/migrar_db.py` (línea base más migraciones) contra el PostgreSQL del servicio y después `verificacion_esquema.sql`.
3. **Nombres.** Formato `AAAAMMDDHHMM_<sala>_<slug>.sql`, donde `<sala>` es el nombre de la sala ADPA (no el del schema SQL) y el orden de aplicación es el orden por nombre. `001_alinear_esquema_con_codigo.sql` queda en una lista cerrada de archivos heredados y no se renombra, porque cambiaría su registro en `public.migraciones_aplicadas`. Al ordenar por nombre, `001` queda antes que `2026…`.
4. **Confinamiento.**
   - Una migración solo escribe (DDL o DML: `CREATE/ALTER/DROP`, `ON <schema>.<tabla>`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`) en los schemas de su sala (mapa sala→schema en el árbitro, alineado por prueba con las salas de `features/` y con los `CREATE SCHEMA` de la línea base).
   - `-- depende: <archivo>` ordena y permite *referenciar* el schema de la sala dependida (`REFERENCES`, lecturas), nunca escribir en él. Si hay que cambiar una tabla ajena, la migración lleva el prefijo de la sala dueña.
   - Una sala sin schema (p. ej. `herramientas_glamping`) no tiene migraciones; `public` es solo para la infraestructura de persistencia.
   - Prohibidos `search_path`/`set_config` y el SQL dinámico (`DO`, `EXECUTE` salvo `EXECUTE FUNCTION` de un trigger); este último requiere un ADR. Solo `persistencia_sql` crea, altera o elimina schemas (o con ADR); `GRANT`/`REVOKE` solo desde `seguridad` o `persistencia_sql`. Cuentan como escritura también `SELECT/MERGE … INTO`, `COPY`, `ALTER INDEX` y `COMMENT ON`.
   - La detección es léxica y falla hacia el lado seguro: un solo recorrido quita comentarios y literales `'…'` (un `--` dentro de un literal no corta nada) y las comillas dobles; una mención dudosa fuera de un literal hace fallar la migración.
   - `migrar_db.py` comprueba que cada dependencia exista y se aplique antes, con la misma función de lectura que el árbitro.
5. **Árbitro** (`scripts/verificar_migraciones.py` y `tests/persistencia_sql/test_migraciones_ordenadas.py`, prueba del núcleo). Corre en el arnés local y en CI, y falla si:
   - un nombre no cumple el formato, la sala no existe o la marca no es una fecha real o está más de un día en el futuro;
   - dos archivos comparten la marca de tiempo;
   - una migración nueva se ordena antes que la última que ya está en la rama base (`origin/main`): quien fusiona segundo renombra la suya una vez;
   - cambió el contenido de `esquema.sql` o de una migración que ya está en la rama base;
   - una migración toca un schema ajeno sin declararlo, o declara una dependencia inexistente o posterior.
6. **Solo `main` aplica migraciones a bases compartidas** (staging y producción). Una migración de rama aplicada en staging y renombrada después por el árbitro rompería el registro.

## Consecuencias
- Desde ahora, cualquier cambio de esquema es una migración nueva con el nombre del formato.
- Antes de aplicar en Cloud SQL, devops debe confirmar con `SELECT nombre, sha256 FROM public.migraciones_aplicadas` qué tiene registrado cada base real.
- La comprobación contra la rama base necesita la base disponible. En local, si falta, el árbitro omite solo esas dos reglas y lo avisa (la prueba del repositorio real se marca *skip*). En CI corre primero con `--exigir-base` y falla si falta: compara contra la rama destino en un PR y contra el commit anterior en un push a `main`. Tras un force-push a `main` ese commit puede no estar en el clon: el job falla, a propósito (lado seguro).

## Árbitro
`tests/persistencia_sql/test_migraciones_ordenadas.py` (casos sintéticos para cada regla, más el repositorio real) y el paso de CI «Aplicar migraciones y verificar el esquema en PostgreSQL real».

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
