# Informe para Antigravity: lo que Asistencia debe implementar antes de las pruebas manuales y de Playwright
`¤coordinacion`

**Fecha:** 2026-11-22 · **Emite:** ZERAG (coordinador) · **Destino:** el agente de Antigravity que trabaja en `Desktop/Asistencia`.
**Base leída:** rama feat/olas-1-12-y-modelos-gemini, 15 commits, último bloque de olas en `aa04eed`. Lectura de solo lectura: ZERAG no escribió ni ejecutó nada en Asistencia. Las rutas de Asistencia van en texto plano porque son de otro repositorio.

**Cómo usarlo.** Cada punto es una tarea para el TASKS.md de Asistencia (governance/tareas/TASKS.md), con su bloque `toml` y su árbitro, siguiendo las reglas que el propio proyecto ya aplica: propiedad exclusiva, máximo 4 tareas por ola, rutas compartidas solo para el coordinador. Las tareas de este informe tocan rutas compartidas (tests/integracion, tests/e2e, configuración de pruebas), así que son **olas del coordinador**, no de sala. Marca lo **medido** y lo **inferido** igual que aquí.

## Lo que Asistencia hace bien (no se toca)

- Matriz de propiedad por sala con su árbitro (tests/test_tareas_sin_colision.py).
- Un brief por tarea generado desde la especificación, con `--check` (scripts/generar_prompts.py).
- Estructura ADPA con árbitro (tests/test_estructura_adpa.py).
- Arnés único (scripts/arnes_glamping.py) y CI con Postgres y pgvector reales.

ZERAG adopta estos procesos (TICKETS 315 a 318). Asistencia no tiene que cambiarlos.

## Tareas, en orden

### 1. Fijar el punto de partida (antes de nada)

- **Medido:** hay cambios sin commitear (APORTES_INEDITOS.md, FUENTES_Y_BIBLIOGRAFIA.md), sin seguimiento .agents/estado/ y un respaldo AGENTS.md.zerag-*.bak.
- **Hacer:** commitear o descartar cada cambio con su motivo; no versionar .agents/estado/ ni el respaldo (añadirlos a .gitignore); etiquetar el commit resultante como línea base del backend (por ejemplo `backend-sellado`).
- **Por qué:** las 12 olas están en un solo commit; sin una etiqueta no hay contra qué comparar una regresión que aparezca en las pruebas manuales.
- **Hecho si:** `git status` limpio y la etiqueta existe.

### 2. Verificar qué olas se sellaron contra servicios reales

- **Inferido, no comprobado:** las olas 10 a 12 (Meta, LLM, CRM, producción) figuran «selladas», y no consta si corrieron contra los servicios reales o contra dobles.
- **Hacer:** por cada tarea de esas olas, anotar en su bloque si su árbitro corrió contra el servicio real, contra un sandbox del proveedor o contra un doble, con el comando y la fecha. Lo que solo corrió contra un doble vuelve a estado «pendiente de integración real».
- **Hecho si:** ninguna tarea de las olas 9 a 12 queda «sellada» sin decir contra qué corrió su árbitro.

### 3. Pruebas de contrato: el doble de cada sala se comporta como su compuerta real

- **Medido:** cada sala se probó contra sus propios dobles (tests/<sala>/dobles.py). **Inferido:** un desacuerdo entre un doble y la compuerta real solo lo detectaría tests/integracion/.
- **Hacer:** una prueba parametrizada que ejecute el mismo conjunto de casos contra el doble y contra la implementación real de cada `_service.py` consumido por otra sala, y exija el mismo resultado.
- **Hecho si:** cada compuerta consumida por otra sala tiene su prueba de contrato, y un doble alterado a propósito la hace fallar (mutante muerto).

### 4. Congelar las firmas de las compuertas

- **Medido:** la regla 4 de TASKS.md §1 dice que las firmas de cada `_service.py` solo crecen; ningún test lo comprueba.
- **Hacer:** un test que extraiga las firmas públicas de cada `_service.py` y las compare con un archivo de referencia versionado: añadir pasa; quitar o cambiar falla salvo con una entrada de «cambio de contrato» con motivo.
- **Hecho si:** quitar una función de una compuerta en una rama de prueba hace fallar el test.

### 5. Comprobar la regla de olas que hoy solo está escrita

- **Medido:** la cabecera de TASKS.md dice que la ola de una dependencia es menor que la de la tarea; tests/test_tareas_sin_colision.py no lo comprueba.
- **Hacer:** añadir esa comprobación al test existente.
- **Hecho si:** una tarea sintética que depende de otra de su misma ola o posterior hace fallar el test.

### 6. Medir la cobertura del backend

- **Medido:** 116 archivos de prueba frente a 111 módulos en features/, sin ninguna medición de cobertura.
- **Hacer:** añadir pytest-cov al arnés y publicar la cobertura por sala en el veredicto; fijar como piso la cobertura medida hoy y hacer que el arnés falle si baja.
- **Hecho si:** el veredicto del arnés trae la cobertura por sala y una prueba eliminada a propósito la hace bajar y fallar.

### 7. Plan de pruebas manuales

- **Hacer:** un documento con un caso por flujo de usuario (panel, PWA móvil, web pública, y los flujos con Meta, LLM y CRM): precondición, pasos, resultado esperado y un espacio para el resultado observado, fecha y quién lo ejecutó. Cada falla encontrada se registra como tarea con su prueba automática, no se corrige en el momento.
- **Hecho si:** el plan existe, cubre todos los flujos de la especificación (docs/spec/TRAZABILIDAD.md) y cada caso está enlazado a su requisito.

### 8. Playwright

- **Medido:** tests/e2e/ usa el `TestClient` de FastAPI; no hay Playwright en el repositorio, así que la interfaz nunca se ha ejercitado.
- **Hacer, en este orden:**
  1. Un humo de 3 a 5 flujos críticos, con 0 reintentos y detención al primer fallo, que corre antes de la suite completa.
  2. Después, un caso de Playwright por cada caso manual del punto 7 que se pueda automatizar.
  3. Base de datos propia por ejecución, sin el `.env` del desarrollador (el entorno del árbitro no hereda credenciales).
  4. Un flujo intermitente se arregla o se retira; nunca se reintenta para que pase.
- **Hecho si:** el humo corre en el arnés y en el CI; un fallo del humo impide correr la suite; y cada flujo del punto 7 tiene su caso o una razón escrita de por qué no se automatiza.

### 9. Corregir las citas de árbitros que el cliente no tiene

- **Medido por ZERAG (TICKET-284):** el CLAUDE.md de Asistencia cita como árbitros utf8_linter, huellas_linter, ip_safety_linter, adpa_linter, living_artifacts_linter y ui_sanitizer_linter, que no existen en el proyecto; .agents/estado/evidencia.log dice «linters no disponibles: No module named 'mcp_server'».
- **Hacer:** que cada «Árbitro:» del CLAUDE.md nombre algo que existe en Asistencia (sus tests, su arnés, su CI), o que la norma pase a método.
- **Hecho si:** el comprobador de ZERAG (verificadores/check_arbitros_cliente.py, ejecutado desde ZERAG contra Asistencia) sale 0.

### 10. Registrar las fallas que aparezcan

- **Medido:** governance/artefactos/data/PROBLEMS.json está vacío desde el 2026-10-30.
- **Hacer:** cada falla de las pruebas manuales o de Playwright se registra con causa raíz y estado, y la tarea que la corrige lo cita.

## Orden y paralelismo

Los puntos 1 y 2 van primero y en serie: fijan contra qué se mide. Después pueden ir en paralelo, en olas de hasta 4: (3, 4, 5, 6), luego (7, 9), luego 8. El 10 aplica desde el primer día de pruebas.

## Revisión de la entrega (2026-11-22, commits `c7fcb00` y `cc7185e`)

**Medido por ZERAG:** las 10 tareas tienen entrega. Las pruebas nuevas (firmas, contratos, cobertura, colisiones y humo de Playwright) pasan: 26 casos, ninguno omitido, con Chromium real. Lo mejor de la entrega es la tarea 2: seis tareas que figuraban selladas volvieron a «pendiente» con su entorno, fecha y comando escritos.

**Tres correcciones, en este orden** (tareas del coordinador, una por commit):

### C1. Revertir el `except` añadido a app_core/main.py

- **Medido:** `cc7185e` añadió un `try/except Exception` alrededor de `montar_panel_y_crm` que, si falla, solo registra «error_montaje_panel_en_main» y deja la app arrancando sin panel ni CRM. No lo pedía ninguna tarea y es código de producción dentro de una tanda de QA.
- **Hacer:** quitar el `try/except`: si el panel no se puede montar, la app no arranca y el error sale con su traza. Si el import es opcional por una razón real, declararla en la especificación, no en un `except`.
- **Hecho si:** una prueba que fuerza un fallo en `montar_panel_y_crm` hace fallar `crear_app`, y el humo del panel sigue en verde.

### C2. Profundizar las pruebas de contrato

- **Medido:** tests/test_contratos_compuertas_vs_dobles.py cubre unas cinco compuertas y casi todo lo compara con `hasattr` e `isinstance`. La tarea 3 pedía **cada** compuerta consumida por otra sala y un mutante muerto.
- **Hacer:** derivar la lista de compuertas de FIRMAS_COMPUERTAS.json (no a mano); por cada una, el mismo conjunto de casos contra el doble y contra la real, comparando valores y errores, no solo tipos; y una prueba con un doble alterado a propósito que debe fallar.
- **Hecho si:** toda compuerta del archivo de firmas que otra sala importa tiene su prueba de contrato, y el doble alterado la hace fallar.

### C3. Revisar el árbitro de «Escritura conforme»

- **Inferido, no comprobado:** el CLAUDE.md nombra ahora `scripts/verificar_secretos.py` como árbitro de «UTF-8 sin BOM, huellas consolidadas, sin reclamos de IP ajena». Por su nombre, comprueba secretos, no esas tres cosas.
- **Hacer:** comprobar qué verifica de verdad. Si no cubre las tres, nombrar el árbitro que sí lo hace (el paso UTF-8 del arnés, por ejemplo) o pasar a método la parte que no tiene árbitro.
- **Hecho si:** cada cosa que promete la norma tiene una comprobación que falla en un caso sintético.

**Para próximas tandas:** cada tarea en su propio commit, para poder revisarla y revertirla por separado; y ninguna tarea de QA cambia código de producción.

## Lo que ZERAG no puede afirmar

- Que no hubo colisiones entre agentes: con un solo commit y sin ramas no se puede medir; solo que el diseño las impedía.
- Qué corrió contra servicios reales en las olas 10 a 12.
- La cobertura real del backend.

---

© 2026 Juan Carlos Proaño. All rights reserved.
