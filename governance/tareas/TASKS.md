# TASKS — Tareas ejecutables por sala ADPA
`¤tareas-glamping` `¤coordinacion`

> **Qué es este archivo.** La lista canónica de tareas ejecutables del proyecto, optimizada bajo **ADPA** y **Spec-Driven Development (SDD)** en **tandas paralelas de 4 tareas con 0 archivos en común** y ordenada en dos etapas estrictas:
> 1. **Etapa I (Olas 1 a 8 — Diseño Documental, Contratos y Desarrollo Clean-Room en Salas):** 32 tareas de sala agrupadas en **8 tandas exactas de 4 tareas en paralelo**. Cada tarea actualiza primero el diseño de su módulo (`docs/modulos/<sala>.md`), implementa esquemas, contratos, lógica privada (`*_internal.py`) y compuerta (`*_service.py`), y se verifica en local con dobles propios (`tests/<sala>/dobles.py` y `Fake*`) sin depender de plataformas de nube.
> 2. **Etapa II (Olas 9 a 12 — Orquestación en Pasillo Central, Comprobación con Plataformas de Nube y Despliegue en Producción):** Una vez selladas las salas en local, se ejecuta el ensamblaje modular en `app_core` (Ola 9) seguido de las tandas de comprobación en vivo contra plataformas de nube (Meta WhatsApp Cloud API, Anthropic Claude API, PostgreSQL/pgvector con RLS y corpus real, proveedor CRM en nube, pruebas de carga, servidor de producción y Web Push HTTPS/VAPID en Olas 10 a 12).
>
> **Árbitro de este archivo:** `tests/test_tareas_sin_colision.py` lee los bloques `toml` de cada tarea y falla si una tanda supera las 4 tareas en paralelo, si dos tareas de la misma ola comparten cualquier ruta (cero colisiones absolutas), si una dependencia no pertenece a una ola anterior (`ola(dep) < ola(tarea)`), o si una tarea de sala invade rutas del coordinador.

## 1. Reglas de independencia (ADPA aplicado al trabajo en paralelo)

1. **Tandas de máximo 4 tareas con 0 archivos en común.** Cada tarea declara en `propiedad` las rutas exclusivas que puede escribir. Dentro de una misma ola (tanda), dos tareas nunca comparten ruta ni sala.
2. **Diseño y desarrollo Clean-Room antes que comprobación en nube.** Todas las tareas de las Olas 1 a 8 documentan su módulo (`docs/modulos/<sala>.md`), implementan su contrato y pasan su árbitro local con dobles/fakes sin requerir credenciales externas. Las pruebas con plataformas de nube y despliegues reales viven exclusivamente en las Olas 10 a 12.
3. **Toda tarea de sala posee siempre** `features/<sala>/**`, `tests/<sala>/**` y `docs/modulos/<sala>.md`, más los recursos asignados a esa sala (evals, prompts, scripts) en la tabla §2.
4. **Contratos congelados.** Las firmas de las compuertas `*_service.py` quedaron fijadas en la fase 0 (TASK-000). Una tarea de sala puede **añadir** métodos a su propia compuerta, nunca cambiar ni quitar los existentes.
5. **Dobles de prueba propios.** Las pruebas de una sala no importan los `Fake*` de otra sala: cada sala escribe sus propios dobles en `tests/<sala>/dobles.py` contra la interfaz de la compuerta (DPD: duplicar para delegar). Los `Fake*` de ejecución (`fake_internal.py`) viven en la sala dueña y los usa `app_core` en beta.
6. **Rutas reservadas al coordinador** (solo tareas `T-x10`, `T-x11` y de infraestructura en Olas 9 a 12): `app_core/**`, `compose.yaml`, `compose.production.yaml`, `Dockerfile`, `infra/**`, `.env.example`, `pyproject.toml`, `.github/**`, `scripts/arnes_glamping.py`, `scripts/verificar_secretos.py`, `tests/conftest.py`, `tests/test_*.py` (raíz), `tests/integracion/**`, `tests/app_core/**`, `governance/**`, `docs/PRD.md`, `docs/spec/**`, `docs/ARQUITECTURA.md`, `docs/FRONTEND.md`, `docs/adr/**`, `README.md`, `CLAUDE.md`.
7. **Una tarea abierta por sala a la vez.** Las tareas sobre la misma sala están ubicadas en olas distintas y encadenadas secuencialmente por `depende_de` (`ola(dep) < ola(tarea)`).
8. **Sellado individual.** Cada tarea termina con `ejecutar_arnes_glamping` en Exit Code 0 sobre todo el repositorio, huellas `¦` consolidadas a `¤` y su bloque de este archivo en `estado = "sellada"`.
9. **Integración y nube son trabajo del coordinador (Olas 9 a 12).** Las pruebas que levantan varias salas juntas o verifican plataformas de nube viven en `tests/integracion/` y pertenecen a las Olas 10 a 12; una tarea de sala no las escribe.
10. **Evaluaciones.** Cada sala con suite expone `evaluar(...)` en su compuerta y es dueña de su archivo de casos en `evals/`. `scripts/run_evals.py` (sala `observabilidad`) solo despacha a esas compuertas y aplica los umbrales de `config_observabilidad.yaml`.
11. **Toda tarea traduce la especificación.** Una tarea implementa los contratos de `docs/spec/contratos/`, las tablas de su esquema en `docs/spec/esquema.sql` y los escenarios de `docs/spec/features/` con las etiquetas de sus `requisitos`. La matriz está en `docs/spec/TRAZABILIDAD.md`.

## 2. Matriz de propiedad por sala (constante en todas las olas)

| Sala | Rutas propias además de `features/<sala>/**`, `tests/<sala>/**`, `docs/modulos/<sala>.md` | Rol |
| :--- | :--- | :--- |
| `canal_whatsapp` | — | `¤¤integration-engineer` |
| `seguridad` | `evals/inyecciones.jsonl`, `evals/pii.jsonl`, `docs/privacidad/**` | `¤¤security-engineer` |
| `agente` | `docs/prompts/**`, `evals/enrutador.jsonl` | `¤¤machine-learning-engineer` |
| `conocimiento` | `scripts/seed_knowledge.py`, `evals/set_dorado.jsonl`, `docs/negocio/README.md` (checklist; el corpus lo entrega el negocio en `CORPUS_DIR`, fuera del repositorio) | `¤¤data-engineer` |
| `pms_conector` | — | `¤¤integration-engineer` |
| `herramientas_glamping` | — | `¤¤backend-developer` |
| `crm_conector` | — | `¤¤integration-engineer` |
| `arm_jarvis` | `evals/ventas.jsonl` | `¤¤backend-developer` |
| `comisiones` | — | `¤¤backend-developer` |
| `observabilidad` | `scripts/run_evals.py` | `¤¤devops-engineer` |
| `panel_operativo` | `tests/e2e/**` | `¤¤frontend-developer` |
| `web_huespedes` | — | `¤¤frontend-developer` |
| `anfitriones` | — | `¤¤backend-developer` |
| *(`operaciones` no nace: ADR-0007)* | — | — |
| *coordinador* (`pasillo_central`, `infraestructura`) | las rutas reservadas de la regla 6 (particionadas sin colisión en Olas 9–12) | `¤¤solutions-architect`, `¤¤devops-engineer`, `¤¤qa-engineer` |

## 3. Plan de ejecución en Tandas de 4 (0 archivos en común por tanda)

### Etapa I — Diseño Documental, Contratos y Desarrollo Clean-Room en Salas (Sin Nube)

| Tanda (Ola) | Tareas en paralelo (4 salas distintas, 0 archivos en común) | Naturaleza |
| :--- | :--- | :--- |
| **Ola 1** | `T-101` (`canal_whatsapp`) · `T-102` (`seguridad`) · `T-104` (`agente`) · `T-105` (`web_huespedes`) | Diseño documental + MVP Clean-Room con dobles |
| **Ola 2** | `T-103` (`observabilidad`) · `T-201` (`conocimiento`) · `T-202` (`pms_conector`) · `T-303` (`panel_operativo`) | Diseño documental + RAG sintético, FakePMS, trazas y panel base |
| **Ola 3** | `T-203` (`herramientas_glamping`) · `T-205` (`web_huespedes`) · `T-301` (`agente`) · `T-302` (`crm_conector`) | Herramientas MCP huéspedes, búsqueda web, enrutador y FakeCRM |
| **Ola 4** | `T-212` (`pms_conector`) · `T-304` (`seguridad`) · `T-305` (`anfitriones`) · `T-404` (`panel_operativo`) | Calendario PMS propio, políticas RLS, anfitriones y panel admin |
| **Ola 5** | `T-306` (`herramientas_glamping`) · `T-401` (`seguridad`) · `T-402` (`observabilidad`) · `T-403` (`agente`) | Herramientas anfitrión, 40 patrones inyección/PII, métricas/evals y caché |
| **Ola 6** | `T-405` (`web_huespedes`) · `T-501` (`comisiones`) · `T-502` (`arm_jarvis`) · `T-505` (`panel_operativo`) | Web publicados, motor de comisiones, ARM «Jarvis» y validación en panel |
| **Ola 7** | `T-503` (`canal_whatsapp`) · `T-504` (`herramientas_glamping`) · `T-506` (`anfitriones`) · `T-604` (`panel_operativo`) | Enrutamiento canal vendedores, herramientas ventas, estados de cuenta y tablero panel |
| **Ola 8** | `T-601` (`crm_conector`) · `T-602` (`arm_jarvis`) · `T-603` (`comisiones`) · `T-801` (`panel_operativo`) | Firma HMAC/cola CRM, tablero ARM, exportación comisiones y terminal móvil PWA |

### Etapa II — Orquestación en Pasillo Central y Comprobación con Plataformas de Nube / Producción

| Tanda (Ola) | Tareas en paralelo (rutas exclusivas, 0 archivos en común) | Plataformas / Hitos verificados |
| :--- | :--- | :--- |
| **Ola 9** | `T-110` (`webhook_router`) · `T-210` (`compose` + RAG arnés) · `T-310` (`worker` + `panel_crm_router`) · `T-510` (`contenedor` + `.env.example`) | Ensamblaje modular completo en `pasillo_central` (`app_core`) |
| **Ola 10** | `T-111` (Meta WhatsApp Cloud API) · `T-211` (Claude + RAG Corpus Real) · `T-311` (PostgreSQL RLS + Multi-propiedad) · `T-410` (Carga 200 msg/min + `agent-net`) | TASK-001, TASK-002, TASK-003, TASK-004 y carga beta |
| **Ola 11** | `T-411` (Salida de Beta) · `T-511` (Meta Canal Vendedores + Plantillas) · `T-610` (Servidor Producción + Backups `S-08`) · `T-810` (Proxy HTTPS + Claves VAPID) | TASK-005, TASK-006, servidor propio y despliegue móvil |
| **Ola 12** | `T-611` (Proveedor CRM Cloud Real + Cierre Producción) · `T-701` (Inbox Huéspedes condicional `ADR-0010`) | TASK-007 y TASK-008 |
| **Ola 13** | `T-901` (C1 — Fail-fast en montaje de panel operativo y CRM) | Calidad pasillo central (`app_core`) |
| **Ola 14** | `T-902` (C2 — Profundizar pruebas de contrato dobles vs compuertas) | Contratos tipados y mutantes muertos |
| **Ola 15** | `T-903` (C3 — Árbitro real de escritura conforme y casos sintéticos) | Verificación formal UTF-8, huellas e IP safety |
| **Ola 16** (A) | `T-408` (H-1, `herramientas_glamping`) · `T-409` (I-1, `inferencia`) · `T-416` (`observabilidad`) · `T-417` (`agente`, `estado_asistente`) | Anotaciones `x-pii`, espera ante 429 y estado del asistente |
| **Ola 17** (B) | `T-412` (P-1, pasillo) · `T-407` (A11 con A2, `agente`) · `T-413` (S-2, `seguridad`) · `T-414` (O-1, `observabilidad`) | Entorno de producción, salidas de herramientas tokenizadas y suite PII real |
| **Ola 18** (C) | `T-415` (A8-bis, `agente`) · `T-507` (TL-2, `arm_jarvis`) · `G-2` (árbitro de especificaciones) · `S-3` (`seguridad`, secretos sin clave publicada) | Argumentos inválidos al modelo, ARM con inferencia y secretos con clave efímera |
| **Ola 19** | `T-508` (TL-2, pasillo: `app_core` inyecta `inferencia` en el ARM) · `T-420` (`agente`, pausa dinámica) · `T-418` (`web_huespedes`, contraste de `--aviso`) · `T-419` (`herramientas_glamping`, `incidencia_id` acotado) | Ensamblaje del ARM con inferencia, pausa dinámica del asistente, contraste AA e `incidencia_id` sin forma de teléfono |
| **Ola 20** | `T-702` (`panel_operativo`, estado del asistente) · `T-421` (`agente`, derivación a una persona) · `T-422` (`seguridad`, aviso LOPDP) | Estado del asistente en el panel, con la pausa dinámica; aviso LOPDP y derivación |
| **Ola 21** | `T-509` (pasillo: lazo del huésped con aviso) · `T-423` (`seguridad`, rotación de `PII_VAULT_KEY`) | Filtro de entrada, aviso y respuesta enviada al huésped; rotación de la clave de la bóveda |
| **Ola 22** | `T-425` (`inferencia`, transcripción de audio) · `T-426` (`canal_whatsapp`, audio efímero) · `T-428` (`seguridad`, PII de nombres y correos) | Transcripción de audio, audio que se elimina siempre y detección de nombres propios y correos con tilde |
| **Ola 23** | `T-427` (`pasillo_central`, el lazo transcribe el audio) | Audio del huésped, apagado por omisión |
| **Ola 24** | `T-430` (`pasillo_central`, arranque productivo exige Vertex) · `T-431` (`observabilidad`, las evaluaciones de ventas pasan seguridad) | Arranque productivo sin Vertex incompleto y evaluaciones de ventas con seguridad real |
| **Ola 25** | `T-429` (`arm_jarvis`, seguridad obligatoria en el ARM) | Seguridad obligatoria en el ARM, sin doble por defecto |

Estados: `pendiente` → `boceto` → `sellada` · `bloqueada`.

---

## Ola 1 — Tanda 1 Clean-Room: Canal WhatsApp, Seguridad Base, Agente MVP y Web Pública

### T-101 — Canal de WhatsApp: diseño de módulo, webhook, envío, ventana de 24 h, plantillas y medios (API simulada)
`¤canal-whatsapp`
```toml
id = "T-101"
ola = 1
fase = 1
estado = "sellada"
sala = "canal_whatsapp"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-01", "RF-GW-02", "RF-GW-03", "RF-GW-04", "RF-GW-05", "RF-GW-07", "RF-GW-08"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/canal_whatsapp/**", "tests/canal_whatsapp/**", "docs/modulos/canal_whatsapp.md"]
consume = ["seguridad_service (solo descargar_medio)", "observabilidad_service"]
arbitro = "tests/canal_whatsapp/{test_webhook,test_envio,test_ventana_24h,test_plantillas,test_medios}.py con la API de Meta simulada; arnés Exit Code 0"
```
Entregables: documentación técnica en `docs/modulos/canal_whatsapp.md`, `webhook_internal.py` (verificación, firma HMAC, dedup), `envio_internal.py` (texto, botones, listas, estados, reintentos), `plantillas_internal.py`, `medios_internal.py`, persistencia `esquema canal`. Dobles propios de `seguridad` y `observabilidad` en `tests/canal_whatsapp/dobles.py`. **Hecho cuando** los cinco tests existen y pasan con la API simulada, e `INV_FIRMA_WEBHOOK_META` e `INV_VENTANA_24H` tienen prueba que falla si se quita la validación. La comprobación con el número real en Meta Cloud API se ejecuta en `T-111` (Ola 10).

### T-102 — Seguridad base: diseño de privacidad, identidad, allowlist, rate limit, inyección base, PII, audit log y consentimiento
`¤seguridad-canal`
```toml
id = "T-102"
ola = 1
fase = 1
estado = "sellada"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-01", "RF-SEC-02", "RF-SEC-03", "RF-SEC-04 (base)", "RF-SEC-05", "RF-SEC-06", "RF-PRIV-01", "RF-PRIV-02", "RNF-18"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "tests/seguridad/**", "docs/modulos/seguridad.md", "evals/inyecciones.jsonl", "evals/pii.jsonl", "docs/privacidad/**"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/{test_identidad,test_allowlist,test_rate_limit,test_pii,test_audit_log,test_consentimiento,test_inventario_datos}.py; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/seguridad.md` e inventario en `docs/privacidad/INVENTARIO.md`, `identidad_internal.py`, `allowlist_internal.py`, `audit_internal.py` (`INSERT`-only), `consentimiento_internal.py`, `rate_limit_internal.py`, `pii_internal.py` (tokenizar/rehidratar con bóveda cifrada), `identificar`, `filtrar_entrada` con los patrones base de inyección, `filtrar_salida`. `evals/inyecciones.jsonl` queda creado vacío y reservado para `T-401`. **Hecho cuando** `test_rate_limit.py` intenta desactivar el límite con cada rol y falla, y `test_pii.py` captura el cliente HTTP de un doble de modelo sin ningún teléfono en claro.

### T-104 — Agente MVP: diseño de prompts, prompt del glamping, bucle de herramientas, memoria y degradación
`¤agente-enrutador`
```toml
id = "T-104"
ola = 1
fase = 1
estado = "sellada"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-02", "RF-AG-04", "RF-AG-05", "RF-AG-06"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/agente/**", "tests/agente/**", "docs/modulos/agente.md", "docs/prompts/**", "evals/enrutador.jsonl"]
consume = ["seguridad_service", "herramientas_glamping_service", "conocimiento_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/agente/{test_prompts,test_bucle_herramientas,test_degradacion,test_memoria}.py con doble de modelo y dobles de compuertas; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/agente.md`, `docs/prompts/system-prompt-glamping.md` versión 1 con datos sintéticos inyectados desde configuración, `cliente_modelo_internal.py` (cliente con timeout y conteo de tokens), `prompts_internal.py` (carga y hash; variante `glamping`), `bucle_herramientas_internal.py` (tope de iteraciones, errores tipados), `memoria_internal.py` (`esquema agente`), `atender`. `evals/enrutador.jsonl` se crea vacío y reservado para `T-301`. **Hecho cuando** el bucle se detiene al tope y escala, un fallo de herramienta no inventa resultado, y un reinicio simulado conserva la conversación.

### T-105 — Web pública: diseño de módulo, catálogo, ficha y paso a WhatsApp
`¤web-huespedes`
```toml
id = "T-105"
ola = 1
fase = 1
estado = "sellada"
sala = "web_huespedes"
rol = "¤¤frontend-developer"
requisitos = ["RF-WEB-01", "RF-WEB-04", "RF-WEB-05", "RF-WEB-06", "US-18", "INV_WEB_SOLO_LECTURA", "INV_WEB_SIN_PII", "INV_WEB_LIMITE_POR_IP"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/web_huespedes/**", "tests/web_huespedes/**", "docs/modulos/web_huespedes.md"]
consume = ["observabilidad_service"]
arbitro = "tests/web_huespedes/test_catalogo.py; test_contacto.py; test_limites.py; test_calidad.py; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/web_huespedes.md`, rutas `/`, `/propiedades/{id}` y `/contacto`, plantillas Jinja2 con los tokens de `docs/FRONTEND.md` §6, carga del catálogo y límites por IP.

---

## Ola 2 — Tanda 2 Clean-Room: Observabilidad Base, Motor RAG Sintético, Conector PMS Fake y Panel Base

### T-103 — Observabilidad básica: diseño de módulo, logs JSON sin PII y traza por mensaje
`¤observabilidad`
```toml
id = "T-103"
ola = 2
fase = 1
estado = "sellada"
sala = "observabilidad"
rol = "¤¤devops-engineer"
requisitos = ["RF-OBS-01", "RF-OBS-02"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/observabilidad/**", "tests/observabilidad/**", "docs/modulos/observabilidad.md", "scripts/run_evals.py"]
consume = []
arbitro = "tests/observabilidad/{test_logs,test_trazas}.py; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/observabilidad.md`, `logs_internal.py` (JSON por línea, verificación de ausencia de PII), `trazas_internal.py` (`iniciar_traza`, `span` como context manager, `cerrar_traza`, persistencia `esquema observabilidad`), cálculo de tokens y costo por span. `scripts/run_evals.py` conserva su contrato base y se amplía en `T-402`. **Hecho cuando** una traza sintética con tres spans se persiste y se recupera, y un log con un teléfono en claro es rechazado.

### T-201 — Conocimiento: diseño de RAG, indexación, chunking, recuperación híbrida, «no lo sé» y set dorado (corpus sintético)
`¤conocimiento-rag`
```toml
id = "T-201"
ola = 2
fase = 2
estado = "sellada"
sala = "conocimiento"
rol = "¤¤data-engineer"
requisitos = ["RF-RAG-01", "RF-RAG-02", "RF-RAG-03", "RF-RAG-04", "RF-RAG-05", "RF-RAG-06", "RNF-04"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/conocimiento/**", "tests/conocimiento/**", "docs/modulos/conocimiento.md", "scripts/seed_knowledge.py", "evals/set_dorado.jsonl", "docs/negocio/README.md"]
consume = ["observabilidad_service"]
arbitro = "tests/conocimiento/{test_indexacion,test_chunking,test_recuperacion,test_citacion}.py sobre corpus sintético; ConocimientoService.evaluar(set_dorado) ≥ umbrales; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/conocimiento.md` y checklist en `docs/negocio/README.md`, `chunker_internal.py`, `indexador_internal.py` (idempotente, reemplazo por `version_hash`), `recuperador_internal.py` (HNSW + BM25, filtro obligatorio por propiedad), `embeddings_internal.py`, `evaluador_internal.py`, `scripts/seed_knowledge.py`, `evals/set_dorado.jsonl` (≥ 100 preguntas + ≥ 30 trampa sobre corpus sintético determinista), esquema `conocimiento` con políticas RLS declaradas. La ingesta del corpus comercial definitivo y validación en nube se realiza en `T-211` (Ola 10). **Hecho cuando** fidelidad ≥ 95 %, abstención ≥ 90 %, 0 alucinaciones de precio/política y P95 ≤ 150 ms en el benchmark local.

### T-202 — Conector PMS: diseño de módulo, interfaz completa, FakePMS y selección por configuración
`¤pms-conector`
```toml
id = "T-202"
ola = 2
fase = 3
estado = "sellada"
sala = "pms_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-PMS-01", "RF-PMS-02 (fake)", "RF-PMS-03", "RF-PMS-04", "RF-PMS-05", "RF-PMS-06"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/pms_conector/**", "tests/pms_conector/**", "docs/modulos/pms_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/pms_conector/{test_contrato,test_seleccion_proveedor,test_errores}.py contra FakePMS; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/pms_conector.md`, `base_internal.py` (ABC `PMSConnector`), `fake_internal.py` (dos propiedades, unidades, disponibilidad, cotización, reservas preliminares con expiración, instrucciones de check-in, incidencias y housekeeping en memoria), errores tipados, escrituras deshabilitadas por defecto con clave de idempotencia, `esquema pms` (caché e idempotencia). **Hecho cuando** el test de contrato está parametrizado para aceptar cualquier implementación y pasa con `FakePMS`.

### T-303 — Panel operativo base: diseño de módulo, acceso, inicio, handoffs por zona, detalle de conversación e incidencias
`¤panel-operativo`
```toml
id = "T-303"
ola = 2
fase = 4
estado = "sellada"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-01", "RF-PAN-07", "RF-PAN-08", "INV_PANEL_POR_ROL", "INV_PANEL_SIN_LOGICA"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["seguridad_service", "agente_service", "canal_whatsapp_service", "crm_conector_service", "pms_conector_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/{test_sesiones,test_bff_handoff,test_sin_logica}.py (cada endpoint con cada rol usando dobles); tests/e2e/test_handoff_zona.py; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/panel_operativo.md`, `sesiones_internal.py` (código por WhatsApp, cookie, CSRF), `bff_internal.py` con las rutas de sesión, handoffs e incidencias, `ui/` con P-01, P-02, P-08, P-09, P-10 (`docs/FRONTEND.md` §4), build en `estaticos/`, `esquema panel`. Los dobles de las compuertas consumidas viven en `tests/panel_operativo/dobles.py`. **Hecho cuando** un gestor de la zona A recibe 403 al tocar la zona B y las pruebas de US-09/US-10 pasan contra los dobles.

---

## Ola 3 — Tanda 3 Clean-Room: Herramientas MCP Huéspedes, Búsqueda Web, Enrutador Multi-Propiedad y CRM Fake

### T-203 — Herramientas MCP: diseño de esquemas, autorización y ejecución de las 7 herramientas de huéspedes
`¤herramientas-mcp`
```toml
id = "T-203"
ola = 3
fase = 3
estado = "sellada"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-MCP-01", "RF-MCP-02", "RF-MCP-03", "RF-MCP-04", "RF-MCP-05", "RF-MCP-06", "RF-MCP-07"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/herramientas_glamping/**", "tests/herramientas_glamping/**", "docs/modulos/herramientas_glamping.md"]
consume = ["seguridad_service", "pms_conector_service", "conocimiento_service", "crm_conector_service", "observabilidad_service"]
arbitro = "tests/herramientas_glamping/{test_contratos,test_server}.py con dobles propios de todas las compuertas; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/herramientas_glamping.md`, `esquemas/*.json` (entrada y salida de las siete herramientas), `herramientas_internal.py` (validación, `seguridad.autorizar`, despacho a la compuerta dueña, `ResultadoHerramienta`), `listar`/`ejecutar`/`esquema`, transporte MCP en `server.py` (stdio y http en `agent-net`). **Hecho cuando** cada herramienta rechaza entrada inválida con mensaje legible, rechaza rol no autorizado y pasa su contrato con los dobles.

### T-205 — Web pública: búsqueda, comparación y contexto para el agente
`¤web-huespedes`
```toml
id = "T-205"
ola = 3
fase = 3
estado = "sellada"
sala = "web_huespedes"
rol = "¤¤frontend-developer"
requisitos = ["RF-WEB-02", "RF-WEB-03", "RF-WEB-04", "US-18", "INV_WEB_PRECIO_EN_VIVO"]
depende_de = ["T-105", "T-202"]
bloqueada_por = []
propiedad = ["features/web_huespedes/**", "tests/web_huespedes/**", "docs/modulos/web_huespedes.md"]
consume = ["pms_conector_service", "observabilidad_service"]
arbitro = "tests/web_huespedes/test_busqueda.py con doble de PMS; tests/web_huespedes/test_contacto.py; arnés Exit Code 0"
```
Entregables: actualización de `docs/modulos/web_huespedes.md`, rutas `/buscar` y `/comparar`, y `resolver_contacto` para que el agente reciba propiedad, fechas y huéspedes.

### T-301 — Agente: enrutador multi-propiedad, herramientas por rol, prompts de enrutador, departamentos y hospedaje general
`¤agente-enrutador`
```toml
id = "T-301"
ola = 3
fase = 4
estado = "sellada"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-01", "RF-AG-03", "RF-AG-08", "US-03 (lógica)", "INV_ENVIO_UNICO"]
depende_de = ["T-104"]
bloqueada_por = []
propiedad = ["features/agente/**", "tests/agente/**", "docs/modulos/agente.md", "docs/prompts/**", "evals/enrutador.jsonl"]
consume = ["seguridad_service", "herramientas_glamping_service", "conocimiento_service", "canal_whatsapp_service", "pms_conector_service (vía herramientas)", "observabilidad_service"]
arbitro = "tests/agente/{test_enrutador,test_allowlist_herramientas}.py 20/20; AgenteService.evaluar(enrutador) = 1.0 aciertos; arnés Exit Code 0"
```
Entregables: `enrutador_internal.py`, prompts `enrutador` y `departamentos` versión 1 en `docs/prompts/`, `herramientas_para(rol, propiedad)`, `enviar_checkins_del_dia`, `entrar_en_silencio`/`reanudar`, `evals/enrutador.jsonl` con 20 conversaciones etiquetadas (incluidas ambiguas). **Hecho cuando** `INV_PROPIEDAD_RESUELTA` e `INV_SIN_FUGA_ENTRE_PROPIEDADES` tienen prueba que falla si se quita el filtro.

### T-302 — Conector CRM: diseño de módulo, interfaz completa, FakeCRM y asignación de conversaciones
`¤crm-conector`
```toml
id = "T-302"
ola = 3
fase = 4
estado = "sellada"
sala = "crm_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-CRM-01", "RF-CRM-02 (fake)", "RF-CRM-06", "RF-MCP-06 (real)"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/crm_conector/**", "tests/crm_conector/**", "docs/modulos/crm_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/crm_conector/{test_contrato,test_seleccion_proveedor,test_confinamiento}.py contra FakeCRM; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/crm_conector.md`, `base_internal.py` (ABC `CRMConnector`), `fake_internal.py` (contactos, oportunidades, conversaciones asignables por zona, eventos), `registrar_receptor`, `esquema crm` (referencias). `publicar_venta`, cola y eventos firmados se completan en `T-601` (Ola 8).

---

## Ola 4 — Tanda 4 Clean-Room: Calendario PMS Propio, Políticas RLS, Dominio Anfitriones y Administración del Panel

### T-212 — Conector PMS: calendario y tarifas propios de plataforma
`¤pms-conector`
```toml
id = "T-212"
ola = 4
fase = 3
estado = "sellada"
sala = "pms_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-PMS-02 (plataforma)", "RF-PMS-07", "RF-PMS-08"]
depende_de = ["T-202"]
bloqueada_por = []
propiedad = ["features/pms_conector/**", "tests/pms_conector/**", "docs/modulos/pms_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/pms_conector/test_contrato.py con el proveedor plataforma; tests/pms_conector/test_calendario.py con concurrencia; arnés Exit Code 0"
```
Separada de `T-202` en una tanda distinta para garantizar cero colisión en `features/pms_conector/**`. Entregables: `plataforma_internal.py`, actualización de `docs/modulos/pms_conector.md` y soporte de `proveedor: plataforma`. **Hecho cuando** el mismo test de contrato pasa con `FakePMS` y con `plataforma`, y dos reservas simultáneas no ocupan la misma noche.

### T-304 — Seguridad: diseño y migraciones de Row-Level Security por propiedad y secretos operativos
`¤seguridad-canal`
```toml
id = "T-304"
ola = 4
fase = 4
estado = "sellada"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-07", "RF-SEC-08", "INV_RLS_MULTI_INQUILINO", "INV_SECRETO_OPERATIVO"]
depende_de = ["T-102"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "tests/seguridad/**", "docs/modulos/seguridad.md", "evals/inyecciones.jsonl"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/test_rls.py (aislamiento entre propiedades y verificación de políticas SQL NOBYPASSRLS); arnés Exit Code 0"
```
Entregables: migraciones de políticas RLS para todos los esquemas con `propiedad_id`, rol de aplicación `NOBYPASSRLS`, guardas de contexto de inquilino y prueba en `tests/seguridad/test_rls.py` que verifica que con propiedad A activa nunca se exponen filas de propiedad B. La comprobación de extremo a extremo contra la instancia PostgreSQL en contenedor/nube se ejecuta en `T-311` (Ola 10).

### T-305 — Anfitriones: diseño de módulo, alta, publicación, solicitud y resultado de la estadía
`¤anfitriones`
```toml
id = "T-305"
ola = 4
fase = 4
estado = "sellada"
sala = "anfitriones"
rol = "¤¤backend-developer"
requisitos = ["RF-ANF-01", "RF-ANF-02", "RF-ANF-04", "RF-ANF-05", "RF-ANF-06", "US-19"]
depende_de = ["T-202"]
bloqueada_por = []
propiedad = ["features/anfitriones/**", "tests/anfitriones/**", "docs/modulos/anfitriones.md"]
consume = ["seguridad_service", "canal_whatsapp_service", "pms_conector_service", "observabilidad_service"]
arbitro = "tests/anfitriones/{test_publicacion,test_solicitudes,test_resultado,test_aislamiento}.py; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/anfitriones.md`, `registro_internal.py`, `solicitudes_internal.py`, persistencia `esquema anfitriones`. **Hecho cuando** el contacto no sale antes de confirmar y un anfitrión no puede operar lo de otro.

### T-404 — Panel operativo: administración básica y calidad de la interfaz
`¤panel-operativo`
```toml
id = "T-404"
ola = 4
fase = 5
estado = "sellada"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-09 (usuarios, auditoría, privacidad, salud)", "RF-PAN-10", "RF-ANF-01", "RF-ANF-02", "RF-PMS-08 (pantalla)"]
depende_de = ["T-303"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["seguridad_service", "anfitriones_service", "pms_conector_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/test_bff_admin.py (cada rol); tests/e2e/test_calidad_ui.py (accesibilidad AA, LCP ≤ 2,5 s, 0 rastros en el build); arnés Exit Code 0"
```
Entregables: P-11 usuarios, roles y bloqueos, auditoría, solicitudes de titulares, salud del sistema; auditoría de accesibilidad y presupuesto de rendimiento; función de comprobación de interfaz purificada sobre el build expuesta por la sala.

---

## Ola 5 — Tanda 5 Clean-Room: Herramientas MCP Anfitrión, Blindaje de Seguridad, Observabilidad/Evals y Caché de Agente

### T-306 — Herramientas MCP de solicitud y anfitrión
`¤herramientas-mcp`
```toml
id = "T-306"
ola = 5
fase = 4
estado = "sellada"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-ANF-04", "RF-ANF-05", "RF-ANF-06", "RF-PMS-08 (herramienta)"]
depende_de = ["T-203"]
bloqueada_por = []
propiedad = ["features/herramientas_glamping/**", "tests/herramientas_glamping/**", "docs/modulos/herramientas_glamping.md"]
consume = ["seguridad_service", "anfitriones_service", "pms_conector_service", "observabilidad_service"]
arbitro = "tests/herramientas_glamping/test_anfitriones.py; arnés Exit Code 0"
```
Entregables: `solicitar_reserva`, `responder_solicitud`, `reportar_resultado_estadia` y `actualizar_calendario` según `docs/spec/contratos/herramientas.yaml`. `anfitrion_id` sale siempre de la identidad.

### T-401 — Seguridad completa: allowlist por acción, 40 patrones de inyección, retención y criptoborrado
`¤seguridad-canal`
```toml
id = "T-401"
ola = 5
fase = 5
estado = "sellada"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-04", "RF-PRIV-03", "RF-PRIV-04", "RF-PRIV-05", "RF-PRIV-06", "OP-10", "RNF-07", "RNF-17"]
depende_de = ["T-304"]
bloqueada_por = []
propiedad = ["features/seguridad/**", "tests/seguridad/**", "docs/modulos/seguridad.md", "evals/inyecciones.jsonl"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/{test_retencion,test_criptoborrado,test_solicitudes_titular,test_inventario_datos}.py; SeguridadService.evaluar(inyecciones) = 0 éxitos y ≤ 2 % falsos positivos; suite pii sobre umbral; arnés Exit Code 0"
```
Entregables: `injection_internal.py` + `patrones_inyeccion.yaml` (≥ 40 patrones, es/en/pt/fr, heurísticas), `retencion_internal.py`, `titulares_internal.py` (solicitudes y criptoborrado), `informe_semanal`, `administrar_usuarios`, `evals/inyecciones.jsonl` completo. **Hecho cuando** las suites `inyecciones` y `pii` superan su umbral y el criptoborrado no altera el audit log.

### T-402 — Observabilidad completa: despacho de evaluaciones, métricas del PRD y alertas
`¤observabilidad`
```toml
id = "T-402"
ola = 5
fase = 5
estado = "sellada"
sala = "observabilidad"
rol = "¤¤devops-engineer"
requisitos = ["RF-OBS-03", "RF-OBS-04", "RNF-13"]
depende_de = ["T-103"]
bloqueada_por = []
propiedad = ["features/observabilidad/**", "tests/observabilidad/**", "docs/modulos/observabilidad.md", "scripts/run_evals.py"]
consume = ["conocimiento_service.evaluar", "seguridad_service.evaluar", "agente_service.evaluar", "arm_jarvis_service.evaluar"]
arbitro = "tests/observabilidad/{test_alertas,test_metricas}.py; scripts/run_evals.py despacha las cuatro suites y falla bajo umbral; arnés Exit Code 0"
```
Entregables: `metricas_internal.py` (OP-01..OP-10 desde trazas), `alertas_internal.py` (silencio, errores, cola, costo), `scripts/run_evals.py` que despacha a `evaluar(...)` de cada compuerta y aplica umbrales de `config_observabilidad.yaml`. Una suite cuya sala aún no expone `evaluar` se reporta OMITIDA, nunca verde.

### T-403 — Agente: caché semántico y enrutamiento de modelos
`¤agente-enrutador`
```toml
id = "T-403"
ola = 5
fase = 5
estado = "sellada"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-07", "OP-09", "RNF-16", "INV_CACHE_SIN_PRECIOS"]
depende_de = ["T-301"]
bloqueada_por = []
propiedad = ["features/agente/**", "tests/agente/**", "docs/modulos/agente.md", "docs/prompts/**", "evals/enrutador.jsonl"]
consume = ["conocimiento_service (embeddings vía compuerta)", "observabilidad_service"]
arbitro = "tests/agente/test_enrutamiento_modelos.py; arnés Exit Code 0"
```
Entregables: `cache_internal.py` (exclusión por términos de precio/disponibilidad), decisión de modelo registrada en la traza, acuse «un momento…» si una herramienta tarda más de 3 s.

---

## Ola 6 — Tanda 6 Clean-Room: Web Solo Publicados, Motor de Comisiones, ARM «Jarvis» y Validación de Ventas en Panel

### T-405 — Web pública: filtro de solo hospedajes publicados
`¤web-huespedes`
```toml
id = "T-405"
ola = 6
fase = 5
estado = "sellada"
sala = "web_huespedes"
rol = "¤¤frontend-developer"
requisitos = ["RF-ANF-03", "INV_SOLO_PUBLICADO"]
depende_de = ["T-205", "T-305"]
bloqueada_por = []
propiedad = ["features/web_huespedes/**", "tests/web_huespedes/**", "docs/modulos/web_huespedes.md"]
consume = ["anfitriones_service", "observabilidad_service"]
arbitro = "tests/web_huespedes/test_publicados.py; arnés Exit Code 0"
```
Entregables: el catálogo filtra con `anfitriones.publicados()` y cada ficha indica quién ofrece el hospedaje. La compuerta recibe `anfitriones` por inyección con doble propio en `tests/web_huespedes/dobles.py`.

### T-501 — Comisiones: diseño de módulo, reglas versionadas, cálculo reproducible y cierre de período
`¤comisiones`
```toml
id = "T-501"
ola = 6
fase = 6
estado = "sellada"
sala = "comisiones"
rol = "¤¤backend-developer"
requisitos = ["RF-COM-01", "RF-COM-02", "RF-COM-04", "INV_COMISION_REPRODUCIBLE"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/comisiones/**", "tests/comisiones/**", "docs/modulos/comisiones.md"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/comisiones/{test_reglas,test_cierre_periodo}.py; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/comisiones.md`, `desglose` y `estado_cuenta` para el panel (ADR-0009 y ADR-0015), `reglas_internal.py` (vigencia a fecha de venta, versiones, escalones), `periodo_internal.py` (cierre inmutable, ajustes al período abierto), `esquema comisiones` con disparador que rechaza `UPDATE` en períodos cerrados.

### T-502 — ARM «Jarvis»: diseño de módulo, ingesta, extracción, estados, ticket, comisión, notificación, consulta propia y asistente del líder
`¤arm-jarvis`
```toml
id = "T-502"
ola = 6
fase = 6
estado = "sellada"
sala = "arm_jarvis"
rol = "¤¤backend-developer"
requisitos = ["RF-ARM-01", "RF-ARM-02", "RF-ARM-03", "RF-ARM-04", "RF-ARM-05", "RF-ARM-06", "RF-ARM-07", "RF-ARM-09", "RF-ARM-10", "OP-07", "OP-08", "RNF-03"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["features/arm_jarvis/**", "tests/arm_jarvis/**", "docs/modulos/arm_jarvis.md", "evals/ventas.jsonl"]
consume = ["seguridad_service", "comisiones_service", "crm_conector_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/arm_jarvis/{test_ingesta,test_estados,test_comision,test_ticket,test_notificacion,test_consulta_comision,test_asistente_lider}.py; ArmJarvisService.evaluar(ventas) ≥ 95 %; arnés Exit Code 0"
```
Entregables: diseño en `docs/modulos/arm_jarvis.md`, `extractor_internal.py` (cliente de modelo propio → `VentaExtraida`, preguntas por campos faltantes), `estados_internal.py` (transiciones auditadas), `ticket_internal.py` (secuencia por año con bloqueo de fila), `notificador_internal.py`, `asistente_lider_internal.py`, `evals/ventas.jsonl` (≥ 60 mensajes anonimizados), `esquema arm`. Dobles propios de `comisiones`, `crm`, `canal` y `seguridad`. **Hecho cuando** `test_ticket.py` prueba concurrencia sin huecos ni duplicados y `test_consulta_comision.py` demuestra que no hay fuga entre vendedores.

### T-505 — Panel operativo: ventas por validar, detalle de venta y Jarvis
`¤panel-operativo`
```toml
id = "T-505"
ola = 6
fase = 6
estado = "sellada"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-02", "RF-PAN-03", "RF-PAN-06", "US-06"]
depende_de = ["T-404"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["arm_jarvis_service", "comisiones_service", "seguridad_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/{test_bff_ventas,test_bff_jarvis}.py; tests/e2e/test_validar_venta.py (validar con un toque, corrección de campos dudosos, conflicto); arnés Exit Code 0"
```
Entregables: P-03, P-04, P-07 (`docs/FRONTEND.md` §4), componentes `TarjetaVenta`, `HojaCorreccion`, `DialogoMotivo`, `ChatJarvis` probados contra dobles en `tests/panel_operativo/dobles.py`.

---

## Ola 7 — Tanda 7 Clean-Room: Canal de Vendedores, Herramientas MCP Ventas, Estados de Cuenta Anfitriones y Tablero del Panel

### T-503 — Canal de WhatsApp: enrutamiento del canal de vendedores (parametrizable grupo o 1:1)
`¤canal-whatsapp`
```toml
id = "T-503"
ola = 7
fase = 6
estado = "sellada"
sala = "canal_whatsapp"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-06"]
depende_de = ["T-101"]
bloqueada_por = []
propiedad = ["features/canal_whatsapp/**", "tests/canal_whatsapp/**", "docs/modulos/canal_whatsapp.md"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/canal_whatsapp/test_enrutamiento_canal.py (un mensaje de vendedor nunca llega al receptor de huéspedes y viceversa en modos grupo y 1a1); arnés Exit Code 0"
```
Entregables: `enrutamiento_canal_internal.py` (`clasificar_canal` por remitente registrado como vendedor en modo `1a1` o por `grupo_id` en modo `grupo`), despacho al receptor correcto, definición local de la plantilla `comision_validada`. La aprobación en vivo de la plantilla en Meta Business Manager se verifica en `T-511` (Ola 11).

### T-504 — Herramientas MCP: registrar_venta y consultar_comision_propia
`¤herramientas-mcp`
```toml
id = "T-504"
ola = 7
fase = 6
estado = "sellada"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-MCP-08", "RF-MCP-09", "RF-ANF-07"]
depende_de = ["T-306"]
bloqueada_por = []
propiedad = ["features/herramientas_glamping/**", "tests/herramientas_glamping/**", "docs/modulos/herramientas_glamping.md"]
consume = ["seguridad_service", "arm_jarvis_service", "comisiones_service", "anfitriones_service", "observabilidad_service"]
arbitro = "tests/herramientas_glamping/test_contratos.py ampliado a las dos herramientas con dobles propios; arnés Exit Code 0"
```
Entregables: esquemas y despachadores de `registrar_venta` y `consultar_comision_propia` en `features/herramientas_glamping/`, actualizando `docs/modulos/herramientas_glamping.md`.

### T-506 — Anfitriones: estado de cuenta, cobro y pausa
`¤anfitriones`
```toml
id = "T-506"
ola = 7
fase = 6
estado = "sellada"
sala = "anfitriones"
rol = "¤¤backend-developer"
requisitos = ["RF-ANF-07", "RF-ANF-08", "US-20", "INV_COMISION_PLATAFORMA_UNICA"]
depende_de = ["T-305"]
bloqueada_por = []
propiedad = ["features/anfitriones/**", "tests/anfitriones/**", "docs/modulos/anfitriones.md"]
consume = ["seguridad_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/anfitriones/test_estado_cuenta.py; arnés Exit Code 0"
```
Entregables: `estado_cuenta_internal.py` con cierre mensual, registro de pago, ajustes y pausa por vencimiento. **Hecho cuando** una estadía no se cobra dos veces y el total coincide con sus líneas.

### T-604 — Panel operativo: tablero, cierre de período, exportación y administración completa
`¤panel-operativo`
```toml
id = "T-604"
ola = 7
fase = 7
estado = "sellada"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-04", "RF-PAN-05", "RF-PAN-09 (reglas, plantillas, conocimiento, propiedades)", "US-08", "RF-ANF-08"]
depende_de = ["T-505"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["anfitriones_service", "arm_jarvis_service", "comisiones_service", "pms_conector_service", "canal_whatsapp_service", "conocimiento_service", "seguridad_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/test_bff_comisiones.py (409 tras cierre); tests/e2e/test_tablero.py (totales al centavo con la exportación); arnés Exit Code 0"
```
Entregables: P-05, P-06 y el resto de P-11 (`docs/FRONTEND.md` §4), componentes `TarjetaMetrica`, `GraficoBarras`, `TablaDensa`.

---

## Ola 8 — Tanda 8 Clean-Room: Firma/Cola CRM, Tablero ARM, Exportación de Comisiones y Terminal Móvil PWA

### T-601 — Conector CRM: publicación firmada HMAC-SHA256 e idempotente, cola de reintentos, eventos y adaptador HTTP sobre fixtures
`¤crm-conector`
```toml
id = "T-601"
ola = 8
fase = 7
estado = "sellada"
sala = "crm_conector"
rol = "¤¤integration-engineer"
requisitos = ["RF-CRM-02 (real)", "RF-CRM-03", "RF-CRM-04", "RF-CRM-05", "RNF-09", "S-05"]
depende_de = ["T-302"]
bloqueada_por = []
propiedad = ["features/crm_conector/**", "tests/crm_conector/**", "docs/modulos/crm_conector.md"]
consume = ["observabilidad_service"]
arbitro = "tests/crm_conector/{test_publicar_venta,test_cola_reintentos,test_eventos}.py con receptor simulado que verifica HMAC y fixtures grabados; arnés Exit Code 0"
```
Entregables: `firma_internal.py` (HMAC-SHA256 sobre cuerpo JSON canónico), `cola_internal.py` (backoff exponencial, ventana de 24 h, estado `validada/no_publicada`), `eventos_internal.py` (verificación de firma de eventos entrantes), adaptador HTTP configurable y `esquema crm` completo. La conexión en vivo con el proveedor CRM comercial en nube (`ADR-0008`/`S-05`) se verifica en `T-611` (Ola 12).

### T-602 — ARM: tablero de métricas y marcado de publicación en CRM
`¤arm-jarvis`
```toml
id = "T-602"
ola = 8
fase = 7
estado = "sellada"
sala = "arm_jarvis"
rol = "¤¤backend-developer"
requisitos = ["RF-ARM-08", "RF-CRM-04 (receptor marcar_publicacion)"]
depende_de = ["T-502"]
bloqueada_por = []
propiedad = ["features/arm_jarvis/**", "tests/arm_jarvis/**", "docs/modulos/arm_jarvis.md", "evals/ventas.jsonl"]
consume = ["comisiones_service", "observabilidad_service"]
arbitro = "tests/arm_jarvis/test_tablero.py (totales al centavo con la exportación de comisiones); arnés Exit Code 0"
```
Entregables: agregaciones del tablero en `features/arm_jarvis/` y receptor `marcar_publicacion` sincronizado con la compuerta.

### T-603 — Comisiones: exportación CSV y JSON validada contra esquema
`¤comisiones`
```toml
id = "T-603"
ola = 8
fase = 7
estado = "sellada"
sala = "comisiones"
rol = "¤¤backend-developer"
requisitos = ["RF-COM-03"]
depende_de = ["T-501"]
bloqueada_por = []
propiedad = ["features/comisiones/**", "tests/comisiones/**", "docs/modulos/comisiones.md"]
consume = ["observabilidad_service"]
arbitro = "tests/comisiones/test_exportacion.py valida CSV y JSON contra esquema_exportacion.json; arnés Exit Code 0"
```
Entregables: generador determinista de exportación CSV y JSON en `features/comisiones/` y validación contractual contra `esquema_exportacion.json`.

### T-801 — Panel operativo: terminal móvil PWA instalable, avisos Web Push e idempotencia
`¤panel-operativo`
```toml
id = "T-801"
ola = 8
fase = 8
estado = "sellada"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-11", "RF-PAN-12", "RF-PAN-13", "RF-PAN-14", "INV_MOVIL_SIN_PII_EN_DISCO", "INV_MOVIL_SIN_ESCRITURA_SIN_RED", "INV_AVISO_SIN_PII", "INV_ACCION_IDEMPOTENTE"]
depende_de = ["T-604"]
bloqueada_por = []
propiedad = ["features/panel_operativo/**", "tests/panel_operativo/**", "tests/e2e/**", "docs/modulos/panel_operativo.md"]
consume = ["arm_jarvis_service", "crm_conector_service", "seguridad_service", "observabilidad_service"]
arbitro = "tests/e2e/test_terminal_movil.py; tests/panel_operativo/test_avisos.py; tests/panel_operativo/test_idempotencia.py; arnés Exit Code 0"
```
Entregables: manifiesto PWA, iconos propios y service worker que guarda solo el shell estático; pantalla P-12 (`docs/FRONTEND.md` §4); suscripción Web Push con claves VAPID leídas de entorno; `Idempotency-Key` en todas las acciones mutadoras del BFF.

---

## Ola 9 — Tanda 9 Orquestación en Pasillo Central: Ensamblaje Modular de Compuertas y Contenedores

### T-110 — Pasillo central (módulo webhook y web pública): rutas HTTP `/webhook` y montaje del catálogo público
`¤pasillo-central`
```toml
id = "T-110"
ola = 9
fase = 1
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-GW-01 (ruta)", "RNF-08", "RNF-11", "RNF-12", "RNF-14", "RNF-19"]
depende_de = ["T-101", "T-102", "T-103", "T-104", "T-105"]
bloqueada_por = []
propiedad = ["app_core/main.py", "app_core/webhook_router.py", "tests/app_core/test_webhook_app.py"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/test_webhook_app.py; arnés Exit Code 0"
entorno_arbitro = "servicio_local_y_compuertas_reales"
fecha_arbitro = "2026-11-02"
comando_arbitro = "pytest tests/app_core/test_webhook_app.py"
```
Entregables: `app_core/webhook_router.py` y enlace en `app_core/main.py` para `GET/POST /webhook` → `canal.verificar_webhook` / `canal.recibir` → receptor con cola asíncrona (responder 200 en < 2 s) y montaje de las rutas públicas de `web_huespedes`. **Hecho cuando** `tests/app_core/test_webhook_app.py` cubre la ruta del webhook con firma válida e inválida y `GET /` de la web pública.

### T-210 — Pasillo central (compose y arnés RAG): servicio MCP en compose, egreso y semilla sintética del RAG en el arnés
`¤pasillo-central`
```toml
id = "T-210"
ola = 9
fase = 3
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RNF-10 (egreso)", "RNF-14"]
depende_de = ["T-201", "T-202", "T-203"]
bloqueada_por = []
propiedad = ["compose.yaml", "scripts/arnes_glamping.py", "tests/app_core/test_mcp_compose.py"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/test_mcp_compose.py; arnés Exit Code 0 incluyendo el paso de semilla sintética del RAG"
entorno_arbitro = "servicio_local_y_compuertas_reales"
fecha_arbitro = "2026-11-02"
comando_arbitro = "pytest tests/app_core/test_mcp_compose.py"
```
Entregables: servicio `mcp-tools` operativo en `compose.yaml`, lista de egreso con PMS y embeddings, y paso en `scripts/arnes_glamping.py` que ejecuta `seed_knowledge.py` sobre el corpus sintético y la evaluación `rag`.

### T-310 — Pasillo central (worker y rutas de panel/CRM): planificador de check-in, montaje de `/panel/*` y eventos del CRM
`¤pasillo-central`
```toml
id = "T-310"
ola = 9
fase = 4
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["US-03 (disparo)", "RF-PAN (montaje)", "RF-CRM-05 (ruta)", "RF-ANF-04 (procesos diarios)"]
depende_de = ["T-301", "T-302", "T-303", "T-304", "T-305", "T-306"]
bloqueada_por = []
propiedad = ["app_core/worker.py", "app_core/panel_crm_router.py", "tests/app_core/test_worker_y_panel.py"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/test_worker_y_panel.py; arnés Exit Code 0"
entorno_arbitro = "servicio_local_y_compuertas_reales"
fecha_arbitro = "2026-11-02"
comando_arbitro = "pytest tests/app_core/test_worker_y_panel.py"
```
Entregables: tarea programada `checkin_del_dia` en `app_core/worker.py`, montaje de `/panel/*` y estáticos, y ruta `POST /crm/eventos` → `crm.recibir_evento` → receptores (`agente.reanudar`, panel) en `app_core/panel_crm_router.py`.

### T-510 — Pasillo central (contenedor y entorno): configuración del canal de vendedores y enlace de receptores ARM
`¤pasillo-central`
```toml
id = "T-510"
ola = 9
fase = 6
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-GW-06 (configuración)", "RF-ARM-06 (plantilla aprobada)"]
depende_de = ["T-501", "T-502", "T-503", "T-504", "T-505", "T-604"]
bloqueada_por = []
propiedad = ["app_core/contenedor.py", "app_core/config_app.yaml", ".env.example", "tests/app_core/test_vendedores_app.py"]
consume = ["todas las compuertas"]
arbitro = "tests/app_core/test_vendedores_app.py; arnés Exit Code 0"
entorno_arbitro = "servicio_local_y_compuertas_reales"
fecha_arbitro = "2026-11-02"
comando_arbitro = "pytest tests/app_core/test_vendedores_app.py"
```
Entregables: enlace de `canal_vendedores.modo` y compuertas de `arm_jarvis`, `comisiones` y `anfitriones` en `app_core/contenedor.py`, `app_core/config_app.yaml` y `.env.example`, verificado en `tests/app_core/test_vendedores_app.py`.

---

## Ola 10 — Tanda 10 Comprobación con Plataformas de Nube (Fase I): Meta WhatsApp, Claude + RAG Real, PostgreSQL RLS y Carga Beta

### T-111 — Comprobación Cloud Fase 1 (Meta WhatsApp Cloud API): conversación real con número de pruebas, RNF-01, S-01 y decisión de audio
`¤bbap-glamping`
```toml
id = "T-111"
ola = 10
fase = 1
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["RNF-01", "INV_INTERFAZ_PURIFICADA", "S-01", "S-02", "S-09"]
depende_de = ["T-110"]
bloqueada_por = ["S-02"]
propiedad = ["tests/integracion/test_fase1.py", "tests/test_interfaz_purificada.py", "governance/tareas/TASK-001-mvp-whatsapp.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase1.py; conversación real registrada en Meta WhatsApp Cloud API con traza; RNF-01 anotado en TASK-001; arnés Exit Code 0"
entorno_arbitro = "doble_simulado_meta"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_fase1.py"
```
Entregables: prueba de integración de extremo a extremo en `tests/integracion/test_fase1.py`; conversación real con el número de pruebas de Meta Cloud API y P95 de la semana anotado; `tests/test_interfaz_purificada.py` sobre plantillas y mensajes; comprobación empírica de `S-01` (lectura del canal de vendedores con la API oficial de Meta) y `S-09` (transcripción de audio) documentadas en `TASK-001-mvp-whatsapp.md`. **Estado:** Pendiente de integración real contra número y API de Meta WhatsApp Cloud en vivo (validada previamente con doble simulado). **Hecho cuando** TASK-001 pasa a `sellada`.

### T-211 — Comprobación Cloud Fases 2–3 (Claude API + Corpus Real RAG + PMS): reserva preliminar E2E y medición RNF-02
`¤bbap-glamping`
```toml
id = "T-211"
ola = 10
fase = 3
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["US-01", "US-02", "US-04", "US-12", "RNF-02"]
depende_de = ["T-210", "T-212"]
bloqueada_por = ["S-03", "ADR-0012"]
propiedad = ["tests/integracion/test_fase3.py", "governance/tareas/TASK-002-rag.md", "governance/tareas/TASK-003-pms-mcp.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase3.py (agente + herramientas + PMS + RAG con corpus real en PostgreSQL/pgvector); RNF-02 medido; arnés Exit Code 0"
entorno_arbitro = "doble_fake_pms_y_modelo_test"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_fase3.py"
```
Entregables: prueba E2E en `tests/integracion/test_fase3.py`, indexación del corpus comercial real (`S-03`) sobre el almacén vectorial elegido (`ADR-0012`) y medición de latencia P95 `RNF-02` con el modelo en vivo. **Estado:** Pendiente de integración real contra API de Gemini/Claude en producción y PMS en vivo (validada previamente con FakePMS y corpus de prueba). **Hecho cuando** TASK-002 y TASK-003 pasan a `sellada`.

### T-311 — Comprobación Cloud Fase 4 (PostgreSQL RLS + Multi-Propiedad): check-in autónomo y handoff con dos propiedades
`¤bbap-glamping`
```toml
id = "T-311"
ola = 10
fase = 4
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["US-03", "US-09", "US-10", "US-13"]
depende_de = ["T-310"]
bloqueada_por = []
propiedad = ["tests/integracion/test_fase4.py", "governance/tareas/TASK-004-multipropiedad.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase4.py contra PostgreSQL real con RLS activo; arnés Exit Code 0"
entorno_arbitro = "doble_crm_y_postgresql_local"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_fase4.py"
```
Entregables: prueba de integración multi-propiedad en `tests/integracion/test_fase4.py` verificando aislamiento RLS en motor PostgreSQL real, disparo de check-in autónomo y handoff por zona. **Estado:** Pendiente de integración real en entorno multi-propiedad productivo (validada contra PostgreSQL local con RLS y dobles de CRM). **Hecho cuando** TASK-004 pasa a `sellada`.

### T-410 — Comprobación de Infraestructura Beta: prueba de carga (200 msg/min), aislamiento de red `agent-net` y alertas CI
`¤infra-hibrida`
```toml
id = "T-410"
ola = 10
fase = 5
estado = "pendiente"
sala = "infraestructura"
rol = "¤¤devops-engineer"
requisitos = ["RNF-05", "RNF-06", "RNF-10", "INV_RED_AISLADA"]
depende_de = ["T-401", "T-402", "T-403", "T-404", "T-405", "T-310"]
bloqueada_por = []
propiedad = ["tests/integracion/carga/__init__.py", "tests/integracion/carga/test_aislamiento_red.py", "tests/integracion/carga/test_carga_concurrente.py", "tests/integracion/carga/test_sondeo_salud.py", ".github/workflows/ci.yml", ".github/workflows/health_probe.yml", "scripts/verificar_secretos.py"]
consume = ["todas las compuertas"]
arbitro = "prueba de carga (50 conversaciones, 200 msg/min) con RNF-01 dentro de umbral; prueba de conexión negativa desde agent-net; sondeo de salud; arnés Exit Code 0"
entorno_arbitro = "carga_sintetica_local"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/carga/"
```
Entregables: suite de carga en `tests/integracion/carga/`, pipeline en `.github/workflows/` con prueba de conexión negativa desde `agent-net`, sondeo externo de `/health` y alertas conectadas al canal del administrador. **Estado:** Pendiente de prueba de carga sobre infraestructura final en Cloud Run / Cloud SQL (validada en simulación local).

---

## Ola 11 — Tanda 11 Comprobación con Plataformas de Nube (Fase II) y Despliegue: Salida de Beta, Meta Vendedores, Servidor de Producción y Móvil HTTPS

### T-411 — Comprobación Fase 5: evaluación integral de salida de beta
`¤bbap-glamping`
```toml
id = "T-411"
ola = 11
fase = 5
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["OP-10", "RNF-06", "RNF-10", "RNF-13", "US-11", "US-17"]
depende_de = ["T-410"]
bloqueada_por = []
propiedad = ["tests/integracion/test_fase5.py", "governance/tareas/TASK-005-seguridad-observabilidad.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase5.py; arnés Exit Code 0 con las cuatro suites de evaluación sobre umbral; métricas anotadas en TASK-005; aprobación del propietario"
entorno_arbitro = "evaluaciones_sinteticas_locales"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_fase5.py"
```
Entregables: verificación integral de seguridad y observabilidad en `tests/integracion/test_fase5.py` y acta de métricas en `TASK-005-seguridad-observabilidad.md`. **Estado:** Pendiente de evaluación de salida de beta con tráfico y usuarios reales (validada previamente en simulación local). **Hecho cuando** TASK-005 pasa a `sellada` y el propietario aprueba la salida de beta.

### T-511 — Comprobación Cloud Fase 6 (Meta Canal de Vendedores y Plantillas): venta de extremo a extremo y medición OP-08
`¤bbap-glamping`
```toml
id = "T-511"
ola = 11
fase = 6
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["US-05", "US-06", "US-07", "US-15", "OP-07", "OP-08"]
depende_de = ["T-510", "T-111"]
bloqueada_por = ["S-01"]
propiedad = ["tests/integracion/test_fase6.py", "governance/tareas/TASK-006-arm-jarvis.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase6.py (vendedor → ticket → validación en el panel → notificación con plantilla comision_validada aprobada en Meta); OP-08 medido; arnés Exit Code 0"
entorno_arbitro = "doble_meta_vendedores_y_fake_crm"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_fase6.py"
```
Entregables: prueba E2E de venta en `tests/integracion/test_fase6.py`, verificación con la plantilla `comision_validada` aprobada en Meta Cloud API y medición de `OP-08` documentada en `TASK-006-arm-jarvis.md`. **Estado:** Pendiente de verificación con canal de vendedores de Meta y plantilla aprobada en vivo (validada previamente con simulador). **Hecho cuando** TASK-006 pasa a `sellada`.

### T-610 — Despliegue en Servidor de Producción: `compose.production.yaml`, aislamiento del flujo contable y backups cifrados
`¤infra-hibrida`
```toml
id = "T-610"
ola = 11
fase = 7
estado = "pendiente"
sala = "infraestructura"
rol = "¤¤devops-engineer"
requisitos = ["RNF-14", "RNF-15", "INV_RED_AISLADA", "INV_MISMO_COMPOSE", "S-08"]
depende_de = ["T-601", "T-602", "T-603", "T-604", "T-410"]
bloqueada_por = ["S-08"]
propiedad = ["compose.production.yaml", "infra/backups/README.md", "infra/backups/backup.sh", "infra/backups/restaurar.sh", "tests/integracion/test_aislamiento_produccion.py"]
consume = ["todas las compuertas"]
arbitro = "stack levantado en el servidor propio con compose.production.yaml; tests/integracion/test_aislamiento_produccion.py verifica conexión negativa hacia servicios contables; restauración de backup documentada; arnés Exit Code 0"
entorno_arbitro = "compose_local"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_aislamiento_produccion.py"
```
Entregables: configuración productiva en `compose.production.yaml`, scripts de backup cifrado y restauración en `infra/backups/` (`backup.sh`, `restaurar.sh`, `README.md`), y prueba de aislamiento de red contable en `tests/integracion/test_aislamiento_produccion.py`. **Estado:** Pendiente de despliegue en servidor productivo en Google Cloud Platform (ADR-0019); validada en compose local.

### T-810 — Despliegue Cloud/HTTPS de la Terminal Móvil: proxy TLS, cabeceras `no-store` y claves VAPID Web Push
`¤infra-hibrida`
```toml
id = "T-810"
ola = 11
fase = 8
estado = "pendiente"
sala = "infraestructura"
rol = "¤¤devops-engineer"
requisitos = ["RF-PAN-11", "RF-PAN-12", "INV_SIN_SECRETOS_EN_REPO"]
depende_de = ["T-801", "T-310"]
bloqueada_por = []
propiedad = ["infra/proxy/Caddyfile", "infra/proxy/README.md", "infra/proxy/nginx.conf", "infra/proxy/vapid.env.example", "tests/integracion/test_terminal_movil_despliegue.py"]
consume = ["panel_operativo_service"]
arbitro = "tests/integracion/test_terminal_movil_despliegue.py (HTTPS, manifiesto y cabecera no-store); arnés Exit Code 0"
entorno_arbitro = "proxy_test_local"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_terminal_movil_despliegue.py"
```
Entregables: configuración del proxy inverso en `infra/proxy/` (`Caddyfile`, `nginx.conf`, `README.md`, `vapid.env.example`) para servir manifiesto y service worker por HTTPS conservando `Cache-Control: no-store`, variables VAPID declaradas sin secretos en el repositorio y prueba en `tests/integracion/test_terminal_movil_despliegue.py`. **Estado:** Pendiente de verificación bajo dominio HTTPS y Web Push VAPID en producción (validada con servidor de pruebas local).

---

## Ola 12 — Tanda 12 Cierre de Producción CRM en Nube y Extensión Condicional

### T-611 — Comprobación Cloud Fase 7 (Proveedor CRM Real): publicación firmada en vivo, primer cierre de período e hito de producción
`¤bbap-glamping`
```toml
id = "T-611"
ola = 12
fase = 7
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["RNF-09", "RNF-10", "US-08", "US-14", "US-16", "ON-03"]
depende_de = ["T-610", "T-511"]
bloqueada_por = ["ADR-0008", "S-05"]
propiedad = ["tests/integracion/test_fase7.py", "governance/tareas/TASK-007-integracion-crm.md"]
consume = ["todas las compuertas"]
arbitro = "tests/integracion/test_fase7.py (venta validada → CRM real firmado e idempotente → tablero → cierre → exportación); aprobación del propietario"
entorno_arbitro = "doble_fake_crm"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/integracion/test_fase7.py"
```
Entregables: prueba E2E de producción en `tests/integracion/test_fase7.py` contra el proveedor CRM elegido (`ADR-0008`/`S-05`) y cierre de `TASK-007-integracion-crm.md`. **Estado:** Pendiente de integración real contra SaaS de CRM en vivo (validada contra FakeCRM). **Hecho cuando** TASK-007 pasa a `sellada` y el propietario aprueba el hito de producción.

### T-701 — Panel operativo (condicional ADR-0010): inbox completo de conversaciones de huéspedes
`¤panel-operativo`
```toml
id = "T-701"
ola = 12
fase = 8
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-07 (extensión)", "TASK-008"]
depende_de = ["T-801"]
bloqueada_por = []
propiedad = [
  "features/panel_operativo/bff_internal.py",
  "features/panel_operativo/panel_operativo_service.py",
  "features/panel_operativo/tipos.py",
  "features/panel_operativo/config_panel_operativo.yaml",
  "features/panel_operativo/ui/p13_inbox_huespedes.ts",
  "features/panel_operativo/estaticos/app.js",
  "features/panel_operativo/estaticos/styles.css",
  "features/panel_operativo/ui/tests/bffSimulado.ts",
  "features/panel_operativo/ui/tests/inbox/inbox.spec.ts",
  "tests/panel_operativo/dobles.py",
  "tests/panel_operativo/test_bff_inbox.py",
  "tests/e2e/test_inbox_huespedes.py",
  "docs/modulos/panel_operativo.md",
]
crea = ["features/panel_operativo/ui/tests/inbox/inbox.spec.ts", "tests/panel_operativo/test_bff_inbox.py"]
consume = ["agente_service", "seguridad_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/e2e/test_inbox_huespedes.py; arnés Exit Code 0"
entorno_arbitro = "doble_testclient_fastapi"
fecha_arbitro = "2026-11-03"
comando_arbitro = "pytest tests/e2e/test_inbox_huespedes.py"

# Archivos compartidos dentro de la propia sala (rutas exactas de UX/UI, 2026-11-25). No son pruebas de otra sala (R2):
# el árbitro los admite como límite de alcance, no como permiso para tocar otra sala.
[limites]
"features/panel_operativo/estaticos/app.js" = "Solo el registro de la ruta y la navegación de P-13. No cambia el código de otras pantallas."
"features/panel_operativo/estaticos/styles.css" = "Solo añade clases con el prefijo .inbox-. No cambia tokens ni clases que ya existen, y el valor claro de --aviso pasa a #8A5300."
"features/panel_operativo/ui/tests/bffSimulado.ts" = "Solo añade respuestas simuladas de los endpoints del inbox. No cambia las que ya existen."
"tests/panel_operativo/dobles.py" = "Solo añade dobles para el inbox. No cambia los dobles que ya existen."
"features/panel_operativo/config_panel_operativo.yaml" = "Solo la clave del disparador de volumen del ADR-0010. No toca otras claves."
"docs/modulos/panel_operativo.md" = "Solo la sección de P-13."
```
Entregables: vista de inbox completo de conversaciones de huéspedes si se activa el disparador de volumen definido en `ADR-0010`. **Estado:** Pendiente de validación e2e con navegador real (Playwright) y tráfico real de WhatsApp (validada con TestClient).

---

## Ola 13 — Tanda 13 Corrección C1 Pasillo Central

### T-901 — Pasillo central: fail-fast en montaje de panel operativo y CRM sin captura silenciosa de excepciones
`¤pasillo-central`
```toml
id = "T-901"
ola = 13
fase = 9
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-PAN-01", "RF-CRM-01"]
depende_de = ["T-611"]
bloqueada_por = []
propiedad = ["app_core/main.py", "tests/app_core/test_error_montaje_panel.py"]
consume = ["panel_operativo_service", "crm_conector_service"]
arbitro = "tests/app_core/test_error_montaje_panel.py; arnés Exit Code 0"
entorno_arbitro = "local_pytest"
fecha_arbitro = "2026-11-22"
comando_arbitro = "pytest tests/app_core/test_error_montaje_panel.py"
```
Entregables: remoción de captura silenciosa `try/except Exception` en `app_core/main.py` para montaje de panel operativo y CRM, garantizando fallo explícito de `crear_app` ante error de montaje, y prueba unitaria en `tests/app_core/test_error_montaje_panel.py`.

---

## Ola 14 — Tanda 14 Corrección C2 Contratos de Compuertas

### T-902 — Contratos profundos: verificación exhaustiva de valores y errores entre dobles y compuertas reales derivados de FIRMAS_COMPUERTAS.json
`¤pasillo-central`
```toml
id = "T-902"
ola = 14
fase = 9
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["RNF-08", "RNF-10"]
depende_de = ["T-901"]
bloqueada_por = []
propiedad = ["tests/test_contratos_compuertas_vs_dobles.py"]
consume = ["todas las compuertas"]
arbitro = "tests/test_contratos_compuertas_vs_dobles.py; arnés Exit Code 0"
entorno_arbitro = "local_pytest"
fecha_arbitro = "2026-11-22"
comando_arbitro = "pytest tests/test_contratos_compuertas_vs_dobles.py"
```
Entregables: derivación programática de compuertas consumidas desde `FIRMAS_COMPUERTAS.json`, pruebas de contrato con aserciones estrictas de valor y error (no solo tipos), y tests de mutantes muertos con dobles alterados.

---

## Ola 15 — Tanda 15 Corrección C3 Escritura Conforme

### T-903 — Gobernanza: formalización de árbitro real para escritura conforme con casos sintéticos
`¤pasillo-central`
```toml
id = "T-903"
ola = 15
fase = 9
estado = "sellada"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = ["RNF-08"]
depende_de = ["T-902"]
bloqueada_por = []
propiedad = ["CLAUDE.md", "tests/test_escritura_conforme.py"]
consume = []
arbitro = "tests/test_escritura_conforme.py; arnés Exit Code 0"
entorno_arbitro = "local_pytest"
fecha_arbitro = "2026-11-22"
comando_arbitro = "pytest tests/test_escritura_conforme.py"
```
Entregables: prueba `tests/test_escritura_conforme.py` que audita UTF-8 sin BOM, ausencia de huellas abiertas e IP safety sobre el repositorio, casos de prueba sintéticos que fallan ante transgresiones, y actualización de `CLAUDE.md` para que los 7 árbitros ejecuten pruebas físicas y `check_arbitros_cliente.py` termine en Exit Code 0.

---

## Olas 16 a 19 — Plan v3: PII fuera del modelo, entorno de producción y ARM con inferencia

> **Origen:** dictámenes del Arquitecto ADPA G.I. del 2026-11-25 (`TL1_TL5` con A1-A5, `TL1_TL5.v2`, `T406_y_olas.v3` y `practicas_ortogonalidad`). Las olas A, B y C del plan v3 son las olas 16, 17 y 18 de este archivo; la 19 recibe la parte de pasillo de TL-2 (`T-508`). Fichas escritas con R1 a R3: archivos exactos, `crea` para lo que no existe y `limites` para cada prueba de otra sala.
>
> **Tareas del plan sin ficha en este archivo:** TL-1 (PR #5), T-406 (PR #6), G-1 (PR #7) y T-406-b (PR #8) se hicieron sin ficha en este archivo y ya están fusionados en `main`; ninguna ficha de las olas 16 a 19 queda bloqueada por ellas.

### T-408 — Herramientas MCP: anotaciones `x-pii` y `x-pii-exento` en los esquemas de salida (H-1)
`¤herramientas-mcp` `¤seguridad-canal`
```toml
id = "T-408"
ola = 16
fase = 5
estado = "pendiente"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-SEC-05", "RF-AG-04", "INV_PII_FUERA_DEL_MODELO"]
depende_de = ["T-504"]
bloqueada_por = []
propiedad = [
  "features/herramientas_glamping/esquemas/actualizar_calendario.json",
  "features/herramientas_glamping/esquemas/buscar_contacto_crm.json",
  "features/herramientas_glamping/esquemas/consultar_comision_propia.json",
  "features/herramientas_glamping/esquemas/consultar_disponibilidad.json",
  "features/herramientas_glamping/esquemas/cotizar.json",
  "features/herramientas_glamping/esquemas/crear_oportunidad_crm.json",
  "features/herramientas_glamping/esquemas/crear_reserva_preliminar.json",
  "features/herramientas_glamping/esquemas/obtener_instrucciones_checkin.json",
  "features/herramientas_glamping/esquemas/registrar_venta.json",
  "features/herramientas_glamping/esquemas/reportar_incidencia.json",
  "features/herramientas_glamping/esquemas/reportar_resultado_estadia.json",
  "features/herramientas_glamping/esquemas/responder_solicitud.json",
  "features/herramientas_glamping/esquemas/solicitar_humano.json",
  "features/herramientas_glamping/esquemas/solicitar_reserva.json",
  "tests/herramientas_glamping/test_x_pii_esquemas.py",
  "docs/modulos/herramientas_glamping.md",
]
crea = ["tests/herramientas_glamping/test_x_pii_esquemas.py"]
consume = ["seguridad_service (semántica de x-pii, decisión A1)"]
arbitro = "tests/herramientas_glamping/test_x_pii_esquemas.py; tests/herramientas_glamping/test_contratos.py; arnés Exit Code 0"
```
Entregables (decisión A1): la sala dueña del dato declara en el esquema de `salida` qué campos son PII. Un campo `x-pii` se tokeniza entero, sin detector; un campo `x-pii-exento` (por ejemplo `codigo_reserva`) solo queda exento si su esquema declara un `pattern`; todo campo de texto no declarado pasa por el detector. La prueba nueva recorre los catorce esquemas y falla si un `x-pii-exento` no trae `pattern` o si un campo con PII conocida (`contacto_emergencia`, `direccion`, nombres y teléfonos de contacto) queda sin anotar. `docs/modulos/herramientas_glamping.md` documenta la anotación. No toca el código de la sala: la compuerta ya expone `esquema_salida`.

### T-409 — Inferencia: espera ante 429 de 1,0 s con jitter, `Retry-After` y solo si cabe en el plazo (I-1, A4)
`¤inferencia`
```toml
id = "T-409"
ola = 16
fase = 5
estado = "pendiente"
sala = "inferencia"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-05"]
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = [
  "features/inferencia/config_inferencia.yaml",
  "features/inferencia/inferencia_service.py",
  "tests/inferencia/test_paso4_adr0021.py",
  "tests/inferencia/test_reintento_429.py",
]
crea = ["tests/inferencia/test_reintento_429.py"]
consume = ["observabilidad_service (cuota_inferencia, ya inyectada)"]
arbitro = "tests/inferencia/test_reintento_429.py; tests/inferencia/test_paso4_adr0021.py; arnés Exit Code 0"
```
Entregables (decisión A4): el reintento único ante 429 se mantiene (Decisión 6 del ADR-0021); cambia la espera. `espera_reintento_s: 1.0` con su jitter en `config_inferencia.yaml`; si el proveedor envía `Retry-After`, se respeta; el reintento solo ocurre si la espera cabe en el plazo restante y, si no cabe, falla cerrado con `InferenciaNoDisponible`. Pruebas nuevas en rojo primero. La Enmienda 2 del ADR-0021 no está en esta propiedad (`docs/adr/` es ruta del coordinador): entró por gobernanza y el propietario la aceptó el 2026-11-25.

### T-416 — Observabilidad: `run_evals` y la evaluación interna construyen `AgenteService` con `SeguridadService` real, y la suite `enrutador` no se omite en silencio
`¤observabilidad` `¤seguridad-canal`
```toml
id = "T-416"
ola = 16
fase = 5
estado = "pendiente"
sala = "observabilidad"
rol = "¤¤devops-engineer"
requisitos = ["RF-OBS-03", "RF-SEC-05"]
depende_de = ["T-402"]
bloqueada_por = []
propiedad = [
  "features/observabilidad/observabilidad_service.py",
  "scripts/run_evals.py",
  "tests/observabilidad/test_t416_enrutador_con_seguridad.py",
]
crea = ["tests/observabilidad/test_t416_enrutador_con_seguridad.py"]
consume = ["agente_service", "seguridad_service"]
arbitro = "tests/observabilidad/test_t416_enrutador_con_seguridad.py; scripts/run_evals.py --suite enrutador; arnés Exit Code 0"
```
Entregables: `features/observabilidad/observabilidad_service.py` (evaluación de la suite `enrutador`) y `scripts/run_evals.py` dejan de construir `AgenteService(cargar_config_agente())` sin `seguridad`: lo construyen con un `SeguridadService` real, importado por su compuerta. Funciona hoy sin romper nada, porque el parámetro ya existe, y deja libre a `T-407` para exigirlo (A2). La prueba nueva fija que la suite `enrutador` no queda omitida en silencio: hoy la llamada de `observabilidad_service.py` está envuelta en `except Exception: pass`. No pone un doble por defecto en `AgenteService`.

### T-417 — Agente: `estado_asistente()` informa si el asistente está disponible y por qué
`¤agente-enrutador`
```toml
id = "T-417"
ola = 16
fase = 5
estado = "pendiente"
sala = "agente"
rol = "¤¤backend-developer"
requisitos = ["RF-AG-05"]
depende_de = ["T-403"]
bloqueada_por = []
propiedad = [
  "features/agente/agente_service.py",
  "features/agente/tipos.py",
  "docs/modulos/agente.md",
  "tests/agente/test_estado_asistente.py",
]
crea = ["tests/agente/test_estado_asistente.py"]
consume = ["inferencia_service (estado)", "observabilidad_service"]
arbitro = "tests/agente/test_estado_asistente.py; tests/test_firmas_compuertas.py; arnés Exit Code 0"
```
Entregables: la compuerta añade `AgenteService.estado_asistente()`, que devuelve `EstadoAsistente(disponible, motivo, desde, derivadas)` (tipo nuevo en `features/agente/tipos.py`). Solo se añade un método: las firmas existentes no cambian (regla 4). `docs/modulos/agente.md` documenta el método y el tipo. Va en la ola 16 porque ninguna otra ficha de esa ola reclama archivos de `agente`; `T-407` (ola 17) y `T-415` (ola 18) vuelven a tocar `agente_service.py` y `agente.md` después.

### T-412 — Pasillo central: con `K_SERVICE` se exige PostgreSQL, SQLite solo en beta o prueba, y producción rechaza la clave efímera (P-1)
`¤pasillo-central`
```toml
id = "T-412"
ola = 17
fase = 5
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RNF-16", "RNF-18"]
depende_de = ["T-510", "T-901"]
bloqueada_por = []
propiedad = [
  "app_core/contenedor.py",
  "infra/gcp/cloudrun.yaml",
  "infra/gcp/cloudbuild.yaml",
  "tests/app_core/test_o1_entorno_cuota.py",
  "docs/modulos/app_core.md",
]
crea = ["tests/app_core/test_o1_entorno_cuota.py"]
consume = ["persistencia_sql_service (es_postgres)", "seguridad_service (estado().clave_efimera)", "observabilidad_service"]
arbitro = "tests/app_core/test_o1_entorno_cuota.py (rojo v2 del QA, con A14 y A15: 13 rojos y 13 guardas); arnés Exit Code 0"
```
Entregables (T1-a, O1 del QA): `K_SERVICE` manda: si está, `construir` exige PostgreSQL sea cual sea `APP_ENV`. Sin `K_SERVICE`, SQLite solo con `APP_ENV` en {beta, prueba}; cualquier otro valor, también uno desconocido, exige PostgreSQL. Un árbitro estático exige `APP_ENV=produccion` en `infra/gcp/cloudrun.yaml` y en el `run deploy` de `infra/gcp/cloudbuild.yaml`. En producción, `construir` rechaza `seguridad.estado().clave_efimera`. `tests/app_core/test_o1_entorno_cuota.py` define su propio entorno y **no importa** `ENTORNO_PRUEBA` de `tests/app_core/test_contenedor.py` (cada suite monta sus datos), porque `T-414` cambia esa constante en la misma ola. Es la única ficha de la ola 17 sobre `app_core/`; no reclama `tests/app_core/test_contenedor.py`, que es de `T-414`.

### T-407 — Agente: tokenizar cada salida de herramienta con `tokenizar_estructura` y exigir `seguridad` (A11 con A2)
`¤agente-enrutador` `¤seguridad-canal`
```toml
id = "T-407"
ola = 17
fase = 5
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-04", "RF-SEC-05", "INV_PII_FUERA_DEL_MODELO"]
depende_de = ["T-403", "T-408", "T-416", "T-417"]
bloqueada_por = []
propiedad = [
  "features/agente/agente_service.py",
  "features/agente/bucle_herramientas_internal.py",
  "docs/modulos/agente.md",
  "tests/agente/dobles.py",
  "tests/agente/test_pii_salidas_herramientas.py",
  "tests/agente/test_sin_doble_seguridad_en_servicios.py",
  "tests/agente/test_allowlist_herramientas.py",
  "tests/agente/test_bucle_herramientas.py",
  "tests/agente/test_enrutador.py",
  "tests/agente/test_enrutamiento_modelos.py",
  "tests/agente/test_planificador.py",
  "tests/agente/test_plazo_turno_adr0021.py",
  "tests/test_contratos_compuertas_vs_dobles.py",
]
crea = ["tests/agente/dobles.py", "tests/agente/test_pii_salidas_herramientas.py", "tests/agente/test_sin_doble_seguridad_en_servicios.py"]
consume = ["seguridad_service (tokenizar_estructura)", "herramientas_glamping_service (esquema_salida con x-pii)", "inferencia_service (solo en pruebas, con inyectar_cliente_de_prueba)", "observabilidad_service"]
arbitro = "tests/agente/test_pii_salidas_herramientas.py; tests/agente/test_sin_doble_seguridad_en_servicios.py; tests/agente/test_bucle_herramientas.py; arnés Exit Code 0"

[limites]
"tests/test_contratos_compuertas_vs_dobles.py" = "Solo la construcción de AgenteService real: recibe un doble de seguridad explícito. No cambia ninguna aserción."
```
Entregables (A1 y A2): justo antes de anexar el resultado al historial, `bucle_herramientas_internal.py` pasa `resultado_h.salida` por `seguridad.tokenizar_estructura(...)` con las anotaciones `x-pii` y `x-pii-exento` del esquema de salida (`T-408`); si la tokenización falla, el turno se degrada y la salida nunca llega a `inferencia`. `AgenteService` exige `seguridad`, sin valor por defecto; `_DobleSeguridadNulo` sale de `agente_service.py` y se muda a `tests/agente/dobles.py`; las pruebas de la sala que dependían del valor por defecto pasan el doble de forma explícita. La prueba de estructura exige que ningún `*_service.py` instancie un doble de seguridad.

### T-413 — Seguridad: la suite PII mide de verdad sobre `evals/pii.jsonl` (S-2, reabre T-401)
`¤seguridad-canal`
```toml
id = "T-413"
ola = 17
fase = 5
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-05", "RF-OBS-03"]
depende_de = ["T-401"]
bloqueada_por = []
propiedad = [
  "features/seguridad/seguridad_service.py",
  "evals/pii.jsonl",
  "tests/seguridad/test_evaluar_pii.py",
  "docs/modulos/seguridad.md",
]
crea = ["tests/seguridad/test_evaluar_pii.py"]
consume = ["observabilidad_service"]
arbitro = "tests/seguridad/test_evaluar_pii.py; scripts/run_evals.py --suite pii sobre umbral medido; arnés Exit Code 0"
```
Entregables: `SeguridadService.evaluar_pii` deja de devolver constantes y mide sobre `evals/pii.jsonl` (200 casos sintéticos, RF-SEC-05 e): recall de 100 % en teléfono, correo, documento y tarjeta, y al menos 95 % en nombres y direcciones. La prueba nueva falla si el archivo está vacío o si la métrica no depende de los casos. El fallo honesto de `T-401` (suite PII sin medir) se cierra con esta ficha.

### T-414 — Observabilidad: `AlmacenTrazas` abre con el `db_url` inyectado, sin `os.environ` (O-1, T1-b)
`¤observabilidad`
```toml
id = "T-414"
ola = 17
fase = 5
estado = "pendiente"
sala = "observabilidad"
rol = "¤¤devops-engineer"
requisitos = ["RF-OBS-02", "RNF-16"]
depende_de = ["T-402"]
bloqueada_por = []
propiedad = [
  "features/observabilidad/trazas_internal.py",
  "tests/observabilidad/test_o1_almacen_db_url.py",
  "tests/app_core/test_contenedor.py",
  "tests/app_core/test_mcp_compose.py",
  "tests/app_core/test_vendedores_app.py",
  "tests/app_core/test_webhook_app.py",
  "tests/app_core/test_worker_y_panel.py",
  "tests/integracion/carga/test_carga_concurrente.py",
  "tests/integracion/carga/test_sondeo_salud.py",
  "tests/integracion/test_fase1.py",
  "tests/integracion/test_fase3.py",
  "tests/integracion/test_fase4.py",
  "tests/integracion/test_fase5.py",
  "tests/integracion/test_fase6.py",
  "tests/integracion/test_fase7.py",
  "tests/integracion/test_terminal_movil_despliegue.py",
  "tests/test_interfaz_purificada.py",
]
crea = ["tests/observabilidad/test_o1_almacen_db_url.py"]
consume = ["persistencia_sql_service"]
arbitro = "tests/observabilidad/test_o1_almacen_db_url.py (6 casos, A1 a A6 de la spec); tests/observabilidad, tests/app_core, tests/integracion y tests/test_interfaz_purificada.py sin DATABASE_URL; arnés Exit Code 0"

[limites]
"tests/app_core/test_contenedor.py" = "Solo la constante ENTORNO_PRUEBA pierde DATABASE_URL."
"tests/app_core/test_mcp_compose.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/app_core/test_vendedores_app.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/app_core/test_webhook_app.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/app_core/test_worker_y_panel.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/carga/test_carga_concurrente.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/carga/test_sondeo_salud.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_fase1.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_fase3.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_fase4.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_fase5.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_fase6.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_fase7.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/integracion/test_terminal_movil_despliegue.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
"tests/test_interfaz_purificada.py" = "Solo se quita DATABASE_URL de la constante de entorno de la prueba."
```
Entregables: `AlmacenTrazas` abre la base con `config["db_url"]`, que `app_core` ya resuelve con el `env` inyectado, y deja de leer `os.environ`. **Primero en rojo:** demostrar que, con el arreglo aplicado y sin el ajuste de `ENTORNO_PRUEBA`, la suite `tests/app_core` falla; después, el ajuste del límite y la suite completa en verde. El verde corre `tests/observabilidad`, `tests/app_core`, `tests/integracion` y `tests/test_interfaz_purificada.py` sin `DATABASE_URL`: además de `ENTORNO_PRUEBA` (que también importa `tests/app_core/test_inferencia_con_tope.py`), otros 14 archivos arman su propio entorno con `"DATABASE_URL": "postgresql://prueba"` y, con el arreglo, intentarían conectar a un PostgreSQL inexistente (82 pruebas en rojo medidas por el Arquitecto). Esas pruebas usan SQLite en memoria: dejan de declarar PostgreSQL, y el almacén sigue fallando cerrado ante un PostgreSQL inalcanzable. Si al tomar T-414 alguna de T-111, T-211, T-311, T-410, T-411, T-511, T-810 o T-611 sigue sin sellar, T-414 rebasa su cambio de una línea sobre ella; quien llega después, carga.

### T-415 — Agente: los argumentos inválidos se devuelven al modelo, tokenizados (A8-bis, A5)
`¤agente-enrutador`
```toml
id = "T-415"
ola = 18
fase = 5
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-04", "RF-SEC-05"]
depende_de = ["T-407"]
bloqueada_por = []
propiedad = [
  "features/agente/bucle_herramientas_internal.py",
  "tests/agente/test_argumentos_invalidos.py",
  "docs/modulos/agente.md",
]
crea = ["tests/agente/test_argumentos_invalidos.py"]
consume = ["seguridad_service (tokenizar_estructura)", "herramientas_glamping_service", "observabilidad_service"]
arbitro = "tests/agente/test_argumentos_invalidos.py; tests/agente/test_bucle_herramientas.py; arnés Exit Code 0"
```
Entregables: si los argumentos de una llamada no validan (`EntradaInvalida`), el bucle devuelve al modelo un error tipado para que corrija la llamada, dentro del tope de iteraciones, en lugar de degradar el turno a `herramienta_caida`. El mensaje de error pasa por `tokenizar_estructura` antes de volver al modelo, porque puede repetir argumentos con PII (A5).

### T-507 — ARM «Jarvis»: extracción de ventas con el modelo a través de la compuerta `inferencia` (TL-2, sala)
`¤arm-jarvis` `¤inferencia`
```toml
id = "T-507"
ola = 18
fase = 6
estado = "pendiente"
sala = "arm_jarvis"
rol = "¤¤backend-developer"
requisitos = ["RF-ARM-02", "RF-SEC-05"]
depende_de = ["T-602", "T-407", "T-409"]
bloqueada_por = ["diseño con el Arquitecto: falla cerrada de inferencia y salida estructurada"]
propiedad = [
  "features/arm_jarvis/arm_jarvis_service.py",
  "features/arm_jarvis/extractor_internal.py",
  "features/arm_jarvis/config_arm_jarvis.yaml",
  "tests/arm_jarvis/test_extraccion_inferencia.py",
  "docs/modulos/arm_jarvis.md",
]
crea = ["tests/arm_jarvis/test_extraccion_inferencia.py"]
consume = ["inferencia_service", "seguridad_service (tokenizar_estructura)", "comisiones_service", "crm_conector_service", "canal_whatsapp_service", "observabilidad_service"]
arbitro = "tests/arm_jarvis/test_extraccion_inferencia.py (extracción correcta, inferencia falla cerrada, salida inválida no crea venta, reserva y conciliación de cuota); tests/test_interfaz_purificada.py; arnés Exit Code 0"
```
Entregables: `ArmJarvisService(..., inferencia=None)` acepta la compuerta como parámetro opcional (la firma solo crece); `extractor_internal.py` extrae de texto (nunca imágenes, Decisión 12 del ADR-0021) con prompts y esquema propios del ARM, y lo que envía a `inferencia` va tokenizado por `seguridad`. Las pruebas inyectan `inferencia` con `inyectar_cliente_de_prueba()`. No toca `app_core/`: la inyección en `app_core/contenedor.py` es de `T-508`, en la ola 19.

### G-2 — Gobernanza: árbitro de especificaciones de ficha (`docs/spec/tareas/<id>.md`, reglas E1-E7)
`¤spec-glamping` `¤tareas-glamping`
```toml
id = "G-2"
ola = 18
fase = 9
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤qa-engineer"
requisitos = []
depende_de = ["TASK-000"]
bloqueada_por = []
propiedad = ["scripts/verificar_especificaciones.py", "tests/test_verificar_especificaciones.py"]
crea = ["scripts/verificar_especificaciones.py", "tests/test_verificar_especificaciones.py"]
consume = []
arbitro = "tests/test_verificar_especificaciones.py"
```
Entregables: según `2026-11-25_spec_G-2.md` del QA. Las especificaciones de `docs/spec/tareas/` no están en esta propiedad: las escribe el Arquitecto en su propio PR.

### S-3 — Seguridad: `secretos_internal.py` sin `CLAVE_DEFECTO_BOVEDA`, con aviso de clave efímera y `InvalidTag` como marcador neutro
`¤seguridad-canal`
```toml
id = "S-3"
ola = 18
fase = 5
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-PRIV-04", "INV_SIN_SECRETOS_EN_REPO"]
depende_de = ["T-401"]
bloqueada_por = []
propiedad = ["features/seguridad/secretos_internal.py", "features/seguridad/pii_internal.py", "tests/seguridad/test_s3_secretos_clave_efimera.py"]
crea = ["tests/seguridad/test_s3_secretos_clave_efimera.py"]
consume = []
arbitro = "tests/seguridad/test_s3_secretos_clave_efimera.py"

[limites]
"features/seguridad/pii_internal.py" = "Solo añade clave_efimera_del_proceso() -> str, que devuelve la clave efímera que ya usa PIIRedactor; no cambia nada más."
```
Entregables: `secretos_internal.py` deja de importar `CLAVE_DEFECTO_BOVEDA`; reporta cuando usa la clave efímera; ante `InvalidTag` actúa como T-406-b (C2): devuelve el marcador neutro y registra un aviso sin PII, en lugar de lanzar. El marcador neutro de `rehidratar_secretos` es `[DATO_BORRADO]` y la advertencia va por `logging`, sin dependencia nueva de `observabilidad_service`. `pii_internal.py` solo gana `clave_efimera_del_proceso()`, para que el gestor comparta la clave efímera de `PIIRedactor`. Va en la ola 18 porque la 17 ya tiene cuatro fichas; es disjunta de `T-413` (S-2).

### T-508 — Pasillo central: `app_core` inyecta `inferencia` en `ArmJarvisService` (TL-2, pasillo)
`¤pasillo-central` `¤arm-jarvis`
```toml
id = "T-508"
ola = 19
fase = 6
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-ARM-02"]
depende_de = ["T-507", "T-412"]
bloqueada_por = []
propiedad = ["app_core/contenedor.py", "tests/app_core/test_arm_con_inferencia.py"]
crea = ["tests/app_core/test_arm_con_inferencia.py"]
consume = ["arm_jarvis_service", "inferencia_service"]
arbitro = "tests/app_core (suite completa); tests/arm_jarvis/test_extraccion_inferencia.py; arnés Exit Code 0"

[limites]
"app_core/contenedor.py" = "Pasa inferencia= a ArmJarvisService y mueve, sin cambiarlo, el bloque que construye InferenciaService (sin_tope_compartido, inferencia y su comentario) antes de la construcción del ARM."
```
Entregables: `construir` pasa a `ArmJarvisService` la misma instancia de `InferenciaService` que ya recibe el agente. Es la única ficha de la ola 19 sobre `app_core/`.

### T-420 — Agente: la pausa dinámica del asistente (cuota agotada, proveedor caído o modelo lento)
`¤agente-enrutador` `¤inferencia`
```toml
id = "T-420"
ola = 19
fase = 5
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-05", "RF-PAN-09"]
depende_de = ["T-415", "T-417"]
bloqueada_por = []
propiedad = [
  "features/agente/tipos.py",
  "features/agente/bucle_herramientas_internal.py",
  "features/agente/agente_service.py",
  "docs/modulos/agente.md",
  "tests/agente/test_pausa_dinamica.py",
]
crea = ["tests/agente/test_pausa_dinamica.py"]
consume = ["inferencia_service (códigos de InferenciaNoDisponible, a través de ClienteModelo)", "observabilidad_service"]
arbitro = "tests/agente/test_pausa_dinamica.py; tests/agente/test_estado_asistente.py; tests/test_firmas_compuertas.py; arnés Exit Code 0"

# Archivos de la sala que ya tocaron T-417 (ola 16), T-407 (ola 17) y T-415 (ola 18).
[limites]
"features/agente/tipos.py" = "Solo añade el campo Respuesta.motivo_degradacion (al final, con defecto \"\") y la constante MOTIVOS_PAUSA."
"features/agente/bucle_herramientas_internal.py" = "Solo _generar_degradacion y las dos ramas de error del modelo fijan motivo_degradacion; los textos de cara al huésped no cambian."
"features/agente/agente_service.py" = "Solo la transición de la pausa después de self._bucle.ejecutar, la copia de motivo_degradacion en la respuesta final y estado_asistente."
"docs/modulos/agente.md" = "Solo la sección de estado_asistente."
```
Entregables: el motivo de cada degradación viaja en `Respuesta.motivo_degradacion`. Si el modelo falla por cuota agotada, proveedor caído o tiempo agotado, `estado_asistente()` informa una pausa con ese código, hasta que el modelo vuelve a responder. Los textos al huésped no cambian.

### T-702 — Panel operativo: estado del asistente en el inicio (P-02), los handoffs (P-08) y la salud del sistema (P-11)
`¤panel-operativo`
```toml
id = "T-702"
ola = 20
fase = 8
estado = "pendiente"
sala = "panel_operativo"
rol = "¤¤frontend-developer"
requisitos = ["RF-PAN-09", "RF-AG-05"]
depende_de = ["T-417", "T-420", "T-701"]
bloqueada_por = []
propiedad = [
  "features/panel_operativo/bff_internal.py",
  "features/panel_operativo/panel_operativo_service.py",
  "features/panel_operativo/tipos.py",
  "features/panel_operativo/estaticos/app.js",
  "features/panel_operativo/estaticos/styles.css",
  "features/panel_operativo/ui/tests/asistente/estado.spec.ts",
  "features/panel_operativo/ui/tests/bffSimulado.ts",
  "tests/panel_operativo/dobles.py",
  "tests/panel_operativo/test_bff_estado_asistente.py",
  "docs/modulos/panel_operativo.md",
]
crea = ["features/panel_operativo/ui/tests/asistente/estado.spec.ts", "tests/panel_operativo/test_bff_estado_asistente.py"]
consume = ["agente_service (estado_asistente)", "seguridad_service", "observabilidad_service"]
arbitro = "tests/panel_operativo/test_bff_estado_asistente.py; features/panel_operativo/ui/tests/asistente/estado.spec.ts; arnés Exit Code 0"

# Archivos compartidos dentro de la propia sala; T-701 (ola 12) también los toca.
[limites]
"features/panel_operativo/bff_internal.py" = "Solo GET /inicio, GET /admin/salud y, si la especificación lo decide, el endpoint de handoffs (P-08) añaden estado_asistente a su respuesta."
"features/panel_operativo/panel_operativo_service.py" = "Solo lee agente.estado_asistente() para el inicio y para estado_sistema."
"features/panel_operativo/tipos.py" = "Solo añade el campo del estado del asistente a EstadoSistema."
"features/panel_operativo/estaticos/app.js" = "Solo muestra el estado del asistente en las vistas de inicio, de salud y de handoffs (P-08)."
"features/panel_operativo/estaticos/styles.css" = "Solo añade clases .asistente-; no cambia tokens ni clases existentes."
"features/panel_operativo/ui/tests/bffSimulado.ts" = "Solo añade las respuestas simuladas de estado_asistente; no cambia las que ya existen."
"tests/panel_operativo/dobles.py" = "Solo añade estado_asistente a DobleAgenteService; no cambia los dobles existentes."
"docs/modulos/panel_operativo.md" = "Solo las secciones de P-02, P-08 y de salud del sistema (P-11)."
```
Entregables: `GET /inicio` (`bff_internal.py`, `inicio_endpoint`) y `GET /admin/salud` (`bff_internal.py`, `salud_sistema_endpoint`, que sirve `PanelOperativoService.estado_sistema`) exponen el `EstadoAsistente` que devuelve `agente.estado_asistente()` por la compuerta. La interfaz lo muestra en el inicio, en la salud del sistema y en P-08 Handoffs (franja `role="status"` y chip «Asistente en pausa», en `estaticos/app.js` y `estaticos/styles.css`; la pausa usa `--aviso`). P-08 lo toma de `GET /inicio`. La salud del sistema es una vista mínima: una rama `salud` en `navegar` que llama a `GET /panel/api/admin/salud`, con la franja del asistente; las métricas OP-01 a OP-10 y el resto de P-11 no entran. Su arnés de interfaz va en `ui/tests/asistente/estado.spec.ts`. La pausa muestra su causa (`motivo`) y no presenta "disponible" como garantía de cuota ni de proveedor activos. Los textos de cara al equipo los fija el UX/UI y el PR trae pegado el Playwright en verde.

### T-421 — Agente: la derivación a una persona (PERSONA, persona, humano y agente) y la oferta en los prompts
`¤agente-enrutador` `¤seguridad-canal`
```toml
id = "T-421"
ola = 20
fase = 5
estado = "pendiente"
sala = "agente"
rol = "¤¤machine-learning-engineer"
requisitos = ["RF-AG-05", "RF-MCP-06"]
depende_de = ["T-420"]
bloqueada_por = []
propiedad = [
  "features/agente/derivacion_internal.py",
  "features/agente/agente_service.py",
  "docs/prompts/system-prompt-glamping.md",
  "docs/prompts/system-prompt-hospedaje.md",
  "docs/prompts/system-prompt-departamentos.md",
  "docs/modulos/agente.md",
  "tests/agente/test_derivacion_persona.py",
]
crea = ["features/agente/derivacion_internal.py", "tests/agente/test_derivacion_persona.py"]
consume = ["herramientas_glamping_service (solicitar_humano)"]
arbitro = "tests/agente/test_derivacion_persona.py; tests/agente/test_estado_asistente.py; tests/test_firmas_compuertas.py; arnés Exit Code 0"

# agente_service.py ya lo tocaron T-417 (ola 16), T-407 (ola 17), T-415 (ola 18) y T-420 (ola 19).
[limites]
"features/agente/agente_service.py" = "Solo el método derivar_a_persona y la comprobación de la palabra clave en atender, entre el silencio y la tokenización."
"docs/prompts/system-prompt-glamping.md" = "Solo el párrafo de la regla de derivación."
"docs/prompts/system-prompt-hospedaje.md" = "Solo el párrafo de la regla de derivación."
"docs/prompts/system-prompt-departamentos.md" = "Solo el párrafo de la regla de derivación."
"docs/modulos/agente.md" = "Solo la sección de la derivación."
```
Entregables: PERSONA, persona, humano y agente, como mensaje completo y normalizado, derivan a una persona sin llamar al modelo (`AgenteService.derivar_a_persona`), y los tres prompts traen la oferta "¿Prefieres que te atienda una persona? Escribe PERSONA".

### T-422 — Seguridad: el aviso LOPDP del primer mensaje, con texto, versión y hash (`aviso_primer_mensaje`)
`¤seguridad-canal` `¤inferencia`
```toml
id = "T-422"
ola = 20
fase = 5
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-PRIV-01", "RF-SEC-05"]
depende_de = ["S-3"]
bloqueada_por = []
propiedad = [
  "features/seguridad/consentimiento_internal.py",
  "features/seguridad/seguridad_service.py",
  "features/seguridad/tipos.py",
  "features/seguridad/config_seguridad.yaml",
  "docs/modulos/seguridad.md",
  "tests/seguridad/test_consentimiento.py",
  "tests/integracion/test_fase5.py",
  "tests/seguridad/test_identidad.py",
  "tests/seguridad/test_aviso_primer_mensaje.py",
]
crea = ["tests/seguridad/test_aviso_primer_mensaje.py"]
consume = []
arbitro = "tests/seguridad/test_aviso_primer_mensaje.py; tests/seguridad/test_consentimiento.py; tests/integracion/test_fase5.py; arnés Exit Code 0"

# Cada ruta de propiedad se limita a lo que dice su especificación (T-422).
[limites]
"features/seguridad/consentimiento_internal.py" = "Solo el texto, la versión y el registro del aviso."
"features/seguridad/seguridad_service.py" = "Solo aviso_primer_mensaje, registrar_aviso_enviado y el paso 5 de filtrar_entrada."
"features/seguridad/tipos.py" = "Solo AvisoPrivacidad y AvisoNoDisponible."
"features/seguridad/config_seguridad.yaml" = "Solo la clave aviso."
"docs/modulos/seguridad.md" = "Solo la sección del aviso."
"tests/seguridad/test_consentimiento.py" = "Solo las aserciones sobre la versión del aviso y sobre cuándo se registra."
"tests/integracion/test_fase5.py" = "Solo las aserciones sobre la versión del aviso y sobre cuándo se registra."
"tests/seguridad/test_identidad.py" = "Solo las aserciones sobre la versión del aviso y sobre cuándo se registra."
```
Entregables: `SeguridadService.aviso_primer_mensaje(pais)` devuelve el aviso aprobado de la Enmienda 3 con versión 2.0 y hash, y falla cerrado sin país o sin enlace https. El aviso se registra cuando se envía (`registrar_aviso_enviado`), no al filtrar. Fuera de alcance: las columnas de hash, canal y respuesta del huésped, que solo necesita la variante con consentimiento, todavía [DECISIÓN PENDIENTE].

### T-509 — Pasillo central: el lazo del huésped (filtro de entrada, aviso LOPDP y respuesta enviada)
`¤pasillo-central` `¤seguridad-canal` `¤canal-whatsapp`
```toml
id = "T-509"
ola = 21
fase = 5
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RF-PRIV-01", "RF-GW-06", "RF-SEC-01", "RF-AG-05"]
depende_de = ["T-421", "T-422", "T-508"]
bloqueada_por = []
propiedad = [
  "app_core/lazo_huesped.py",
  "app_core/contenedor.py",
  "tests/app_core/test_contenedor.py",
  ".env.example",
  "infra/gcp/cloudrun.yaml",
  "docs/modulos/app_core.md",
  "tests/app_core/test_lazo_huesped.py",
]
crea = ["app_core/lazo_huesped.py", "tests/app_core/test_lazo_huesped.py"]
consume = [
  "seguridad_service (filtrar_entrada, aviso_primer_mensaje, registrar_aviso_enviado)",
  "agente_service (atender, derivar_a_persona)",
  "canal_whatsapp_service (enviar)",
  "inferencia_service (estado)",
]
arbitro = "tests/app_core/test_lazo_huesped.py; tests/app_core/test_contenedor.py; arnés Exit Code 0"

# app_core/contenedor.py ya lo toca T-508 (ola 19); esta ficha va después y solo cambia el receptor de huéspedes.
[limites]
"app_core/contenedor.py" = "Solo la línea que registra el receptor de huéspedes."
"tests/app_core/test_contenedor.py" = "Solo la aserción del receptor de huéspedes."
".env.example" = "Solo la línea PRIVACIDAD_URL."
"infra/gcp/cloudrun.yaml" = "Solo la variable PRIVACIDAD_URL en env, sin secretKeyRef."
"docs/modulos/app_core.md" = "Solo la sección del lazo del huésped."
```
Entregables: el receptor de huéspedes pasa a ser `LazoHuesped`: filtra la entrada, envía el aviso antes del primer mensaje al modelo, falla cerrado hacia una persona y envía la respuesta del agente. Hallazgo medido sobre `origin/main ecf9119`: en producción la respuesta del agente nunca llega al huésped y `filtrar_entrada` no tiene llamador fuera de `tests/` (`contenedor.py:325`, `trabajador_internal.py:140-145`, `enrutamiento_canal_internal.py:166`). Fuera de alcance: botones y listas con formato propio, el lazo del canal de vendedores, la cortesía de caída por conversación y la variante con consentimiento, todavía [DECISIÓN PENDIENTE].

### T-423 — Seguridad: rotación de `PII_VAULT_KEY` con clave anterior de respaldo y reencriptado por lotes
`¤seguridad-canal`
```toml
id = "T-423"
ola = 21
fase = 5
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-05", "RF-SEC-08"]
depende_de = ["T-412", "S-3", "T-422"]
bloqueada_por = []
propiedad = [
  "features/seguridad/rotacion_internal.py",
  "features/seguridad/pii_internal.py",
  "features/seguridad/secretos_internal.py",
  "features/seguridad/seguridad_service.py",
  "features/seguridad/tipos.py",
  "features/seguridad/config_seguridad.yaml",
  "scripts/rotar_pii_vault_key.py",
  "docs/operacion/ROTACION_PII_VAULT_KEY.md",
  "docs/modulos/seguridad.md",
  "tests/seguridad/test_t423_rotacion_pii_vault_key.py",
]
crea = ["features/seguridad/rotacion_internal.py", "scripts/rotar_pii_vault_key.py", "docs/operacion/ROTACION_PII_VAULT_KEY.md", "tests/seguridad/test_t423_rotacion_pii_vault_key.py"]
consume = ["persistencia_sql_service (envolver, es_postgres)"]
arbitro = "tests/seguridad/test_t423_rotacion_pii_vault_key.py; tests/seguridad; tests/app_core/test_o1_entorno_cuota.py; arnés Exit Code 0"

[limites]
"features/seguridad/pii_internal.py" = "Solo la lectura de la clave anterior y el descifrado de respaldo."
"features/seguridad/secretos_internal.py" = "Solo la lectura de la clave anterior y el descifrado de respaldo."
"features/seguridad/seguridad_service.py" = "Solo la resolución de pii.clave_anterior y los dos métodos nuevos."
"features/seguridad/tipos.py" = "Solo EstadoRotacion y ResultadoRotacion."
"features/seguridad/config_seguridad.yaml" = "Solo pii.clave_anterior."
"docs/modulos/seguridad.md" = "Solo la sección de la bóveda."
```
Entregables: La bóveda se cifra siempre con `PII_VAULT_KEY` y se descifra con esa o, si no abre, con `PII_VAULT_KEY_ANTERIOR`. `SeguridadService.reencriptar_boveda` y `estado_rotacion_boveda` y el script `scripts/rotar_pii_vault_key.py` vuelven a cifrar lo guardado con la clave anterior, por lotes y sin repetir trabajo, y avisan con código de salida cuándo se puede retirar la clave anterior. `docs/operacion/ROTACION_PII_VAULT_KEY.md` explica el procedimiento en cinco pasos. La falla cerrada de T-412 se mantiene. Los pasos en Google Cloud los ejecuta el propietario por medio de Antigravity.

### T-425 — Inferencia: `InferenciaService.transcribir`, el audio del huésped se transcribe con Gemini en Vertex y se descarta
`¤inferencia`
```toml
id = "T-425"
ola = 22
fase = 5
estado = "pendiente"
sala = "inferencia"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-05 (medios: recibe audio)", "RF-PRIV-01", "RF-PRIV-02"]
depende_de = ["T-409"]
bloqueada_por = ["respuesta del abogado sobre la voz (la Enmienda 4 del ADR-0021 ya está aceptada)"]
propiedad = [
  "features/inferencia/inferencia_service.py",
  "features/inferencia/tipos.py",
  "features/inferencia/config_inferencia.yaml",
  "docs/modulos/inferencia.md",
  "tests/inferencia/test_transcripcion_audio.py",
]
crea = ["docs/modulos/inferencia.md", "tests/inferencia/test_transcripcion_audio.py"]
consume = []
arbitro = "tests/inferencia/test_transcripcion_audio.py; tests/inferencia; tests/test_firmas_compuertas.py; arnés Exit Code 0"

[limites]
"features/inferencia/inferencia_service.py" = "Solo transcribir y la extracción del reintento y de la reserva de cuota a una función privada compartida, sin cambiar la conducta de generar."
"features/inferencia/tipos.py" = "Solo Transcripcion."
"features/inferencia/config_inferencia.yaml" = "Solo la clave audio."
"docs/modulos/inferencia.md" = "Archivo nuevo, solo la sección de la transcripción."
```
Entregables: `InferenciaService.transcribir` convierte un audio en texto con Gemini en Vertex, con la falla cerrada, la lista blanca, el tope diario, el plazo y el único reintento de `generar`. El audio se procesa y se descarta: ninguna parte de la sala lo conserva. El `bloqueada_por` es informativo: el código se construye y se sella con pruebas; lo que sigue bloqueado es el tráfico real con audio.

### T-426 — Canal WhatsApp: `CanalWhatsappService.con_audio`, el audio se entrega a una función y se elimina siempre
`¤canal-whatsapp`
```toml
id = "T-426"
ola = 22
fase = 5
estado = "pendiente"
sala = "canal_whatsapp"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-05"]
depende_de = ["T-101"]
bloqueada_por = []
propiedad = [
  "features/canal_whatsapp/canal_whatsapp_service.py",
  "features/canal_whatsapp/medios_internal.py",
  "features/canal_whatsapp/persistencia_internal.py",
  "docs/modulos/canal_whatsapp.md",
  "tests/canal_whatsapp/test_audio_efimero.py",
]
crea = ["tests/canal_whatsapp/test_audio_efimero.py"]
consume = ["seguridad_service", "observabilidad_service"]
arbitro = "tests/canal_whatsapp/test_audio_efimero.py; tests/canal_whatsapp; tests/test_firmas_compuertas.py; arnés Exit Code 0"

[limites]
"features/canal_whatsapp/canal_whatsapp_service.py" = "Solo el método con_audio."
"features/canal_whatsapp/medios_internal.py" = "Solo eliminar en AlmacenamientoMedios y GestorMedios.con_audio."
"features/canal_whatsapp/persistencia_internal.py" = "Solo eliminar_medio."
"docs/modulos/canal_whatsapp.md" = "Solo la sección del audio."
```
Entregables: `CanalWhatsappService.con_audio` entrega los bytes y el tipo MIME de un audio a una función y elimina siempre el medio, del almacén y de `canal.medios`, también cuando algo falla.

### T-427 — Pasillo central: el lazo del huésped transcribe el audio (apagado por omisión)
`¤pasillo-central` `¤inferencia` `¤canal-whatsapp`
```toml
id = "T-427"
ola = 23
fase = 5
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤integration-engineer"
requisitos = ["RF-GW-05 (medios: recibe audio)", "RF-PRIV-01"]
depende_de = ["T-509", "T-425", "T-426"]
bloqueada_por = ["respuesta del abogado sobre la voz (la Enmienda 4 del ADR-0021 ya está aceptada)"]
propiedad = [
  "app_core/lazo_huesped.py",
  "app_core/contenedor.py",
  "tests/app_core/test_lazo_huesped.py",
  ".env.example",
  "infra/gcp/cloudrun.yaml",
  "docs/modulos/app_core.md",
  "tests/app_core/test_lazo_audio.py",
]
crea = ["tests/app_core/test_lazo_audio.py"]
consume = ["canal_whatsapp_service", "inferencia_service", "seguridad_service", "agente_service"]
arbitro = "tests/app_core/test_lazo_audio.py; tests/app_core; tests/canal_whatsapp; arnés Exit Code 0"

[limites]
"app_core/lazo_huesped.py" = "Solo el camino del audio (R1 a R7) y el parámetro audio_activo."
"app_core/contenedor.py" = "Solo la línea que construye LazoHuesped, para pasarle audio_activo."
"tests/app_core/test_lazo_huesped.py" = "Solo el tipo AUDIO en las filas de A13 y A16."
".env.example" = "Solo la línea AUDIO_TRANSCRIPCION."
"infra/gcp/cloudrun.yaml" = "Solo la variable AUDIO_TRANSCRIPCION en env, sin secretKeyRef."
"docs/modulos/app_core.md" = "Solo la sección del audio en el lazo del huésped."
```
Entregables: `LazoHuesped` transcribe el audio del huésped después del aviso, filtra y tokeniza la transcripción y la atiende como un mensaje normal. Ningún paso guarda el audio. Un audio con texto también se transcribe y el agente recibe el texto y la transcripción. Si la transcripción falla, el huésped recibe la petición de explicarse (T-509), o solo se atiende su texto si lo trae. Nace apagado con `AUDIO_TRANSCRIPCION=0`. El `bloqueada_por` es informativo: lo que sigue bloqueado es el tráfico real con audio.

### T-428 — Seguridad: el detector de PII redacta correos con tilde y nombres propios sin introductor
`¤seguridad-canal`
```toml
id = "T-428"
ola = 22
fase = 5
estado = "pendiente"
sala = "seguridad"
rol = "¤¤security-engineer"
requisitos = ["RF-SEC-05"]
depende_de = ["T-412", "T-413"]
bloqueada_por = []
propiedad = [
  "features/seguridad/pii_internal.py",
  "features/seguridad/nombres_propios.yaml",
  "evals/pii_nombres.jsonl",
  "docs/modulos/seguridad.md",
  "tests/seguridad/test_pii_nombres_correos.py",
]
crea = ["features/seguridad/nombres_propios.yaml", "evals/pii_nombres.jsonl", "tests/seguridad/test_pii_nombres_correos.py"]
consume = []
arbitro = "tests/seguridad/test_pii_nombres_correos.py; tests/seguridad; arnés Exit Code 0"

[limites]
"features/seguridad/pii_internal.py" = "Solo RX_CORREO, RX_NOMBRE, la detección de nombres y la carga del archivo de nombres."
"docs/modulos/seguridad.md" = "Solo la sección de la detección de nombres."
```
Entregables: El detector de PII redacta correos con tilde y nombres propios sin introductor (introductores de parentesco, tratamientos y un diccionario de nombres sin ambiguos), sin tokenizar palabras comunes ni lugares; falla cerrado si falta `nombres_propios.yaml`. Se mide con `evals/pii_nombres.jsonl`.

### T-429 — ARM «Jarvis»: `seguridad` obligatoria en `ArmJarvisService` y retiro del doble por defecto
`¤arm-jarvis`
```toml
id = "T-429"
ola = 25
fase = 5
estado = "pendiente"
sala = "arm_jarvis"
rol = "¤¤integration-engineer"
requisitos = ["RF-SEC-05"]
depende_de = ["T-407", "T-507", "T-431"]
bloqueada_por = []
propiedad = [
  "features/arm_jarvis/arm_jarvis_service.py",
  "tests/agente/test_sin_doble_seguridad_en_servicios.py",
  "tests/arm_jarvis/test_ventas_multiples.py",
  "tests/arm_jarvis/test_asistente_lider.py",
  "tests/arm_jarvis/test_notificacion.py",
  "tests/arm_jarvis/test_tablero.py",
  "tests/arm_jarvis/test_comision.py",
  "tests/arm_jarvis/test_ingesta.py",
  "tests/arm_jarvis/test_consulta_comision.py",
  "tests/arm_jarvis/test_estados.py",
  "tests/arm_jarvis/test_ticket.py",
  "tests/test_contratos_compuertas_vs_dobles.py",
  "docs/modulos/arm_jarvis.md",
  "tests/arm_jarvis/test_seguridad_obligatoria.py",
]
crea = ["tests/arm_jarvis/test_seguridad_obligatoria.py"]
consume = ["seguridad_service"]
arbitro = "tests/arm_jarvis/test_seguridad_obligatoria.py; tests/arm_jarvis; tests/observabilidad; tests/agente/test_sin_doble_seguridad_en_servicios.py; arnés Exit Code 0"

[limites]
"features/arm_jarvis/arm_jarvis_service.py" = "Solo el constructor (seguridad obligatoria) y el import de DobleSeguridad."
"tests/agente/test_sin_doble_seguridad_en_servicios.py" = "Solo retirar EXCEPCIONES."
"tests/test_contratos_compuertas_vs_dobles.py" = "Solo pasar seguridad= en cada construcción."
"docs/modulos/arm_jarvis.md" = "Solo la línea de la compuerta."
```
Entregables: `ArmJarvisService` exige `seguridad` y retira el doble por defecto; se retira la excepción nominal de T-407. Los nueve archivos de `tests/arm_jarvis/` de la propiedad solo pasan `seguridad=` en cada construcción. De otra sala toca solo pruebas con su límite (`tests/agente/test_sin_doble_seguridad_en_servicios.py` y `tests/test_contratos_compuertas_vs_dobles.py`). El código de `observabilidad` y `scripts/run_evals.py` lo cambia T-431 antes, en la ola 24.

### T-431 — Observabilidad: las evaluaciones de ventas pasan una seguridad real al ARM
`¤arm-jarvis`
```toml
id = "T-431"
ola = 24
fase = 5
estado = "pendiente"
sala = "observabilidad"
rol = "¤¤integration-engineer"
requisitos = ["RF-SEC-05"]
depende_de = ["T-416"]
bloqueada_por = []
propiedad = [
  "features/observabilidad/observabilidad_service.py",
  "scripts/run_evals.py",
  "tests/observabilidad/test_ventas_con_seguridad.py",
]
crea = ["tests/observabilidad/test_ventas_con_seguridad.py"]
consume = ["seguridad_service"]
arbitro = "tests/observabilidad/test_ventas_con_seguridad.py; tests/observabilidad; tests/arm_jarvis; arnés Exit Code 0"

[limites]
"features/observabilidad/observabilidad_service.py" = "Solo la construcción de la suite ventas."
"scripts/run_evals.py" = "Solo la construcción de la suite ventas."
```
Entregables: Las dos evaluaciones de ventas (`ObservabilidadService.evaluar` y `scripts/run_evals.py`) construyen `ArmJarvisService` con una `seguridad` real, antes de que T-429 la haga obligatoria. Cada ficha toca solo su sala.

### T-430 — Pasillo central: el arranque productivo exige Vertex configurado
`¤pasillo-central`
```toml
id = "T-430"
ola = 24
fase = 5
estado = "pendiente"
sala = "pasillo_central"
rol = "¤¤solutions-architect"
requisitos = ["RNF-18"]
depende_de = ["T-412", "T-427"]
bloqueada_por = []
propiedad = [
  "app_core/contenedor.py",
  "docs/modulos/app_core.md",
  "tests/app_core/test_inferencia_obligatoria_en_produccion.py",
]
crea = ["tests/app_core/test_inferencia_obligatoria_en_produccion.py"]
consume = ["inferencia_service"]
arbitro = "tests/app_core/test_inferencia_obligatoria_en_produccion.py; tests/app_core/test_o1_entorno_cuota.py; tests/app_core/test_r4_cuota_produccion.py; arnés Exit Code 0"

[limites]
"app_core/contenedor.py" = "Solo la comprobación nueva, justo después de construir InferenciaService."
"docs/modulos/app_core.md" = "Solo la sección del arranque productivo."
```
Entregables: El arranque productivo (`K_SERVICE` o entorno fuera de beta y prueba) falla cerrado con un mensaje fijo si faltan `GOOGLE_CLOUD_PROJECT` o una `VERTEX_LOCATION` permitida, si hay una clave de API en el entorno o si falta el SDK `google-genai`. El arranque sin tope diario sigue permitido (T-412 R2).

### T-418 — Web pública: el valor claro de `--aviso` pasa a `#8A5300` (contraste AA)
`¤web-huespedes`
```toml
id = "T-418"
ola = 19
fase = 5
estado = "pendiente"
sala = "web_huespedes"
rol = "¤¤frontend-developer"
requisitos = ["RF-WEB-01"]
depende_de = ["T-405"]
bloqueada_por = []
propiedad = ["features/web_huespedes/templates/base.html", "tests/web_huespedes/test_token_aviso.py"]
crea = ["tests/web_huespedes/test_token_aviso.py"]
consume = []
arbitro = "tests/web_huespedes/test_token_aviso.py; arnés Exit Code 0"

[limites]
"features/web_huespedes/templates/base.html" = "Solo el valor claro de --aviso pasa a #8A5300."
```
Entregables: en `features/web_huespedes/templates/base.html`, el token `--aviso` del tema claro pasa de `#B26A00` a `#8A5300`, el mismo valor de `docs/FRONTEND.md` §6. El tema oscuro no cambia. La prueba nueva `tests/web_huespedes/test_token_aviso.py` comprueba que el valor claro de `--aviso` en `base.html` es igual al de `docs/FRONTEND.md:287` y que su contraste con el fondo claro de `base.html` es de al menos 4,5:1; la mutación es volver a `#B26A00`.

### T-419 — Herramientas: `incidencia_id` acotado y exento de PII (sin forma de teléfono)
`¤herramientas-glamping`
```toml
id = "T-419"
ola = 19
fase = 5
estado = "pendiente"
sala = "herramientas_glamping"
rol = "¤¤backend-developer"
requisitos = ["RF-SEC-05", "INV_PII_FUERA_DEL_MODELO"]
depende_de = ["T-408"]
bloqueada_por = []
propiedad = [
  "features/herramientas_glamping/esquemas/reportar_incidencia.json",
  "features/herramientas_glamping/herramientas_internal.py",
  "tests/herramientas_glamping/test_t419_incidencia_id.py",
  "tests/herramientas_glamping/test_x_pii_esquemas.py",
  "docs/modulos/herramientas_glamping.md",
]
crea = ["tests/herramientas_glamping/test_t419_incidencia_id.py"]
consume = ["seguridad_service (detector de PII)"]
arbitro = "tests/herramientas_glamping/test_t419_incidencia_id.py; tests/herramientas_glamping/test_x_pii_esquemas.py; arnés Exit Code 0"

[limites]
"features/herramientas_glamping/esquemas/reportar_incidencia.json" = "Solo el pattern de incidencia_id pasa a ^I-[0-9]{4}-[0-9]{4,5}$ y se le agrega x-pii-exento."
"features/herramientas_glamping/herramientas_internal.py" = "Solo el id de respaldo (línea 487) pasa de 4 hexadecimales a 4 dígitos decimales."
"tests/herramientas_glamping/test_x_pii_esquemas.py" = "Solo añade a la tabla R1 la entrada (\"reportar_incidencia\", \"incidencia_id\"): {\"x-pii-exento\": True}."
```
Entregables: `incidencia_id` queda acotado a `^I-[0-9]{4}-[0-9]{4,5}$` y declarado `x-pii-exento`, para que nunca tenga forma de teléfono. Se descarta `{4,8}`: el Arquitecto midió que con sufijos de 6 a 8 dígitos cerca del 90 % se detecta como TELEFONO. El id de respaldo de `herramientas_internal.py` usa 4 dígitos decimales en lugar de 4 hexadecimales, para cumplir el pattern. `docs/modulos/herramientas_glamping.md` documenta el pattern y la exención. `tests/herramientas_glamping/test_x_pii_esquemas.py` lo creó T-408 y ya está en `main`; su caso `test_r1_anotaciones_obligatorias` exige que las rutas anotadas sean exactamente las de la tabla `R1`, así que la propiedad lo incorpora, solo para añadir a `R1` la entrada de `incidencia_id` (decisión del CTO, 2026-11-25). Su A10 admite la exención de incidencia_id solo si el pattern rechaza sufijos de 6 dígitos o más, y T-419 la cumple sin tocarla. `test_t419_incidencia_id.py` prueba el pattern acotado, la exención declarada, las cero fugas del detector sobre ids válidos y el id de respaldo en dígitos.

---

## 4. Cómo tomar una tanda en paralelo

1. **Seleccionar la tanda activa (Ola 1 a 8 en Etapa I; Ola 9 a 12 en Etapa II):** Lanzar hasta **4 agentes en paralelo**, asignando a cada agente una tarea de la misma ola con su prompt atómico (`docs/spec/prompts/T-NNN.md`).
2. **Triaje obligatorio:** Cada agente inicia con `mcp_orchestrate_triage` indicando su `T-NNN` y su rastro; el rol asignado coincide con `rol` en el bloque TOML.
3. **Diseño documental y desarrollo Clean-Room:** En las Olas 1 a 8, cada agente actualiza primero `docs/modulos/<sala>.md`, implementa el contrato dentro de su `propiedad` y escribe sus dobles en `tests/<sala>/dobles.py`. Ningún agente toca archivos fuera de su `propiedad`.
4. **Sellado de la tarea:** Cada agente ejecuta `ejecutar_arnes_glamping` en Exit Code 0, consolida huellas `¦` a `¤`, cambia `estado = "sellada"` y cierra con `mcp_close_session`.
5. **Comprobación con plataformas de nube al final:** Solo cuando las 8 tandas de salas están selladas y enlazadas en `app_core` (Ola 9), se ejecutan las tandas de comprobación contra plataformas de nube y producción (Olas 10 a 12).

`¤tareas-glamping/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
