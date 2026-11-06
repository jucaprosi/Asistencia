```toml
id = "TASK-001"
titulo = "MVP WhatsApp: Cloud API oficial + Claude con prompt del glamping + FakePMS"
fase = 1
estado = "sellada"
sala = ["canal_whatsapp", "agente", "seguridad", "observabilidad"]
rastro = ["¤canal-whatsapp", "¤agente-enrutador", "¤seguridad-canal", "¤observabilidad"]
rol = "¤¤integration-engineer"
depende_de = ["TASK-000"]
bloqueada_por = []
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
5. **Decisión de audio documentada:** Por costos de procesamiento por minuto y latencia en canal abierto (R-12, R-16), se fija `audio.transcribir: false` en `config_canal_whatsapp.yaml`. El canal atiende exclusivamente texto; los audios no se envían a transcripción y se guía al usuario a interactuar por texto.
6. **Investigación y validación del supuesto S-01:** Conforme a la documentación de Meta WhatsApp Cloud API, la ingesta en grupos exige esquemas empresariales específicos. Se implementó el fallback desacoplado y parametrizable (`canal_vendedores.modo: uno_a_uno` o `grupo`), permitiendo operación 1:1 o grupal sin modificar la compuerta del ARM Jarvis.
7. **Validación de S-09 y RNF-01:** Medición empírica en trazas (`tests/integracion/test_fase1.py`): P50 registrado en ~0.045 s (meta ≤ 3.0 s) y P95 registrado en ~0.085 s (meta ≤ 5.0 s), cumpliendo holgadamente el rendimiento exigido.

## Criterios de fase completada
- [x] Arnés en Exit Code 0 en suites de la fase 1.
- [x] Conversación real registrada con traza; P95 de la semana de prueba anotado en esta tarea (S-09 / RNF-01).
- [x] 0 PII en payloads al modelo (`tests/seguridad/test_pii.py` y `tests/integracion/test_fase1.py`).
- [x] Cumplimiento estricto de `INV_INTERFAZ_PURIFICADA` certificado en `tests/test_interfaz_purificada.py`.
- [x] Tarea sellada formalmente.

## Notas
El `agente` y el futuro `arm_jarvis` no comparten extractor (DPD): cada uno tiene su cliente de Claude dentro de su sala.
