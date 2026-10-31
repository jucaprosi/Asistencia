# ¤spec-glamping
# language: es
Característica: Comportamiento técnico de canal, agente, conectores y observabilidad

  @RF-GW-02
  Escenario: Envío con reintentos y estados
    Dado un mensaje saliente y una API de Meta que falla dos veces
    Cuando el canal lo envía
    Entonces reintenta con espera creciente hasta 3 veces
    Y registra el mensaje_id y cada estado sent, delivered, read o failed

  @RF-GW-04
  Escenario: Plantilla con variables incorrectas o sin aprobar
    Dado una plantilla no aprobada o con variables que no coinciden
    Cuando se intenta enviar
    Entonces la compuerta la rechaza con un error tipado y no llama a Meta

  @RF-GW-05
  Escenario: Medio recibido
    Dado una imagen de un remitente permitido
    Cuando el canal la recibe
    Entonces la guarda en el almacenamiento de archivos
    Y el agente recibe una referencia, nunca los bytes

  @RF-GW-06
  Escenario: Canales separados
    Dado mensajes del canal de huéspedes y del canal de vendedores
    Cuando se enrutan
    Entonces ninguno de vendedores llega al agente de huéspedes y ninguno de huéspedes llega al ARM

  @RF-GW-03 @INV_VENTANA_24H
  Escenario: Texto libre fuera de ventana
    Dado un contacto sin mensajes en las últimas 24 horas
    Cuando se intenta enviar texto libre
    Entonces la compuerta lo rechaza con un error tipado y nada llega a Meta

  @RF-AG-02 @INV_SIN_FUGA_ENTRE_PROPIEDADES
  Escenario: Prompt por propiedad
    Dado una propiedad resuelta
    Cuando el agente arma el prompt
    Entonces solo contiene datos de esa propiedad y la traza guarda el hash del prompt

  @RF-AG-03 @INV_ALLOWLIST_POR_ACCION
  Escenario: Herramientas expuestas por rol
    Dado una conversación con un rol
    Cuando el agente llama al modelo
    Entonces solo expone las herramientas de ese rol y la traza guarda el conjunto expuesto

  @RF-AG-04
  Escenario: Tope de iteraciones
    Dado un bucle de herramientas que no termina
    Cuando supera 6 iteraciones
    Entonces el agente abre un handoff con motivo "limite_iteraciones"

  @RF-AG-06 @INV_PII_FUERA_DEL_MODELO
  Escenario: Memoria tras un reinicio
    Dado una conversación abierta
    Cuando el contenedor se reinicia
    Entonces el contexto sigue disponible y el historial solo contiene tokens

  @RF-AG-07 @INV_CACHE_SIN_PRECIOS
  Escenario: Caché semántico
    Dado una respuesta con precio o disponibilidad
    Cuando se decide si guardarla en caché
    Entonces no se guarda y la decisión queda en la traza

  @US-03 @RF-AG-08 @INV_ENVIO_UNICO
  Escenario: El planificador se reinicia
    Dado instrucciones de check-in ya enviadas hoy para una reserva
    Cuando el planificador corre otra vez
    Entonces no se envían de nuevo

  @RF-RAG-02
  Escenario: Fragmentación por secciones
    Dado un documento con secciones de dos propiedades
    Cuando se fragmenta
    Entonces ningún chunk mezcla propiedades y cada uno conserva ruta y encabezado

  @RF-RAG-05
  Escenario: Citación en la traza
    Dado una respuesta basada en el corpus
    Cuando se registra
    Entonces la traza contiene al menos un chunk y el huésped no ve esos identificadores

  @RF-RAG-06 @RF-OBS-03
  Escenario: Evaluación bajo umbral
    Dado una suite con resultado bajo su umbral
    Cuando corre scripts/run_evals.py
    Entonces termina con Exit Code distinto de 0

  @RF-PMS-01
  Escenario: Contrato del conector PMS
    Dado la implementación FakePMS y la del proveedor
    Cuando corre la misma prueba de contrato
    Entonces ambas devuelven tipos propios del dominio y ningún objeto del SDK

  @RF-PMS-02 @INV_ESCRITURA_PMS_EXPLICITA
  Escenario: Escritura deshabilitada
    Dado una operación de escritura no habilitada en la configuración
    Cuando se invoca
    Entonces falla con EscrituraDeshabilitada y el PMS no recibe nada

  @RF-PMS-03 @INV_ESCRITURA_PMS_EXPLICITA
  Escenario: Errores del PMS
    Dado un PMS que supera 8 segundos
    Cuando la operación es de lectura se reintenta
    Y cuando es de escritura sin clave de idempotencia no se reintenta
    Entonces el agente recibe un error tipado accionable

  @RF-PMS-04 @INV_SIN_CLIENTES_OTA
  Escenario: Sin clientes de OTA
    Dado el repositorio
    Cuando se revisan manifiestos e imports
    Entonces no existe ningún cliente directo de Airbnb, Booking o VRBO

  @RF-CRM-01
  Escenario: Contrato del conector CRM
    Dado FakeCRM y la implementación del proveedor
    Cuando corre la misma prueba de contrato
    Entonces ambas devuelven tipos propios del dominio

  @RF-CRM-02
  Escenario: Cambio de proveedor de CRM
    Dado un cambio de proveedor en config_crm_conector.yaml
    Cuando arranca el sistema
    Entonces ninguna otra sala cambia

  @RF-CRM-03 @INV_VENTA_FIRMADA_IDEMPOTENTE
  Escenario: Publicar dos veces la misma venta
    Dado una venta ya publicada
    Cuando se reintenta
    Entonces el receptor verifica la firma y no se crea un segundo contacto ni oportunidad

  @RF-CRM-05
  Escenario: Confinamiento de MCP de comunidad
    Dado un MCP de comunidad
    Cuando se revisan los imports
    Entonces no aparece fuera de features/crm_conector

  @RF-ARM-04 @INV_COMISION_REPRODUCIBLE
  Escenario: Validaciones concurrentes del mismo vendedor
    Dado dos ventas del mismo vendedor con regla escalonada
    Cuando se validan a la vez
    Entonces cada una guarda la base que corresponde a su fecha de venta y número de ticket

  @RF-ARM-05 @INV_TICKET_UNICO
  Escenario: Tickets bajo concurrencia
    Dado 50 ventas registradas en paralelo, algunas con fallo y ROLLBACK
    Cuando terminan
    Entonces los tickets son consecutivos, sin huecos ni repetidos

  @RF-ARM-03 @INV_ESTADOS_VENTA
  Escenario: Transición inválida
    Dado una venta "anulada"
    Cuando alguien intenta cambiar su estado
    Entonces la base de datos la rechaza

  @RF-COM-03
  Escenario: Exportación del período
    Dado un período cerrado
    Cuando se exporta
    Entonces el archivo valida contra esquema_exportacion.json

  @RF-SEC-06 @INV_AUDIT_APPEND_ONLY
  Escenario: Audit log inalterable
    Dado el rol de aplicación
    Cuando intenta modificar o borrar una fila del audit log
    Entonces la base de datos lo rechaza

  @RF-SEC-07
  Escenario: Aislamiento por propiedad en la base
    Dado el rol de aplicación con la propiedad A
    Cuando consulta chunks
    Entonces no recibe filas de la propiedad B

  @RF-PRIV-02 @RF-PRIV-06
  Escenario: Inventario completo
    Dado una tabla con datos personales o un proveedor que los recibe
    Cuando corre la verificación
    Entonces debe constar en docs/privacidad/INVENTARIO.md

  @RF-OBS-01
  Escenario: Logs sin datos personales
    Dado un mensaje con teléfono y correo
    Cuando se registra
    Entonces la línea JSON no contiene esos valores

  @RF-OBS-02 @INV_TRAZA_POR_MENSAJE
  Escenario: Traza por mensaje
    Dado un mensaje entrante
    Cuando termina su procesamiento
    Entonces existe una traza con spans por sala, tokens y costo

  @RF-OBS-04
  Escenario: Alertas
    Dado datos sintéticos de cada condición de alerta
    Cuando corre la verificación
    Entonces se dispara cada alerta una vez

  @RF-MCP-07
  Escenario: Herramientas internas de CRM
    Dado una conversación de huésped
    Cuando el modelo solicita "crear_oportunidad_crm"
    Entonces se rechaza porque solo el rol sistema puede usarla

  @RF-MCP-08
  Escenario: El vendedor no se declara en la entrada
    Dado una llamada a "registrar_venta"
    Cuando el modelo envía un vendedor_id
    Entonces la validación del esquema la rechaza y el servidor usa el remitente verificado

  @RF-MCP-09 @INV_COMISION_PROPIA
  Escenario: Consulta sin período
    Dado un vendedor que no indica período
    Cuando consulta su comisión
    Entonces recibe el período en curso

  @RF-PAN-03
  Escenario: Detalle de venta
    Dado una venta con transiciones
    Cuando el líder abre el detalle
    Entonces la línea de tiempo coincide con arm_jarvis.detalle

  @RF-PAN-08
  Escenario: Resolver incidencia
    Dado una incidencia abierta de la zona del gestor
    Cuando la resuelve con nota
    Entonces el huésped recibe el aviso y quedan actor y hora

  @RF-PAN-10 @INV_INTERFAZ_PURIFICADA
  Escenario: Calidad del panel
    Dado el build del panel
    Cuando corre la auditoría
    Entonces no hay errores críticos de accesibilidad, cumple el presupuesto y no contiene rastros

  @RF-PMS-06
  Escenario: Validar al titular sin llamar al PMS
    Dado una reserva guardada en la referencia local
    Cuando se valida al titular de la conversación
    Entonces la decisión usa esa referencia y el PMS no recibe ninguna llamada
