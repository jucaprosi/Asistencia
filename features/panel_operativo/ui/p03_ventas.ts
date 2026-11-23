// Pantalla P-03: Bandeja de ventas por validar (US-06, RF-PAN-02)
// © 2026 Juan Carlos Proaño. Todos los derechos reservados.

export interface VentaItem {
  venta_id: string;
  ticket: string;
  vendedor: string;
  cliente: string;
  producto: string;
  monto: string | number;
  fecha_venta: string;
  confianza: number;
  campos_dudosos: string[];
  texto_original: string;
  comision_estimada: string | number;
  creada: string;
}

export function DialogoMotivo(
  venta_id: string,
  accion: 'rechazar' | 'anular',
  motivosSugeridos: string[] = [
    'Monto incorrecto',
    'Cliente duplicado',
    'Fecha fuera de rango',
    'Cancelación solicitada por cliente',
    'Otro motivo',
  ]
): string {
  const opciones = motivosSugeridos
    .map((m) => `<option value="${m}">${m}</option>`)
    .join('');

  const titulo = accion === 'rechazar' ? 'Rechazar venta' : 'Anular venta';

  return `
    <div class="modal-backdrop" id="modal-motivo-${venta_id}">
      <div class="dialogo-modal tarjeta" role="dialog" aria-labelledby="modal-titulo-${venta_id}">
        <h3 id="modal-titulo-${venta_id}">${titulo}</h3>
        <p class="instruccion-modal">Indica el motivo obligatorio para registrar en la auditoría.</p>
        <div class="campo-formulario">
          <label for="motivo-select-${venta_id}">Motivo frecuente</label>
          <select id="motivo-select-${venta_id}" class="control-select" onchange="seleccionarMotivoRapido('${venta_id}')">
            <option value="">Selecciona un motivo...</option>
            ${opciones}
          </select>
        </div>
        <div class="campo-formulario">
          <label for="motivo-texto-${venta_id}">Detalle del motivo</label>
          <textarea id="motivo-texto-${venta_id}" class="control-textarea" rows="3" placeholder="Describe la razón..."></textarea>
        </div>
        <div class="acciones-modal">
          <button class="boton boton-secundario" onclick="cerrarModalMotivo('${venta_id}')">Cancelar</button>
          <button class="boton boton-peligro" onclick="confirmarAccionConMotivo('${venta_id}', '${accion}')">Confirmar</button>
        </div>
      </div>
    </div>
  `;
}

export function HojaCorreccion(venta: VentaItem): string {
  return `
    <div class="hoja-inferior" id="hoja-correccion-${venta.venta_id}">
      <div class="hoja-contenido tarjeta">
        <div class="hoja-cabecera">
          <h3>Corregir datos de venta (${venta.ticket})</h3>
          <button class="boton-cerrar" onclick="cerrarHojaCorreccion('${venta.venta_id}')" aria-label="Cerrar">×</button>
        </div>
        <div class="fragmento-original">
          <span class="etiqueta-pequena">Texto original del vendedor:</span>
          <blockquote class="cita-mensaje">${venta.texto_original}</blockquote>
        </div>
        <form id="form-correccion-${venta.venta_id}" onsubmit="guardarCorreccion(event, '${venta.venta_id}')">
          <div class="campo-formulario">
            <label for="corr-cliente-${venta.venta_id}">Cliente</label>
            <input type="text" id="corr-cliente-${venta.venta_id}" value="${venta.cliente}" class="control-input" required />
          </div>
          <div class="campo-formulario">
            <label for="corr-monto-${venta.venta_id}">Monto (USD)</label>
            <input type="number" step="0.01" id="corr-monto-${venta.venta_id}" value="${venta.monto}" class="control-input" required />
          </div>
          <div class="campo-formulario">
            <label for="corr-producto-${venta.venta_id}">Producto / Hospedaje</label>
            <input type="text" id="corr-producto-${venta.venta_id}" value="${venta.producto}" class="control-input" required />
          </div>
          <div class="campo-formulario">
            <label for="corr-fecha-${venta.venta_id}">Fecha de venta</label>
            <input type="date" id="corr-fecha-${venta.venta_id}" value="${venta.fecha_venta}" class="control-input" required />
          </div>
          <div class="acciones-hoja">
            <button type="button" class="boton boton-secundario" onclick="cerrarHojaCorreccion('${venta.venta_id}')">Cancelar</button>
            <button type="submit" class="boton boton-primario">Validar con cambios</button>
          </div>
        </form>
      </div>
    </div>
  `;
}

export function TarjetaVenta(venta: VentaItem): string {
  const tieneDudosos = venta.campos_dudosos && venta.campos_dudosos.length > 0;
  const chipDudosos = tieneDudosos
    ? `<span class="chip chip-alerta" title="Campos con baja confianza">Dudoso: ${venta.campos_dudosos.join(', ')}</span>`
    : `<span class="chip chip-exito">Sin dudas</span>`;

  const puntosConfianza = Math.round(venta.confianza * 5);
  const barraConfianza = '●'.repeat(puntosConfianza) + '○'.repeat(5 - puntosConfianza);

  return `
    <article class="tarjeta tarjeta-venta" id="tarjeta-venta-${venta.venta_id}">
      <div class="venta-cabecera">
        <div>
          <strong class="ticket-venta">${venta.ticket}</strong>
          <span class="vendedor-venta">${venta.vendedor}</span>
        </div>
        <div>
          ${chipDudosos}
        </div>
      </div>
      <div class="venta-cuerpo">
        <p class="detalle-linea">
          <strong>${venta.cliente}</strong> · ${venta.producto}
        </p>
        <p class="monto-linea">
          <span class="monto-valor">USD ${venta.monto}</span>
          <span class="comision-est">Comisión estimada: USD ${venta.comision_estimada}</span>
        </p>
        <p class="confianza-linea">
          Confianza: <span class="confianza-puntos">${barraConfianza}</span> (${Math.round(venta.confianza * 100)} %)
        </p>
        <div class="texto-original-bloque">
          <span class="etiqueta-pequena">Mensaje recibido:</span>
          <p class="texto-original-contenido">"${venta.texto_original}"</p>
        </div>
      </div>
      <div class="acciones-tarjeta">
        <button class="boton boton-secundario" onclick="verDetalleVenta('${venta.venta_id}')">
          Detalle
        </button>
        <button class="boton boton-peligro" onclick="abrirRechazo('${venta.venta_id}')">
          Rechazar
        </button>
        ${
          tieneDudosos
            ? `<button class="boton boton-primario" onclick="abrirCorreccion('${venta.venta_id}')">Revisar y validar</button>`
            : `<button class="boton boton-primario" onclick="validarVentaDirecta('${venta.venta_id}')">Validar</button>`
        }
      </div>
      ${HojaCorreccion(venta)}
      ${DialogoMotivo(venta.venta_id, 'rechazar')}
    </article>
  `;
}

export function renderP03Ventas(ventas: VentaItem[]): string {
  const tarjetas = ventas.length
    ? ventas.map((v) => TarjetaVenta(v)).join('')
    : `<div class="estado-vacio tarjeta"><p>No hay ventas pendientes por validar.</p></div>`;

  return `
    <div class="pantalla-ventas">
      <div class="cabecera-seccion">
        <h2>Ventas por validar</h2>
        <span class="contador-pendientes chip">${ventas.length} pendientes</span>
      </div>
      <div class="aviso-banner" id="banner-aviso" style="display: none;"></div>
      <div class="lista-ventas" id="lista-ventas-por-validar">
        ${tarjetas}
      </div>
    </div>
  `;
}
