# ¤spec-glamping
# language: es
Característica: Anfitriones y comisión de plataforma

  @RF-ANF-01
  Escenario: Alta de un anfitrión
    Dado un anfitrión con términos aceptados y porcentaje pactado
    Cuando el administrador lo registra
    Entonces queda activo y su teléfono se guarda como token

  @RF-ANF-01
  Escenario: Alta sin términos aceptados
    Dado un anfitrión sin versión de términos
    Cuando el administrador intenta registrarlo
    Entonces el registro se rechaza

  @RF-ANF-02
  Escenario: El equipo publica un hospedaje
    Dado un hospedaje en borrador
    Cuando un administrador lo publica
    Entonces queda publicado con el actor y la fecha

  @RF-ANF-03 @INV_SOLO_PUBLICADO
  Escenario: Un hospedaje pausado no se ofrece
    Dado un hospedaje pausado
    Cuando un visitante busca o pregunta al asistente
    Entonces ese hospedaje no aparece
    Y cada hospedaje visible dice quién lo ofrece

  @US-19 @RF-ANF-04
  Escenario: El huésped solicita una reserva
    Dado una reserva preliminar de un hospedaje publicado
    Cuando el asistente crea la solicitud
    Entonces fechas y total salen del PMS
    Y el porcentaje del anfitrión queda congelado
    Y el anfitrión recibe la plantilla con vigencia de 24 horas

  @US-19 @RF-ANF-05 @INV_CONTACTO_TRAS_CONFIRMAR
  Escenario: El anfitrión confirma
    Dado una solicitud vigente
    Cuando su anfitrión la confirma
    Entonces el estado pasa a confirmada
    Y solo entonces huésped y anfitrión reciben el contacto del otro

  @US-19 @RF-ANF-05
  Escenario: Solicitud sin respuesta
    Dado una solicitud sin respuesta al vencer
    Cuando corre el vencimiento
    Entonces pasa a expirada y el huésped recibe otras opciones

  @RF-ANF-05 @INV_AISLAMIENTO_ANFITRION
  Escenario: Otro anfitrión intenta responder
    Dado una solicitud de otro anfitrión
    Cuando un anfitrión intenta responderla o verla
    Entonces la operación se rechaza y queda en el audit log

  @RF-ANF-06
  Escenario: El anfitrión reporta que el huésped no llegó
    Dado una reserva confirmada dentro del plazo de reporte
    Cuando el anfitrión reporta no_show
    Entonces no se genera comisión

  @RF-ANF-06
  Escenario: Sin reporte la estadía se completa
    Dado una reserva confirmada cuyo plazo de reporte venció
    Cuando corre el proceso diario
    Entonces pasa a completada

  @US-20 @RF-ANF-07 @INV_COMISION_PLATAFORMA_UNICA
  Escenario: Estado de cuenta mensual
    Dado estadías completadas en un período
    Cuando corre el cierre
    Entonces cada estadía aparece una sola vez con base, porcentaje y comisión
    Y el anfitrión puede consultar su estado de cuenta por WhatsApp

  @US-20 @RF-ANF-08
  Escenario: Pago registrado
    Dado un estado de cuenta emitido
    Cuando el administrador registra el pago
    Entonces pasa a pagado con actor y fecha

  @RF-ANF-08
  Escenario: Estado de cuenta vencido
    Dado un estado de cuenta vencido por más de los días configurados
    Cuando corre el proceso diario
    Entonces los hospedajes del anfitrión pasan a pausado
