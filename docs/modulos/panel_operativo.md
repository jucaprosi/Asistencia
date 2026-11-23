# Módulo `panel_operativo` — Frontend y BFF del equipo
`¤panel-operativo`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/panel_operativo/` |
| Compuerta | `panel_operativo_service.py` → `PanelOperativoService` |
| Privados | `bff_internal.py` (rutas HTTP `/panel/api/*`), `componentes_internal.py`, `sesiones_internal.py`, `persistencia_internal.py`, `ui/` (código TypeScript/JavaScript, `p12_terminal_movil.ts`, `p13_inbox_huespedes.ts`), `estaticos/` (build servido, `sw.js`, `manifest.webmanifest`, iconos), `tipos.py` |
| Config | `config_panel_operativo.yaml` |
| Rol | `¤¤frontend-developer` |
| Requisitos | RF-PAN-01..14 ([`../PRD.md` §5.11](../PRD.md#511-panel-operativo--sala-panel_operativo)) · RF-ANF-01, RF-ANF-02, RF-PMS-08 · US-09, US-10, US-13, US-16 · INV_PANEL_POR_ROL, INV_PANEL_SIN_LOGICA, INV_ACCION_IDEMPOTENTE, INV_INTERFAZ_PURIFICADA, INV_AISLAMIENTO_ANFITRION, INV_AVISO_SIN_PII, INV_MOVIL_SIN_ESCRITURA_SIN_RED, INV_MOVIL_SIN_PII_EN_DISCO |
| Tareas | T-303 (Ola 2, Fase 4: base, acceso, inicio, handoffs por zona, incidencias), T-404 (Ola 4, Fase 5: administración P-11 y calidad UI), T-505, T-604, T-701 (Ola 8, Fase 8: Inbox completo de huéspedes en panel propio), T-801 (Ola 8, Fase 8: terminal móvil PWA, avisos Web Push e idempotencia) |
| Decisión | Construir propio ([ADR-0013](../adr/ADR-0013-panel-operativo-propio.md)). Diseño de pantallas, navegación, componentes y tokens visuales en [`../FRONTEND.md`](../FRONTEND.md). |

## Propósito
Proveer al líder comercial, los gestores de propiedad y el administrador una interfaz unificada (móvil primero) para validar ventas, revisar el tablero de comisiones, atender handoffs por zona, resolver incidencias y administrar el sistema.

El panel **no contiene lógica de negocio propia** (`INV_PANEL_SIN_LOGICA`): cada acción es una llamada a la compuerta de la sala dueña, autorizada en el BFF por rol y zona (`INV_PANEL_POR_ROL`).

## Tipos del dominio (`tipos.py`)

```python
@dataclass(frozen=True)
class Sesion:
    usuario_id: str
    rol: str
    zonas: tuple[str, ...]
    expira_en: datetime
    csrf: str

@dataclass(frozen=True)
class VistaVentaPorValidar:
    venta_id: str
    ticket: str
    vendedor: str
    cliente: str
    producto: str
    monto: Decimal
    fecha_venta: date
    confianza: float
    campos_dudosos: tuple[str, ...]
    texto_original: str
    comision_estimada: Decimal
    creada: datetime

@dataclass(frozen=True)
class VistaHandoff:
    conversacion_id: str
    propiedad: str
    zona_id: str
    motivo: str
    resumen: str
    esperando_desde: datetime
    asignado_a: str | None = None

@dataclass(frozen=True)
class EstadoSistema:
    metricas: tuple = ()
    alertas: tuple = ()
    cola_crm: int = 0
    ultima_traza: datetime | None = None

@dataclass(frozen=True)
class AvisoMovil:
    tipo: str
    cantidad: int
    ruta: str

@dataclass(frozen=True)
class VistaUsuario:
    usuario_id: str
    correo_enmascarado: str
    numero_enmascarado: str
    rol: str
    activo: bool
    creado_en: datetime

@dataclass(frozen=True)
class VistaReglaComision:
    regla_id: str
    version: int
    nombre: str
    tipo: str
    parametros: Mapping[str, Any]
    vigencia_desde: str
    activa: bool

@dataclass(frozen=True)
class VistaAnfitrion:
    anfitrion_id: str
    nombre: str
    telefono_token: str
    porcentaje_comision: Decimal
    version_terminos: str
    estado: str
    creado_en: datetime

@dataclass(frozen=True)
class VistaHospedaje:
    hospedaje_id: str
    anfitrion_id: str
    titulo: str
    estado: str
    publicado_por: str | None = None
    publicado_en: datetime | None = None

@dataclass(frozen=True)
class SolicitudPrivacidad:
    solicitud_id: str
    tipo: str
    titular_hash: str
    estado: str
    creada_en: datetime
```

## Compuerta (`PanelOperativoService`)

```python
class PanelOperativoService:
    # Sesión y acceso (RF-PAN-01)
    def solicitar_codigo(self, correo: str) -> dict[str, Any]: ...
    def iniciar_sesion(self, correo: str, codigo_un_uso: str) -> tuple[Sesion, str]: ...
    def validar_sesion(self, cookie_token: str) -> Sesion: ...
    def cerrar_sesion(self, sesion: Sesion, cookie_token: str | None = None) -> None: ...

    # Conversaciones y handoffs por zona (RF-PAN-07)
    def handoffs(self, sesion: Sesion, zona_filtro: str | None = None) -> tuple[VistaHandoff, ...]: ...
    def detalle_conversacion(self, sesion: Sesion, conversacion_id: str) -> Mapping[str, Any]: ...
    def tomar_handoff(self, sesion: Sesion, conversacion_id: str) -> None: ...
    def responder(self, sesion: Sesion, conversacion_id: str, texto: str) -> None: ...
    def devolver_al_asistente(self, sesion: Sesion, conversacion_id: str) -> None: ...

    # Incidencias (RF-PAN-08)
    def incidencias(self, sesion: Sesion, filtros: Mapping[str, Any] | None = None) -> tuple[Mapping[str, Any], ...]: ...
    def resolver_incidencia(self, sesion: Sesion, incidencia_id: str, nota: str) -> None: ...

    # Desglose de comisión sin lógica de negocio propia (INV_PANEL_SIN_LOGICA)
    def desglose_comision(self, sesion: Sesion, venta_id: str) -> Mapping[str, Any]: ...

    # Ventas y validación (RF-PAN-02, RF-PAN-03, US-06)
    def ventas_por_validar(self, sesion: Sesion, filtros: Mapping[str, Any] | None = None) -> tuple[VistaVentaPorValidar, ...]: ...
    def validar_venta(self, sesion: Sesion, venta_id: str, correcciones: Mapping[str, Any] | None = None) -> dict[str, Any]: ...
    def rechazar_venta(self, sesion: Sesion, venta_id: str, motivo: str) -> dict[str, Any]: ...
    def detalle_venta(self, sesion: Sesion, venta_id: str) -> Mapping[str, Any]: ...
    def anular_venta(self, sesion: Sesion, venta_id: str, motivo: str) -> dict[str, Any]: ...
    def reintentar_publicacion_crm(self, sesion: Sesion, venta_id: str) -> dict[str, Any]: ...

    # Jarvis (RF-PAN-06, RF-ARM-09)
    def preguntar_jarvis(self, sesion: Sesion, pregunta: str, conversacion_id: str = "") -> dict[str, Any]: ...
    def confirmar_cambio_jarvis(self, sesion: Sesion, cambio: Mapping[str, Any], confirmado: bool) -> dict[str, Any]: ...

    # Administración (RF-PAN-09, RF-ANF-01, RF-ANF-02, RF-PMS-08)
    def usuarios(self, sesion: Sesion) -> tuple[VistaUsuario, ...]: ...
    def editar_usuario(self, sesion: Sesion, numero: str, rol: str, alta: bool, sujeto_id: str | None = None, correo: str | None = None) -> None: ...
    def bloquear_numero(self, sesion: Sesion, numero: str, motivo: str) -> None: ...
    def desbloquear_numero(self, sesion: Sesion, numero: str) -> None: ...
    def reglas_comision(self, sesion: Sesion) -> tuple[VistaReglaComision, ...]: ...
    def crear_regla_comision(self, sesion: Sesion, regla: Mapping[str, Any]) -> VistaReglaComision: ...
    def registrar_anfitrion(self, sesion: Sesion, anfitrion_data: Mapping[str, Any]) -> VistaAnfitrion: ...
    def publicar_hospedaje(self, sesion: Sesion, hospedaje_id: str) -> VistaHospedaje: ...
    def bloquear_fechas(self, sesion: Sesion, unidad_id: str, desde: date, hasta: date) -> dict[str, Any]: ...
    def liberar_fechas(self, sesion: Sesion, unidad_id: str, desde: date, hasta: date) -> dict[str, Any]: ...
    def auditoria(self, sesion: Sesion, filtros: Mapping[str, Any] | None = None) -> tuple[Mapping[str, Any], ...]: ...
    def exportar_auditoria_csv(self, sesion: Sesion, desde: date | None = None, hasta: date | None = None) -> bytes: ...
    def solicitudes_privacidad(self, sesion: Sesion) -> tuple[SolicitudPrivacidad, ...]: ...
    def estado_sistema(self, sesion: Sesion) -> EstadoSistema: ...
    def reindexar(self, sesion: Sesion) -> Mapping[str, Any]: ...
    def comprobar_interfaz_purificada(self, ruta_build: Path | None = None) -> list[str]: ...

    # Terminal móvil y Web Push (RF-PAN-11, RF-PAN-12)
    def obtener_vapid_public_key(self) -> str: ...
    def suscribir_dispositivo(self, sesion: Sesion, endpoint: str, clave_p256dh: str, clave_auth: str) -> dict[str, Any]: ...
    def revocar_dispositivo(self, sesion: Sesion, endpoint: str) -> bool: ...
    def dispositivos_usuario(self, sesion: Sesion) -> tuple[dict[str, Any], ...]: ...
    def enviar_aviso_movil(self, usuario_id: str, aviso: AvisoMovil) -> int: ...
    def enviar_aviso_por_rol(self, rol: str, aviso: AvisoMovil, zona: str | None = None) -> int: ...
```

## Rutas del BFF (`/panel/api`)

| Método y ruta | Pantalla | Descripción |
| :--- | :--- | :--- |
| `POST /panel/api/sesion/codigo` | P-01 | Solicita código WhatsApp de 6 dígitos (válido 10 min, máx 5 intentos). |
| `POST /panel/api/sesion` | P-01 | Verifica código, entrega cookie segura de 12 h (`HttpOnly`, `Secure`, `SameSite=Strict`) y token CSRF. |
| `DELETE /panel/api/sesion` | P-01 | Cierra la sesión activa y revoca la cookie. |
| `GET /panel/api/sesion` | — | Devuelve los metadatos de la sesión activa o 401. |
| `GET /panel/api/inicio` | P-02 | Resumen con métricas según el rol activo. |
| `GET /panel/api/handoffs` | P-08 | Bandeja de conversaciones en handoff filtradas por la zona del gestor (403 si consulta otra zona). |
| `GET /panel/api/handoffs/{id}` | P-09 | Detalle de conversación con PII rehidratada solo para el huésped de la reserva. |
| `POST /panel/api/handoffs/{id}/tomar` | P-08, P-09 | Silencia al agente y asigna el handoff al gestor. Requiere `Idempotency-Key` y CSRF. |
| `POST /panel/api/handoffs/{id}/responder` | P-09 | Envía mensaje al huésped por WhatsApp dentro de la ventana de 24 h. |
| `POST /panel/api/handoffs/{id}/devolver` | P-09 | Reanuda al asistente conversacional y marca el handoff como devuelto. |
| `GET /panel/api/incidencias` | P-10 | Lista de incidencias por zona asignada (403 si intenta ver otra zona). |
| `POST /panel/api/incidencias/{id}/resolver` | P-10 | Resuelve la incidencia con nota, registra actor y hora, y notifica al huésped. |
| `GET /panel/api/comisiones/{id}/desglose` | P-04 | Muestra regla, versión, acumulado y tramos servidos directamente desde `comisiones`. |
| `GET /panel/api/comisiones/tablero` | P-05 | Tablero de ventas y comisiones por mes, vendedor y propiedad con accesibilidad WCAG 2.1 AA. |
| `GET /panel/api/comisiones/vendedores/{id}/estado_cuenta` | P-05b | Estado de cuenta detallado por vendedor con líneas por venta y ajuste idénticas al centavo con exportación. |
| `GET /panel/api/comisiones/periodos/{id}/resumen_cierre` | P-06 | Resumen previo de cierre mensual alertando ventas pendientes que quedarán fuera. |
| `POST /panel/api/comisiones/periodos/{id}/cerrar` | P-06 | Cierre inmutable de período con confirmación escrita obligatoria; responde 409 tras cierre. |
| `GET /panel/api/comisiones/periodos/{id}/exportar` | P-06 | Exportación oficial del período en CSV y JSON validado contra esquema_exportacion.json. |
| `GET /panel/api/ventas/por_validar` | P-03 | Bandeja de ventas en estado por_validar con campos dudosos marcados (solo líder y admin). |
| `POST /panel/api/ventas/{id}/validar` | P-03 | Valida venta en 1 toque o con correcciones, fija comisión y notifica; 409 ante conflicto. |
| `POST /panel/api/ventas/{id}/rechazar` | P-03 | Rechaza venta exigiendo motivo obligatorio y notifica al vendedor; 409 ante conflicto. |
| `GET /panel/api/ventas/{id}` | P-04 | Detalle de venta completo con desglose de comisión y línea de tiempo de transiciones. |
| `POST /panel/api/ventas/{id}/anular` | P-04 | Anulación con motivo obligatorio (solo administrador); crea ajuste negativo y notifica CRM. |
| `POST /panel/api/ventas/{id}/reintentar_publicacion` | P-04 | Reintento manual de publicación en CRM para ventas no_publicadas. |
| `POST /panel/api/jarvis/chat` | P-07 | Chat con Jarvis dentro del alcance del rol; sin historial persistente en disco. |
| `POST /panel/api/jarvis/configuracion` | P-07 | Modificación de configuración operativa exigiendo confirmación explícita (422 si no confirma). |
| `GET /panel/api/admin/usuarios` | P-11 | Lista usuarios con correo y número enmascarados (solo admin). |
| `POST /panel/api/admin/usuarios` | P-11 | Alta o baja de usuarios autorizados con auditoría de actor (solo admin). |
| `POST /panel/api/admin/bloqueos` | P-11 | Bloqueo preventivo de número telefónico (solo admin). |
| `DELETE /panel/api/admin/bloqueos/{num}` | P-11 | Desbloqueo de número telefónico (solo admin). |
| `GET /panel/api/admin/reglas_comision` | P-11 | Consulta histórico de versiones de reglas de comisión (solo admin). |
| `POST /panel/api/admin/reglas_comision` | P-11 | Crea nueva versión inmutable de regla sin mutación en sitio (solo admin). |
| `POST /panel/api/admin/anfitriones` | P-11 | Alta de anfitrión exigiendo versión de términos y tokenizando teléfono (solo admin). |
| `POST /panel/api/admin/hospedajes/{id}/publicar` | P-11 | Publicación revisada de hospedaje registrando actor y fecha (solo admin). |
| `POST /panel/api/calendario/bloquear` | P-11 | Bloqueo de fechas respetando aislamiento de anfitrión (`INV_AISLAMIENTO_ANFITRION`). |
| `POST /panel/api/calendario/liberar` | P-11 | Liberación de fechas omitiendo noches con reservas activas. |
| `GET /panel/api/admin/auditoria` | P-11 | Consulta de audit log append-only filtrable por actor y acción (solo admin). |
| `GET /panel/api/admin/auditoria/exportar` | P-11 | Exportación de auditoría en formato CSV (solo admin). |
| `GET /panel/api/admin/privacidad/solicitudes` | P-11 | Consulta de solicitudes ARCO de titulares de datos (solo admin). |
| `GET /panel/api/admin/salud` | P-11 | Salud del sistema con métricas OP-01..10 y cola de mensajería (solo admin). |
| `POST /panel/api/admin/conocimiento/reindexar` | P-11 | Disparo de reindexación con reporte del set dorado (solo admin). |
| `GET /panel/api/admin/plantillas` | P-11 | Lista de plantillas de WhatsApp y estado de aprobación (solo admin). |
| `POST /panel/api/admin/plantillas/{nombre}/aprobar` | P-11 | Aprobación de plantilla de WhatsApp (solo admin). |
| `GET /panel/api/admin/anfitriones/estados_cuenta` | P-11 | Consulta estados de cuenta emitidos para cobro de comisiones a anfitriones (solo admin). |
| `POST /panel/api/admin/anfitriones/estados_cuenta/{id}/pago` | P-11 | Registra pago de anfitrión por fuera de la plataforma guardando actor y fecha (solo admin). |
| `POST /panel/api/admin/anfitriones/pausar_vencidos` | P-11 | Pasa a pausado los hospedajes de anfitriones con cobros vencidos por más de 15 días (solo admin). |
| `GET /panel/manifest.webmanifest` | P-12 | Manifiesto PWA para instalación en Android e iPhone con pantalla completa e iconos. |
| `GET /panel/sw.js` | P-12 | Service Worker con ciclo de vida inmediato y caché restringida al shell estático. |
| `GET /panel/api/dispositivos/vapid-public-key` | P-12 | Entrega de clave pública VAPID leída de entorno para suscripción Web Push. |
| `POST /panel/api/dispositivos/suscribir` | P-12 | Registra suscripción del dispositivo móvil tras toque explícito del usuario. |
| `DELETE /panel/api/dispositivos` | P-12 | Revocación manual de dispositivo Web Push. |
| `GET /panel/api/dispositivos` | P-12 | Lista dispositivos activos suscritos por el usuario actual. |
| `GET /panel/api/conversaciones` | P-13 | Inbox completo: lista todas las conversaciones de huéspedes con filtros por estado, propiedad y búsqueda de texto. |
| `GET /panel/api/conversaciones/{id}` | P-13 | Detalle de conversación con historial, notas internas y etiquetas, rehidratando PII según rol. |
| `POST /panel/api/conversaciones/{id}/etiquetas` | P-13 | Asigna una etiqueta a la conversación respetando aislamiento de zona. |
| `DELETE /panel/api/conversaciones/{id}/etiquetas/{etiqueta}` | P-13 | Remueve una etiqueta de la conversación respetando aislamiento de zona. |
| `POST /panel/api/conversaciones/{id}/notas` | P-13 | Agrega una nota interna a la conversación registrando autor y marca temporal. |
| `POST /panel/api/conversaciones/{id}/responder` | P-13 | Envío de respuesta manual que sale directamente por el canal de WhatsApp oficial sin CRM externo. |

## Invariantes Garantizados

| Código | Predicado | Mecanismo |
| :--- | :--- | :--- |
| `INV_ACCION_IDEMPOTENTE` | `∀ n ≥ 1 : efecto(accion(k)^n) = efecto(accion(k))` | Cabecera `Idempotency-Key` con UUID; `INSERT ... ON CONFLICT DO NOTHING` en `panel.acciones_idempotentes`. |
| `INV_AVISO_SIN_PII` | `∀ a ∈ avisos : carga(a) ⊆ {tipo, cantidad, ruta}` | El tipo `AvisoMovil` no admite otros campos; el detalle se pide al abrir, con sesión. |
| `INV_MOVIL_SIN_ESCRITURA_SIN_RED` | `¬red ⇒ ∣acciones_enviadas∣ = 0 ∧ ∣cola_local∣ = 0` | Botones deshabilitados y sin Background Sync. |
| `INV_MOVIL_SIN_PII_EN_DISCO` | `∀ r ∈ almacenamiento(telefono) : r ∈ interfaz_estatica` | El service worker solo guarda archivos versionados del build; `/panel/api` va con `Cache-Control: no-store`; los datos viven en memoria. |
| `INV_PANEL_POR_ROL` | `ejecutada(accion, sesion) ⇒ accion ∈ allowlist(rol) ∧ zona(dato) ∈ zonas(sesion)` | Autorización estricta en el BFF por endpoint y verificación de pertenencia de zona (403 Forbidden). |
| `INV_PANEL_SIN_LOGICA` | `∀ c ∈ cálculos_de_negocio : c ∉ panel_operativo` | Verificación por AST; los cálculos de comisiones y transiciones de estado ocurren exclusivamente en las salas dueñas. |
| `INV_INTERFAZ_PURIFICADA` | `∀ t ∈ textos_de_usuario : t ∩ marcadores_internos = ∅` | Cero rastros de gobernanza ni marcadores internos en código frontend o respuestas servidas. |
| `INV_AISLAMIENTO_ANFITRION` | `anfitrion(actor) ⇒ unidad.anfitrion_id = actor.id` | Verificación obligatoria de propiedad antes de bloquear o liberar fechas en el calendario. |

## Persistencia (`esquema panel`)

```sql
CREATE TABLE panel.codigos_acceso (
  codigo_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id       uuid NOT NULL,
  codigo_hash      text NOT NULL,
  intentos         integer NOT NULL DEFAULT 0 CHECK (intentos BETWEEN 0 AND 5),
  expira_en        timestamptz NOT NULL,
  usado_en         timestamptz
);

CREATE TABLE panel.dispositivos (
  dispositivo_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id       uuid NOT NULL,
  endpoint         text NOT NULL UNIQUE,
  clave_p256dh     text NOT NULL,
  clave_auth       text NOT NULL,
  creado_en        timestamptz NOT NULL DEFAULT now(),
  revocado_en      timestamptz
);

CREATE TABLE panel.acciones_idempotentes (
  usuario_id       uuid NOT NULL,
  clave            uuid NOT NULL,
  accion           text NOT NULL,
  respuesta        jsonb,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (usuario_id, clave)
);

CREATE TABLE panel.sesiones (
  sesion_id_hash   text PRIMARY KEY,
  usuario_id       uuid NOT NULL,
  creada_en        timestamptz NOT NULL DEFAULT now(),
  expira_en        timestamptz NOT NULL,
  cerrada_en       timestamptz
);
```

## Árbitro y Suites de Prueba
- `tests/panel_operativo/test_sesiones.py`: ciclo de vida de códigos de acceso (6 dígitos, 10 min, 5 intentos), sesión 12 h, auditoría de correos desconocidos.
- `tests/panel_operativo/test_bff_handoff.py`: bandeja por zona, aislamiento 403, tomar (silencia agente), responder, devolver (reanuda agente), incidencias e idempotencia.
- `tests/panel_operativo/test_bff_admin.py`: aislamiento de administración por rol (403), gestión de usuarios y enmascaramiento, reglas inmutables por versión, alta de anfitrión con términos obligatorios, publicación revisada, calendario con aislamiento y omisión de reservas activas.
- `tests/panel_operativo/test_bff_ventas.py`: bandeja P-03, validación con un toque o correcciones, rechazo con motivo, anulación por admin, desglose P-04, conflicto 409 e idempotencia.
- `tests/panel_operativo/test_bff_jarvis.py`: chat P-07, aislamiento de rol, confirmación explícita de cambios de configuración y ausencia de persistencia en disco.
- `tests/panel_operativo/test_bff_comisiones.py`: tablero P-05, estado de cuenta P-05b, cierre inmutable P-06 con confirmación escrita, 409 tras cierre, exportación CSV/JSON y cobro a anfitriones RF-ANF-08.
- `tests/panel_operativo/test_sin_logica.py`: verificación por AST de ausencia de lógica de negocio y desglose fiel de comisiones.
- `tests/e2e/test_handoff_zona.py`: simulación E2E de inicio de sesión de gestor, bandeja, toma de conversación y devolución al agente.
- `tests/e2e/test_validar_venta.py`: simulación E2E de validación de ventas, corrección de campos dudosos en HojaCorreccion, conflicto entre usuarios y componentes UI.
- `tests/e2e/test_tablero.py`: simulación E2E de tablero que cuadra al centavo con la exportación CSV, estado de cuenta por vendedor con ventas y ajustes, y componentes UI accesibles.
- `tests/e2e/test_calidad_ui.py`: auditoría de accesibilidad WCAG 2.1 AA (móvil primero 360 px), presupuesto de rendimiento en CI (JS inicial comprimido <= 200 KB, LCP <= 2,5 s e INP <= 200 ms) y verificación de interfaz purificada (`INV_INTERFAZ_PURIFICADA`).
- `tests/e2e/test_terminal_movil.py`: PWA instalable con manifiesto e iconos, actualización inmediata del service worker, revocación de dispositivos al cerrar sesión, y modo sin red de solo lectura en memoria bloqueando escritura (RF-PAN-11, RF-PAN-13, INV_MOVIL_SIN_ESCRITURA_SIN_RED, INV_MOVIL_SIN_PII_EN_DISCO).
- `tests/panel_operativo/test_avisos.py`: activación con un toque, entrega de clave pública VAPID, aviso con solo tipo, cantidad y ruta sin datos personales, apertura de pantalla tras validar sesión, y tolerancia a fallos de red (RF-PAN-12, INV_AVISO_SIN_PII).
- `tests/panel_operativo/test_idempotencia.py`: cabecera `Idempotency-Key` en acciones mutadoras del panel, protección contra doble toque y reintentos, y persistencia en `panel.acciones_idempotentes` (RF-PAN-14, INV_ACCION_IDEMPOTENTE).
- `tests/e2e/test_inbox_huespedes.py`: Inbox completo de huéspedes nativo en el panel operativo (T-701, TASK-008, ADR-0010), aislamiento por rol (`INV_PANEL_POR_ROL`), detalle cronológico con rehidratación de PII, gestión de etiquetas y notas internas, y respuesta manual por canal de WhatsApp oficial sin intermediarios CRM.

### Arnés de interfaz en el navegador (`ui/`, Playwright TypeScript)
`¤panel-arnes-ui`

Complementa las suites anteriores: verifica lo que la interfaz servida en `/panel` hace en Chromium con cada respuesta del BFF, sin backend real. Adaptado de la configuración del equipo de EVYDENTIA (2026-11-22) a esta arquitectura: el servidor que levanta es uvicorn con el pasillo central y entorno aislado (dobles), y el BFF se simula con `page.route` sobre `/panel/api/**`; toda ruta no declarada responde 404 `NO_SIMULADA` y queda registrada.

| Pieza | Ruta |
| :--- | :--- |
| Workspace Node y scripts (`typecheck`, `test:e2e`) | `features/panel_operativo/ui/package.json` |
| Configuración (proyectos `escritorio` y `movil-360`, puerto `PLAYWRIGHT_PORT`, por omisión 8101) | `features/panel_operativo/ui/playwright.config.ts` |
| Helpers: BFF simulado, centinela de consola, contraste WCAG 4,5:1, utilidades de P-01 | `features/panel_operativo/ui/tests/{bffSimulado,consoleSentinel,contraste,utiles}.ts` |
| Specs por pantalla | `features/panel_operativo/ui/tests/acceso/acceso.spec.ts` (P-01), `tests/inicio/inicio.spec.ts` (P-02) |
| Guía para quien escriba pruebas | `features/panel_operativo/ui/tests/GUIA_PLAYWRIGHT.md` |

Reglas: selectores por rol y nombre accesible; nunca `waitForTimeout`; cada prueba parte limpia; una prueba por pantalla exige cero errores de consola y contraste 4,5:1; ninguna pantalla muestra marcadores de gobernanza. Ejecución local: `cd features/panel_operativo/ui` y `npx playwright test`. Aún no corre en CI (`.github/**` es ruta del coordinador): un Playwright en verde se pega en el PR con comando y puerto. Sin regresión visual por píxel ni axe-core, a propósito (ver guía §5).

`¤panel-arnes-ui/`

`¤panel-operativo/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
