# ¤spec-glamping
# language: es
Característica: Disponibilidad y reserva por WhatsApp

  @US-01 @CU-01 @RF-MCP-01 @RF-MCP-02
  Escenario: Consulta con disponibilidad
    Dado una propiedad resuelta y fechas válidas
    Cuando el huésped pregunta "¿tienen del 12 al 14 de diciembre para 2?"
    Entonces recibe en 10 segundos o menos la disponibilidad, el total con desglose y la política de cancelación
    Y esos datos provienen del PMS y del RAG

  @US-01 @RF-MCP-01
  Escenario: Consulta sin disponibilidad
    Dado fechas sin unidades libres
    Cuando el huésped pregunta
    Entonces recibe el motivo y hasta 3 alternativas de fechas o unidades

  @US-01 @RF-AG-05
  Escenario: El PMS no responde
    Dado que el PMS está caído
    Cuando el huésped pregunta por disponibilidad
    Entonces el agente lo declara, no inventa disponibilidad y ofrece pasar con una persona

  @US-02 @RF-MCP-03
  Escenario: Reserva preliminar
    Dado disponibilidad confirmada
    Cuando el huésped confirma "resérvalo"
    Entonces se crea una reserva "preliminar" con código y expiración a 24 horas
    Y recibe el código y los pasos de pago del corpus

  @US-02 @RF-MCP-03
  Escenario: Reintento idempotente
    Dado una reserva creada con una clave de idempotencia
    Cuando el agente reintenta con la misma clave
    Entonces devuelve la misma reserva y no crea otra

  @US-02 @RF-PMS-05
  Escenario: Una reserva preliminar sin pago expira
    Dado una reserva "preliminar" vencida
    Cuando se consulta en el PMS
    Entonces su estado es "expirada" y la unidad vuelve a estar libre

  @US-02 @RF-MCP-06
  Escenario: Cancelar o cambiar una reserva pasa por una persona
    Dado un huésped con reserva
    Cuando pide cancelarla o cambiar las fechas
    Entonces el agente abre un handoff con motivo "fuera_alcance"
