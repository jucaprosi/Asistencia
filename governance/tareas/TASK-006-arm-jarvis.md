```toml
id = "TASK-006"
titulo = "ARM «Jarvis»: lectura del canal de vendedores, extracción de ventas, estados, ticket, comisión y notificación"
fase = 6
estado = "pendiente"
sala = ["arm_jarvis", "comisiones", "canal_whatsapp (RF-GW-06)"]
rastro = ["¤arm-jarvis", "¤comisiones", "¤canal-whatsapp"]
rol = "¤¤backend-developer"
depende_de = ["TASK-005"]
bloqueada_por = ["S-01", "ADR-0009"]
propiedad = ["features/arm_jarvis/**", "features/comisiones/**", "features/canal_whatsapp/enrutamiento_canal_internal.py", "evals/ventas.jsonl", "tests/arm_jarvis/**", "tests/comisiones/**", "tests/canal_whatsapp/test_enrutamiento_canal.py"]
arbitro = "ejecutar_arnes_glamping.bat (Exit Code 0); run_evals --suite ventas ≥ 95 %; test_ticket.py concurrente; test_consulta_comision.py sin fuga; OP-08 medido"
```

# TASK-006 — ARM «Jarvis»
`¤arm-jarvis` `¤comisiones`

## Objetivo
Un vendedor escribe la venta en texto libre y en segundos recibe un ticket con la venta estructurada y la comisión estimada; el líder la valida; el vendedor recibe su comisión; cualquier vendedor puede preguntar cuánto lleva.

## Requisitos cubiertos
RF-ARM-01..07, RF-ARM-09 (asistente del líder), RF-COM-01, 02, RF-MCP-08, 09, RF-GW-06. Invariantes: `INV_ESTADOS_VENTA`, `INV_COMISION_REPRODUCIBLE`, `INV_COMISION_PROPIA`, `INV_TICKET_UNICO`.

## Entregables
1. Canal de vendedores según el resultado de S-01 (grupo por API oficial o chats 1:1): la lógica del ARM es la misma.
2. `extractor_internal.py` con Claude → `VentaExtraida`; preguntas por campos faltantes; `evals/ventas.jsonl` ≥ 60 mensajes reales anonimizados.
3. Máquina de estados con auditoría; numeración `V-AAAA-NNNN` segura bajo concurrencia.
4. `comisiones_service`: reglas versionadas con vigencia, cálculo reproducible, cierre de período.
5. Notificación privada al vendedor (plantilla `comision_validada` fuera de ventana); consulta de comisión propia.
6. Asistente del líder acotado a lectura y cambios de `config_arm_jarvis.yaml` con confirmación.

## Criterios de fase completada
- OP-07 ≥ 95 %; OP-08 P95 ≤ 10 s.
- 0 fugas entre vendedores; concurrencia del ticket probada.
- Puede correr en paralelo con TASK-007 si el contrato `publicar_venta` se fija primero con `FakeCRM`.

## Pantallas del panel operativo en esta tarea (ADR-0013)
`¤panel-operativo` · Sala adicional: `panel_operativo`. Entregables: P-03 Ventas por validar (validar con un toque, corrección de campos dudosos, rechazo con motivo, conflicto), P-04 Detalle de venta, P-07 Jarvis (RF-PAN-02, 03, 06). Criterio: US-06 en `tests/e2e/test_validar_venta.py`; `INV_PANEL_POR_ROL` y `INV_PANEL_SIN_LOGICA` en verde.
