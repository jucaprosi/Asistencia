```toml
id = "TASK-001"
titulo = "MVP WhatsApp: Cloud API oficial + Claude con prompt del glamping + FakePMS"
fase = 1
estado = "pendiente"
sala = ["canal_whatsapp", "agente", "seguridad", "observabilidad"]
rastro = ["¤canal-whatsapp", "¤agente-enrutador", "¤seguridad-canal", "¤observabilidad"]
rol = "¤¤integration-engineer"
depende_de = ["TASK-000"]
bloqueada_por = ["S-02"]
propiedad = ["features/canal_whatsapp/**", "features/agente/**", "features/seguridad/**", "features/observabilidad/**", "tests/canal_whatsapp/**", "tests/agente/**", "tests/seguridad/**", "tests/observabilidad/**", "tests/test_interfaz_purificada.py", "docs/prompts/system-prompt-glamping.md"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0) con tests de las cuatro salas; conversación real de extremo a extremo con el número de pruebas; RNF-01 medido en trazas"
```

# TASK-001 — MVP WhatsApp
`¤canal-whatsapp` `¤agente-enrutador`

## Objetivo
Una conversación real: un huésped escribe al número de pruebas y recibe una respuesta de Claude con el prompt del glamping, sin RAG ni PMS real (`FakePMS` responde disponibilidad sintética), con whitelist, rate limit, redacción de PII y traza por mensaje desde el primer día.

## Requisitos cubiertos
RF-GW-01, 02, 03, 04, 05 (sin transcripción de audio salvo decisión en esta tarea), RF-AG-02 (solo `glamping`), RF-AG-04, 05, 06 (básicos), RF-SEC-01, 03, 05, RF-OBS-01, 02. Invariantes: `INV_FIRMA_WEBHOOK_META`, `INV_VENTANA_24H`, `INV_WHITELIST_PRIMERO`, `INV_PII_FUERA_DEL_MODELO`, `INV_RATE_LIMIT_NO_ANULABLE`, `INV_TRAZA_POR_MENSAJE`, `INV_INTERFAZ_PURIFICADA`.

## Entregables
1. Webhook con verificación y firma; envío de texto, botones y listas; estados de entrega; ventana de 24 h; catálogo de plantillas en `config_canal_whatsapp.yaml` (solicitar aprobación a Meta de `instrucciones_checkin`, `recordatorio_llegada`, `comision_validada`, `incidencia_actualizada`).
2. Agente con bucle de herramientas sobre `FakePMS`, memoria persistida, timeouts y degradación.
3. Seguridad: whitelist por rol, rate limit, bóveda de tokens de PII.
4. Observabilidad: logs JSON y traza con spans; cálculo de OP-01, OP-09.
5. Decisión menor documentada aquí: transcribir audio (costo) o responder que el canal es de texto.
6. **Investigación del supuesto S-01** (lectura del canal de vendedores con la API oficial) con la documentación de Meta: resultado anotado en esta tarea y en el PRD §13.2, porque decide las plantillas a solicitar.

## Criterios de fase completada
- Arnés en Exit Code 0.
- Conversación real registrada con traza; P95 de la semana de prueba anotado en esta tarea (S-09).
- 0 PII en payloads al modelo (`tests/seguridad/test_pii.py`).

## Notas
El `agente` y el futuro `arm_jarvis` no comparten extractor (DPD): cada uno tiene su cliente de Claude dentro de su sala.
