// Pantalla P-04: Detalle de venta y desglose de comisión (RF-PAN-03, US-06)

import { DialogoMotivo } from './p03_ventas';

export interface TramoComision {
  monto: string | number;
  porcentaje: number;
  comision: string | number;
}

export interface DesgloseComision {
  regla: string;
  version: number;
  modo: string;
  acumulado: string | number;
  tramos: TramoComision[];
  total_comision: string | number;
}

export interface TransicionItem {
  actor: string;
  rol: string;
  de: string;
  a: string;
  motivo: string | null;
  timestamp: string;
}

export interface DetalleVentaItem {
  venta_id: string;
  ticket: string;
  vendedor: string;
  cliente: string;
  producto: string;
  monto: string | number;
  fecha_venta: string;
  estado: string;
  comision_estimada: string | number | null;
  comision_fijada: string | number | null;
  reserva_ref: string | null;
  crm_publicacion_estado: string;
  desglose_comision: DesgloseComision;
  linea_tiempo: TransicionItem[];
  texto_original: string;
}

export function renderP04DetalleVenta(detalle: DetalleVentaItem, rolUsuario: string): string {
  const tramosHtml = detalle.desglose_comision?.tramos?.length
    ? detalle.desglose_comision.tramos
        .map(
          (t) => `
        <li class="tramo-item">
          <span>USD ${t.monto} al ${t.porcentaje} %</span>
          <strong>USD ${t.comision}</strong>
        </li>
      `
        )
        .join('')
    : `<li class="tramo-item"><span>Comisión estándar</span><strong>USD ${detalle.comision_fijada || detalle.comision_estimada}</strong></li>`;

  const transicionesHtml = detalle.linea_tiempo?.length
    ? detalle.linea_tiempo
        .map(
          (t) => `
        <li class="linea-tiempo-nodo">
          <div class="tiempo-marcador"></div>
          <div class="tiempo-contenido">
            <strong>${t.de} → ${t.a}</strong>
            <span class="tiempo-actor">Por ${t.actor} (${t.rol})</span>
            <span class="tiempo-fecha">${t.timestamp}</span>
            ${t.motivo ? `<p class="tiempo-motivo"><em>"${t.motivo}"</em></p>` : ''}
          </div>
        </li>
      `
        )
        .join('')
    : `<li>Sin transiciones registradas.</li>`;

  const esAdmin = rolUsuario === 'administrador';
  const puedeAnular = esAdmin && detalle.estado !== 'anulada';

  return `
    <div class="pantalla-detalle-venta" id="detalle-venta-${detalle.venta_id}">
      <div class="cabecera-seccion">
        <button class="boton boton-secundario" onclick="volverAVentas()">← Volver</button>
        <h2>Venta ${detalle.ticket}</h2>
        <span class="chip chip-${detalle.estado}">${detalle.estado}</span>
      </div>

      <div class="seccion-bloque tarjeta">
        <h3>Datos Generales</h3>
        <p><strong>Vendedor:</strong> ${detalle.vendedor}</p>
        <p><strong>Cliente:</strong> ${detalle.cliente}</p>
        <p><strong>Producto:</strong> ${detalle.producto}</p>
        <p><strong>Monto:</strong> USD ${detalle.monto}</p>
        <p><strong>Fecha de venta:</strong> ${detalle.fecha_venta}</p>
        <p><strong>Reserva vinculada:</strong> ${detalle.reserva_ref || 'Ninguna'}</p>
        <p><strong>Estado en CRM:</strong> <span class="chip">${detalle.crm_publicacion_estado}</span></p>
        <div class="texto-original-bloque">
          <span class="etiqueta-pequena">Mensaje original:</span>
          <p class="texto-original-contenido">"${detalle.texto_original}"</p>
        </div>
      </div>

      <div class="seccion-bloque tarjeta">
        <h3>Desglose de Comisión</h3>
        <p class="regla-info">
          <strong>${detalle.desglose_comision?.regla}</strong> · Versión ${detalle.desglose_comision?.version}
        </p>
        <p class="modo-info">Modo: ${detalle.desglose_comision?.modo}</p>
        <p class="acumulado-info">Acumulado previo: USD ${detalle.desglose_comision?.acumulado}</p>
        <ul class="lista-tramos">
          ${tramosHtml}
        </ul>
        <div class="total-fijado">
          <strong>Total comisión: USD ${detalle.comision_fijada || detalle.desglose_comision?.total_comision}</strong>
        </div>
      </div>

      <div class="seccion-bloque tarjeta">
        <h3>Línea de Tiempo de Transiciones</h3>
        <ul class="linea-tiempo-lista">
          ${transicionesHtml}
        </ul>
      </div>

      ${
        puedeAnular
          ? `
        <div class="seccion-acciones tarjeta">
          <button class="boton boton-peligro" onclick="abrirModalAnulacion('${detalle.venta_id}')">
            Anular venta (solo administrador)
          </button>
        </div>
        ${DialogoMotivo(detalle.venta_id, 'anular')}
      `
          : ''
      }
    </div>
  `;
}
