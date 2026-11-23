# Aportes inéditos
`¤spec-glamping`

Hallazgos verificados de este proyecto que conviene no volver a descubrir.

### A-01. Sumas por tramos: redondear el acumulado, no cada diferencia

**Descripción:** si el monto de cada operación es `F(base + m) − F(base)`, la suma se cancela en cadena y da `F(S)` en cualquier orden. Eso solo se cumple exacto si se redondea `F` antes de restar. Redondear cada diferencia reintroduce la dependencia del orden, por centavos.

**Por qué es útil aquí:** las comisiones escalonadas deben cuadrar al centavo con la exportación. El mismo patrón sirve para cualquier cálculo acumulado por tramos.

**Verificabilidad:** con ventas 333.33, 700.10 y 566.57 y tramos de 5 % y 10 % desde 1000, en las 6 permutaciones: `{total con F redondeada} = {110.00}` y `{total redondeando cada diferencia} = {110.00, 110.01}`. Lo primero lo fija `tests/test_especificacion.py::test_el_escalon_marginal_no_depende_del_orden`.

**Soporte bibliográfico:** sin cita. No se verificó una fuente específica y es mejor omitirla que forzarla.

**Estado:** aplicado en `docs/spec/contratos/dominio.yaml` e `INV_COMISION_REPRODUCIBLE`. Sin concepto nuevo de gobernanza.

---

### A-02. Exclusión Estricta de Cotizaciones y Disponibilidad en Caché Semántico

**Tarea que lo Originó:** T-403 (Agente: Caché Semántico y Enrutamiento de Modelos, Chat `b8575328`).

**Mecanismo Descubierto:**
En asistentes conversacionales de hospitalidad, las consultas semánticamente equivalentes (por ejemplo, "¿tienen cabaña libre este fin de semana?") superan el umbral de similitud de embeddings ($\cos \theta \ge 0.95$). Si se cachea una respuesta generada que contenga cotizaciones o disponibilidad calculada dinámicamente, consultas posteriores en fechas distintas reciben datos obsoletos, provocando alucinaciones tarifarias y riesgo crítico de sobreventa. El caché semántico debe restringirse exclusivamente a respuestas informativas estáticas (políticas de check-in, servicios, normas, ubicación) y purgar de inmediato cualquier respuesta derivada de herramientas de calendario o cotización.

**Invariante o Regla de Verificación:**
- `INV_CACHE_SIN_PRECIOS`:
  `es_dinamico(respuesta) ⟹ cachear(respuesta) == False` (Verificado en `tests/agente/test_cache.py`).

**Soporte Bibliográfico:**
Solución fundamentada en el diseño del sistema; sin literatura externa aplicable.

**Evidencia en Código:**
Implementado y comprobado en `features/agente/cache_internal.py` y `features/agente/agente_service.py`.

**Alcance en el Modelo de Dominio:**
- `Comportamiento Preexistente`: Confinamiento del subsistema de caché en la sala `agente` sin filtración hacia el PMS.

---

### A-03. Desacoplamiento de Webhook Meta con Acuse Asíncrono e Idempotencia

**Tarea que lo Originó:** T-101 (Canal WhatsApp, Chat `1ecb2690`) y T-901 (Chat `f02f2244`).

**Mecanismo Descubierto:**
La API de WhatsApp Cloud de Meta impone un SLA estricto de respuesta HTTP 200 en menos de 2.000 ms; ante cualquier demora superior, Meta aborta la conexión e inicia reintentos automáticos concurrentes con backoff. En una arquitectura agéntica donde el pipeline de inferencia (RAG sobre `pgvector` + llamada a LLM) supera habitualmente los 2 s, procesar el mensaje de forma síncrona dentro del webhook desencadena una tormenta de mensajes duplicados que satura el motor conversacional. La compuerta debe desacoplarse: validar la firma `X-Hub-Signature-256`, persistir el evento en almacenamiento durable con clave `message_id`, devolver 200 OK inmediatamente (en < 500 ms) y procesar la inferencia en segundo plano con deduplicación exacta.

**Invariante o Regla de Verificación:**
- `INV_ACCION_IDEMPOTENTE`:
  `tiempo_respuesta(webhook) ≤ 2.0 s ∧ deduplicacion(message_id) == True` (Verificado en `tests/canal_whatsapp/test_webhook.py::test_webhook_duplicados_descartados`).

**Soporte Bibliográfico:**
* **Meta Platforms, Inc. (2024).** *«WhatsApp Business Platform Cloud API: Webhooks Best Practices»*: Requisito formal de acuse HTTP inmediato y deduplicación obligatoria ante reintentos de red.

**Evidencia en Código:**
Implementado y comprobado en `features/canal_whatsapp/canal_whatsapp_service.py` y `features/canal_whatsapp/webhook_internal.py`.

**Alcance en el Modelo de Dominio:**
- `Comportamiento Preexistente`: Garantía de entrega exactamente una vez en la capa de transporte del canal.

---

### A-04. Eliminación de Cold Starts en Webhooks de Mensajería con `min-instances: 1`

**Tarea que lo Originó:** T-901 (Plan de Despliegue en Google Cloud y ADR-0019, Chat `f02f2244`).

**Mecanismo Descubierto:**
El aprovisionamiento serverless tradicional con escalado a cero (Cloud Run, AWS Lambda o Render) sufre arranques en frío (*cold starts*) de 8 a 15 segundos en imágenes Python/FastAPI con dependencias multimodales. Al recibir un webhook de Meta tras un período de inactividad, el cold start supera el timeout de 2 s de Meta, provocando que los primeros mensajes de nuevos huéspedes fallen y el endpoint sea marcado como no saludable por Meta. Fijar `min-instances: 1` mantiene un contenedor tibio de manera ininterrumpida para atender el tráfico conversacional en tiempo real, absorbiendo el costo operativo con los créditos iniciales de Google Cloud ($300).

**Invariante o Regla de Verificación:**
- `RNF-14 / ADR-0019`:
  En la directiva de despliegue Cloud Run: `min_instances ≥ 1 ∧ max_instances ≤ 5`.

**Soporte Bibliográfico:**
Solución fundamentada en la arquitectura de infraestructura cloud; documentada en la guía oficial de escalado y rendimiento de Google Cloud Run.

**Evidencia en Código:**
Especificado en `docs/adr/ADR-0019-despliegue-google-cloud-y-gemini.md` y `docs/PRD.md §6 (RNF-14)`.

**Alcance en el Modelo de Dominio:**
- `Extensión Ontológica`: Incorporación de la topología cloud administrada en la gobernanza viva del sistema.

---

### A-05. Sincronía Bidireccional Mandatoria en Especificaciones Vivas ZERAG

**Tarea que lo Originó:** Refactorización integral del PRD v1.0.0 (Chat `f02f2244`).

**Mecanismo Descubierto:**
La suite de verificación estricta (`test_especificacion.py`) valida la identidad exacta de los prompts de implementación contra los requisitos declarados en `docs/PRD.md`. Cualquier actualización conceptual en el PRD que no vaya acompañada de la ejecución inmediata de `scripts/generar_prompts.py` y `scripts/generar_trazabilidad.py` provoca la falla del arnés por desactualización de prompts derivados (`AssertionError: docs/spec/prompts está desactualizado`). Asimismo, el motor de extracción de trazabilidad descarta silenciosamente los requisitos funcionales y no funcionales que no utilicen estrictamente los prefijos `- **` o `| **`.

**Invariante o Regla de Verificación:**
- `INV_ESPECIFICACION_VIVA`:
  `modificacion(docs/PRD.md) ⟹ ejecutar(generar_prompts.py) ∧ ejecutar(generar_trazabilidad.py) ∧ pytest(test_especificacion.py) == 0`.

**Soporte Bibliográfico:**
Solución fundamentada en el diseño del arnés de gobernanza del repositorio; sin literatura externa aplicable.

**Evidencia en Código:**
Implementado y comprobado en `scripts/generar_prompts.py`, `scripts/generar_trazabilidad.py` y `tests/test_especificacion.py`.

**Alcance en el Modelo de Dominio:**
- `Comportamiento Preexistente`: Consolidación del ciclo de verificación y compilación de la especificación viva.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
