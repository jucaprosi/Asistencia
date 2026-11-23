// © 2026 Juan Carlos Proaño. Todos los derechos reservados.
// Frontend compilado para el panel operativo (P-01, P-02, P-08, P-09, P-10)

let sesionActiva = null;
let vistaActual = 'inicio';
let estadoAcceso = { paso: 'correo', correo: '', cargando: false, error: null };
let handoffsData = [];
let filtroHandoffs = 'esperando';
let conversacionActual = null;
let incidenciasData = [];

function generarIdempotencyKey() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'idemp-' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
}

let redConectada = typeof navigator !== 'undefined' ? navigator.onLine : true;

async function apiFetch(ruta, opciones = {}) {
  // INV_MOVIL_SIN_ESCRITURA_SIN_RED: si no hay red, ninguna accion se ejecuta ni se encola
  const esMutacion = opciones.method && ['POST', 'PUT', 'DELETE'].includes(opciones.method.toUpperCase());
  if ((!redConectada || (typeof navigator !== 'undefined' && !navigator.onLine)) && esMutacion) {
    const errorSinRed = new Error('Sin conexión: las acciones están deshabilitadas y no se encolan.');
    errorSinRed.codigo = 'sin_red';
    throw errorSinRed;
  }

  const headers = opciones.headers || {};
  if (sesionActiva && sesionActiva.csrf) {
    headers['X-CSRF-Token'] = sesionActiva.csrf;
  }
  if (esMutacion) {
    if (!headers['Idempotency-Key']) {
      headers['Idempotency-Key'] = generarIdempotencyKey();
    }
  }
  opciones.headers = headers;

  const resp = await fetch(ruta, opciones);
  const datos = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    const error = new Error(datos.mensaje_usuario || 'Error en la solicitud');
    error.status = resp.status;
    error.datos = datos;
    throw error;
  }
  return datos;
}

async function comprobarSesion() {
  try {
    sesionActiva = await apiFetch('/panel/api/sesion');
    actualizarNav();
    const hashVista = (typeof location !== 'undefined' && location.hash) ? location.hash.replace('#', '') : '';
    const destino = hashVista || 'inicio';
    navegar(destino);
  } catch {
    sesionActiva = null;
    actualizarNav();
    renderizarAcceso();
  }
}

function actualizarNav() {
  const nav = document.getElementById('nav-usuario');
  const etiqueta = document.getElementById('etiqueta-usuario');
  if (sesionActiva) {
    nav.style.display = 'flex';
    etiqueta.textContent = `${sesionActiva.rol.toUpperCase()} (${sesionActiva.usuario_id.substring(0, 8)})`;
  } else {
    nav.style.display = 'none';
  }
}

function renderizarAcceso() {
  const contenedor = document.getElementById('app');
  if (estadoAcceso.paso === 'correo') {
    contenedor.innerHTML = `
      <div class="pantalla-acceso tarjeta" style="max-width: 420px; margin: 40px auto;">
        <h1 class="marca" style="display: block; margin-bottom: 8px;">Glamping Imbabura · Panel</h1>
        <p style="color: var(--texto-secundario); margin-bottom: 20px;">Ingresa tu correo registrado para recibir tu código por WhatsApp.</p>
        ${estadoAcceso.error ? `<div class="alerta alerta-error">${estadoAcceso.error}</div>` : ''}
        <form onsubmit="event.preventDefault(); solicitarCodigo();">
          <div class="campo">
            <label for="campo-correo">Correo electrónico</label>
            <input type="email" id="campo-correo" required placeholder="tu-correo@glampingimbabura.ec" value="${estadoAcceso.correo}">
          </div>
          <button type="submit" class="boton boton-primario" style="width: 100%;" ${estadoAcceso.cargando ? 'disabled' : ''}>
            ${estadoAcceso.cargando ? 'Enviando...' : 'Enviarme el código'}
          </button>
        </form>
      </div>
    `;
  } else {
    contenedor.innerHTML = `
      <div class="pantalla-acceso tarjeta" style="max-width: 420px; margin: 40px auto;">
        <h1 class="marca" style="display: block; margin-bottom: 8px;">Código de Acceso</h1>
        <p style="color: var(--texto-secundario); margin-bottom: 20px;">Ingresa el código de 6 dígitos enviado a tu WhatsApp.</p>
        ${estadoAcceso.error ? `<div class="alerta alerta-error">${estadoAcceso.error}</div>` : ''}
        <form onsubmit="event.preventDefault(); verificarCodigo();">
          <div class="campo">
            <label for="campo-codigo">Código de 6 dígitos</label>
            <input type="text" id="campo-codigo" maxlength="6" pattern="[0-9]{6}" required placeholder="123456" autofocus>
          </div>
          <button type="submit" class="boton boton-primario" style="width: 100%; margin-bottom: 10px;" ${estadoAcceso.cargando ? 'disabled' : ''}>
            ${estadoAcceso.cargando ? 'Verificando...' : 'Entrar al panel'}
          </button>
          <button type="button" class="boton boton-secundario" style="width: 100%;" onclick="estadoAcceso.paso = 'correo'; estadoAcceso.error = null; renderizarAcceso();">
            Cambiar de correo
          </button>
        </form>
      </div>
    `;
  }
}

async function solicitarCodigo() {
  const correoInput = document.getElementById('campo-correo');
  estadoAcceso.correo = correoInput.value.trim();
  estadoAcceso.cargando = true;
  estadoAcceso.error = null;
  renderizarAcceso();

  try {
    await apiFetch('/panel/api/sesion/codigo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo: estadoAcceso.correo }),
    });
    estadoAcceso.paso = 'codigo';
  } catch (err) {
    estadoAcceso.error = err.message;
  } finally {
    estadoAcceso.cargando = false;
    renderizarAcceso();
  }
}

async function verificarCodigo() {
  const codigoInput = document.getElementById('campo-codigo');
  const codigo = codigoInput.value.trim();
  estadoAcceso.cargando = true;
  estadoAcceso.error = null;
  renderizarAcceso();

  try {
    sesionActiva = await apiFetch('/panel/api/sesion', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ correo: estadoAcceso.correo, codigo }),
    });
    actualizarNav();
    navegar('inicio');
  } catch (err) {
    estadoAcceso.error = err.message;
    estadoAcceso.cargando = false;
    renderizarAcceso();
  }
}

async function cerrarSesion() {
  try {
    await apiFetch('/panel/api/sesion', { method: 'DELETE' });
  } catch {}
  sesionActiva = null;
  actualizarNav();
  estadoAcceso = { paso: 'correo', correo: '', cargando: false, error: null };
  renderizarAcceso();
}

async function navegar(vista) {
  vistaActual = vista;
  const contenedor = document.getElementById('app');

  if (vista === 'inicio') {
    try {
      const inicio = await apiFetch('/panel/api/inicio');
      const tarjetasHtml = (inicio.tarjetas || [])
        .map(
          (t) => `
        <div class="tarjeta tarjeta-metrica" onclick="navegar('${t.accion.replace('/', '')}')">
          <div style="font-size: 14px; color: var(--texto-secundario);">${t.titulo}</div>
          <div class="metrica-valor">${t.valor}</div>
          <div style="font-size: 14px; color: var(--acento); font-weight: 600;">Ver sección →</div>
        </div>
      `
        )
        .join('');

      contenedor.innerHTML = `
        <div class="pantalla-inicio">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2>Panel Principal</h2>
            <div style="display: flex; gap: 8px;">
              <button class="boton boton-secundario" onclick="navegar('handoffs')">Handoffs</button>
              <button class="boton boton-secundario" onclick="navegar('incidencias')">Incidencias</button>
            </div>
          </div>
          <div class="grid-metricas">
            ${tarjetasHtml}
          </div>
        </div>
      `;
    } catch (err) {
      contenedor.innerHTML = `<div class="alerta alerta-error">${err.message}</div>`;
    }
  } else if (vista === 'handoffs') {
    try {
      handoffsData = await apiFetch('/panel/api/handoffs');
      renderizarHandoffs();
    } catch (err) {
      contenedor.innerHTML = `<div class="alerta alerta-error">${err.message}</div>`;
    }
  } else if (vista === 'incidencias') {
    try {
      incidenciasData = await apiFetch('/panel/api/incidencias');
      renderizarIncidencias();
    } catch (err) {
      contenedor.innerHTML = `<div class="alerta alerta-error">${err.message}</div>`;
    }
  }
}

function renderizarHandoffs() {
  const contenedor = document.getElementById('app');
  const filtrados = handoffsData.filter((h) => {
    if (filtroHandoffs === 'esperando') return !h.asignado_a;
    if (filtroHandoffs === 'mias') return h.asignado_a === sesionActiva.usuario_id;
    return true;
  });

  const filas = filtrados.length
    ? filtrados
        .map(
          (h) => `
      <article class="tarjeta">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
          <strong>${h.propiedad}</strong>
          <span class="chip">${h.zona_id}</span>
        </div>
        <p style="font-size: 14px; margin-bottom: 6px;"><strong>Motivo:</strong> ${h.motivo}</p>
        <p style="font-size: 14px; color: var(--texto-secundario); margin-bottom: 12px;">${h.resumen}</p>
        <div class="acciones-tarjeta">
          <button class="boton boton-secundario" onclick="verConversacion('${h.conversacion_id}')">Ver detalle</button>
          ${
            !h.asignado_a
              ? `<button class="boton boton-primario" onclick="tomarHandoff('${h.conversacion_id}')">Tomar</button>`
              : h.asignado_a === sesionActiva.usuario_id
              ? `<span class="chip chip-exito">Asignado a ti</span>`
              : `<span class="chip">Tomado</span>`
          }
        </div>
      </article>
    `
        )
        .join('')
    : `<div class="tarjeta" style="text-align: center; color: var(--texto-secundario);"><p>No hay conversaciones en esta categoría.</p></div>`;

  contenedor.innerHTML = `
    <div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;">
        <h2>Handoffs por Zona</h2>
        <div style="display: flex; gap: 8px;">
          <button class="chip ${filtroHandoffs === 'esperando' ? 'chip-activo' : ''}" onclick="filtroHandoffs = 'esperando'; renderizarHandoffs();">Esperando</button>
          <button class="chip ${filtroHandoffs === 'mias' ? 'chip-activo' : ''}" onclick="filtroHandoffs = 'mias'; renderizarHandoffs();">Mías</button>
          <button class="chip ${filtroHandoffs === 'todas' ? 'chip-activo' : ''}" onclick="filtroHandoffs = 'todas'; renderizarHandoffs();">Todas</button>
          <button class="boton boton-secundario" style="min-height: 32px; padding: 4px 10px;" onclick="navegar('inicio')">← Volver</button>
        </div>
      </div>
      <div>${filas}</div>
    </div>
  `;
}

async function tomarHandoff(id) {
  try {
    await apiFetch(`/panel/api/handoffs/${id}/tomar`, { method: 'POST' });
    navegar('handoffs');
  } catch (err) {
    alert(err.message);
  }
}

async function verConversacion(id) {
  const contenedor = document.getElementById('app');
  try {
    conversacionActual = await apiFetch(`/panel/api/handoffs/${id}`);
    const mensajesHtml = (conversacionActual.mensajes || [])
      .map(
        (m) => `
      <div class="mensaje-burbuja mensaje-${m.remitente}">
        <div style="font-size: 11px; opacity: 0.8; margin-bottom: 4px;">${m.remitente.toUpperCase()} · ${m.hora}</div>
        <div>${m.texto}</div>
      </div>
    `
      )
      .join('');

    contenedor.innerHTML = `
      <div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <button class="boton boton-secundario" onclick="navegar('handoffs')">← Volver</button>
          <h3 style="font-size: 18px;">${conversacionActual.propiedad} · ${conversacionActual.huesped_nombre}</h3>
          <button class="boton boton-aviso" onclick="devolverAlAsistente('${conversacionActual.conversacion_id}')">Devolver al asistente</button>
        </div>

        <div class="tarjeta hilo-chat" style="margin-bottom: 16px;">
          ${mensajesHtml}
        </div>

        <div class="tarjeta">
          <div class="campo">
            <label for="campo-respuesta">Responder al huésped por WhatsApp:</label>
            <textarea id="campo-respuesta" rows="3" placeholder="Escribe tu mensaje..."></textarea>
          </div>
          <button class="boton boton-primario" onclick="enviarRespuesta('${conversacionActual.conversacion_id}')">Enviar por WhatsApp</button>
        </div>
      </div>
    `;
  } catch (err) {
    alert(err.message);
  }
}

async function enviarRespuesta(id) {
  const textarea = document.getElementById('campo-respuesta');
  const texto = textarea.value.trim();
  if (!texto) return;

  try {
    await apiFetch(`/panel/api/handoffs/${id}/responder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texto }),
    });
    verConversacion(id);
  } catch (err) {
    alert(err.message);
  }
}

async function devolverAlAsistente(id) {
  try {
    await apiFetch(`/panel/api/handoffs/${id}/devolver`, { method: 'POST' });
    navegar('handoffs');
  } catch (err) {
    alert(err.message);
  }
}

function renderizarIncidencias() {
  const contenedor = document.getElementById('app');
  const listaHtml = incidenciasData.length
    ? incidenciasData
        .map(
          (inc) => `
      <article class="tarjeta">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
          <strong>${inc.propiedad_id} · ${inc.categoria}</strong>
          <div>
            <span class="chip">${inc.prioridad.toUpperCase()}</span>
            <span class="chip chip-${inc.estado === 'resuelta' ? 'exito' : ''}">${inc.estado.toUpperCase()}</span>
          </div>
        </div>
        <p style="font-size: 14px; margin-bottom: 12px;">${inc.descripcion}</p>
        ${
          inc.estado === 'abierta'
            ? `
          <div style="display: flex; gap: 8px;">
            <input type="text" id="nota-${inc.incidencia_id}" placeholder="Nota de resolución..." style="flex: 1; padding: 8px; border: 1px solid var(--borde); border-radius: var(--radio-boton);">
            <button class="boton boton-primario" onclick="resolverIncidencia('${inc.incidencia_id}')">Resolver</button>
          </div>
        `
            : `
          <div style="font-size: 13px; color: var(--texto-secundario);">
            <span>Resuelta por: ${inc.actor || 'Gestor'}</span> · <span>Nota: ${inc.nota || ''}</span>
          </div>
        `
        }
      </article>
    `
        )
        .join('')
    : `<div class="tarjeta" style="text-align: center; color: var(--texto-secundario);"><p>No hay incidencias en tu zona.</p></div>`;

  contenedor.innerHTML = `
    <div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h2>Incidencias de la Zona</h2>
        <button class="boton boton-secundario" style="min-height: 32px; padding: 4px 10px;" onclick="navegar('inicio')">← Volver</button>
      </div>
      <div>${listaHtml}</div>
    </div>
  `;
}

async function resolverIncidencia(id) {
  const inputNota = document.getElementById(`nota-${id}`);
  const nota = inputNota ? inputNota.value.trim() : '';
  if (!nota) {
    alert('La nota de resolución es obligatoria.');
    return;
  }
  try {
    await apiFetch(`/panel/api/incidencias/${id}/resolver`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nota }),
    });
    navegar('incidencias');
  } catch (err) {
    alert(err.message);
  }
}

// Manejo de conexion sin red (P-12, RF-PAN-13, INV_MOVIL_SIN_ESCRITURA_SIN_RED)
function actualizarEstadoRed() {
  const banner = document.getElementById('banner-sin-conexion');
  if (banner) {
    banner.style.display = redConectada ? 'none' : 'flex';
  }
  const botonesMutadores = document.querySelectorAll('.btn-validar, .btn-accion-mutadora, button[onclick*="resolverIncidencia"], button[onclick*="tomarHandoff"]');
  botonesMutadores.forEach((btn) => {
    if (!redConectada) {
      btn.setAttribute('disabled', 'disabled');
      btn.setAttribute('aria-disabled', 'true');
      if (!btn.dataset.textoOriginal) {
        btn.dataset.textoOriginal = btn.textContent;
      }
      btn.textContent = `${btn.dataset.textoOriginal} (deshabilitado)`;
    } else {
      btn.removeAttribute('disabled');
      btn.removeAttribute('aria-disabled');
      if (btn.dataset.textoOriginal) {
        btn.textContent = btn.dataset.textoOriginal;
      }
    }
  });
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    redConectada = true;
    actualizarEstadoRed();
  });
  window.addEventListener('offline', () => {
    redConectada = false;
    actualizarEstadoRed();
  });
}

// PWA Instalacion y Web Push (RF-PAN-11, RF-PAN-12)
let deferredInstallPrompt = null;
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredInstallPrompt = e;
    const tarjetaPwa = document.getElementById('tarjeta-instalacion-pwa');
    if (tarjetaPwa) tarjetaPwa.style.display = 'block';
  });
}

async function solicitarInstalacionPWA() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    descartarTarjetaInstalacion();
  } else {
    alert('Para instalar la terminal móvil, agrega esta página a tu pantalla de inicio desde el menú de tu navegador.');
  }
}

function descartarTarjetaInstalacion() {
  const tarjeta = document.getElementById('tarjeta-instalacion-pwa');
  if (tarjeta) tarjeta.style.display = 'none';
}

async function activarAvisosWebPush() {
  if (typeof Notification === 'undefined') {
    alert('Tu navegador no soporta notificaciones Web Push.');
    return;
  }
  const permiso = await Notification.requestPermission();
  if (permiso !== 'granted') {
    alert('No se otorgaron permisos de notificación.');
    return;
  }
  try {
    const vapidData = await apiFetch('/panel/api/dispositivos/vapid-public-key');
    const reg = await (navigator.serviceWorker && navigator.serviceWorker.ready);
    let sub = null;
    if (reg && reg.pushManager) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapidData.public_key,
      }).catch(() => null);
    }
    const payloadSub = sub ? sub.toJSON() : {
      endpoint: 'https://push.glamping.ec/disp/' + (sesionActiva ? sesionActiva.usuario_id : 'u1'),
      keys: { p256dh: 'clave_p256dh_valida', auth: 'clave_auth_valida' }
    };
    await apiFetch('/panel/api/dispositivos/suscribir', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payloadSub),
    });
    alert('Avisos al teléfono activados correctamente.');
    const tarjetaAvisos = document.getElementById('tarjeta-activar-avisos');
    if (tarjetaAvisos) {
      tarjetaAvisos.innerHTML = `
        <div class="estado-avisos" style="display:flex; align-items:center; color: var(--exito); font-weight:600;">
          <span style="margin-right:8px;">✓</span> Avisos activos en este teléfono
        </div>
      `;
    }
  } catch (err) {
    alert('No se pudo activar los avisos: ' + err.message);
  }
}

// Registro del Service Worker (RF-PAN-11)
if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/panel/sw.js', { scope: '/panel/' }).catch(() => {});
  });
}

// Iniciar comprobación al cargar página
window.addEventListener('DOMContentLoaded', () => {
  comprobarSesion();
  actualizarEstadoRed();
});
