/**
 * P-05 Tablero de ventas y comisiones & P-05b Estado de cuenta por vendedor.
 * Requisitos: RF-PAN-04, US-08, CU-07, RF-ARM-08.
 * Cumple INV_INTERFAZ_PURIFICADA e INV_PANEL_SIN_LOGICA.
 */

export interface MetricaTablero {
  periodo_id: string;
  ventas_mes: string;
  comisiones_validadas: string;
  comisiones_pendientes: string;
  numero_ventas: number;
}

export interface VentaPorMes {
  mes: string;
  total_ventas: string;
  total_comisiones: string;
}

export interface VentaPorVendedor {
  vendedor_id: string;
  nombre: string;
  ventas: number;
  monto_total: string;
  comision_total: string;
  pendientes: number;
  comision_pendiente: string;
}

export interface VentaPorPropiedad {
  propiedad_id: string;
  nombre: string;
  ventas: number;
  monto_total: string;
}

export interface LineaEstadoCuenta {
  tipo: "venta" | "ajuste";
  comision_id: string;
  venta_id: string;
  fecha_venta: string;
  monto_venta: string;
  monto_comision: string;
  estado: string;
  periodo_origen: string;
  motivo: string | null;
}

export interface EstadoCuentaVendedor {
  vendedor_id: string;
  periodo_id: string;
  lineas: LineaEstadoCuenta[];
  total_ventas: string;
  total_comisiones: string;
  numero_ventas: number;
  numero_ajustes: number;
}

export function renderP05Tablero(
  metricas: MetricaTablero,
  ventasMes: VentaPorMes[],
  vendedores: VentaPorVendedor[],
  propiedades: VentaPorPropiedad[]
): string {
  const filasVendedores = vendedores
    .map(
      (v) => `
      <tr class="fila-interactiva" onclick="abrirEstadoCuentaVendedor('${v.vendedor_id}')">
        <td><strong>${v.nombre}</strong></td>
        <td class="td-der">${v.ventas}</td>
        <td class="td-der">USD ${v.monto_total}</td>
        <td class="td-der comision-resaltada">USD ${v.comision_total}</td>
        <td class="td-der">${v.pendientes > 0 ? `<span class="chip chip-alerta">${v.pendientes} pend</span>` : "-"}</td>
      </tr>
    `
    )
    .join("");

  const filasPropiedades = propiedades
    .map(
      (p) => `
      <tr>
        <td>${p.nombre}</td>
        <td class="td-der">${p.ventas}</td>
        <td class="td-der">USD ${p.monto_total}</td>
      </tr>
    `
    )
    .join("");

  return `
    <section class="pantalla-p05-tablero" aria-labelledby="titulo-tablero">
      <header class="tablero-cabecera">
        <div>
          <h2 id="titulo-tablero">Tablero de Ventas y Comisiones</h2>
          <span class="subtitulo-periodo">Período: ${metricas.periodo_id}</span>
        </div>
        <div class="tablero-acciones">
          <select id="selector-periodo" class="control-select" onchange="cambiarPeriodo(this.value)">
            <option value="2026-10" selected>Octubre 2026</option>
            <option value="2026-09">Septiembre 2026</option>
            <option value="2026-08">Agosto 2026</option>
          </select>
          <button class="boton boton-secundario" onclick="navegarACierrePeriodo('${metricas.periodo_id}')">
            Cierre de Período
          </button>
        </div>
      </header>

      <div class="grid-metricas">
        <div class="tarjeta tarjeta-metrica">
          <span class="metrica-titulo">Ventas del Período</span>
          <strong class="metrica-valor">USD ${metricas.ventas_mes}</strong>
          <p class="metrica-subtitulo">${metricas.numero_ventas} reservas registradas</p>
        </div>
        <div class="tarjeta tarjeta-metrica variante-exito">
          <span class="metrica-titulo">Comisiones Validadas</span>
          <strong class="metrica-valor">USD ${metricas.comisiones_validadas}</strong>
          <p class="metrica-subtitulo">Listas para cierre contable</p>
        </div>
        <div class="tarjeta tarjeta-metrica variante-alerta">
          <span class="metrica-titulo">Comisiones Pendientes</span>
          <strong class="metrica-valor">USD ${metricas.comisiones_pendientes}</strong>
          <p class="metrica-subtitulo">En ventas por validar</p>
        </div>
      </div>

      <div class="seccion-tablas-grid">
        <div class="bloque-vendedores tarjeta">
          <h3>Ventas por Vendedor</h3>
          <p class="instruccion-pequena">Toca un vendedor para revisar su estado de cuenta detallado.</p>
          <div class="contenedor-tabla-densa">
            <table class="tabla-densa">
              <thead>
                <tr>
                  <th scope="col">Vendedor</th>
                  <th scope="col" class="th-der">Ventas</th>
                  <th scope="col" class="th-der">Monto</th>
                  <th scope="col" class="th-der">Comisión</th>
                  <th scope="col" class="th-der">Pendientes</th>
                </tr>
              </thead>
              <tbody>
                ${filasVendedores}
              </tbody>
            </table>
          </div>
        </div>

        <div class="bloque-propiedades tarjeta">
          <h3>Ventas por Propiedad</h3>
          <div class="contenedor-tabla-densa">
            <table class="tabla-densa">
              <thead>
                <tr>
                  <th scope="col">Propiedad</th>
                  <th scope="col" class="th-der">Ventas</th>
                  <th scope="col" class="th-der">Total</th>
                </tr>
              </thead>
              <tbody>
                ${filasPropiedades}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  `;
}

export function renderP05bEstadoCuenta(estadoCuenta: EstadoCuentaVendedor): string {
  const lineasHtml = estadoCuenta.lineas
    .map((l) => {
      const esAjuste = l.tipo === "ajuste";
      const claseTipo = esAjuste ? "linea-ajuste" : "linea-venta";
      const chipTipo = esAjuste
        ? `<span class="chip chip-alerta">Ajuste</span>`
        : `<span class="chip chip-exito">Venta</span>`;
      const motivoHtml = l.motivo ? `<div class="motivo-ajuste">${l.motivo}</div>` : "";

      return `
      <tr class="${claseTipo}">
        <td>${chipTipo}</td>
        <td><strong>${l.venta_id}</strong></td>
        <td>${l.fecha_venta}</td>
        <td class="td-der">USD ${l.monto_venta}</td>
        <td class="td-der ${esAjuste ? 'texto-ajuste' : ''}">USD ${l.monto_comision}</td>
        <td>${motivoHtml}</td>
      </tr>
    `;
    })
    .join("");

  return `
    <div class="modal-backdrop" id="modal-estado-cuenta">
      <div class="dialogo-modal tarjeta modal-ancho" role="dialog" aria-labelledby="titulo-estado-cuenta">
        <header class="modal-cabecera">
          <div>
            <h3 id="titulo-estado-cuenta">Estado de Cuenta: ${estadoCuenta.vendedor_id}</h3>
            <span class="subtitulo-periodo">Período: ${estadoCuenta.periodo_id}</span>
          </div>
          <button class="boton-cerrar" onclick="cerrarModalEstadoCuenta()" aria-label="Cerrar">×</button>
        </header>

        <div class="resumen-totales-estado">
          <div class="total-caja">
            <span>Total Ventas:</span>
            <strong>USD ${estadoCuenta.total_ventas}</strong>
          </div>
          <div class="total-caja comision-caja">
            <span>Total Comisión:</span>
            <strong>USD ${estadoCuenta.total_comisiones}</strong>
          </div>
          <div class="total-caja">
            <span>Registros:</span>
            <span>${estadoCuenta.numero_ventas} ventas · ${estadoCuenta.numero_ajustes} ajustes</span>
          </div>
        </div>

        <div class="contenedor-tabla-densa">
          <table class="tabla-densa">
            <thead>
              <tr>
                <th scope="col">Tipo</th>
                <th scope="col">Ticket / ID</th>
                <th scope="col">Fecha</th>
                <th scope="col" class="th-der">Monto Venta</th>
                <th scope="col" class="th-der">Comisión</th>
                <th scope="col">Detalles</th>
              </tr>
            </thead>
            <tbody>
              ${lineasHtml}
            </tbody>
          </table>
        </div>

        <div class="modal-acciones">
          <button class="boton boton-primario" onclick="cerrarModalEstadoCuenta()">Entendido</button>
        </div>
      </div>
    </div>
  `;
}
