# ¤infra-hibrida
<!-- ¤¤devops-engineer -->
# Infraestructura Proxy Inverso TLS — Terminal Móvil y Panel Operativo

Este directorio contiene las configuraciones de referencia para el despliegue en producción con terminación TLS/HTTPS y soporte completo para Progressive Web App (PWA) de la Terminal Móvil del Glamping.

## Componentes

1. **`Caddyfile`**: Configuración para Caddy Server v2 con aprovisionamiento automático de certificados TLS, compresión (zstd/gzip) y cabeceras de seguridad estrictas.
2. **`nginx.conf`**: Configuración para Nginx con soporte HTTP/2, terminación SSL y redirección de HTTP a HTTPS.
3. **`vapid.env.example`**: Plantilla de variables para el protocolo VAPID (Voluntary Application Server Identification) requerido por Web Push (`RF-PAN-12`).

## Directivas Críticas para PWA (`RF-PAN-11`)

Para garantizar que los dispositivos móviles siempre ejecuten la versión más reciente del código y que los datos sensibles no queden retenidos en cachés intermedias ni en el navegador:

- **Service Worker (`/panel/sw.js`)**:
  - `Cache-Control: no-store, no-cache, must-revalidate`
  - `Service-Worker-Allowed: /panel/`
- **Manifiesto Web (`/panel/manifest.webmanifest`, `/panel/manifest.json`)**:
  - `Cache-Control: no-store, no-cache, must-revalidate`
  - `Content-Type: application/manifest+json; charset=utf-8`
- **API del Panel (`/panel/api/*`)**:
  - `Cache-Control: no-store, no-cache, must-revalidate, private`
  - `Pragma: no-cache` (cumple `INV_MOVIL_SIN_PII_EN_DISCO`)

## Notificaciones Web Push y Cero Secretos (`RF-PAN-12`, `INV_SIN_SECRETOS_EN_REPO`)

- Las claves VAPID no deben versionarse en el repositorio bajo ninguna circunstancia.
- El servidor expone la clave pública a través del endpoint del panel operativo (`panel.obtener_vapid_public_key()`).
- Los avisos móviles cumplen estrictamente con `INV_AVISO_SIN_PII`: la carga útil enviada vía Web Push se restringe exclusivamente a `{tipo, cantidad, ruta}`, omitiendo nombres, números telefónicos, montos o identificadores personales.
