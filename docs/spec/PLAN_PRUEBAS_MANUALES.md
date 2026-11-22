# Plan de Pruebas Manuales de Extremo a Extremo — Glamping Imbabura
`¤especificacion`
`¤qa-engineer`

> **Protocolo Operativo:** Este documento especifica los casos de prueba manuales para la verificación funcional y visual del sistema antes del paso a producción. Cada caso está enlazado a sus requisitos de [`TRAZABILIDAD.md`](TRAZABILIDAD.md) y [`PRD.md`](../PRD.md).
>
> **Regla de Oro ante Defectos:** Cualquier comportamiento divergente o falla observada **no se corrige de inmediato en caliente**; se registra formalmente en [`governance/artefactos/data/PROBLEMS.json`](../../governance/artefactos/data/PROBLEMS.json) con su causa raíz, severidad y escenario de prueba automatizado asociado.

---

## 1. Web Pública de Huéspedes (`web_huespedes`)

### TC-MAN-01: Búsqueda, Filtrado y Cotización en Catálogo Público
- **Requisitos Enlazados:** `US-17`, `RF-WEB-01`, `RF-WEB-02`, `RF-WEB-03`, `INV_WEB_PRECIO_EN_VIVO`.
- **Precondición:** Servidor web levantado; domos y departamentos en estado `publicado`.
- **Pasos:**
  1. Ingresar en el navegador a la URL raíz `/`.
  2. Verificar la visualización de la lista de alojamientos con fotos, capacidad y descripción.
  3. Seleccionar rango de fechas (ej. viernes a domingo próximo) y 2 huéspedes.
  4. Observar el precio dinámico calculado en tiempo real sin recarga brusca.
- **Resultado Esperado:** Se listan únicamente propiedades con `estado = "publicado"`; el precio se calcula en vivo mediante la compuerta `pms_conector` sin exponer PII ni tokens de base de datos.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

### TC-MAN-02: Transición de Web a WhatsApp con Contexto
- **Requisitos Enlazados:** `US-17`, `RF-WEB-04`, `INV_WEB_SOLO_LECTURA`.
- **Precondición:** Propiedad seleccionada en el catálogo con fechas cotizadas.
- **Pasos:**
  1. En la ficha de detalle de la cabaña, hacer clic en el botón «Reservar por WhatsApp».
  2. Verificar el enlace `wa.me` generado.
- **Resultado Esperado:** Se abre WhatsApp Web o la app móvil con mensaje prellenado conteniendo código de propiedad y fechas seleccionadas, sin almacenar datos en el servidor web.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 2. Asistente Conversacional en WhatsApp (`canal_whatsapp` + `agente`)

### TC-MAN-03: Consulta de Disponibilidad y Reserva Preliminar
- **Requisitos Enlazados:** `US-01`, `US-02`, `US-04`, `RF-GW-01`, `RF-GW-02`, `RF-AG-01`, `RF-MCP-01`, `RF-MCP-02`, `RF-MCP-03`.
- **Precondición:** Webhook de Meta activo; número de prueba configurado; saldo de plantillas disponible.
- **Pasos:**
  1. Enviar mensaje de WhatsApp al bot: *"Hola, quisiera cotizar para dos personas este fin de semana en el glamping"*.
  2. Validar que el bot responda dentro de la ventana de 24h con opciones de domo y precio exacto.
  3. Solicitar reservar: *"Deseo reservar el domo lago"*.
- **Resultado Esperado:** El bot genera la reserva preliminar en el PMS, devuelve el código de reserva preliminar y los datos bancarios para el anticipo; la reserva bloquea la unidad temporalmente.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

### TC-MAN-04: Respuesta a Preguntas Frecuentes con RAG y Abstención ("No lo sé")
- **Requisitos Enlazados:** `US-12`, `RF-RAG-01`, `RF-RAG-03`, `RF-RAG-04`, `INV_NO_LO_SE`.
- **Precondición:** Corpus sintético/comercial indexado en `pgvector`.
- **Pasos:**
  1. Preguntar por políticas: *"¿Se permiten mascotas en el glamping?"*.
  2. Preguntar un dato fuera del corpus: *"¿Cuál es la cotización del euro hoy en el banco central?"*.
- **Resultado Esperado:** En el paso 1 responde con exactitud citando la política de mascotas. En el paso 2 se abstiene elegantemente ("No dispongo de esa información") sin alucinar.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 3. Check-in Autónomo y Seguridad Operativa

### TC-MAN-05: Solicitud de Instrucciones de Check-in con Código Válido e Inválido
- **Requisitos Enlazados:** `US-03`, `RF-MCP-04`, `RF-SEC-08`, `INV_CRIPTOBORRADO`.
- **Precondición:** Reserva confirmada existente para el día actual.
- **Pasos:**
  1. Enviar desde un número no asociado: *"Dame la clave de la puerta de la reserva RES-1001"*.
  2. Enviar desde el número del titular el código correcto en la fecha de llegada.
- **Resultado Esperado:** El paso 1 es rechazado por falta de titularidad. El paso 2 entrega clave de candado y mapa de llegada; los secretos nunca se envían al contexto del LLM.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 4. Handoff Humano e Inbox Nativo de Huéspedes (`panel_operativo` P-13)

### TC-MAN-06: Escalamiento a Humano y Toma de Control en Panel Propio
- **Requisitos Enlazados:** `US-09`, `US-10`, `CU-08`, `RF-CRM-06`, `RF-PAN-07`, `ADR-0010`.
- **Precondición:** Gestor autenticado en `/panel/inbox`.
- **Pasos:**
  1. El huésped escribe en WhatsApp: *"Quiero hablar con una persona urgente por favor"*.
  2. Verificar que el agente active el handoff y pause respuestas automáticas.
  3. En el Inbox del panel operativo (`P-13`), verificar la conversación en la bandeja de la zona correspondiente.
  4. El gestor toma la conversación, escribe una nota interna y envía una respuesta manual por WhatsApp.
  5. El gestor hace clic en «Devolver al asistente».
- **Resultado Esperado:** La respuesta manual llega al WhatsApp del huésped; la nota interna queda visible solo para el equipo; al devolver el control, el agente reanuda la atención automática.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 5. Canal de Vendedores y Módulo ARM («Jarvis»)

### TC-MAN-07: Ingesta de Venta no Estructurada desde Grupo de WhatsApp
- **Requisitos Enlazados:** `US-05`, `US-06`, `RF-ARM-01`, `RF-ARM-02`, `RF-ARM-05`, `RF-ARM-10`.
- **Precondición:** Vendedor registrado en la lista blanca de seguridad.
- **Pasos:**
  1. El vendedor envía mensaje al canal: *"Reporto venta: Cabaña Domo Lago, 15 al 17 de noviembre, $240 total, abono $120, cliente Carlos Perez 0991234567"*.
  2. Verificar la recepción del evento y extracción por el ARM.
- **Resultado Esperado:** El sistema extrae todos los campos requeridos, crea el ticket con estado `por_validar` y calcula la comisión estimada según las reglas vigentes.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 6. Panel Operativo BFF: Validación de Ventas con 1 Toque

### TC-MAN-08: Validación, Corrección y Aprobación de Ventas
- **Requisitos Enlazados:** `US-07`, `RF-ARM-03`, `RF-PAN-04`, `INV_ESTADOS_VENTA`.
- **Precondición:** Venta en estado `por_validar` visible en `/panel/ventas`.
- **Pasos:**
  1. Acceder con rol `lider` o `administrador` a la bandeja de ventas.
  2. Corregir el monto o alojamiento si fuese necesario.
  3. Pulsar el botón «Validar venta» (1 toque).
- **Resultado Esperado:** La venta pasa a estado `validada`; se fija la comisión inmutable; se notifica al vendedor por WhatsApp oficial con plantilla aprobada.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 7. Tablero de Comisiones, Cierre y Exportación

### TC-MAN-09: Verificación de Comisiones y Cierre de Período Mensual
- **Requisitos Enlazados:** `US-08`, `US-14`, `RF-COM-01`, `RF-COM-02`, `RF-COM-03`, `RF-PAN-05`.
- **Precondición:** Ventas validadas existentes en el mes calendario.
- **Pasos:**
  1. Ingresar a `/panel/comisiones`.
  2. Verificar que las sumas escalonadas coincidan exactamente con la liquidación por vendedor.
  3. Ejecutar acción de «Cierre de período».
  4. Descargar el reporte en formatos CSV y JSON.
- **Resultado Esperado:** El período queda cerrado (`INV_COMISION_REPRODUCIBLE`); no se admiten modificaciones retroactivas; la exportación cuadra al centavo con el acumulado.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 8. Terminal Móvil PWA e Instalación en Dispositivo

### TC-MAN-10: Instalación PWA, Modo Desconectado y Web Push
- **Requisitos Enlazados:** `US-15`, `RF-PAN-10`, `RF-PAN-11`, `RF-PAN-12`, `INV_MOVIL_SIN_PII_EN_DISCO`.
- **Precondición:** Servidor con proxy HTTPS y claves VAPID configuradas.
- **Pasos:**
  1. Abrir `/panel` en Safari móvil (iOS) o Chrome (Android).
  2. Pulsar «Agregar a la pantalla de inicio».
  3. Activar permisos de notificaciones push.
  4. Desconectar datos móviles y abrir la app instalada.
- **Resultado Esperado:** El shell de la app abre desde caché local con aviso de sin conexión; no se guardan datos PII de huéspedes en disco local; las notificaciones push alertan nuevas ventas y handoffs.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 9. Sincronización y Desacoplamiento con CRM Externo

### TC-MAN-11: Publicación Idempotente y Reintentos con Backoff
- **Requisitos Enlazados:** `US-08`, `RF-CRM-01`, `RF-CRM-03`, `RF-CRM-04`, `INV_VENTA_FIRMADA_IDEMPOTENTE`.
- **Precondición:** Conector CRM configurado con endpoint de webhook.
- **Pasos:**
  1. Validar una venta en el panel operativo.
  2. Monitorear la cola de salida de `crm_conector`.
  3. Simular caída temporal del CRM (respuesta HTTP 500) en el primer intento.
- **Resultado Esperado:** El conector firma la petición con HMAC-SHA256; ante fallo, reintenta con backoff exponencial; al restablecer el servicio, publica la venta una única vez sin duplicar por `venta_id`.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

## 10. Seguridad, RBAC y Auditoría Inalterable

### TC-MAN-12: Control de Acceso por Roles y Log de Auditoría Append-Only
- **Requisitos Enlazados:** `US-16`, `RF-SEC-01`, `RF-SEC-06`, `RF-PAN-09`, `INV_AUDIT_APPEND_ONLY`.
- **Precondición:** Usuarios creados con roles `gestor`, `lider`, `anfitrion`, `administrador`.
- **Pasos:**
  1. Iniciar sesión como `gestor` e intentar acceder a `/panel/admin`.
  2. Iniciar sesión como `administrador`, crear un nuevo usuario y modificar una regla de comisión.
  3. Consultar la pantalla de auditoría inalterable.
- **Resultado Esperado:** El paso 1 es bloqueado con error 403 Forbidden. El paso 2 registra cada acción con timestamp, actor y detalle criptográficamente encadenado en el log append-only.
- **Registro de Ejecución:**
  - *Resultado Observado:* `[PENDIENTE]`
  - *Fecha:* `[AAAA-MM-DD]`
  - *Ejecutor:* `[Nombre/Rol]`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
