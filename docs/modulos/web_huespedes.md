# Módulo `web_huespedes` — Web pública para huéspedes
`¤web-huespedes`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/web_huespedes/` |
| Compuerta | `web_huespedes_service.py` → `WebHuespedesService` |
| Privados | `repositorio.py`, `rutas.py`, `tipos.py`, `templates/` |
| Config | `config_web_huespedes.yaml` |
| Rol | `¤¤frontend-developer` |
| Requisitos | RF-WEB-01..06, RF-ANF-03 · US-18 · INV_INTERFAZ_PURIFICADA, INV_SOLO_PUBLICADO, INV_WEB_LIMITE_POR_IP, INV_WEB_PRECIO_EN_VIVO, INV_WEB_SIN_PII, INV_WEB_SOLO_LECTURA |
| Tareas | T-105 (Ola 1, Fase 1: catálogo, ficha, límites IP y paso a WhatsApp), T-205 (Ola 3, Fase 3: búsqueda, comparación y contexto para el agente), T-405 (Ola 6, Fase 5: filtro de solo hospedajes publicados) |
| Decisión | [ADR-0017](../adr/ADR-0017-web-publica-huespedes.md) y [ADR-0018](../adr/ADR-0018-plataforma-local-de-hospedajes.md) |

## Propósito
Web pública para descubrir, consultar y comparar los hospedajes disponibles en Glamping Imbabura. Ofrece exclusivamente hospedajes en estado publicado de anfitriones activos (`INV_SOLO_PUBLICADO`), indicando explícitamente en cada ficha y tarjeta quién ofrece el hospedaje. Opera bajo una arquitectura estrictamente de solo lectura (`INV_WEB_SOLO_LECTURA`): no realiza reservas en la web ni interactúa con pasarelas de pago; todo flujo de reserva o consulta se transfiere directamente al canal oficial de WhatsApp con un código de contexto seguro y anónimo (`W-XXXXXXXX`), sin exponer ni almacenar datos personales (`INV_WEB_SIN_PII`).

## Tipos del dominio (`tipos.py`)

```python
@dataclass(frozen=True)
class FichaPropiedad:
    propiedad_id: str
    tipo: str
    nombre: str
    zona: str
    capacidad: int
    resumen: str
    comodidades: tuple[str, ...] = ()
    fotos: tuple[str, ...] = ()
    anfitrion_id: str | None = None
    ofrecido_por: str | None = None

@dataclass(frozen=True)
class Busqueda:
    desde: date
    hasta: date
    huespedes: int
    tipo: str | None = None
    zona: str | None = None

@dataclass(frozen=True)
class OpcionDisponible:
    ficha: FichaPropiedad
    unidad_id: str
    total: Decimal
    moneda: str = "USD"

@dataclass(frozen=True)
class EnlaceContacto:
    codigo: str
    propiedad_id: str
    desde: date | None = None
    hasta: date | None = None
    huespedes: int | None = None
```

## Compuerta (`WebHuespedesService`)

```python
class WebHuespedesService:
    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        pms: Any = None,
        observabilidad: Any = None,
        anfitriones: Any = None,
        repositorio: RepositorioWeb | None = None,
    ) -> None: ...

    def catalogo(self) -> tuple[FichaPropiedad, ...]: ...                                     # RF-WEB-01, RF-ANF-03 (filtrado con anfitriones.publicados())
    def ficha(self, propiedad_id: str) -> FichaPropiedad: ...                                 # RF-WEB-01, RF-ANF-03 (detalle de propiedad publicada)
    def buscar(self, busqueda: Busqueda) -> tuple[OpcionDisponible, ...]: ...                 # T-205 RF-WEB-02 (precios en vivo sobre catálogo publicado)
    def comparar(self, propiedades: tuple[str, ...], busqueda: Busqueda) -> tuple[OpcionDisponible, ...]: ... # T-205 RF-WEB-03 (solo publicados)
    def crear_enlace_contacto(self, propiedad_id: str, busqueda: Busqueda | None = None) -> str: ... # RF-WEB-04 (enlace WhatsApp)
    def resolver_contacto(self, codigo: str) -> EnlaceContacto | None: ...                    # RF-WEB-04 (recuperado por el asistente)
    def verificar_limite_ip(self, ip: str) -> tuple[bool, int, str]: ...                      # RF-WEB-05 (cuota por minuto)
    def crear_app(self) -> FastAPI: ...                                                       # Aplicación web FastAPI
```

## Rutas públicas

| Método y ruta | Pantalla / Acción | Fase | Descripción |
| :--- | :--- | :--- | :--- |
| `GET /` | Catálogo de hospedajes | 1 | Renderiza `catalogo.html` con propiedades publicadas, comodidades, capacidad, fotos y anfitrión que lo ofrece. Sin precios ni cupos. |
| `GET /propiedades/{id}` | Ficha de propiedad | 1 | Renderiza `ficha.html` con galería de fotos, comodidades, descripción completa, anfitrión que lo ofrece y formulario a WhatsApp. 404 si está pausada. |
| `POST /contacto` | Crear enlace de contacto | 1 | Genera código `W-XXXXXXXX`, persiste contexto y redirige (303) al enlace seguro de WhatsApp (`wa.me`). |
| `GET /contacto?propiedad_id=...` | Enlace directo | 1 | Variante GET para redirección inmediata a WhatsApp con código de contexto. |
| `GET /buscar?desde=&hasta=&huespedes=` | Búsqueda por fechas | 3 | Consulta tarifas y disponibilidad en vivo contra el PMS sobre hospedajes publicados (`T-205`, `T-405`). |
| `GET /comparar?ids=&desde=&hasta=` | Comparación de hasta 3 | 3 | Comparativa lado a lado de hasta 3 opciones publicadas (`T-205`, `T-405`). |

## Invariantes del módulo

| Código | Predicado | Mecanismo obligatorio |
| :--- | :--- | :--- |
| `INV_INTERFAZ_PURIFICADA` | `∀ t ∈ textos_de_usuario : t ∩ {simbolos_gobernanza} = ∅` | Prueba exhaustiva sobre plantillas, mensajes de error y respuestas HTML. |
| `INV_SOLO_PUBLICADO` | `visible(h) ⇒ estado(h) = publicado ∧ estado(anfitrion(h)) = activo` | La web lee `anfitriones.publicados()`; hospedajes pausados o con anfitrión suspendido se omiten del catálogo y devuelven 404. |
| `INV_WEB_LIMITE_POR_IP` | `conteo(ip, minuto) > limite ⇒ ∣llamadas_pms∣ = 0` | `INSERT ... ON CONFLICT DO UPDATE` en `web.limites_ip` antes de cualquier llamada a servicios posteriores. |
| `INV_WEB_PRECIO_EN_VIVO` | `mostrado(precio, t) ⇒ precio = cotizar(t)` | `Cache-Control: no-store` en `/buscar` y `/comparar`; sin caché del servidor para disponibilidad o cotización. |
| `INV_WEB_SIN_PII` | `∀ f ∈ tablas(web) ∪ enlaces ∪ logs : PII(f) = ∅` | Sin formularios de datos personales; código aleatorio `W-` mediante `secrets`; IP persistida exclusivamente como HMAC-SHA256 con sal secreta. |
| `INV_WEB_SOLO_LECTURA` | `∀ r ∈ rutas(web) : efectos_pms(r) = ∅` | Ninguna ruta web crea, modifica ni cancela reservas. Sin integración mutadora con el PMS. |

## Interfaz y Experiencia de Usuario
- **Renderizado Server-Side (SSR):** FastAPI con plantillas Jinja2 para indexación óptima por motores de búsqueda y carga inmediata en conexiones móviles.
- **Sistema visual (tokens de `FRONTEND.md` §6):** Uso de variables CSS para `--fondo` (`#FAFAF9`), `--superficie` (`#FFFFFF`), `--borde` (`#E6E4E0`), `--texto` (`#1B1F1B`), `--acento` (`#2F6B4F`), etc., con adaptación automática a tema oscuro mediante `@media (prefers-color-scheme: dark)`.
- **Móvil primero y WCAG 2.1 AA:** Tipografía de sistema, contraste visual superior a 4.5:1, etiquetas y atributos `alt` en imágenes, objetivos táctiles de al menos 44 px.
- **Transparencia de anfitrión (RF-ANF-03):** Cada tarjeta del catálogo, resultado de búsqueda, comparación y ficha detalla explícitamente "Ofrecido por:" con el nombre comercial o identificador del anfitrión.
- **Presupuesto LCP ≤ 2,5 s en 4G:** Cero dependencias externas pesadas, sin fuentes web externas ni librerías de tracking de terceros.
- **Datos estructurados:** Inclusión de Schema.org JSON-LD (`ItemList` y `LodgingBusiness`) para buscadores.

## Configuración (`config_web_huespedes.yaml`)
- `url_base`: URL pública del servicio (por defecto `http://localhost:8080`).
- `catalogo`: Ruta del catálogo YAML de propiedades (por defecto `features/web_huespedes/catalogo_ejemplo.yaml`, en producción apunta a `CORPUS_DIR`).
- `whatsapp_numero`: Número oficial de WhatsApp de Glamping Imbabura.
- `idioma`: Idioma predeterminado (`es`).
- `comparar_max`: Máximo de propiedades comparables (3).
- `enlace_contacto_validez_h`: Período de validez del código de contexto (72 horas).
- `limites.por_ip_minuto`: Límite máximo de solicitudes por IP por minuto (30).
- `limites.retencion_h`: Período de retención de registros de cuota (24 horas).
- `limites.ip_hmac_secreto`: Clave secreta para derivar el hash HMAC de la IP.

## Compuertas que consume
- `anfitriones_service`: `anfitriones.publicados()` para filtrar estrictamente los hospedajes visibles y resolver quién ofrece cada propiedad (`INV_SOLO_PUBLICADO`, `RF-ANF-03`).
- `observabilidad_service`: Registro estructurado de eventos (`web_contacto_creado`, `web_limite_ip_excedido`).
- `pms_conector_service`: Exclusivamente para lectura de disponibilidad y cotización en vivo (`INV_WEB_SOLO_LECTURA`).

## Persistencia (`esquema web`)

```sql
CREATE TABLE web.enlaces_contacto (
  codigo           text PRIMARY KEY CHECK (codigo ~ '^W-[A-Z0-9]{8}$'),
  propiedad_id     text NOT NULL,
  desde            date,
  hasta            date,
  huespedes        integer CHECK (huespedes >= 1),
  creado_en        timestamptz NOT NULL DEFAULT now(),
  expira_en        timestamptz NOT NULL,
  CHECK (hasta IS NULL OR hasta > desde)
);

CREATE TABLE web.limites_ip (
  ip_hash          text NOT NULL,
  ventana          timestamptz NOT NULL,
  conteo           integer NOT NULL DEFAULT 1,
  PRIMARY KEY (ip_hash, ventana)
);
```

## Árbitro y Pruebas
- `tests/web_huespedes/test_catalogo.py`: Inicio y ficha, funcionamiento sin PMS, ausencia de precios y cupos (RF-WEB-01, US-18).
- `tests/web_huespedes/test_publicados.py`: Árbitro de RF-ANF-03 e INV_SOLO_PUBLICADO (T-405). Verifica exclusión de hospedajes pausados o de anfitriones suspendidos en catálogo, búsqueda, comparación y ficha, e indicación de quién ofrece cada hospedaje.
- `tests/web_huespedes/test_busqueda.py`: Búsqueda por fechas, huéspedes, tipo y zona con precios en vivo; degradación a WhatsApp si el PMS falla; comparación de hasta 3 alojamientos lado a lado; invariantes de cuota y solo lectura (RF-WEB-02, RF-WEB-03, INV_WEB_PRECIO_EN_VIVO, INV_WEB_LIMITE_POR_IP, INV_WEB_SOLO_LECTURA, US-18).
- `tests/web_huespedes/test_contacto.py`: Paso a WhatsApp con código `W-XXXXXXXX`, resolución de contexto, ausencia de PII y solo lectura (RF-WEB-04, INV_WEB_SIN_PII, INV_WEB_SOLO_LECTURA).
- `tests/web_huespedes/test_limites.py`: Límite por IP, respuesta 429, cero llamadas a PMS ante exceso, anonimización por HMAC (RF-WEB-05, INV_WEB_LIMITE_POR_IP).
- `tests/web_huespedes/test_calidad.py`: Auditoría móvil primero, WCAG 2.1 AA, presupuesto LCP, datos estructurados, purificación de interfaz (RF-WEB-06, INV_INTERFAZ_PURIFICADA).

`¤web-huespedes/`
