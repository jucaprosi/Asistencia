# ¤spec-glamping
# language: es
Característica: Comisiones, tablero y cierre

  @US-07 @CU-06 @RF-ARM-07 @INV_COMISION_PROPIA
  Escenario: Consulta propia
    Dado ventas propias en el período
    Cuando el vendedor pregunta "¿cuánto llevo?"
    Entonces recibe validada, pendiente y número de ventas, solo suyas

  @US-07 @RF-ARM-07
  Escenario: Consulta ajena
    Dado un vendedor que pregunta por otro
    Cuando el ARM responde
    Entonces no revela datos ajenos y el intento queda en el audit log

  @US-08 @CU-07 @RF-ARM-08 @RF-PAN-04
  Escenario: Tablero que cuadra
    Dado ventas validadas en el mes
    Cuando el líder abre el tablero
    Entonces ve ventas por mes, vendedor y propiedad y comisiones validadas y pendientes
    Y los totales coinciden al centavo con la exportación CSV

  @US-14 @RF-COM-02 @RF-PAN-05
  Escenario: Cierre de período
    Dado un período abierto con su resumen previo
    Cuando el líder confirma por escrito el período
    Entonces el período queda inmutable y el BFF responde 409 a cualquier modificación

  @US-14 @RF-COM-02
  Escenario: Venta tardía
    Dado una venta de octubre validada cuando octubre ya cerró
    Cuando se fija la comisión
    Entonces entra al período abierto más antiguo con periodo_origen octubre

  @US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE
  Escenario: Escalón por volumen reproducible
    Dado una regla escalonada y una base acumulada guardada de 1000.00
    Cuando se recalcula la comisión con la misma versión y la misma base
    Entonces el monto es idéntico aunque hayan llegado ventas posteriores

  @US-14 @RF-COM-01 @INV_COMISION_REPRODUCIBLE
  Escenario: El orden de validación no cambia el total
    Dado dos ventas del mismo vendedor y mes que cruzan un escalón
    Cuando el líder valida primero la de fecha posterior y luego la anterior
    Entonces la comisión fijada no se modifica y entra un ajuste en el período abierto
    Y el total coincide con validarlas en orden de fecha
