# ¤spec-glamping
# language: es
Característica: Registro de ventas desde WhatsApp

  @US-05 @CU-04 @RF-ARM-02 @RF-ARM-05
  Escenario: Venta completa
    Dado un vendedor en la whitelist
    Cuando escribe "vendí 3 noches en el depa del centro a María López, 450, llega el 15"
    Entonces en 10 segundos o menos recibe un ticket V-AAAA-NNNN con cliente, producto, monto, llegada y comisión estimada
    Y la venta queda "por_validar" con noches 3 y fecha_llegada el próximo día 15

  @US-05 @RF-ARM-02
  Escenario: Falta un campo obligatorio
    Dado un mensaje de venta sin monto
    Cuando el ARM lo procesa
    Entonces pregunta solo por el monto y no registra hasta tenerlo

  @US-05 @RF-ARM-02
  Escenario: No es una venta
    Dado un saludo o una pregunta
    Cuando el ARM lo procesa
    Entonces no crea ninguna venta

  @US-05 @RF-ARM-10
  Escenario: Varias ventas en un mensaje
    Dado un mensaje con dos ventas distintas
    Cuando el ARM lo procesa
    Entonces crea dos ventas con dos tickets y responde con ambos

  @US-05 @RF-ARM-10
  Escenario: Posible duplicado
    Dado una venta con igual cliente, producto, monto y fecha_venta en los últimos 7 días
    Cuando se registra otra igual, del mismo o de otro vendedor
    Entonces se crea marcada como posible duplicado
    Y el líder la ve señalada antes de validar

  @US-05 @RF-ARM-10
  Escenario: La reentrega no duplica la venta
    Dado un mensaje ya procesado
    Cuando el trabajador lo reintenta
    Entonces la restricción de mensaje e índice impide un segundo ticket

  @US-05 @RF-ARM-01
  Escenario: Remitente no registrado en el canal de vendedores
    Dado un número sin rol de vendedor
    Cuando escribe en el canal de vendedores
    Entonces el mensaje se registra por hash y se descarta sin respuesta

  @US-06 @CU-05 @RF-ARM-03 @RF-PAN-02
  Escenario: Validar una venta
    Dado una venta "por_validar" sin campos dudosos
    Cuando el líder la valida con una acción
    Entonces pasa a "validada", la comisión se fija y el vendedor recibe la notificación privada
    Y la publicación al CRM se encola firmada e idempotente

  @US-06 @RF-ARM-03 @RF-ARM-06
  Escenario: Rechazar una venta
    Dado una venta "por_validar"
    Cuando el líder la rechaza con motivo
    Entonces pasa a "rechazada", no genera comisión y el vendedor recibe el motivo
    Y fuera de ventana se usa la plantilla "venta_rechazada"

  @US-06 @RF-PAN-02
  Escenario: Conflicto entre dos usuarios
    Dado dos líderes sobre la misma venta
    Cuando el segundo intenta validar
    Entonces recibe conflicto y la tarjeta se recarga sin doble transición

  @US-06 @RF-ARM-03
  Escenario: Una venta validada no se edita
    Dado una venta "validada"
    Cuando alguien intenta editar el monto
    Entonces el sistema lo impide y ofrece anulación con motivo al administrador

  @US-06 @RF-COM-01
  Escenario: Sin regla vigente
    Dado una venta sin regla de comisión aplicable
    Cuando el líder intenta validar
    Entonces recibe SinReglaVigente y la venta sigue "por_validar"

  @US-06 @RF-COM-04 @RF-CRM-03
  Escenario: Anular una venta publicada
    Dado una venta "publicada" con comisión en un período cerrado
    Cuando el administrador la anula con motivo
    Entonces pasa a "anulada" y se crea un ajuste negativo en el período abierto
    Y se publica el evento "venta_anulada" al CRM

  @US-06 @RF-CRM-04 @INV_VENTA_NO_SE_PIERDE
  Escenario: El CRM no acepta la venta
    Dado una publicación que falla durante 24 horas
    Cuando se agotan los reintentos automáticos
    Entonces la venta sigue "no_publicada", se dispara una alerta y el panel ofrece reintentar
    Y un reintento exitoso la pasa a "publicada"
