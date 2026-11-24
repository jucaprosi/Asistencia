# ADR-0021 — Inferencia Gemini en Vertex AI con ADC, región us, sala inferencia y falla cerrada
`¤inferencia` `¤agente-enrutador`

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado** (decisiones del propietario, 2026-11-23). Opción 1 elegida por el propietario (2026-11-24) con base en el dictamen ADPA del Arquitecto. El tráfico real con huéspedes queda bloqueado por ADR-0012 |
| Fecha | 2026-11-23 |
| Decisores | Propietario del proyecto, CTO |
| Revisores | Tech Lead G.I., Arquitecto ADPA G.I., QA G.I., UX/UI G.I.; asesoría externa de CTO Evydentia (plataforma LOPDP 360) |
| Sustituye parcialmente | [ADR-0019](ADR-0019-despliegue-google-cloud-y-gemini.md): el respaldo a Claude, la ubicación del conector y la extracción multimodal de comprobantes (el modelo ya no recibe imágenes de comprobantes) |
| Depende de | [ADR-0012](ADR-0012-residencia-datos.md) (residencia y transferencia internacional) |

## Contexto
El agente aún no llama a un modelo real: `ClienteModelo` responde con un texto simulado cuando no tiene conector (falla abierta). La configuración tiene valores de respaldo (`us-central1`, `claude-opus-5-5`, API keys anidadas), y en `us-central1` no está disponible `gemini-3.8-flash`. La revisión del equipo encontró además siete bloqueantes en el código actual:
1. respuesta simulada sin conector;
2. valores por defecto vivos y nombres de variables incoherentes;
3. el timeout no corta la llamada;
4. el turno del modelo pierde las `function_call` y la `thought_signature`;
5. los resultados de herramientas usan un rol `tool` que Gemini no acepta;
6. el modelo enrutado no llega al proveedor;
7. el respaldo a Claude contradice esta decisión.

## Opciones consideradas
1. **Sala nueva `features/inferencia/`, consumida por `agente` y por el ARM (elegida): unificación por compuerta canónica (ADPA §5 fase 2, §3).**
   - ADPA §5 no prohíbe unificar entre salas: prohíbe compartir código sin pasar por una compuerta. Unificar Vertex detrás de `inferencia_service.py` es el mecanismo que prescribe la fase de sellado.
   - `inferencia` es una sala de dominio con identidad propia (modelo, región, transferencia LOPDP), igual que `seguridad` es dueña de la tokenización (§2.4).
   - La contención de fallos se conserva (§1): una caída se contiene con la falla cerrada y con la cortesía y el handoff en `agente`.
   - El ARM consume solo texto: los comprobantes en imagen no van al modelo (Decisión 12). La extracción de ventas en texto también necesita la lista blanca y la región.
2. **Cliente Vertex duplicado en `agente` y en `arm_jarvis`, cada uno con su lista blanca. Descartada:** dos listas blancas, dos mapas de región y dos avisos LOPDP que pueden divergir sin que nada lo detecte, con un riesgo legal en esa divergencia.
3. Un archivo `vertex_internal.py` dentro de `agente`. Deja deuda cuando el ARM necesite el modelo.
4. AI Studio con API key. Descartada: agrega un secreto y no permite fijar la región.

ADR-0021 se justifica por ADPA §7.1 (sala nueva); no invoca §7.4.

## Decisión
1. **Sala `inferencia` y frontera con `agente`.**
   - `inferencia_service.py` es dueña de: `MODELOS_PERMITIDOS` y el mapa región→ubicación; la tabla de precios y el costo por `usage_metadata`; el tope diario compartido por `agente` y ARM; la traducción al formato de Gemini; el timeout por llamada; la falla cerrada; `estado()` (disponible, motivo neutro, región y ubicación) e `inyectar_cliente_de_prueba()`. Su configuración vive en `config_inferencia.yaml`; ningún modelo ni precio queda en `config_agente.yaml` ni en `cliente_modelo_internal.py`.
   - La compuerta devuelve tipos propios, definidos en `features/inferencia/tipos.py`: texto, llamadas a herramientas, uso y un `contexto_turno` opaco y serializable (dict o bytes) que `agente` guarda y devuelve sin inspeccionarlo. Ningún tipo de `google-genai` sale de la sala (ADPA §3); `import google.genai` solo aparece en `features/inferencia/`.
   - `agente` se queda con el presupuesto del turno (pasa el plazo restante a la compuerta), el bucle neutro (`LlamadaHerramienta`, `ResultadoHerramienta`), la memoria y la decisión de cortesía o handoff. `ClienteModelo` queda como adaptador del turno; su `ThreadPoolExecutor`, que no corta la llamada, desaparece.
   - `app_core/contenedor.py` construye `InferenciaService` y lo inyecta en `AgenteService` y en el servicio del ARM, como hoy inyecta `seguridad` (ADPA §3). Ni `agente` ni `arm_jarvis` instancian ni configuran `inferencia`.
   - Los prompts y esquemas de extracción del ARM siguen siendo del ARM: `inferencia` solo transporta.
   - `inferencia` no persiste nada: trazas y costo van por la compuerta de `observabilidad`, y la cuota diaria se lee desde allí. Entra en `SCHEMAS_POR_SALA` sin schema (ADR-0023); tablas propias requerirían ADR (§7.3).
2. **Proveedor único: Gemini en Vertex AI. Se elimina Claude.** No hay respaldo automático a otro proveedor en tiempo de ejecución. Cambiar de proveedor es un cambio explícito de configuración y despliegue.
3. **Autenticación ADC** con la cuenta de servicio de Cloud Run (`roles/aiplatform.user`) y `google-genai==2.34.0` en modo `vertexai=True`, con import perezoso; la versión se confirma en PyPI y queda fijada en `pyproject.toml` con su hash en el lock. Sin API key. `GOOGLE_API_KEY` y `GEMINI_API_KEY` no deben existir en el entorno, y se comprueba al arrancar.
4. **Configuración sin valores por defecto:** `GOOGLE_CLOUD_PROJECT` y `VERTEX_LOCATION=us`. Si falta alguna, la región no está en el mapa o el modelo no está en la lista blanca, no se genera respuesta. Cloud Run, Cloud SQL y Artifact Registry siguen en `us-central1`; solo Vertex va a `us`.
5. **Modelos:** `gemini-3.8-flash` (principal) y `gemini-3.5-flash-lite` (económico). Ambos quedan fijados: la prueba de humo real del 2026-11-24 (Antigravity, endpoint `aiplatform.us.rep.googleapis.com`, `locations/us`) devolvió HTTP 200 con `modelVersion` `gemini-3.8-flash` y `gemini-3.5-flash-lite`. En la misma prueba, `gemini-2.0-flash` y `gemini-1.5-flash` devolvieron 404 y no se usan. El propietario confirma que todo el procesamiento queda dentro de EE. UU. (multirregión `us`, nunca `global`), base para la configuración LOPDP.
6. **Tiempo:** presupuesto único de 45 s por turno (reemplaza los 30 s de RF-AG-05(a) y de `config_agente.yaml`, que se actualizan en el mismo cambio que la implementación), que incluye las iteraciones de herramientas, un reintento ante 5xx o 429 con backoff y jitter, y `HttpOptions.timeout` en milisegundos. 400, 403 y 404 no se reintentan.
7. **Bucle de herramientas** (la traducción es de `inferencia`; `agente` solo ve tipos neutros):
   - el `contexto_turno` opaco, que conserva `function_call` y `thought_signature`, se reinyecta intacto;
   - las `function_response` de una misma iteración van en un único turno `user`, en orden y con su id;
   - `parameters_json_schema`;
   - AFC desactivado;
   - `system_instruction`.
8. **Respuestas no utilizables** (bloqueo de safety, `MAX_TOKENS`, `MALFORMED_FUNCTION_CALL`, respuesta vacía): no se entrega texto parcial. El huésped recibe la cortesía. El bloqueo por safety solo deja traza y métrica, sin alerta.
9. **Costo:** `usage_metadata` (prompt, candidates y thoughts como salida), calculado en `inferencia`. El tope diario, único para `agente` y ARM, se aplica en `inferencia` antes de llamar y cuenta también el reintento.
10. **Si el modelo no está disponible:**
    - el huésped recibe una sola vez por conversación: «Gracias por escribirnos. Una persona de nuestro equipo va a continuar tu atención por este mismo chat en breve.»;
    - la conversación entra a la bandeja de handoff de su zona;
    - se emite una alerta deduplicada al administrador (`observabilidad.emitir_alerta`, con su plantilla de Meta; su aprobación externa tarda días y es requisito del paso 5 del Orden).
11. **PII:** sigue siendo dueña la sala `seguridad` (`tokenizar`/`rehidratar`), también para las salidas de herramientas. La sala `inferencia` solo hace una verificación defensiva, con el verificador de `seguridad` que `app_core` construye una vez y le inyecta.
12. **Transferencia internacional.** El propietario acepta el criterio de CTO Evydentia (plataforma LOPDP 360), documentado en ADR-0012: informar no basta. Se aplican cuatro medidas:
    - Aviso fijo antes de que el primer mensaje llegue al modelo, una vez por huésped. Dueña: la sala `seguridad` (`obtener_aviso_privacidad(pais, region)`, con texto, versión y hash). `app_core` obtiene país y región de `inferencia.estado()` y los pasa a `seguridad`, que no conoce a `inferencia` (ADPA §3; una prueba de estructura confirma que `seguridad` no importa `inferencia`). Indica responsable, finalidad, base, destinatario (Google como encargado), país y región leídos de `inferencia.estado()`, plazo, derechos y la alternativa humana. No califica la transferencia («adecuada», «conforme»).
    - Registro por conversación con versión y hash del aviso, fecha, canal y respuesta del huésped, en el schema `seguridad`, junto a `tiene_consentimiento` y `revocar_consentimiento`.
    - Base contractual (art. 7) y garantía del art. 57: contrato de encargo y Cloud Data Processing Addendum archivados.
    - Si el huésped rechaza o escribe «persona», todo su caso pasa a atención humana.

    Los comprobantes de pago en imagen no se envían al modelo. El tráfico real espera los pendientes legales de ADR-0012.

## Consecuencias
- Se retiran `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `clave_api` y los valores por defecto de `config_agente.yaml`, `.env.example`, `cloudrun.yaml` y `playwright.config.ts`.
- `cloudbuild.yaml` despliega con:
  - `--service-account=sa-cloud-run@…`;
  - `--update-env-vars` (nunca `--set-env-vars`);
  - `--no-cpu-throttling`;
  - `--execution-environment=gen2`.

  `aiplatform.googleapis.com` se habilita en la configuración inicial del proyecto.
- El panel muestra `estado_asistente {disponible, motivo, desde, derivadas}` en `/inicio` y `/admin/salud` (a cargo de UX/UI).
- Invariantes nuevos: `INV_MODELO_FALLA_CERRADA` e `INV_MODELO_EN_LISTA_BLANCA`. El árbitro de este último exige además que `google.genai` solo aparezca en `features/inferencia/` y que no queden `claude-*` ni `anthropic` en configuración ni código. Se amplía `INV_PII_FUERA_DEL_MODELO`.
- PRD:
  - RF-AG-05 pasa a hablar de «caída del modelo»;
  - se quita Claude de la tabla de proveedores;
  - nuevos RF-INF-01 a RF-INF-03;
  - fila de la sala en el catálogo.

## Árbitro
- Bloqueantes 1 a 7: cada uno con su prueba en rojo, en un commit anterior al del arreglo.
  - 1, 2 y 7 se prueban contra `agente` tal como está hoy (el 7 con la prueba de `INV_MODELO_EN_LISTA_BLANCA`).
  - 3 a 6 se escriben como contratos de la compuerta `inferencia` (con `inyectar_cliente_de_prueba`) sobre un esqueleto de `inferencia_service.py` que lanza `NotImplementedError`: fallan por aserción, no por `ImportError`, y sobreviven al arreglo sin reescribirse.
- El commit que crea `features/inferencia/` la agrega a `SCHEMAS_POR_SALA` y lleva `COBERTURA_BASE.json` y `test_cobertura_arnes` a 15 salas.
- `tests/inferencia/`: contratos de QA (a–i, fc, s, t, r, c, w, e) y el contrato del doble frente al conector real.
- Arnés en Exit 0 con veredicto APROBADO, y el piso de cobertura de `agente` no baja; `inferencia` ≥ 90 %.
- Humo real fuera del CI (`VERTEX_HUMO=1`), que corre el propietario con ADC. Por cada modelo debe dar:
  - texto con `finish_reason` STOP y tokens mayores que cero;
  - una ida y vuelta con una herramienta de solo lectura.

  La evidencia queda en `governance/artefactos/data/humo_vertex.json`, sin prompts ni respuestas.

## Orden
1. Este ADR.
2. Pruebas en rojo de los bloqueantes.
3. Corrección de los bloqueantes.
4. Sala `inferencia` y conector.
5. Migración de variables e infraestructura, y plantilla de alerta aprobada por Meta.
6. Humo real.
7. Tráfico real, solo después de aceptar ADR-0012.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
