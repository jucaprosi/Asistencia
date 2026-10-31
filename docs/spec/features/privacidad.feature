# ¤spec-glamping
# language: es
Característica: Protección de datos personales

  @US-17 @RF-PRIV-01
  Escenario: Aviso en el primer contacto
    Dado un titular sin consentimiento registrado
    Cuando llega su primer mensaje
    Entonces recibe el aviso vigente una sola vez y queda el registro con su versión

  @US-17 @RF-PRIV-04
  Escenario: Eliminación por criptoborrado
    Dado una solicitud de eliminación aprobada
    Cuando el administrador la ejecuta
    Entonces se borran las filas de la bóveda del titular
    Y los tokens en audit log e historial quedan irrecuperables
    Y las filas del audit log no se modifican

  @US-17 @RF-PRIV-03
  Escenario: Retención automática
    Dado un medio más antiguo que su retención
    Cuando corre la tarea diaria
    Entonces el medio se elimina y la purga queda en el audit log

  @US-17 @RF-PRIV-05
  Escenario: Conservación por obligación legal
    Dado un titular con una venta validada sujeta a conservación
    Cuando pide eliminación
    Entonces la solicitud queda "atendida_parcial" con motivo registrado

  @RF-SEC-05 @INV_PII_FUERA_DEL_MODELO
  Escenario: Nada de PII hacia el modelo
    Dado un mensaje con nombre, teléfono, correo, cédula, tarjeta y dirección
    Cuando se llama al modelo
    Entonces el payload capturado no contiene ninguno de esos valores
    Y la respuesta rehidratada restituye el valor exacto
