# Catálogo de invariantes — Glamping Imbabura
`¤invariantes-glamping`

> Cada invariante es una ley que el código, los agentes y el arnés deben preservar bajo cualquier condición. Cada una declara su rastro `¤`, su invariante coercitiva `¤¦`, la sala responsable y la vía de verificación física. **Una invariante sin árbitro no entra en este catálogo.** Las invariantes de la metodología (ADPA, UTF-8, huellas, triaje, IP) las impone el servidor ZERAG y no se repiten aquí.

## 1. Invariantes activas

| Código | Ley | Rastro | `¤¦` | Sala | Verificación física (árbitro) | Desde |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `INV_CANAL_OFICIAL` | Ninguna dependencia de `baileys`, `whatsapp-web.js` ni `whatsmeow` entra al repositorio. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/test_canal_oficial.py` recorre los manifiestos de dependencias; Exit Code ≠ 0 si aparece alguna. | Fase 0 |
| `INV_FIRMA_WEBHOOK_META` | Todo `POST` al webhook sin firma `X-Hub-Signature-256` válida se rechaza antes de cualquier procesamiento. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/canal_whatsapp/test_webhook.py`. | Fase 1 |
| `INV_VENTANA_24H` | Fuera de la ventana de 24 h solo salen plantillas aprobadas; el texto libre se rechaza en la compuerta. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/canal_whatsapp/test_ventana_24h.py`. | Fase 1 |
| `INV_WHITELIST_PRIMERO` | Ningún número bloqueado llega al agente ni al ARM, y ningún remitente sin rol de vendedor llega al ARM. El canal de huéspedes es abierto con permisos mínimos (ADR-0014 D-01). | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_identidad.py`. | Fase 1 |
| `INV_PII_FUERA_DEL_MODELO` | Ningún valor de PII en claro aparece en *payloads* al modelo, logs, trazas ni historial persistido. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad`, `observabilidad`, `agente` | `tests/seguridad/test_pii.py`, `tests/observabilidad/test_logs.py`, `tests/agente/test_memoria.py`. | Fase 1 |
| `INV_RATE_LIMIT_NO_ANULABLE` | Ningún rol ni configuración desactiva el límite por remitente. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_rate_limit.py` intenta desactivarlo con cada rol. | Fase 1 |
| `INV_ALLOWLIST_POR_ACCION` | Una herramienta fuera del mapa rol → acción no se ejecuta aunque el modelo la solicite. | `¤seguridad-canal` `¤herramientas-mcp` | `¤¦seguridad-canal` | `seguridad`, `herramientas_glamping` | `tests/seguridad/test_allowlist.py`, `tests/herramientas_glamping/test_contratos.py`. | Fase 1 |
| `INV_INYECCION_CERO` | 0 ataques del set `evals/inyecciones.jsonl` logran una acción o revelación no autorizada. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `scripts/run_evals.py --suite inyecciones`. | Fase 5 |
| `INV_AUDIT_APPEND_ONLY` | El audit log solo admite `INSERT` desde la aplicación. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_audit_log.py` intenta `UPDATE`/`DELETE` con el rol de aplicación; `docs/spec/verificacion_esquema.sql` en la CI. | Fase 0 |
| `INV_PROPIEDAD_RESUELTA` | Ninguna herramienta que requiera `propiedad_id` se invoca con el campo vacío. | `¤agente-enrutador` | `¤¦agente-enrutador` | `agente` | `tests/agente/test_enrutador.py`. | Fase 4 |
| `INV_SIN_FUGA_ENTRE_PROPIEDADES` | Un chunk, una instrucción de check-in o un prompt de la propiedad A nunca se entrega en una conversación de B. | `¤conocimiento-rag` `¤agente-enrutador` | `¤¦conocimiento-rag` | `conocimiento`, `agente` | `tests/conocimiento/test_recuperacion.py`, `tests/agente/test_prompts.py`, `tests/seguridad/test_rls.py`. | Fase 2 |
| `INV_NO_LO_SE` | Precios, políticas y disponibilidad solo se afirman con chunk de soporte o resultado de herramienta; sin soporte, el agente declara que no lo sabe. | `¤conocimiento-rag` | `¤¦conocimiento-rag` | `conocimiento`, `agente` | `scripts/run_evals.py --suite rag` (0 alucinaciones de precio/política; abstención ≥ 90 %). | Fase 2 |
| `INV_CACHE_SIN_PRECIOS` | El caché semántico nunca sirve respuestas con precios ni disponibilidad. | `¤agente-enrutador` | `¤¦agente-enrutador` | `agente` | `tests/agente/test_enrutamiento_modelos.py`. | Fase 5 |
| `INV_SIN_CLIENTES_OTA` | El repositorio no contiene clientes directos de Airbnb, Booking ni VRBO. | `¤pms-conector` | `¤¦pms-conector` | `pms_conector` | `tests/test_sin_clientes_ota.py`. | Fase 3 |
| `INV_ESCRITURA_PMS_EXPLICITA` | Las escrituras al PMS están deshabilitadas por defecto y se habilitan por operación; ninguna escritura se reintenta sin clave de idempotencia. | `¤pms-conector` | `¤¦pms-conector` | `pms_conector` | `tests/pms_conector/test_errores.py`, `test_seleccion_proveedor.py`. | Fase 3 |
| `INV_VENTA_FIRMADA_IDEMPOTENTE` | Toda publicación al CRM va firmada HMAC-SHA256 y repetir una `venta_id` no crea duplicados. | `¤crm-conector` | `¤¦crm-conector` | `crm_conector` | `tests/crm_conector/test_publicar_venta.py`. | Fase 7 |
| `INV_VENTA_NO_SE_PIERDE` | Una venta validada que el CRM rechaza queda `no_publicada` y en la cola; tras 24 horas dispara alerta y admite reintento manual; nunca se descarta. | `¤arm-jarvis` `¤crm-conector` | `¤¦arm-jarvis` | `arm_jarvis`, `crm_conector` | `tests/crm_conector/test_cola_reintentos.py`. | Fase 7 |
| `INV_ESTADOS_VENTA` | Solo existen las transiciones de `docs/spec/contratos/dominio.yaml`; `anulada` es final, solo la aplica el administrador con motivo, y toda transición registra actor, hora y motivo. | `¤arm-jarvis` | `¤¦arm-jarvis` | `arm_jarvis` | `tests/arm_jarvis/test_estados.py`; `docs/spec/verificacion_esquema.sql` en la CI. | Fase 0 |
| `INV_COMISION_REPRODUCIBLE` | Misma venta, misma versión de regla y misma `base_acumulada` dan la misma comisión; una regla nueva no altera comisiones ya validadas; un período cerrado es inmutable. | `¤comisiones` | `¤¦comisiones` | `comisiones` | `tests/comisiones/test_reglas.py`, `test_cierre_periodo.py`; `docs/spec/verificacion_esquema.sql` en la CI. | Fase 0 |
| `INV_COMISION_PROPIA` | Un vendedor solo recibe datos de su propia comisión. | `¤arm-jarvis` | `¤¦arm-jarvis` | `arm_jarvis` | `tests/arm_jarvis/test_consulta_comision.py`. | Fase 6 |
| `INV_TICKET_UNICO` | La numeración `V-AAAA-NNNN` e `I-AAAA-NNNN` es secuencial por año, sin huecos ni duplicados bajo concurrencia. | `¤arm-jarvis` `¤operaciones-incidencias` | `¤¦arm-jarvis` | `arm_jarvis`, `operaciones`/`pms_conector` | `tests/arm_jarvis/test_ticket.py` (prueba concurrente). | Fase 6 |
| `INV_TRAZA_POR_MENSAJE` | El 100 % de los mensajes entrantes generan una traza con *spans* por sala. | `¤observabilidad` | `¤¦observabilidad` | `observabilidad` | `tests/observabilidad/test_trazas.py`. | Fase 1 |
| `INV_RED_AISLADA` | `agent-net` no alcanza ningún puerto de los servicios contables; el stack beta no alcanza el MCP existente. | `¤infra-hibrida` | `¤¦infra-hibrida` | infraestructura | Prueba de conexión negativa en el arnés de despliegue. | Fase 5 |
| `INV_SIN_SECRETOS_EN_REPO` | 0 secretos en el repositorio. | `¤infra-hibrida` | `¤¦infra-hibrida` | infraestructura | `scripts/verificar_secretos.py` en el arnés y en la CI. | Fase 0 |
| `INV_MISMO_COMPOSE` | Beta y producción se levantan con el mismo `compose.yaml`; la diferencia es solo `compose.production.yaml` y `.env`. | `¤infra-hibrida` | `¤¦infra-hibrida` | infraestructura | `docker compose -f compose.yaml -f compose.production.yaml config` en CI. | Fase 0 |
| `INV_INTERFAZ_PURIFICADA` | Ningún texto de cara a huésped, vendedor o equipo contiene `¤`, `¦`, `¤¬` ni `¤¤`. | `¤canal-whatsapp` `¤arm-jarvis` | `¤¦interfaz` | todas las que emiten texto | `tests/test_interfaz_purificada.py` sobre plantillas, mensajes de prueba y exportaciones. | Fase 1 |
| `INV_SALA_CONFORME` | Cada `features/<sala>/` tiene `<sala>_service.py` y `config_<sala>.yaml`; `app_core/` solo importa compuertas. | `¤arquitectura-salas` | `¤¦adpa` | pasillo central | `tests/test_estructura_adpa.py` + `adpa_linter`. | Fase 0 |
| `INV_PANEL_POR_ROL` | El BFF del panel rechaza con 403 toda acción fuera de la allowlist del rol aunque la UI la muestre; un gestor nunca obtiene datos de otra zona. | `¤panel-operativo` `¤seguridad-canal` | `¤¦panel-operativo` | `panel_operativo`, `seguridad` | `tests/panel_operativo/test_bff_*.py` (cada endpoint con cada rol). | Fase 4 |
| `INV_PANEL_SIN_LOGICA` | El panel no contiene reglas de negocio: cada acción es una llamada a la compuerta de la sala dueña. | `¤panel-operativo` | `¤¦panel-operativo` | `panel_operativo` | `adpa_linter` (solo imports `_service`) + revisión de `bff_internal.py` sin cálculos de comisión ni transiciones de estado propias (`tests/panel_operativo/test_sin_logica.py` por AST). | Fase 4 |
| `INV_WEB_SOLO_LECTURA` | La web pública nunca crea, cambia ni cancela reservas. | `¤web-huespedes` | `¤¦web-huespedes` | `web_huespedes` | `tests/web_huespedes/test_contacto.py`. | Fase 1 |
| `INV_WEB_SIN_PII` | La web pública no pide ni guarda datos personales. | `¤web-huespedes` | `¤¦web-huespedes` | `web_huespedes` | `tests/web_huespedes/test_contacto.py`; `docs/spec/verificacion_esquema.sql` en la CI. | Fase 1 |
| `INV_WEB_PRECIO_EN_VIVO` | Precio y disponibilidad se piden al PMS en cada búsqueda y nunca se guardan. | `¤web-huespedes` | `¤¦web-huespedes` | `web_huespedes` | `tests/web_huespedes/test_busqueda.py`. | Fase 3 |
| `INV_WEB_LIMITE_POR_IP` | Una IP sobre el límite recibe 429 antes de llegar al PMS. | `¤web-huespedes` | `¤¦web-huespedes` | `web_huespedes` | `tests/web_huespedes/test_limites.py`. | Fase 1 |
| `INV_MOVIL_SIN_PII_EN_DISCO` | La terminal móvil no guarda datos de negocio ni personales en el teléfono: solo la interfaz estática. | `¤panel-operativo` | `¤¦panel-operativo` | `panel_operativo` | `tests/e2e/test_terminal_movil.py`. | Fase 8 |
| `INV_MOVIL_SIN_ESCRITURA_SIN_RED` | Sin red no se ejecuta ni se encola ninguna acción. | `¤panel-operativo` | `¤¦panel-operativo` | `panel_operativo` | `tests/e2e/test_terminal_movil.py`. | Fase 8 |
| `INV_AVISO_SIN_PII` | Un aviso al teléfono no lleva nombres, teléfonos, montos ni texto de conversaciones. | `¤panel-operativo` | `¤¦panel-operativo` | `panel_operativo` | `tests/panel_operativo/test_avisos.py`. | Fase 8 |
| `INV_ACCION_IDEMPOTENTE` | Repetir una acción con la misma clave no repite su efecto. | `¤panel-operativo` | `¤¦panel-operativo` | `panel_operativo` | `tests/panel_operativo/test_idempotencia.py`; `docs/spec/verificacion_esquema.sql` en la CI. | Fase 8 |
| `INV_INGESTA_DURABLE` | Ningún mensaje con firma válida se confirma a Meta antes de quedar persistido, y un fallo agotado queda `muerto` con alerta. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/canal_whatsapp/test_ingesta_durable.py`. | Fase 1 |
| `INV_SECRETO_OPERATIVO` | Una clave de wifi o un código de acceso nunca llega al modelo ni al historial, y solo sale hacia el titular de la reserva. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad`, `pms_conector` | `tests/seguridad/test_secretos_operativos.py`. | Fase 4 |
| `INV_HANDOFF_UNICO` | Una conversación tiene a lo sumo un handoff abierto. | `¤crm-conector` | `¤¦crm-conector` | `crm_conector` | `tests/crm_conector/test_handoff.py`; índice único en `docs/spec/esquema.sql`. | Fase 4 |
| `INV_CRIPTOBORRADO` | Eliminar a un titular deja irrecuperables sus tokens sin modificar el audit log. | `¤privacidad-datos` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_criptoborrado.py`. | Fase 5 |
| `INV_ESPECIFICACION_VIVA` | Toda historia tiene escenario; todo rastreo de requisito resuelve; roles, estados, allowlist, plantillas y herramientas de las salas coinciden con los contratos; la matriz está al día. | `¤spec-glamping` | `¤¦spec-glamping` | transversal | `tests/test_especificacion.py`. | Fase 0 |
| `INV_ESQUEMA_VERIFICADO` | `docs/spec/esquema.sql` se aplica en PostgreSQL real y sus pruebas negativas pasan. | `¤spec-glamping` | `¤¦spec-glamping` | transversal | Trabajo `verificar` de `.github/workflows/ci.yml`. | Fase 0 |
| `INV_CORPUS_FUERA_DEL_REPO` | El repositorio público no contiene corpus real, reglas de comisión reales ni evaluaciones con datos reales. | `¤spec-glamping` | `¤¦spec-glamping` | `conocimiento`, `comisiones` | `tests/test_especificacion.py`. | Fase 0 |
| `INV_ENVIO_UNICO` | Un envío programado por reserva, plantilla y día sale una sola vez aunque el planificador se reinicie. | `¤agente-enrutador` | `¤¦agente-enrutador` | `agente` | `tests/agente/test_planificador.py`; `docs/spec/verificacion_esquema.sql` en la CI. | Fase 4 |

## 2. Predicados formales y mecanismo obligatorio

Cada invariante activa se expresa como predicado booleano. El mecanismo no es una sugerencia: dos implementaciones independientes deben usar el mismo, o dejarían de ser compatibles. `tests/test_especificacion.py` exige una fila por invariante activa.

| Código | Predicado | Mecanismo obligatorio |
| :--- | :--- | :--- |
| `INV_CANAL_OFICIAL` | `∀ d ∈ dependencias : d ∉ {baileys, whatsapp-web.js, whatsmeow}` | Revisión de manifiestos. |
| `INV_FIRMA_WEBHOOK_META` | `procesado(m) ⇒ HMAC_SHA256(secreto, cuerpo_crudo(m)) = firma(m)` | Comparación en tiempo constante sobre los bytes crudos, antes de parsear. |
| `INV_VENTANA_24H` | `enviado(m) ∧ ¬plantilla(m) ⇒ ahora − ultimo_mensaje_usuario < 24 h` | Rechazo tipado en la compuerta. |
| `INV_WHITELIST_PRIMERO` | `entrega(m, s) ⇒ ¬bloqueado(r(m)) ∧ (s = arm ⇒ rol(r(m)) = vendedor)` | El rol se deriva del remitente verificado, nunca del texto. |
| `INV_PII_FUERA_DEL_MODELO` | `∀ v ∈ PII(m) : v ∉ payload ∪ logs ∪ trazas ∪ historial` | Tokenización antes de cada llamada; rehidratación solo en la salida. |
| `INV_RATE_LIMIT_NO_ANULABLE` | `∀ rol, config : contador(r, ventana) > limite ⇒ ¬procesado(m)` | Contador en `seguridad.rate_limit` con `INSERT ... ON CONFLICT DO UPDATE`; ninguna configuración lo apaga. |
| `INV_ALLOWLIST_POR_ACCION` | `ejecutada(h, rol) ⇒ h ∈ allowlist(rol)` | `seguridad.autorizar` dentro de cada herramienta, no solo al exponerla. |
| `INV_INYECCION_CERO` | `∣{a ∈ set : exito(a)}∣ = 0` | Suite `inyecciones`. |
| `INV_AUDIT_APPEND_ONLY` | `rol_app ⊬ UPDATE, DELETE, TRUNCATE sobre audit_log` | `REVOKE` en el DDL. |
| `INV_PROPIEDAD_RESUELTA` | `requiere_propiedad(h) ∧ invocada(h) ⇒ propiedad_id ≠ ∅` | Validación en el agente antes de llamar. |
| `INV_SIN_FUGA_ENTRE_PROPIEDADES` | `∀ c ∈ recuperados(A) : propiedad(c) ∈ {A, global}` | RLS con `SET LOCAL app.propiedad_id` dentro de cada transacción. |
| `INV_NO_LO_SE` | `afirma(precio ∨ politica ∨ disponibilidad) ⇒ ∃ soporte(chunk ∨ herramienta)` | Umbral `umbral_suficiente` y suite `rag`. |
| `INV_CACHE_SIN_PRECIOS` | `servida_de_cache(r) ⇒ ¬contiene(r, precio ∨ disponibilidad)` | Filtro antes de escribir en el caché. |
| `INV_SIN_CLIENTES_OTA` | `∀ i ∈ imports : i ∉ clientes_OTA` | Revisión de imports y manifiestos. |
| `INV_ESCRITURA_PMS_EXPLICITA` | `escritura(op) ⇒ habilitada(op)`; `reintento(op) ⇒ ∃ clave_idempotencia(op)` | Lista por operación en configuración; `pms.idempotencia` con `clave` única. |
| `INV_VENTA_FIRMADA_IDEMPOTENTE` | `∀ n ≥ 1 : efecto(publicar^n(v)) = efecto(publicar(v))` | Clave primaria `(venta_id, evento)` en `crm.publicaciones`; `INSERT ... ON CONFLICT DO NOTHING`. |
| `INV_VENTA_NO_SE_PIERDE` | `validada(v) ⇒ ◇ publicada(v) ∨ alerta(v)`; `nunca descartada(v)` | Cola persistente en `crm.publicaciones`. |
| `INV_ESTADOS_VENTA` | `(e, e') ∈ transicion(v) ⇒ e' ∈ transiciones[e]` | `UPDATE arm.ventas SET estado = $nuevo WHERE venta_id = $id AND estado = $esperado`: 0 filas es conflicto. Disparador `arm.validar_transicion`. |
| `INV_COMISION_REPRODUCIBLE` | `comision(v) = F(base(v) + monto(v)) − F(base(v))`, con `F` redondeada a 2 decimales; `∀ π, π' órdenes de validación : Σ comision = F(S)`; la base guardada reproduce el monto | `pg_advisory_xact_lock(hashtext(vendedor_id ∥ regla_id ∥ mes_fecha_venta))` al fijar; `base = Σ monto_venta` de las filas de esa clave, con ajustes en negativo. Aritmética con `Decimal`, nunca `float`. Redondear `F`, nunca cada diferencia. |
| `INV_COMISION_PROPIA` | `respuesta(q, r) ⇒ vendedor(datos) = vendedor(r)` | `vendedor_id` inyectado por el servidor. |
| `INV_TICKET_UNICO` | `∀ año : tickets(año) = {1, …, n}` sin repetidos | `UPDATE ... SET ultimo = ultimo + 1 ... RETURNING ultimo` en la misma transacción del `INSERT`; un `ROLLBACK` no deja huecos. Prohibidas las `SEQUENCE`. |
| `INV_TRAZA_POR_MENSAJE` | `∀ m ∈ entrantes : ∃ traza(m)` | La traza nace al reclamar el evento. |
| `INV_RED_AISLADA` | `¬alcanza(agent-net, servicios_contables)` | Prueba de conexión negativa. |
| `INV_SIN_SECRETOS_EN_REPO` | `∣hallazgos(escaner)∣ = 0` | `scripts/verificar_secretos.py`. |
| `INV_MISMO_COMPOSE` | `stack(beta) = compose.yaml`; `stack(prod) = compose.yaml + compose.production.yaml` | `docker compose config` en la CI. |
| `INV_INTERFAZ_PURIFICADA` | `∀ t ∈ textos_de_usuario : t ∩ {¤, ¦} = ∅` | Prueba sobre plantillas, mensajes y build. |
| `INV_SALA_CONFORME` | `∀ s ∈ salas : ∃ compuerta(s) ∧ ∃ config(s)` | `tests/test_estructura_adpa.py`. |
| `INV_PANEL_POR_ROL` | `ejecutada(accion, sesion) ⇒ accion ∈ allowlist(rol) ∧ zona(dato) ∈ zonas(sesion)` | Autorización en el BFF por endpoint. |
| `INV_PANEL_SIN_LOGICA` | `∀ c ∈ cálculos_de_negocio : c ∉ panel_operativo` | Prueba por AST. |
| `INV_WEB_SOLO_LECTURA` | `∀ r ∈ rutas(web) : efectos_pms(r) = ∅` | La compuerta recibe un puerto de `pms` con solo `consultar_disponibilidad` y `cotizar`. |
| `INV_WEB_SIN_PII` | `∀ f ∈ tablas(web) ∪ enlaces ∪ logs : PII(f) = ∅` | Sin formularios de datos; código aleatorio `W-` con `secrets`; IP solo como HMAC con secreto. |
| `INV_WEB_PRECIO_EN_VIVO` | `mostrado(precio, t) ⇒ precio = cotizar(t)` | `Cache-Control: no-store` en `/buscar` y `/comparar`, sin caché de servidor. |
| `INV_WEB_LIMITE_POR_IP` | `conteo(ip, minuto) > limite ⇒ ∣llamadas_pms∣ = 0` | `INSERT ... ON CONFLICT DO UPDATE` en `web.limites_ip` antes de llamar al PMS. |
| `INV_MOVIL_SIN_PII_EN_DISCO` | `∀ r ∈ almacenamiento(telefono) : r ∈ interfaz_estatica` | El service worker solo guarda archivos versionados del build; `/panel/api` va con `Cache-Control: no-store`; los datos viven en memoria. |
| `INV_MOVIL_SIN_ESCRITURA_SIN_RED` | `¬red ⇒ ∣acciones_enviadas∣ = 0 ∧ ∣cola_local∣ = 0` | Botones deshabilitados y sin Background Sync. |
| `INV_AVISO_SIN_PII` | `∀ a ∈ avisos : carga(a) ⊆ {tipo, cantidad, ruta}` | El tipo `AvisoMovil` no admite otros campos; el detalle se pide al abrir, con sesión. |
| `INV_ACCION_IDEMPOTENTE` | `∀ n ≥ 1 : efecto(accion(k)^n) = efecto(accion(k))` | Cabecera `Idempotency-Key` con UUID; `INSERT ... ON CONFLICT DO NOTHING` en `panel.acciones_idempotentes` dentro de la transacción de la acción. |
| `INV_INGESTA_DURABLE` | `respondio_200(m) ⇒ persistido(m)` | `INSERT ... ON CONFLICT (mensaje_id) DO NOTHING` antes de responder. El trabajador reclama con `FOR UPDATE SKIP LOCKED` y `pg_try_advisory_xact_lock(hashtext(conversacion_clave))`. |
| `INV_SECRETO_OPERATIVO` | `∀ s ∈ secretos : s ∉ payload ∪ historial ∧ (enviado(s, r) ⇒ titular(r))` | Marcador `[[SECRETO:id]]` resuelto solo en la salida. |
| `INV_HANDOFF_UNICO` | `∀ c : ∣{h ∈ handoffs(c) : estado(h) ≠ devuelto}∣ ≤ 1` | Índice único parcial `un_handoff_abierto`. |
| `INV_CRIPTOBORRADO` | `borrado(t) ⇒ ¬rehidratable(tokens(t)) ∧ audit_log' = audit_log` | `DELETE` en `seguridad.boveda_tokens`. |
| `INV_ESPECIFICACION_VIVA` | `∀ us, rf : ∃ escenario`; `∀ inv activa : ∃ predicado`; matriz y prompts al día | `tests/test_especificacion.py`. |
| `INV_ESQUEMA_VERIFICADO` | `aplica(esquema.sql) ∧ ∀ p ∈ negativas : rechazada(p)` | Paso de PostgreSQL en la CI. |
| `INV_CORPUS_FUERA_DEL_REPO` | `archivos(docs/negocio) = {README.md}` | `tests/test_especificacion.py`. |
| `INV_ENVIO_UNICO` | `∣envios(reserva, plantilla, dia)∣ ≤ 1` | `INSERT ... ON CONFLICT DO NOTHING` en `agente.envios_programados` antes de enviar. |

## 3. Invariantes condicionadas a decisiones pendientes

| Código | Ley | Depende de | Entra en vigor |
| :--- | :--- | :--- | :--- |
| `INV_RLS_MULTI_INQUILINO` | Con datos de más de una propiedad en la misma base, RLS por `propiedad_id` con rol `NOBYPASSRLS`. | Siempre que haya ≥ 2 propiedades (fase 4). | `tests/seguridad/test_rls.py` contra PostgreSQL real. |
| `INV_RESIDENCIA_DATOS` | Los datos que ADR-0012 clasifique como restringidos no salen de la ubicación aprobada. | [ADR-0012](../../docs/adr/ADR-0012-residencia-datos.md). | Al aceptar el ADR; inventario referenciado aquí. |
| `INV_PITR_MINIMO` | PostgreSQL gestionado con PITR ≥ 7 días. | Proveedor (ADR-0002). | Fase 0, documentado con captura de configuración. |

`¤invariantes-glamping/`
