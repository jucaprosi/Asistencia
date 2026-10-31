# Matriz de trazabilidad
`¤spec-glamping`

Archivo generado por `scripts/generar_trazabilidad.py`. No se edita a mano.

| Requisito | Tareas | Escenarios |
| :--- | :--- | :--- |
| RF-GW-01 | T-101, T-110 | ingesta_mensajes.feature: Un mensaje válido queda persistido antes de responder a Meta<br>ingesta_mensajes.feature: Una firma inválida se rechaza sin procesar<br>ingesta_mensajes.feature: Un reintento de Meta no duplica el mensaje |
| RF-GW-02 | T-101 | plataforma.feature: Envío con reintentos y estados |
| RF-GW-03 | T-101 | checkin.feature: Fuera de la ventana de 24 horas<br>plataforma.feature: Texto libre fuera de ventana |
| RF-GW-04 | T-101 | plataforma.feature: Plantilla con variables incorrectas o sin aprobar |
| RF-GW-05 | T-101 | plataforma.feature: Medio recibido |
| RF-GW-06 | T-503, T-510 | plataforma.feature: Canales separados |
| RF-GW-07 | T-101 | ingesta_mensajes.feature: Un mensaje válido queda persistido antes de responder a Meta<br>ingesta_mensajes.feature: Un reintento de Meta no duplica el mensaje<br>ingesta_mensajes.feature: Una caída del proceso no pierde el mensaje |
| RF-GW-08 | T-101 | ingesta_mensajes.feature: Los mensajes seguidos de un remitente se atienden como un solo turno |
| RF-AG-01 | T-301 | conocimiento.feature: Propiedad ambigua |
| RF-AG-02 | T-104 | plataforma.feature: Prompt por propiedad |
| RF-AG-03 | T-301 | plataforma.feature: Herramientas expuestas por rol |
| RF-AG-04 | T-104 | plataforma.feature: Tope de iteraciones |
| RF-AG-05 | T-104 | incidencias_handoff.feature: Escalamiento antes de la fase 4<br>reservas.feature: El PMS no responde |
| RF-AG-06 | T-104 | plataforma.feature: Memoria tras un reinicio |
| RF-AG-07 | T-403 | plataforma.feature: Caché semántico |
| RF-AG-08 | T-301 | plataforma.feature: El planificador se reinicia |
| RF-RAG-01 | T-201 | conocimiento.feature: Cambio de política |
| RF-RAG-02 | T-201 | plataforma.feature: Fragmentación por secciones |
| RF-RAG-03 | T-201 | conocimiento.feature: Filtro por propiedad |
| RF-RAG-04 | T-201 | conocimiento.feature: Pregunta fuera del corpus |
| RF-RAG-05 | T-201 | plataforma.feature: Citación en la traza |
| RF-RAG-06 | T-201 | plataforma.feature: Evaluación bajo umbral |
| RF-PMS-01 | T-202 | plataforma.feature: Contrato del conector PMS |
| RF-PMS-02 | T-202, T-212 | plataforma.feature: Escritura deshabilitada |
| RF-PMS-03 | T-202 | plataforma.feature: Errores del PMS |
| RF-PMS-04 | T-202 | plataforma.feature: Sin clientes de OTA |
| RF-PMS-05 | T-202 | reservas.feature: Una reserva preliminar sin pago expira |
| RF-PMS-06 | T-202 | plataforma.feature: Validar al titular sin llamar al PMS |
| RF-CRM-01 | T-302 | plataforma.feature: Contrato del conector CRM |
| RF-CRM-02 | T-302, T-601 | plataforma.feature: Cambio de proveedor de CRM |
| RF-CRM-03 | T-601 | plataforma.feature: Publicar dos veces la misma venta<br>ventas.feature: Anular una venta publicada |
| RF-CRM-04 | T-601, T-602 | ventas.feature: El CRM no acepta la venta |
| RF-CRM-05 | T-310, T-601 | plataforma.feature: Confinamiento de MCP de comunidad |
| RF-CRM-06 | T-302 | incidencias_handoff.feature: Handoff al gestor de la zona<br>incidencias_handoff.feature: Handoff sin zona resuelta<br>incidencias_handoff.feature: Nadie toma el handoff<br>incidencias_handoff.feature: La atención queda abandonada |
| RF-ARM-01 | T-502 | ventas.feature: Remitente no registrado en el canal de vendedores |
| RF-ARM-02 | T-502 | ventas.feature: Venta completa<br>ventas.feature: Falta un campo obligatorio<br>ventas.feature: No es una venta |
| RF-ARM-03 | T-502 | plataforma.feature: Transición inválida<br>ventas.feature: Validar una venta<br>ventas.feature: Rechazar una venta<br>ventas.feature: Una venta validada no se edita |
| RF-ARM-04 | T-502 | plataforma.feature: Validaciones concurrentes del mismo vendedor |
| RF-ARM-05 | T-502 | plataforma.feature: Tickets bajo concurrencia<br>ventas.feature: Venta completa |
| RF-ARM-06 | T-502, T-510 | ventas.feature: Rechazar una venta |
| RF-ARM-07 | T-502 | comisiones.feature: Consulta propia<br>comisiones.feature: Consulta ajena |
| RF-ARM-08 | T-602 | comisiones.feature: Tablero que cuadra |
| RF-ARM-09 | T-502 | administracion.feature: Pregunta al asistente<br>administracion.feature: Cambio de configuración acotado<br>administracion.feature: Cambio reservado |
| RF-ARM-10 | T-502 | ventas.feature: Varias ventas en un mensaje<br>ventas.feature: Posible duplicado<br>ventas.feature: La reentrega no duplica la venta |
| RF-COM-01 | T-501 | comisiones.feature: Escalón por volumen reproducible<br>comisiones.feature: El orden de validación no cambia el total<br>comisiones.feature: Modo graduado<br>comisiones.feature: Modo volumen<br>ventas.feature: Sin regla vigente |
| RF-COM-02 | T-501 | comisiones.feature: Cierre de período<br>comisiones.feature: Venta tardía<br>comisiones.feature: Venta tardía con escalón |
| RF-COM-03 | T-603 | plataforma.feature: Exportación del período |
| RF-COM-04 | T-501 | comisiones.feature: Anular una venta no toca a las demás<br>ventas.feature: Anular una venta publicada |
| RF-SEC-01 | T-102 | seguridad.feature: Un número nuevo puede preguntar como huésped potencial<br>seguridad.feature: Un número bloqueado se ignora<br>seguridad.feature: Pasar a huésped activo |
| RF-SEC-02 | T-102 | seguridad.feature: Pasar a huésped activo<br>seguridad.feature: El modelo pide una herramienta prohibida |
| RF-SEC-03 | T-102 | seguridad.feature: Límite por remitente |
| RF-SEC-04 | T-102, T-401 | seguridad.feature: Intento de inyección |
| RF-SEC-05 | T-102 | privacidad.feature: Nada de PII hacia el modelo |
| RF-SEC-06 | T-102 | plataforma.feature: Audit log inalterable |
| RF-SEC-07 | T-304 | plataforma.feature: Aislamiento por propiedad en la base |
| RF-SEC-08 | T-304 | checkin.feature: Un código de reserva ajeno no abre las instrucciones<br>checkin.feature: Los secretos operativos no pasan por el modelo |
| RF-PRIV-01 | T-102 | privacidad.feature: Aviso en el primer contacto |
| RF-PRIV-02 | T-102 | plataforma.feature: Inventario completo |
| RF-PRIV-03 | T-401 | privacidad.feature: Retención automática |
| RF-PRIV-04 | T-401 | privacidad.feature: Eliminación por criptoborrado |
| RF-PRIV-05 | T-401 | privacidad.feature: Conservación por obligación legal |
| RF-PRIV-06 | T-401 | plataforma.feature: Inventario completo |
| RF-OBS-01 | T-103 | plataforma.feature: Logs sin datos personales |
| RF-OBS-02 | T-103 | plataforma.feature: Traza por mensaje |
| RF-OBS-03 | T-402 | plataforma.feature: Evaluación bajo umbral |
| RF-OBS-04 | T-402 | plataforma.feature: Alertas |
| RF-MCP-01 | T-203 | reservas.feature: Consulta con disponibilidad<br>reservas.feature: Consulta sin disponibilidad |
| RF-MCP-02 | T-203 | reservas.feature: Consulta con disponibilidad |
| RF-MCP-03 | T-203 | reservas.feature: Reserva preliminar<br>reservas.feature: Reintento idempotente |
| RF-MCP-04 | T-203 | checkin.feature: Instrucciones de la propiedad correcta<br>checkin.feature: Un código de reserva ajeno no abre las instrucciones |
| RF-MCP-05 | T-203, T-204 | incidencias_handoff.feature: Registro de incidencia<br>incidencias_handoff.feature: Incidencia crítica |
| RF-MCP-06 | T-203, T-302 | incidencias_handoff.feature: Handoff al gestor de la zona<br>incidencias_handoff.feature: Escalamiento antes de la fase 4<br>reservas.feature: Cancelar o cambiar una reserva pasa por una persona |
| RF-MCP-07 | T-203 | plataforma.feature: Herramientas internas de CRM |
| RF-MCP-08 | T-504 | plataforma.feature: El vendedor no se declara en la entrada |
| RF-MCP-09 | T-504 | plataforma.feature: Consulta sin período |
| RF-PAN-01 | T-303 | seguridad.feature: Acceso al panel<br>seguridad.feature: Correo no registrado<br>seguridad.feature: Demasiados intentos |
| RF-PAN-02 | T-505 | ventas.feature: Validar una venta<br>ventas.feature: Conflicto entre dos usuarios |
| RF-PAN-03 | T-505 | plataforma.feature: Detalle de venta<br>plataforma.feature: Desglose de comisión |
| RF-PAN-04 | T-604 | comisiones.feature: Tablero que cuadra<br>plataforma.feature: Estado de cuenta por vendedor |
| RF-PAN-05 | T-604 | comisiones.feature: Cierre de período |
| RF-PAN-06 | T-505 | administracion.feature: Pregunta al asistente |
| RF-PAN-07 | T-303, T-701 | incidencias_handoff.feature: Bandeja por zona<br>incidencias_handoff.feature: Devolver al asistente |
| RF-PAN-08 | T-303 | plataforma.feature: Resolver incidencia |
| RF-PAN-09 | T-404, T-604 | administracion.feature: Administrar usuarios<br>administracion.feature: Reglas por versión<br>administracion.feature: Solo el administrador entra |
| RF-PAN-10 | T-404 | plataforma.feature: Calidad del panel |
| RF-PAN-11 | T-801, T-810 | plataforma.feature: Instalar la terminal móvil |
| RF-PAN-12 | T-801, T-810 | plataforma.feature: Aviso de venta por validar |
| RF-PAN-13 | T-801 | plataforma.feature: Sin red |
| RF-PAN-14 | T-801 | plataforma.feature: Doble toque con red inestable |
| RF-WEB-01 | T-105 | web_publica.feature: Ver el catálogo sin datos del PMS |
| RF-WEB-02 | T-205 | web_publica.feature: Buscar por fechas<br>web_publica.feature: El PMS no responde durante la búsqueda |
| RF-WEB-03 | T-205 | web_publica.feature: Comparar propiedades |
| RF-WEB-04 | T-105, T-205 | web_publica.feature: Pasar a WhatsApp con contexto<br>web_publica.feature: La web no reserva |
| RF-WEB-05 | T-105 | web_publica.feature: Exceso de consultas |
| RF-WEB-06 | T-105 | web_publica.feature: Calidad pública |
| RNF-01 | T-111 | por árbitro de la tabla del PRD |
| RNF-02 | T-211 | por árbitro de la tabla del PRD |
| RNF-03 | T-502 | por árbitro de la tabla del PRD |
| RNF-04 | T-201 | por árbitro de la tabla del PRD |
| RNF-05 | T-410 | por árbitro de la tabla del PRD |
| RNF-06 | T-410, T-411 | por árbitro de la tabla del PRD |
| RNF-07 | T-401 | por árbitro de la tabla del PRD |
| RNF-08 | T-110 | por árbitro de la tabla del PRD |
| RNF-09 | T-601, T-611 | por árbitro de la tabla del PRD |
| RNF-10 | T-210, T-410, T-411, T-611 | por árbitro de la tabla del PRD |
| RNF-11 | T-110 | por árbitro de la tabla del PRD |
| RNF-12 | T-110 | por árbitro de la tabla del PRD |
| RNF-13 | T-402, T-411 | por árbitro de la tabla del PRD |
| RNF-14 | T-110, T-210, T-610 | por árbitro de la tabla del PRD |
| RNF-15 | T-610 | por árbitro de la tabla del PRD |
| RNF-16 | T-403 | por árbitro de la tabla del PRD |
| RNF-17 | T-401 | por árbitro de la tabla del PRD |
| RNF-18 | T-102 | por árbitro de la tabla del PRD |
| RNF-19 | T-110 | por árbitro de la tabla del PRD |
| US-01 | T-211 | reservas.feature: Consulta con disponibilidad<br>reservas.feature: Consulta sin disponibilidad<br>reservas.feature: El PMS no responde |
| US-02 | T-211 | reservas.feature: Reserva preliminar<br>reservas.feature: Reintento idempotente<br>reservas.feature: Una reserva preliminar sin pago expira<br>reservas.feature: Cancelar o cambiar una reserva pasa por una persona |
| US-03 | T-301, T-310, T-311 | checkin.feature: Instrucciones de la propiedad correcta<br>checkin.feature: Fuera de la ventana de 24 horas<br>checkin.feature: Un código de reserva ajeno no abre las instrucciones<br>checkin.feature: Los secretos operativos no pasan por el modelo<br>plataforma.feature: El planificador se reinicia |
| US-04 | T-211 | incidencias_handoff.feature: Registro de incidencia<br>incidencias_handoff.feature: Incidencia crítica |
| US-05 | T-511 | ventas.feature: Venta completa<br>ventas.feature: Falta un campo obligatorio<br>ventas.feature: No es una venta<br>ventas.feature: Varias ventas en un mensaje<br>ventas.feature: Posible duplicado<br>ventas.feature: La reentrega no duplica la venta<br>ventas.feature: Remitente no registrado en el canal de vendedores |
| US-06 | T-505, T-511 | ventas.feature: Validar una venta<br>ventas.feature: Rechazar una venta<br>ventas.feature: Conflicto entre dos usuarios<br>ventas.feature: Una venta validada no se edita<br>ventas.feature: Sin regla vigente<br>ventas.feature: Anular una venta publicada<br>ventas.feature: El CRM no acepta la venta |
| US-07 | T-511 | comisiones.feature: Consulta propia<br>comisiones.feature: Consulta ajena |
| US-08 | T-604, T-611 | comisiones.feature: Tablero que cuadra |
| US-09 | T-311 | incidencias_handoff.feature: Handoff al gestor de la zona<br>incidencias_handoff.feature: Handoff sin zona resuelta<br>incidencias_handoff.feature: Nadie toma el handoff<br>incidencias_handoff.feature: La atención queda abandonada |
| US-10 | T-311 | incidencias_handoff.feature: Bandeja por zona<br>incidencias_handoff.feature: Devolver al asistente |
| US-11 | T-411 | seguridad.feature: Intento de inyección |
| US-12 | T-211 | conocimiento.feature: Cambio de política |
| US-13 | T-311 | seguridad.feature: Acceso al panel<br>seguridad.feature: Correo no registrado<br>seguridad.feature: Demasiados intentos |
| US-14 | T-611 | comisiones.feature: Cierre de período<br>comisiones.feature: Venta tardía<br>comisiones.feature: Escalón por volumen reproducible<br>comisiones.feature: El orden de validación no cambia el total<br>comisiones.feature: Modo graduado<br>comisiones.feature: Modo volumen<br>comisiones.feature: Anular una venta no toca a las demás<br>comisiones.feature: Venta tardía con escalón |
| US-15 | T-511 | administracion.feature: Pregunta al asistente<br>administracion.feature: Cambio de configuración acotado<br>administracion.feature: Cambio reservado |
| US-16 | T-611 | administracion.feature: Administrar usuarios<br>administracion.feature: Reglas por versión<br>administracion.feature: Solo el administrador entra |
| US-17 | T-411 | privacidad.feature: Aviso en el primer contacto<br>privacidad.feature: Eliminación por criptoborrado<br>privacidad.feature: Retención automática<br>privacidad.feature: Conservación por obligación legal |
| US-18 | T-105, T-205 | web_publica.feature: Ver el catálogo sin datos del PMS<br>web_publica.feature: Buscar por fechas<br>web_publica.feature: El PMS no responde durante la búsqueda<br>web_publica.feature: Comparar propiedades<br>web_publica.feature: Pasar a WhatsApp con contexto |

`¤spec-glamping/`
