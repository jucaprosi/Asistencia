# Módulo `panel_operativo` — Frontend y BFF del equipo
`¤panel-operativo`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/panel_operativo/` |
| Compuerta | `panel_operativo_service.py` → `PanelOperativoService` (casos de uso que la UI consume) |
| Privados | `bff_internal.py` (rutas HTTP `/panel/api/*`), `sesiones_internal.py`, `ui/` (código fuente del frontend, TypeScript), `estaticos/` (build servido), `tipos.py` |
| Config | `config_panel_operativo.yaml` |
| Rol | `¤¤frontend-developer` |
| Requisitos | RF-PAN-01..10 ([`../PRD.md` §5.11](../PRD.md#511-panel-operativo--sala-panel_operativo)) · INV_PANEL_POR_ROL, INV_INTERFAZ_PURIFICADA |
| Tareas | TASK-004 (bandeja de handoff), TASK-005 (administración y salud), TASK-006 (ventas por validar, Jarvis), TASK-007 (tablero, cierre, exportación) |
| Decisión | Construir (ADR-0013). Diseño de pantallas, navegación, componentes y tokens visuales en [`../FRONTEND.md`](../FRONTEND.md). |

## Propósito
Dar al líder comercial, los gestores y el administrador una sola aplicación web (móvil primero) para validar ventas, ver el tablero de comisiones, hablar con Jarvis, atender handoffs por zona y administrar whitelist, propiedades, reglas, plantillas, conocimiento y auditoría. El panel **no contiene lógica de negocio**: cada acción es una llamada a la compuerta de la sala dueña, autorizada por `seguridad`.

## Tipos del dominio

```python
@dataclass(frozen=True)
class Sesion: usuario_id: str; rol: Rol; zonas: tuple[str, ...]; expira_en: datetime; csrf: str
@dataclass(frozen=True)
class VistaVentaPorValidar: venta_id: str; ticket: str; vendedor: str; cliente: str; producto: str; monto: Decimal; fecha_venta: date; confianza: float; campos_dudosos: tuple[str, ...]; texto_original: str; comision_estimada: Decimal; creada: datetime
@dataclass(frozen=True)
class VistaHandoff: conversacion_id: str; propiedad: str; zona_id: str; motivo: str; resumen: str; esperando_desde: datetime; asignado_a: str | None
@dataclass(frozen=True)
class EstadoSistema: metricas: tuple[Metrica, ...]; alertas: tuple[Alerta, ...]; cola_crm: int; ultima_traza: datetime | None
```

## Compuerta

```python
class PanelOperativoService:
    # sesión
    def iniciar_sesion(self, correo: str, codigo_un_uso: str) -> Sesion: ...                  # código enviado por WhatsApp al número en whitelist
    def cerrar_sesion(self, sesion: Sesion) -> None: ...
    # ventas (→ arm_jarvis, comisiones)
    def ventas_por_validar(self, sesion: Sesion, filtros: Mapping[str, Any]) -> tuple[VistaVentaPorValidar, ...]: ...
    def validar_venta(self, sesion: Sesion, venta_id: str, correcciones: Mapping[str, Any] | None) -> None: ...
    def rechazar_venta(self, sesion: Sesion, venta_id: str, motivo: str) -> None: ...
    def detalle_venta(self, sesion: Sesion, venta_id: str) -> Mapping[str, Any]: ...
    def tablero(self, sesion: Sesion, periodo: str) -> Tablero: ...
    def cerrar_periodo(self, sesion: Sesion, periodo: str) -> Periodo: ...
    def exportar_periodo(self, sesion: Sesion, periodo: str, formato: str) -> bytes: ...
    def preguntar_jarvis(self, sesion: Sesion, pregunta: str, conversacion_id: str) -> str: ...
    # conversaciones (→ agente, crm_conector, canal_whatsapp)
    def handoffs(self, sesion: Sesion) -> tuple[VistaHandoff, ...]: ...                       # solo zonas de la sesión
    def tomar_handoff(self, sesion: Sesion, conversacion_id: str) -> None: ...
    def responder(self, sesion: Sesion, conversacion_id: str, texto: str) -> None: ...
    def devolver_al_asistente(self, sesion: Sesion, conversacion_id: str) -> None: ...
    def incidencias(self, sesion: Sesion, filtros: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]: ...
    def resolver_incidencia(self, sesion: Sesion, incidencia_id: str, nota: str) -> None: ...
    # administración (→ seguridad, pms_conector, comisiones, canal_whatsapp, conocimiento)
    def whitelist(self, sesion: Sesion) -> tuple[Mapping[str, Any], ...]: ...
    def editar_whitelist(self, sesion: Sesion, numero: str, rol: str, alta: bool) -> None: ...
    def propiedades(self, sesion: Sesion) -> tuple[Propiedad, ...]: ...
    def reglas_comision(self, sesion: Sesion) -> tuple[ReglaComision, ...]: ...
    def crear_regla_comision(self, sesion: Sesion, regla: Mapping[str, Any]) -> ReglaComision: ...
    def plantillas(self, sesion: Sesion) -> tuple[Mapping[str, Any], ...]: ...
    def conocimiento(self, sesion: Sesion) -> tuple[Documento, ...]: ...
    def reindexar(self, sesion: Sesion) -> ResumenIndexacion: ...
    def auditoria(self, sesion: Sesion, filtros: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]: ...
    def estado_sistema(self, sesion: Sesion) -> EstadoSistema: ...
```

## Configuración (`config_panel_operativo.yaml`)
`url_base: ${PANEL_URL}`, `sesion {duracion_h: 12, cookie_segura: true, same_site: strict, secreto: ${PANEL_SESSION_SECRET}}`, `acceso {metodo: codigo_whatsapp, longitud_codigo: 6, validez_min: 10, intentos_max: 5}`, `roles_permitidos: [lider, gestor, administrador]`, `paginacion: 25`, `tablero {periodo_defecto: actual, moneda: USD}`, `estaticos {ruta: estaticos/, cache_s: 86400}`.

## Compuertas que consume
`seguridad` (`identificar`, `autorizar`, `auditar`), `arm_jarvis`, `comisiones`, `agente` (`entrar_en_silencio`/`reanudar`, `contexto`), `canal_whatsapp` (`enviar` para respuestas del gestor y códigos de acceso), `crm_conector` (contactos, eventos), `pms_conector` (propiedades, incidencias), `conocimiento` (documentos, reindexar), `observabilidad` (métricas, alertas).

## Errores
`CredencialesInvalidas`, `SesionExpirada`, `AccionNoAutorizada` (de `seguridad`, se muestra sin detalle técnico), `ZonaNoAsignada`, `ConflictoDeEstado` (otro usuario validó antes: la UI recarga la tarjeta), `ErrorDeSala` (envuelve el error tipado de la sala dueña con `mensaje_usuario`).

## Persistencia (`esquema panel`)
`usuarios(usuario_id PK, correo, telefono_token, rol, zonas, activo)`, `sesiones(sesion_id PK, usuario_id, csrf, creada, expira)`, `codigos_acceso(correo, codigo_hash, expira, intentos)`. Ningún dato de negocio: todo se lee de las salas dueñas.

## Tests (árbitro)
`tests/panel_operativo/test_bff_ventas.py`, `test_bff_handoff.py`, `test_bff_admin.py` (cada endpoint con cada rol: 403 donde corresponde), `test_sesiones.py`; `tests/e2e/` con navegador real sobre `localhost` (protocolo de autoevaluación E2E de ZERAG) para US-06, US-08, US-09, US-10; `tests/test_interfaz_purificada.py` sobre el build de `estaticos/`.

`¤panel-operativo/`
