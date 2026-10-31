# ¤spec-glamping
# language: es
Característica: Conocimiento del negocio

  @US-12 @RF-RAG-01
  Escenario: Cambio de política
    Dado un cambio en la política de cancelación del corpus privado
    Cuando el administrador reindexa
    Entonces termina con Exit Code 0 y los chunks antiguos se reemplazan
    Y una pregunta sobre esa política devuelve la versión nueva

  @RF-RAG-04 @INV_NO_LO_SE
  Escenario: Pregunta fuera del corpus
    Dado una pregunta sin chunk de soporte
    Cuando el agente responde
    Entonces declara que no tiene esa información y ofrece una persona

  @RF-RAG-03 @INV_SIN_FUGA_ENTRE_PROPIEDADES
  Escenario: Filtro por propiedad
    Dado chunks de las propiedades A y B
    Cuando se consulta con propiedad A
    Entonces no vuelve ningún chunk de B

  @RF-AG-01 @INV_PROPIEDAD_RESUELTA
  Escenario: Propiedad ambigua
    Dado un mensaje compatible con dos propiedades
    Cuando el agente debe usar una herramienta
    Entonces pregunta con una lista y no llama a la herramienta
