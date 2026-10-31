# ¤spec-glamping
# language: es
Característica: Ingesta durable y ordenada de mensajes de WhatsApp

  @RF-GW-01 @RF-GW-07 @INV_FIRMA_WEBHOOK_META
  Escenario: Un mensaje válido queda persistido antes de responder a Meta
    Dado un POST al webhook con firma X-Hub-Signature-256 válida
    Cuando el canal lo recibe
    Entonces el evento queda en canal.eventos_entrantes con estado "pendiente"
    Y Meta recibe 200 en menos de 2 segundos

  @RF-GW-01 @INV_FIRMA_WEBHOOK_META
  Escenario: Una firma inválida se rechaza sin procesar
    Dado un POST al webhook con firma inválida
    Cuando el canal lo recibe
    Entonces responde 401
    Y no se persiste ningún evento

  @RF-GW-01 @RF-GW-07
  Escenario: Un reintento de Meta no duplica el mensaje
    Dado un mensaje_id ya registrado
    Cuando Meta lo reenvía
    Entonces responde 200
    Y el mensaje no se procesa una segunda vez

  @RF-GW-07
  Escenario: Una caída del proceso no pierde el mensaje
    Dado un evento en estado "procesando" cuyo trabajador murió
    Cuando el trabajador se reinicia
    Entonces el evento se reintenta hasta 5 veces
    Y al agotar los intentos pasa a "muerto" y se dispara una alerta

  @RF-GW-08
  Escenario: Los mensajes seguidos de un remitente se atienden como un solo turno
    Dado un huésped que envía 3 mensajes en menos de 3 segundos
    Cuando el trabajador los procesa
    Entonces el agente los recibe juntos y en orden
    Y responde una sola vez
