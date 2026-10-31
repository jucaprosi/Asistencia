# Catálogo de invariantes — Glamping Imbabura
`¤invariantes-glamping`

> Cada invariante es una ley que el código, los agentes y el arnés deben preservar bajo cualquier condición. Cada una declara su rastro `¤`, su invariante coercitiva `¤¦`, la sala responsable y la vía de verificación física. **Una invariante sin árbitro no entra en este catálogo.** Las invariantes de la metodología (ADPA, UTF-8, huellas, triaje, IP) las impone el servidor ZERAG y no se repiten aquí.

## 1. Invariantes activas

| Código | Ley | Rastro | `¤¦` | Sala | Verificación física (árbitro) | Desde |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `INV_CANAL_OFICIAL` | Ninguna dependencia de `baileys`, `whatsapp-web.js` ni `whatsmeow` entra al repositorio. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/test_canal_oficial.py` recorre los manifiestos de dependencias; Exit Code ≠ 0 si aparece alguna. | Fase 0 |
| `INV_FIRMA_WEBHOOK_META` | Todo `POST` al webhook sin firma `X-Hub-Signature-256` válida se rechaza antes de cualquier procesamiento. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/canal_whatsapp/test_webhook.py`. | Fase 1 |
| `INV_VENTANA_24H` | Fuera de la ventana de 24 h solo salen plantillas aprobadas; el texto libre se rechaza en la compuerta. | `¤canal-whatsapp` | `¤¦canal-whatsapp` | `canal_whatsapp` | `tests/canal_whatsapp/test_ventana_24h.py`. | Fase 1 |
| `INV_WHITELIST_PRIMERO` | Ningún mensaje de un remitente fuera de la whitelist llega al agente ni al ARM. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_whitelist.py`. | Fase 1 |
| `INV_PII_FUERA_DEL_MODELO` | Ningún valor de PII en claro aparece en *payloads* al modelo, logs, trazas ni historial persistido. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad`, `observabilidad`, `agente` | `tests/seguridad/test_pii.py`, `tests/observabilidad/test_logs.py`, `tests/agente/test_memoria.py`. | Fase 1 |
| `INV_RATE_LIMIT_NO_ANULABLE` | Ningún rol ni configuración desactiva el límite por remitente. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_rate_limit.py` intenta desactivarlo con cada rol. | Fase 1 |
| `INV_ALLOWLIST_POR_ACCION` | Una herramienta fuera del mapa rol → acción no se ejecuta aunque el modelo la solicite. | `¤seguridad-canal` `¤herramientas-mcp` | `¤¦seguridad-canal` | `seguridad`, `herramientas_glamping` | `tests/seguridad/test_allowlist.py`, `tests/herramientas_glamping/test_contratos.py`. | Fase 5 |
| `INV_INYECCION_CERO` | 0 ataques del set `evals/inyecciones.jsonl` logran una acción o revelación no autorizada. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `scripts/run_evals.py --suite inyecciones`. | Fase 5 |
| `INV_AUDIT_APPEND_ONLY` | El audit log solo admite `INSERT` desde la aplicación. | `¤seguridad-canal` | `¤¦seguridad-canal` | `seguridad` | `tests/seguridad/test_audit_log.py` intenta `UPDATE`/`DELETE` con el rol de aplicación. | Fase 5 |
| `INV_PROPIEDAD_RESUELTA` | Ninguna herramienta que requiera `propiedad_id` se invoca con el campo vacío. | `¤agente-enrutador` | `¤¦agente-enrutador` | `agente` | `tests/agente/test_enrutador.py`. | Fase 4 |
| `INV_SIN_FUGA_ENTRE_PROPIEDADES` | Un chunk, una instrucción de check-in o un prompt de la propiedad A nunca se entrega en una conversación de B. | `¤conocimiento-rag` `¤agente-enrutador` | `¤¦conocimiento-rag` | `conocimiento`, `agente` | `tests/conocimiento/test_recuperacion.py`, `tests/agente/test_prompts.py`, `tests/seguridad/test_rls.py`. | Fase 2 |
| `INV_NO_LO_SE` | Precios, políticas y disponibilidad solo se afirman con chunk de soporte o resultado de herramienta; sin soporte, el agente declara que no lo sabe. | `¤conocimiento-rag` | `¤¦conocimiento-rag` | `conocimiento`, `agente` | `scripts/run_evals.py --suite rag` (0 alucinaciones de precio/política; abstención ≥ 90 %). | Fase 2 |
| `INV_CACHE_SIN_PRECIOS` | El caché semántico nunca sirve respuestas con precios ni disponibilidad. | `¤agente-enrutador` | `¤¦agente-enrutador` | `agente` | `tests/agente/test_enrutamiento_modelos.py`. | Fase 5 |
| `INV_SIN_CLIENTES_OTA` | El repositorio no contiene clientes directos de Airbnb, Booking ni VRBO. | `¤pms-conector` | `¤¦pms-conector` | `pms_conector` | `tests/test_sin_clientes_ota.py`. | Fase 3 |
| `INV_ESCRITURA_PMS_EXPLICITA` | Las escrituras al PMS están deshabilitadas por defecto y se habilitan por operación; ninguna escritura se reintenta sin clave de idempotencia. | `¤pms-conector` | `¤¦pms-conector` | `pms_conector` | `tests/pms_conector/test_errores.py`, `test_seleccion_proveedor.py`. | Fase 3 |
| `INV_VENTA_FIRMADA_IDEMPOTENTE` | Toda publicación al CRM va firmada HMAC-SHA256 y repetir una `venta_id` no crea duplicados. | `¤crm-conector` | `¤¦crm-conector` | `crm_conector` | `tests/crm_conector/test_publicar_venta.py`. | Fase 7 |
| `INV_VENTA_NO_SE_PIERDE` | Una venta validada que el CRM rechaza queda en `validada/no_publicada` y en la cola de reintentos; nunca se descarta. | `¤arm-jarvis` `¤crm-conector` | `¤¦arm-jarvis` | `arm_jarvis`, `crm_conector` | `tests/crm_conector/test_cola_reintentos.py`. | Fase 7 |
| `INV_ESTADOS_VENTA` | Solo existen las transiciones `por_validar→validada|rechazada`, `validada→publicada|no_publicada`, y `→anulada` por administrador con motivo; toda transición registra actor, hora y motivo. | `¤arm-jarvis` | `¤¦arm-jarvis` | `arm_jarvis` | `tests/arm_jarvis/test_estados.py`. | Fase 6 |
| `INV_COMISION_REPRODUCIBLE` | Misma venta + misma versión de regla = misma comisión; una regla nueva no altera comisiones ya validadas; un período cerrado es inmutable. | `¤comisiones` | `¤¦comisiones` | `comisiones` | `tests/comisiones/test_reglas.py`, `test_cierre_periodo.py`. | Fase 6 |
| `INV_COMISION_PROPIA` | Un vendedor solo recibe datos de su propia comisión. | `¤arm-jarvis` | `¤¦arm-jarvis` | `arm_jarvis` | `tests/arm_jarvis/test_consulta_comision.py`. | Fase 6 |
| `INV_TICKET_UNICO` | La numeración `V-AAAA-NNNN` e `I-AAAA-NNNN` es secuencial por año, sin huecos ni duplicados bajo concurrencia. | `¤arm-jarvis` `¤operaciones-incidencias` | `¤¦arm-jarvis` | `arm_jarvis`, `operaciones`/`pms_conector` | `tests/arm_jarvis/test_ticket.py` (prueba concurrente). | Fase 6 |
| `INV_TRAZA_POR_MENSAJE` | El 100 % de los mensajes entrantes generan una traza con *spans* por sala. | `¤observabilidad` | `¤¦observabilidad` | `observabilidad` | `tests/observabilidad/test_trazas.py`. | Fase 1 |
| `INV_RED_AISLADA` | `agent-net` no alcanza ningún puerto de los servicios contables; el stack beta no alcanza el MCP existente. | `¤infra-hibrida` | `¤¦infra-hibrida` | infraestructura | Prueba de conexión negativa en el arnés de despliegue. | Fase 5 |
| `INV_SIN_SECRETOS_EN_REPO` | 0 secretos en el repositorio. | `¤infra-hibrida` | `¤¦infra-hibrida` | infraestructura | Escáner de secretos en el arnés y pre-commit. | Fase 0 |
| `INV_MISMO_COMPOSE` | Beta y producción se levantan con el mismo `compose.yaml`; la diferencia es solo `compose.production.yaml` y `.env`. | `¤infra-hibrida` | `¤¦infra-hibrida` | infraestructura | `docker compose -f compose.yaml -f compose.production.yaml config` en CI. | Fase 0 |
| `INV_INTERFAZ_PURIFICADA` | Ningún texto de cara a huésped, vendedor o equipo contiene `¤`, `¦`, `¤¬` ni `¤¤`. | `¤canal-whatsapp` `¤arm-jarvis` | `¤¦interfaz` | todas las que emiten texto | `tests/test_interfaz_purificada.py` sobre plantillas, mensajes de prueba y exportaciones. | Fase 1 |
| `INV_SALA_CONFORME` | Cada `features/<sala>/` tiene `<sala>_service.py` y `config_<sala>.yaml`; `app_core/` solo importa compuertas. | `¤arquitectura-salas` | `¤¦adpa` | pasillo central | `tests/test_estructura_adpa.py` + `adpa_linter`. | Fase 0 |
| `INV_PANEL_POR_ROL` | El BFF del panel rechaza con 403 toda acción fuera de la allowlist del rol aunque la UI la muestre; un gestor nunca obtiene datos de otra zona. | `¤panel-operativo` `¤seguridad-canal` | `¤¦panel-operativo` | `panel_operativo`, `seguridad` | `tests/panel_operativo/test_bff_*.py` (cada endpoint con cada rol). | Fase 4 |
| `INV_PANEL_SIN_LOGICA` | El panel no contiene reglas de negocio: cada acción es una llamada a la compuerta de la sala dueña. | `¤panel-operativo` | `¤¦panel-operativo` | `panel_operativo` | `adpa_linter` (solo imports `_service`) + revisión de `bff_internal.py` sin cálculos de comisión ni transiciones de estado propias (`tests/panel_operativo/test_sin_logica.py` por AST). | Fase 4 |

## 2. Invariantes condicionadas a decisiones pendientes

| Código | Ley | Depende de | Entra en vigor |
| :--- | :--- | :--- | :--- |
| `INV_RLS_MULTI_INQUILINO` | Con datos de más de una propiedad en la misma base, RLS por `propiedad_id` con rol `NOBYPASSRLS`. | Siempre que haya ≥ 2 propiedades (fase 4). | `tests/seguridad/test_rls.py` contra PostgreSQL real. |
| `INV_RESIDENCIA_DATOS` | Los datos que ADR-0012 clasifique como restringidos no salen de la ubicación aprobada. | [ADR-0012](../../docs/adr/ADR-0012-residencia-datos.md). | Al aceptar el ADR; inventario referenciado aquí. |
| `INV_PITR_MINIMO` | PostgreSQL gestionado con PITR ≥ 7 días. | Proveedor (ADR-0002). | Fase 0, documentado con captura de configuración. |

`¤invariantes-glamping/`
