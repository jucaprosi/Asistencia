# ¤spec-glamping
# language: es
Característica: Incidencias y atención humana por zona

  @US-04 @CU-03 @RF-MCP-05
  Escenario: Registro de incidencia
    Dado una conversación con propiedad resuelta
    Cuando el huésped escribe "no hay agua caliente"
    Entonces recibe un número I-AAAA-NNNN, la prioridad y el tiempo estimado por prioridad
    Y el gestor de la zona recibe la incidencia en el panel

  @US-04 @RF-MCP-05
  Escenario: Incidencia crítica
    Dado una incidencia de categoría "seguridad" o "acceso"
    Cuando se registra
    Entonces su prioridad es "critica" y la conversación pasa a handoff de inmediato

  @US-09 @CU-08 @RF-CRM-06 @RF-MCP-06
  Escenario: Handoff al gestor de la zona
    Dado una propiedad resuelta en la zona Z
    Cuando el huésped pide una persona, o hay 2 abstenciones seguidas, o 3 mensajes marcados por inyección
    Entonces se crea un handoff "pendiente" en la bandeja del panel para el gestor de Z
    Y el gestor recibe la plantilla "handoff_asignado"
    Y el huésped recibe el aviso con tiempo estimado
    Y el agente queda en silencio

  @US-09 @RF-CRM-06
  Escenario: Handoff sin zona resuelta
    Dado una conversación sin propiedad resuelta
    Cuando se solicita el handoff
    Entonces se asigna al administrador con zona vacía

  @US-09 @RF-CRM-06
  Escenario: Nadie toma el handoff
    Dado un handoff "pendiente" durante 15 minutos
    Cuando vence el plazo
    Entonces se asigna al gestor de respaldo y se dispara una alerta

  @US-09 @RF-CRM-06
  Escenario: La atención queda abandonada
    Dado un handoff "tomado" sin actividad durante 24 horas
    Cuando vence el plazo
    Entonces vuelve al asistente con devuelto_por "vencimiento" y se avisa al huésped

  @US-10 @RF-PAN-07 @INV_PANEL_POR_ROL
  Escenario: Bandeja por zona
    Dado un gestor de la zona Z
    Cuando abre la bandeja
    Entonces ve los handoffs de Z con propiedad, resumen e historial redactado
    Y una petición a otra zona responde 403

  @US-10 @RF-PAN-07
  Escenario: Devolver al asistente
    Dado un handoff tomado
    Cuando el gestor pulsa Devolver
    Entonces el agente reanuda y el handoff queda "devuelto"

  @RF-AG-05 @RF-MCP-06
  Escenario: Escalamiento antes de la fase 4
    Dado una instalación sin bandeja de handoff activa
    Cuando el agente debe escalar
    Entonces entrega el contacto humano configurado y registra el motivo en la traza
