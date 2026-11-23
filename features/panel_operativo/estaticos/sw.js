// © 2026 Juan Carlos Proaño. Todos los derechos reservados.
// Service Worker de la Terminal Movil (PWA) - Panel Operativo
// Invariantes: INV_MOVIL_SIN_PII_EN_DISCO, INV_MOVIL_SIN_ESCRITURA_SIN_RED, INV_AVISO_SIN_PII

const CACHE_NAME = 'panel-shell-v2026.1';
const SHELL_ASSETS = [
  '/panel',
  '/panel/',
  '/panel/estaticos/styles.css',
  '/panel/estaticos/app.js',
  '/panel/estaticos/manifest.webmanifest',
  '/panel/estaticos/icon-192.png',
  '/panel/estaticos/icon-512.png'
];

// Ciclo de vida: nueva version se aplica de inmediato al abrir (RF-PAN-11 b)
self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(SHELL_ASSETS).catch((err) => {
        // En entornos de prueba o rutas simuladas continuar instalando
        return Promise.resolve();
      });
    })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Intercepcion de peticiones: INV_MOVIL_SIN_PII_EN_DISCO
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // La API (/panel/api/*) JAMAS se guarda en cache ni en disco
  if (url.pathname.startsWith('/panel/api')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(
          JSON.stringify({
            codigo: 'sin_red',
            mensaje_usuario: 'Sin conexion a la red. Las acciones estan deshabilitadas y no se encolan.'
          }),
          {
            status: 503,
            headers: {
              'Content-Type': 'application/json',
              'Cache-Control': 'no-store'
            }
          }
        );
      })
    );
    return;
  }

  // Shell estatico versionado: Cache first con fallback a red
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(event.request).then((networkResponse) => {
        if (
          networkResponse.status === 200 &&
          (url.pathname.startsWith('/panel/estaticos') || url.pathname === '/panel' || url.pathname === '/panel/')
        ) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return networkResponse;
      });
    })
  );
});

// Avisos Web Push: INV_AVISO_SIN_PII
self.addEventListener('push', (event) => {
  let aviso = { tipo: 'novedades', cantidad: 1, ruta: '/panel' };
  if (event.data) {
    try {
      aviso = event.data.json();
    } catch (e) {
      // Formato plano de respaldo
      aviso = { tipo: 'novedades', cantidad: 1, ruta: '/panel' };
    }
  }

  // Validacion estricta: carga ⊆ {tipo, cantidad, ruta}
  const cantidad = Number(aviso.cantidad) || 1;
  const tipo = String(aviso.tipo || 'novedades');
  const ruta = String(aviso.ruta || '/panel');

  const titulo = 'Panel Operativo';
  const opciones = {
    body: `${cantidad} ${tipo}`,
    icon: '/panel/estaticos/icon-192.png',
    badge: '/panel/estaticos/icon-192.png',
    data: {
      tipo: tipo,
      cantidad: cantidad,
      ruta: ruta
    }
  };

  event.waitUntil(self.registration.showNotification(titulo, opciones));
});

// Al tocar el aviso: abre la ruta especifica tras comprobar sesion (RF-PAN-12 b)
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const rutaDestino = (event.notification.data && event.notification.data.ruta) ? event.notification.data.ruta : '/panel';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url && 'focus' in client) {
          client.navigate(rutaDestino);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(rutaDestino);
      }
    })
  );
});
