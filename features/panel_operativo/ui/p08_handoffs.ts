// Pantalla P-08: Conversaciones en Handoff por zona (US-09, US-10)

export interface HandoffItem {
  conversacion_id: string;
  propiedad: string;
  zona_id: string;
  motivo: string;
  resumen: string;
  esperando_desde: string;
  asignado_a: string | null;
}

export function renderP08Handoffs(
  handoffs: HandoffItem[],
  filtro: 'esperando' | 'mias' | 'todas',
  usuario_id: string
): string {
  const filtrados = handoffs.filter((h) => {
    if (filtro === 'esperando') return !h.asignado_a;
    if (filtro === 'mias') return h.asignado_a === usuario_id;
    return true;
  });

  const filas = filtrados.length
    ? filtrados
        .map(
          (h) => `
      <article class="tarjeta tarjeta-handoff">
        <div class="handoff-cabecera">
          <strong>${h.propiedad}</strong>
          <span class="chip">${h.zona_id}</span>
        </div>
        <p class="motivo"><strong>Motivo:</strong> ${h.motivo}</p>
        <p class="resumen">${h.resumen}</p>
        <div class="acciones-tarjeta">
          <button class="boton boton-secundario" onclick="verConversacion('${h.conversacion_id}')">
            Ver detalle
          </button>
          ${
            !h.asignado_a
              ? `<button class="boton boton-primario" onclick="tomarHandoff('${h.conversacion_id}')">Tomar</button>`
              : h.asignado_a === usuario_id
              ? `<span class="chip chip-exito">Asignado a ti</span>`
              : `<span class="chip">Tomado</span>`
          }
        </div>
      </article>
    `
        )
        .join('')
    : `<div class="estado-vacio tarjeta"><p>No hay conversaciones en esta categoría.</p></div>`;

  return `
    <div class="pantalla-handoffs">
      <div class="cabecera-seccion">
        <h2>Handoffs por Zona</h2>
        <div class="filtros-chips">
          <button class="chip ${filtro === 'esperando' ? 'chip-activo' : ''}" onclick="filtrarHandoffs('esperando')">Esperando</button>
          <button class="chip ${filtro === 'mias' ? 'chip-activo' : ''}" onclick="filtrarHandoffs('mias')">Mías</button>
          <button class="chip ${filtro === 'todas' ? 'chip-activo' : ''}" onclick="filtrarHandoffs('todas')">Todas</button>
        </div>
      </div>
      <div class="lista-handoffs">
        ${filas}
      </div>
    </div>
  `;
}
