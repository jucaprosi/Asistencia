# ¤spec-glamping
# language: es
Característica: Check-in autónomo sin fuga de acceso

  @US-03 @CU-02 @RF-MCP-04 @INV_SIN_FUGA_ENTRE_PROPIEDADES
  Escenario: Instrucciones de la propiedad correcta
    Dado una reserva confirmada para hoy en el departamento X del remitente
    Cuando llega la hora configurada o pregunta "¿cómo entro?"
    Entonces recibe dirección, acceso, wifi y normas de X
    Y ningún dato de otra propiedad

  @US-03 @RF-GW-03
  Escenario: Fuera de la ventana de 24 horas
    Dado un huésped fuera de la ventana
    Cuando el sistema inicia el envío
    Entonces usa la plantilla aprobada "instrucciones_checkin"

  @US-03 @RF-MCP-04 @RF-SEC-08
  Escenario: Un código de reserva ajeno no abre las instrucciones
    Dado un remitente que no es titular de la reserva R
    Cuando pide las instrucciones con el código de R
    Entonces recibe ReservaNoAutorizada sin datos de la propiedad
    Y el intento queda en el audit log
    Y tras 5 intentos fallidos en 24 horas se escala a humano

  @US-03 @RF-SEC-08
  Escenario: Los secretos operativos no pasan por el modelo
    Dado instrucciones con clave de wifi y código de acceso
    Cuando la herramienta responde al agente
    Entonces el modelo recibe solo marcadores [[SECRETO:...]]
    Y el historial persistido conserva los marcadores
    Y el valor real aparece solo en el mensaje saliente al titular
