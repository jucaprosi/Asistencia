# ¤spec-glamping
# language: es
Característica: Administración y asistente del líder

  @US-15 @RF-ARM-09 @RF-PAN-06
  Escenario: Pregunta al asistente
    Dado un líder autenticado
    Cuando pregunta "¿cuánto vendió X en septiembre?"
    Entonces recibe datos del alcance de su rol, sin historial persistente

  @US-15 @RF-ARM-09
  Escenario: Cambio de configuración acotado
    Dado un cambio permitido
    Cuando el líder lo pide
    Entonces ve qué cambiará y debe confirmar
    Y el cambio queda en arm.configuracion con autor y hora

  @US-15 @RF-ARM-09
  Escenario: Cambio reservado
    Dado un pedido de cambiar una regla de comisión
    Cuando el líder lo solicita
    Entonces el asistente lo rechaza y remite al administrador

  @US-16 @CU-09 @RF-PAN-09
  Escenario: Administrar usuarios
    Dado un administrador
    Cuando da de alta un usuario con rol
    Entonces el cambio aplica y deja evento en el audit log con usuario_id

  @US-16 @RF-PAN-09
  Escenario: Reglas por versión
    Dado una regla vigente
    Cuando el administrador la cambia
    Entonces se crea una versión nueva y la anterior no se altera

  @US-16 @RF-PAN-09
  Escenario: Solo el administrador entra
    Dado un líder
    Cuando abre Administración
    Entonces el BFF responde 403
