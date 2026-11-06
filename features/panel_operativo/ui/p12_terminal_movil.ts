// Pantalla P-12: Terminal movil PWA (RF-PAN-11, RF-PAN-12, RF-PAN-13, RF-PAN-14)
// Invariantes: INV_MOVIL_SIN_PII_EN_DISCO, INV_MOVIL_SIN_ESCRITURA_SIN_RED, INV_AVISO_SIN_PII, INV_ACCION_IDEMPOTENTE

export interface EstadoTerminalMovil {
  conectado: boolean;
  rol: 'lider' | 'gestor' | 'administrador';
  usuario_id: string;
  ventas_en_memoria?: Array<{
    venta_id: string;
    ticket: string;
    monto: string | number;
    estado: string;
  }>;
  avisos_activados: boolean;
  instalado_pwa: boolean;
}

export function BannerSinConexion(conectado: boolean): string {
  if (conectado) {
    return '';
  }
  return `
    <div id="banner-sin-conexion" class="banner-offline" role="alert" aria-live="assertive">
      <span class="icono-alerta" aria-hidden="true">&#x26A0;</span>
      <span>Sin conexi&oacute;n &middot; solo lectura</span>
    </div>
  `;
}

export function TarjetaInstalacionPWA(descartada: boolean = false): string {
  if (descartada) {
    return '';
  }
  return `
    <div class="tarjeta tarjeta-pwa-instalacion" id="tarjeta-instalacion-pwa" role="region" aria-label="Instalar aplicacion">
      <div class="cabecera-tarjeta">
        <h3>Instalar en pantalla de inicio</h3>
        <button class="boton-cerrar-tarjeta" onclick="descartarTarjetaInstalacion()" aria-label="Descartar">&times;</button>
      </div>
      <p class="descripcion-pwa">
        Instala el Panel Operativo en tu tel&eacute;fono Android o iPhone para usarlo a pantalla completa y recibir avisos.
      </p>
      <div class="instrucciones-instalacion">
        <span class="paso-instalacion">En iPhone: Toca <strong>Compartir</strong> &rarr; <strong>Agregar al inicio</strong>.</span>
        <span class="paso-instalacion">En Android: Toca el men&uacute; &rarr; <strong>Instalar aplicaci&oacute;n</strong>.</span>
      </div>
      <div class="acciones-tarjeta">
        <button class="boton boton-secundario" id="btn-instalar-pwa" onclick="solicitarInstalacionPWA()">Instalar app</button>
      </div>
    </div>
  `;
}

export function TarjetaAvisosWebPush(activados: boolean = false): string {
  if (activados) {
    return `
      <div class="tarjeta tarjeta-avisos-activos">
        <div class="estado-avisos">
          <span class="indicador-verde" aria-hidden="true">&#x2713;</span>
          <span>Avisos activos en este tel&eacute;fono</span>
        </div>
      </div>
    `;
  }
  return `
    <div class="tarjeta tarjeta-avisos-webpush" id="tarjeta-activar-avisos">
      <h3>Avisos al tel&eacute;fono</h3>
      <p class="descripcion-avisos">
        Recibe notificaciones inmediatas de ventas por validar o handoffs e incidencias de tu zona. Sin datos personales.
      </p>
      <div class="acciones-tarjeta">
        <button class="boton boton-primario" id="btn-activar-avisos" onclick="activarAvisosWebPush()">
          Activar avisos
        </button>
      </div>
    </div>
  `;
}

export function BarraInferiorNavegacion(rol: string, vistaActiva: string): string {
  const enlaces: Array<{ id: string; texto: string; icono: string }> = [];

  if (rol === 'lider' || rol === 'administrador') {
    enlaces.push({ id: 'ventas', texto: 'Ventas', icono: '&#x1F4CB;' });
    enlaces.push({ id: 'comisiones', texto: 'Comisiones', icono: '&#x1F4CA;' });
  }
  if (rol === 'gestor' || rol === 'administrador') {
    enlaces.push({ id: 'handoffs', texto: 'Handoffs', icono: '&#x1F4AC;' });
    enlaces.push({ id: 'incidencias', texto: 'Incidencias', icono: '&#x26A0;' });
  }
  enlaces.push({ id: 'jarvis', texto: 'Jarvis', icono: '&#x1F916;' });

  const items = enlaces
    .map(
      (e) => `
      <button class="item-barra-inferior ${vistaActiva === e.id ? 'activo' : ''}" onclick="navegar('${e.id}')">
        <span class="icono-barra" aria-hidden="true">${e.icono}</span>
        <span class="texto-barra">${e.texto}</span>
      </button>
    `
    )
    .join('');

  return `
    <nav class="barra-inferior-movil" role="navigation" aria-label="Navegacion inferior de la terminal">
      ${items}
    </nav>
  `;
}

export function renderP12TerminalMovil(estado: EstadoTerminalMovil, vistaActual: string = 'ventas'): string {
  const banner = BannerSinConexion(estado.conectado);
  const avisos = TarjetaAvisosWebPush(estado.avisos_activados);
  const barra = BarraInferiorNavegacion(estado.rol, vistaActual);

  // Lista de ventas en memoria (solo lectura si no hay conexion)
  const itemsVentas = (estado.ventas_en_memoria || [])
    .map((v) => {
      const botonValidar = estado.conectado
        ? `<button class="boton boton-primario btn-validar" onclick="validarVentaUnToque('${v.venta_id}')">Validar</button>`
        : `<button class="boton boton-primario btn-validar" disabled aria-disabled="true">Validar (deshabilitado)</button>`;

      return `
        <div class="tarjeta item-venta-movil" id="venta-${v.venta_id}">
          <div class="fila-ticket">
            <span class="ticket-codigo">&#x25A4; ${v.ticket}</span>
            <span class="ticket-monto">$${v.monto}</span>
          </div>
          <div class="fila-acciones">
            ${botonValidar}
          </div>
        </div>
      `;
    })
    .join('');

  return `
    <div class="terminal-movil-contenedor ${!estado.conectado ? 'modo-sin-red' : ''}">
      ${banner}
      <div class="contenido-terminal">
        ${avisos}
        <div class="seccion-lectura-memoria">
          <h3>Bandeja de operaciones (en memoria)</h3>
          <div class="lista-items-memoria">
            ${itemsVentas || '<p class="sin-datos">No hay operaciones pendientes en memoria.</p>'}
          </div>
        </div>
      </div>
      ${barra}
    </div>
  `;
}
