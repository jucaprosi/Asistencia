# Módulo `web_huespedes`
`¤web-huespedes`

| Campo | Valor |
| :--- | :--- |
| Sala | `features/web_huespedes/` |
| Requisitos | [`PRD.md` §5.12](../PRD.md) (RF-WEB-01..06) |
| Decisión | [ADR-0017](../adr/ADR-0017-web-publica-huespedes.md) |

## Propósito
Web pública para buscar y comparar los hospedajes publicados. Solo lectura: la reserva termina en WhatsApp.

## Compuerta

```python
class WebHuespedesService:
    def catalogo(self) -> tuple[FichaPropiedad, ...]: ...                                     # sin precios
    def ficha(self, propiedad_id: str) -> FichaPropiedad: ...
    def buscar(self, busqueda: Busqueda) -> tuple[OpcionDisponible, ...]: ...                 # precio y cupo en vivo del PMS
    def comparar(self, propiedades: tuple[str, ...], busqueda: Busqueda) -> tuple[OpcionDisponible, ...]: ...
    def crear_enlace_contacto(self, propiedad_id: str, busqueda: Busqueda | None) -> str: ... # enlace a WhatsApp con código
    def resolver_contacto(self, codigo: str) -> EnlaceContacto | None: ...                    # lo usa el agente
```

## Rutas

| Ruta | Pantalla | Fase |
| :--- | :--- | :--- |
| `GET /` | Inicio con catálogo | 1 |
| `GET /propiedades/{id}` | Ficha | 1 |
| `POST /contacto` | Crea el código y redirige a WhatsApp | 1 |
| `GET /buscar?desde=&hasta=&huespedes=&tipo=&zona=` | Resultados | 3 |
| `GET /comparar?ids=&desde=&hasta=&huespedes=` | Comparación de hasta 3 | 3 |

## Interfaz
HTML renderizado en el servidor con FastAPI y Jinja2, para que los buscadores lean el contenido, y JavaScript mínimo. Móvil primero con los tokens de [`FRONTEND.md`](../FRONTEND.md) §6. Sin cookies de sesión, sin cuentas y sin analítica de terceros.

## Configuración (`config_web_huespedes.yaml`)
URL, ruta del catálogo, número de WhatsApp, máximo a comparar, validez del enlace y límites por IP. El catálogo real vive en `CORPUS_DIR`; el repositorio solo guarda `catalogo_ejemplo.yaml`, con datos sintéticos.

## Compuertas que consume
`pms_conector_service` (`consultar_disponibilidad`, `cotizar`) y `observabilidad_service`.

## Errores
`ErrorWebHuespedes` con `mensaje_usuario`. Si el PMS no responde, el catálogo sigue visible y la búsqueda ofrece preguntar por WhatsApp.

## Persistencia (`esquema web`)
`enlaces_contacto` y `limites_ip`. Ninguna guarda datos personales.

## Tests (árbitro)
`tests/web_huespedes/test_catalogo.py`, `test_busqueda.py`, `test_contacto.py`, `test_limites.py`, `test_calidad.py`.

`¤web-huespedes/`
