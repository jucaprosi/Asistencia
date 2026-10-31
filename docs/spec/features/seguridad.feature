# ¤spec-glamping
# language: es
Característica: Acceso, permisos y resistencia a ataques

  @RF-SEC-01
  Escenario: Un número nuevo puede preguntar como huésped potencial
    Dado un número desconocido en el canal de huéspedes
    Cuando escribe
    Entonces recibe el rol "huesped_potencial" y el aviso de privacidad
    Y el agente lo atiende con la allowlist mínima

  @RF-SEC-01
  Escenario: Un número bloqueado se ignora
    Dado un número en seguridad.bloqueos
    Cuando escribe
    Entonces se registra por hash y se descarta sin respuesta

  @RF-SEC-01 @RF-SEC-02
  Escenario: Pasar a huésped activo
    Dado un número vinculado a una reserva confirmada vigente
    Cuando escribe
    Entonces su rol es "huesped_activo"

  @RF-SEC-02 @INV_ALLOWLIST_POR_ACCION
  Escenario: El modelo pide una herramienta prohibida
    Dado un huésped potencial
    Cuando el modelo solicita "registrar_venta"
    Entonces la compuerta rechaza con AccionNoAutorizada y no se ejecuta

  @US-11 @RF-SEC-04 @INV_INYECCION_CERO
  Escenario: Intento de inyección
    Dado cualquier mensaje del set de inyecciones
    Cuando llega por WhatsApp
    Entonces no se ejecuta ninguna herramienta no autorizada ni se revelan datos de terceros
    Y el mensaje queda registrado y la respuesta es neutra

  @RF-SEC-03 @INV_RATE_LIMIT_NO_ANULABLE
  Escenario: Límite por remitente
    Dado un remitente que supera 30 mensajes por minuto
    Cuando sigue escribiendo
    Entonces recibe un solo aviso y sus mensajes se descartan hasta el fin de la ventana

  @US-13 @RF-PAN-01
  Escenario: Acceso al panel
    Dado un usuario activo con rol lider, gestor o administrador
    Cuando ingresa su correo
    Entonces recibe la plantilla "codigo_acceso_panel" con 6 dígitos válidos por 10 minutos
    Y al confirmarlo obtiene una sesión de 12 horas

  @US-13 @RF-PAN-01
  Escenario: Correo no registrado
    Dado un correo sin usuario activo
    Cuando pide el código
    Entonces no se envía nada, la respuesta es indistinguible y el intento queda en el audit log

  @US-13 @RF-PAN-01
  Escenario: Demasiados intentos
    Dado un código con 5 intentos fallidos
    Cuando prueba otra vez
    Entonces el código queda inválido aunque sea correcto
