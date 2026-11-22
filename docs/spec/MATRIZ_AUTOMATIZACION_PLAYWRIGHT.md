# Matriz de Automatización con Playwright — Glamping Imbabura
`¤especificacion`
`¤qa-engineer`

> **Alcance y Políticas de Ejecución:**
> 1. **Cero Reintentos (`retries=0`):** Una prueba intermitente no se oculta con reintentos; si falla, se detiene la ejecución inmediatamente (`--maxfail=1`).
> 2. **Aislamiento Criptográfico y de Datos:** El servidor de pruebas se ejecuta en un proceso/hilo aislado con base de datos en memoria (`sqlite:///:memory:`) y credenciales de prueba, sin heredar jamás el archivo `.env` del desarrollador.
> 3. **Prioridad de la Suite de Humo:** La suite de humo (`tests/e2e/test_humo_playwright.py`) corre antes de la suite completa en el arnés y en CI. Un fallo en el humo impide la ejecución del resto del arnés.

---

## 1. Mapeo entre Casos del Plan Manual y Automatización

| Caso Manual | Requisitos Enlazados | Estado de Automatización | Tipo de Prueba / Cobertura | Archivo de Prueba | Justificación Técnica si no aplica Playwright Web |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-MAN-01** | `US-17`, `RF-WEB-01..03` | **AUTOMATIZADO** | E2E Browser (Playwright) | `tests/e2e/test_humo_playwright.py::test_humo_01_catalogo_web_publico` | Renderizado del catálogo público, tarjetas y formulario de búsqueda en navegador Chromium real. |
| **TC-MAN-02** | `US-17`, `RF-WEB-04` | **AUTOMATIZADO** | E2E Browser (Playwright) | `tests/e2e/test_humo_playwright.py::test_humo_02_ficha_propiedad_y_enlace_whatsapp` | Interacción con formulario de ficha, envío POST a `/contacto` y redirección a `wa.me` con código `W-XXXXXXXX`. |
| **TC-MAN-03** | `US-01..04`, `RF-GW-01..02` | **MANUAL / BACKEND** | Integración Backend | `tests/canal_whatsapp/`, `tests/agente/` | Requiere interacción móvil con la app nativa de WhatsApp y webhooks firmados por Meta Cloud API (proveedor externo). No es interfaz web del proyecto. |
| **TC-MAN-04** | `US-12`, `RF-RAG-01..04` | **MANUAL / BACKEND** | Integración Backend | `tests/conocimiento/`, `tests/agente/` | Validación semántica conversacional de WhatsApp y embeddings vectoriales. Se evalúa con la suite RAG sintética (`scripts/run_evals.py`). |
| **TC-MAN-05** | `US-03`, `RF-SEC-08` | **MANUAL / BACKEND** | Integración Backend | `tests/seguridad/`, `tests/herramientas_glamping/` | Flujo de verificación de titularidad por WhatsApp para entrega de códigos de candado. |
| **TC-MAN-06** | `US-09..10`, `RF-CRM-06` | **AUTOMATIZADO BFF** | E2E API / BFF | `tests/e2e/test_inbox_huespedes.py` | El ciclo de handoff, asignación a agente humano y notas internas se verifica exhaustivamente en el BFF del panel y rutas HTTP. |
| **TC-MAN-07** | `US-05..06`, `RF-ARM-01..10` | **MANUAL / BACKEND** | Integración Backend | `tests/arm_jarvis/` | Ingesta no estructurada de mensajes desde chats grupales de WhatsApp de vendedores externos. |
| **TC-MAN-08** | `US-07`, `RF-PAN-04` | **AUTOMATIZADO** | E2E Browser + BFF | `test_humo_playwright.py::test_humo_03`, `tests/e2e/test_validar_venta.py` | Carga del shell del panel con Playwright; la mutación de estado con 1 toque se verifica en el arnés BFF con persistencia aislada. |
| **TC-MAN-09** | `US-08`, `US-14`, `RF-COM-01` | **AUTOMATIZADO BFF** | E2E API / BFF | `tests/e2e/test_tablero.py`, `tests/comisiones/` | Cálculo inmutable de comisiones por tramos y cierre mensual reproducible verificado por el arnés. |
| **TC-MAN-10** | `US-15`, `RF-PAN-10..12` | **AUTOMATIZADO** | E2E Browser + BFF | `test_humo_playwright.py::test_humo_03`, `tests/e2e/test_terminal_movil.py` | Verificación de `manifest.webmanifest`, service worker (`sw.js`), carga de app y simulación offline en el BFF. |
| **TC-MAN-11** | `US-08`, `RF-CRM-01..04` | **MANUAL / BACKEND** | Integración Backend | `tests/crm_conector/` | Publicación de eventos a servidor CRM externo con reintentos backoff y firma HMAC. No tiene UI web directa. |
| **TC-MAN-12** | `US-16`, `RF-SEC-01..06` | **AUTOMATIZADO BFF** | E2E API / BFF | `tests/e2e/test_calidad_ui.py`, `tests/seguridad/` | Restricción RBAC por roles (`gestor`, `lider`, `administrador`), sanitización UI y registro append-only de auditoría. |

---

## 2. Configuración de Ejecución de Humo

```bash
# Ejecución directa de la suite de humo con Playwright (0 reintentos, parada al primer fallo):
pytest tests/e2e/test_humo_playwright.py -q --maxfail=1
```

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
