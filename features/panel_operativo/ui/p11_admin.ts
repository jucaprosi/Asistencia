// © 2026 Juan Carlos Proaño. Todos los derechos reservados.
/**
 * P-11 Administración Completa.
 * Requisitos: RF-PAN-09, RF-ANF-08, RF-PRIV-05, OP-01..10.
 * Cumple INV_INTERFAZ_PURIFICADA.
 */

export interface UsuarioAdmin {
  usuario_id: string;
  correo_enmascarado: string;
  numero_enmascarado: string;
  rol: string;
  activo: boolean;
}

export interface ReglaAdmin {
  regla_id: string;
  version: number;
  nombre: string;
  tipo: string;
  vigencia_desde: string;
  activa: boolean;
}

export interface EstadoCuentaAnfitrionAdmin {
  estado_cuenta_id: string;
  anfitrion_id: string;
  periodo: string;
  total: string;
  estado: "emitido" | "pagado" | "vencido";
  vence_en: string;
  pagado_en: string | null;
}

export interface MetricaSaludAdmin {
  codigo: string;
  nombre: string;
  valor: string;
  estado: "optimo" | "alerta" | "critico";
}

export function renderP11AdminMenu(subpantallaActiva: string): string {
  const items = [
    { id: "usuarios", etiqueta: "Usuarios y Bloqueos" },
    { id: "reglas", etiqueta: "Reglas de Comisión" },
    { id: "anfitriones", etiqueta: "Anfitriones y Pagos" },
    { id: "plantillas", etiqueta: "Plantillas" },
    { id: "conocimiento", etiqueta: "Conocimiento" },
    { id: "auditoria", etiqueta: "Auditoría" },
    { id: "salud", etiqueta: "Salud del Sistema" },
  ];

  const pestanas = items
    .map(
      (it) => `
      <button
        class="pestana-nav ${it.id === subpantallaActiva ? 'activa' : ''}"
        onclick="cambiarSubpantallaAdmin('${it.id}')"
      >
        ${it.etiqueta}
      </button>
    `
    )
    .join("");

  return `
    <nav class="navegacion-subpantallas" aria-label="Secciones de administración">
      ${pestanas}
    </nav>
  `;
}

export function renderP11CobroAnfitriones(estados: EstadoCuentaAnfitrionAdmin[]): string {
  const filas = estados
    .map((e) => {
      const pagado = e.estado === "pagado";
      const botonAccion = pagado
        ? `<span class="chip chip-exito">Pagado</span>`
        : `<button class="boton boton-primario boton-pequeno" onclick="registrarPagoAnfitrion('${e.estado_cuenta_id}')">Registrar Pago</button>`;

      return `
      <tr>
        <td><strong>${e.estado_cuenta_id}</strong></td>
        <td>${e.anfitrion_id}</td>
        <td>${e.periodo}</td>
        <td class="td-der">USD ${e.total}</td>
        <td>${e.vence_en}</td>
        <td>${botonAccion}</td>
      </tr>
    `;
    })
    .join("");

  return `
    <section class="subpantalla-cobro-anfitriones tarjeta">
      <header class="seccion-cabecera">
        <div>
          <h3>Cobro de Comisión a Anfitriones</h3>
          <p class="instruccion-pequena">Los anfitriones pagan por fuera de la plataforma en 14 días. A los 15 días de vencido se pausan sus hospedajes.</p>
        </div>
        <button class="boton boton-secundario" onclick="verificarCobrosVencidos()">Revisar Vencimientos</button>
      </header>

      <div class="contenedor-tabla-densa">
        <table class="tabla-densa">
          <thead>
            <tr>
              <th scope="col">ID Estado</th>
              <th scope="col">Anfitrión</th>
              <th scope="col">Período</th>
              <th scope="col" class="th-der">Total</th>
              <th scope="col">Vence</th>
              <th scope="col">Acción</th>
            </tr>
          </thead>
          <tbody>
            ${filas}
          </tbody>
        </table>
      </div>
    </section>
  `;
}
