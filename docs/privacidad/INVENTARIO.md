# Inventario de Datos Personales y Tratamiento LOPDP
`¤privacidad-datos`

Este documento constituye el inventario formal de actividades de tratamiento de datos personales de **Glamping Imbabura**, conforme a lo dispuesto en la **Ley Orgánica de Protección de Datos Personales (LOPDP)** de la República del Ecuador (Registro Oficial Suplemento 459 de 26-may.-2021) y el estándar canónico del proyecto (`dominio.yaml` y `esquema.sql`).

---

## 1. Principios Rectores del Tratamiento

1. **Minimización de Datos:** Se recopilan únicamente los datos estrictamente necesarios para la atención, cotización, reserva y estadía.
2. **Confidencialidad y Secreto:** Ningún dato personal (PII) en texto claro es transmitido a modelos de lenguaje externos (`INV_PII_FUERA_DEL_MODELO`) ni registrado en logs de observabilidad.
3. **Seguridad y Cifrado:** Los datos personales sensibles y secretos operativos se almacenan cifrados con AES-256-GCM en la bóveda de tokens (`seguridad.boveda_tokens`). Los identificadores de remitente se anonimizan mediante funciones hash unidireccionales SHA-256.
4. **Integridad e Inalterabilidad:** Toda acción y evento de seguridad queda registrado en una bitácora append-only (`seguridad.audit_log`) con revocación estricta de permisos de modificación y eliminación (`INV_AUDIT_APPEND_ONLY`).

---

## 2. Inventario de Tablas con Datos Personales

| Tabla | Columnas con Datos Personales | Finalidad | Base Jurídica (LOPDP) | Ubicación | Retención (`dominio.yaml`) | Medidas de Seguridad |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `seguridad.usuarios` | `correo_hash`, `numero_hash`, `rol`, `sujeto_id` | Identificación, autenticación y control de acceso RBAC de colaboradores (vendedor, líder, gestor, administrador, anfitrión). | Relación laboral o contractual (Art. 7.5 LOPDP) | BD PostgreSQL / esquema `seguridad` | Vigencia de la relación contractual + 5 años de prescripción legal | Hash SHA-256, sin valores en claro, clave foránea a UUID. |
| `seguridad.huespedes` | `telefono_token`, `nombre_token`, `idioma`, `crm_ref` | Gestión de la relación con el huésped, seguimiento comercial y atención durante la estancia. | Medidas precontractuales y ejecución de reserva (Art. 7.1 y 7.5 LOPDP) | BD PostgreSQL / esquema `seguridad` | 365 días tras la última interacción | Tokens opacos desidentificados, desacoplados del valor real. |
| `seguridad.bloqueos` | `numero_hash`, `motivo`, `bloqueado_por` | Prevención de fraudes, ataques de denegación de servicio y protección de los canales operativos. | Interés legítimo y seguridad de las operaciones (Art. 7.8 LOPDP) | BD PostgreSQL / esquema `seguridad` | Indefinida mientras persista la causa del bloqueo | Hash SHA-256, control exclusivo de administrador. |
| `seguridad.boveda_tokens` | `token`, `titular_hash`, `tipo`, `valor_cifrado` | Custodia criptográfica de PII (`nombre`, `telefono`, `correo`, `documento`, `tarjeta`, `direccion`) y secretos operativos (`clave_wifi`, `codigo_acceso`). | Consentimiento explícito y contrato de hospedaje (Art. 7.1 y 7.5 LOPDP) | BD PostgreSQL / esquema `seguridad` | 730 días sin actividad (purga mediante criptoborrado) | Cifrado simétrico autenticado AES-256-GCM con clave `PII_VAULT_KEY` y nonce único. |
| `seguridad.rate_limit` | `remitente_hash`, `ventana`, `inicio`, `contador`, `aviso_enviado` | Control de flujo volumétrico y protección ante spam o saturación de infraestructura. | Interés legítimo y seguridad técnica (Art. 7.8 LOPDP) | BD PostgreSQL / esquema `seguridad` | 7 días (eventos de ventana) | Hash SHA-256 del remitente, sin vinculación directa a nombre. |
| `seguridad.consentimientos` | `titular_hash`, `base`, `version_aviso`, `otorgado_en`, `revocado_en` | Registro probatorio y trazabilidad del consentimiento informado otorgado por titulares. | Obligación legal de cumplimiento normativo (Art. 7.2 LOPDP) | BD PostgreSQL / esquema `seguridad` | 5 años tras la revocación o terminación del tratamiento | Hash SHA-256 del titular, inmutabilidad de registros otorgados. |
| `seguridad.solicitudes_titular`| `titular_hash`, `tipo`, `estado`, `motivo` | Registro y seguimiento de solicitudes de ejercicio de derechos ARCOP. | Obligación legal (Art. 7.2 y Arts. 21-27 LOPDP) | BD PostgreSQL / esquema `seguridad` | 5 años para archivo probatorio ante la autoridad de control | Hash SHA-256 del titular, trazabilidad de plazos de respuesta. |
| `seguridad.audit_log` | `actor_token`, `rol`, `accion`, `herramienta`, `propiedad_id`, `resultado`, `hash_prompt`, `traza_id` | Registro forense e inalterable de auditoría de todas las operaciones realizadas por actores y herramientas. | Cumplimiento legal y rendición de cuentas (Art. 7.2 y Art. 50 LOPDP) | BD PostgreSQL / esquema `seguridad` | 365 días (conservación forense) | Tabla append-only; permisos `UPDATE`, `DELETE` y `TRUNCATE` estrictamente revocados (`REVOKE`). |

---

## 3. Terceros y Encargados del Tratamiento (RF-PRIV-06)

Conforme al artículo 48 de la LOPDP, los siguientes proveedores actúan en calidad de encargados del tratamiento bajo contratos o términos de servicio que garantizan estándares equivalentes de protección:

| Proveedor / Encargado | Servicio Prestado | Datos Personales Transmitidos | Finalidad del Tratamiento | Garantías de Seguridad |
| :--- | :--- | :--- | :--- | :--- |
| **Meta Platforms Ireland Ltd.** | API Oficial de WhatsApp Cloud (`canal_whatsapp`) | Número de teléfono de destino y contenido del mensaje tokenizado. | Entrega bidireccional de mensajería instantánea con huéspedes y colaboradores. | Cifrado en tránsito TLS 1.3, autenticación con token OAuth de corta duración, sin almacenamiento secundario indebido. |
| **Anthropic, PBC** | Modelo de lenguaje natural Claude (`agente`, `arm_jarvis`) | Contenido de mensajes con PII redactada/tokenizada (`[TELEFONO_1]`, `[NOMBRE_1]`, etc.). Cero PII en claro. | Generación de respuestas asistidas, comprensión de intenciones y razonamiento sobre herramientas. | Garantía de no entrenamiento con datos de API (`zero retention`), tokenización previa obligatoria (`INV_PII_FUERA_DEL_MODELO`). |
| **Proveedor PMS (Cloudbeds / FakePMS)** | Sistema de gestión de propiedades y reservas (`pms_conector`) | Identificador de reserva, fechas de estadía, número de huéspedes, tokens de contacto. | Consulta de disponibilidad, creación de reservas preliminares y confirmación de estadía. | Comunicación por API HTTPS segura, firma HMAC de webhooks, principio de mínimo privilegio. |
| **Proveedor CRM (HubSpot / FakeCRM)** | Gestión de relaciones comerciales (`crm_conector`) | Identificador de contacto tokenizado, datos de cotización y montos de venta reportados. | Registro de prospectos y consolidación de oportunidades de venta del canal. | API REST autenticada por Bearer token con scopes restringidos. |

---

## 4. Ejercicio de Derechos del Titular (ARCOP)

En cumplimiento de los artículos 21 al 27 de la LOPDP, los titulares pueden solicitar en cualquier momento:
- **Acceso:** Conocer qué datos personales propios son tratados.
- **Rectificación:** Corregir información inexacta o incompleta.
- **Cancelación / Eliminación:** Solicitar la supresión de sus datos mediante purga o criptoborrado en la bóveda de tokens.
- **Oposición:** Oponerse al tratamiento basado en interés legítimo o prospección comercial.
- **Portabilidad:** Recibir sus datos personales en un formato estructurado y de lectura mecánica.

**Plazo Operativo de Respuesta:** Conforme a la política interna y `dominio.yaml`, las solicitudes son atendidas dentro de un plazo máximo de 15 días hábiles a través del canal oficial de atención o el correo `privacidad@glampingimbabura.com`.

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
