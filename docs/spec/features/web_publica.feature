# ¤spec-glamping
# language: es
Característica: Web pública para huéspedes

  @US-18 @RF-WEB-01
  Escenario: Ver el catálogo sin datos del PMS
    Dado el catálogo público cargado y el PMS sin responder
    Cuando un visitante abre la web
    Entonces ve las propiedades, sin precios ni cupos

  @US-18 @RF-WEB-02 @INV_WEB_PRECIO_EN_VIVO
  Escenario: Buscar por fechas
    Dado propiedades con disponibilidad en el PMS
    Cuando el visitante busca fechas y número de huéspedes
    Entonces ve solo opciones disponibles con el total del PMS en esa consulta

  @US-18 @RF-WEB-02
  Escenario: El PMS no responde durante la búsqueda
    Dado un PMS que supera su tiempo de espera
    Cuando el visitante busca
    Entonces no ve precios y se le ofrece preguntar por WhatsApp

  @US-18 @RF-WEB-03
  Escenario: Comparar propiedades
    Dado tres propiedades con opciones disponibles
    Cuando el visitante las compara
    Entonces ve capacidad, zona, comodidades y total lado a lado
    Y no puede comparar más de tres

  @US-18 @RF-WEB-04 @INV_WEB_SIN_PII
  Escenario: Pasar a WhatsApp con contexto
    Dado una opción elegida
    Cuando el visitante toca reservar por WhatsApp
    Entonces se abre el chat con un código, sin nombre ni teléfono en el enlace
    Y el asistente recibe propiedad, fechas y huéspedes al resolverlo

  @RF-WEB-04 @INV_WEB_SOLO_LECTURA
  Escenario: La web no reserva
    Dado cualquier visitante
    Cuando usa la web
    Entonces ninguna ruta crea, cambia o cancela reservas

  @RF-WEB-05 @INV_WEB_LIMITE_POR_IP
  Escenario: Exceso de consultas
    Dado una IP que supera el límite por minuto
    Cuando sigue buscando
    Entonces recibe 429 y el PMS no recibe esas consultas
    Y la IP se guarda solo como hash

  @RF-WEB-06 @INV_INTERFAZ_PURIFICADA
  Escenario: Calidad pública
    Dado el catálogo publicado
    Cuando corre la auditoría
    Entonces cumple accesibilidad y presupuesto, tiene títulos y datos para buscadores, y no contiene rastros
