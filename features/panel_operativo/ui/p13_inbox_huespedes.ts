// Pantalla P-13: Inbox Completo de Huéspedes (TASK-008, T-701, ADR-0010)
// © 2026 Juan Carlos Proaño. Todos los derechos reservados.

export interface ConversacionInboxItem {
  conversacion_id: string;
  propiedad_id: string;
  zona_id: string;
  huesped_nombre: string;
  huesped_telefono: string;
  estado: string;
  modo: string;
  ultimo_mensaje: string;
  ultimo_instante: string;
  etiquetas: string[];
  total_notas: number;
}

export interface NotaInbox {
  nota_id: string;
  conversacion_id: string;
  autor_id: string;
  autor_nombre: string;
  texto: string;
  creada_en: string;
}

export function renderP13Inbox(
  conversaciones: ConversacionInboxItem[],
  filtroEstado: string,
  busqueda: string
): string {
  const filas = conversaciones.length
    ? conversaciones
        .map(
          (c) => `
      <article class="tarjeta tarjeta-inbox ${c.estado === 'handoff' ? 'inbox-handoff' : ''}">
        <div class="inbox-cabecera">
          <div>
            <strong>${c.huesped_nombre}</strong>
            <span class="telefono">${c.huesped_telefono}</span>
          </div>
          <span class="chip ${c.estado === 'handoff' ? 'chip-alerta' : 'chip-info'}">${c.estado}</span>
        </div>
        <div class="inbox-propiedad">
          <small>${c.propiedad_id} (${c.zona_id})</small>
        </div>
        <p class="inbox-ultimo-mensaje">${c.ultimo_mensaje || '(Sin mensajes recientes)'}</p>
        <div class="inbox-etiquetas">
          ${c.etiquetas.map((et) => `<span class="chip chip-etiqueta">${et}</span>`).join('')}
          ${c.total_notas > 0 ? `<span class="chip chip-notas">📝 ${c.total_notas} notas</span>` : ''}
        </div>
        <div class="acciones-tarjeta">
          <button class="boton boton-primario" onclick="abrirConversacionInbox('${c.conversacion_id}')">
            Abrir chat
          </button>
        </div>
      </article>
    `
        )
        .join('')
    : `<div class="estado-vacio tarjeta"><p>No se encontraron conversaciones con los filtros aplicados.</p></div>`;

  return `
    <div class="pantalla-inbox-completo">
      <div class="cabecera-seccion">
        <h2>Inbox de Huéspedes</h2>
        <div class="busqueda-inbox">
          <input
            type="text"
            placeholder="Buscar por nombre, teléfono o mensaje..."
            value="${busqueda}"
            oninput="buscarInbox(this.value)"
            class="input-busqueda"
          />
        </div>
        <div class="filtros-chips">
          <button class="chip ${filtroEstado === 'todas' ? 'chip-activo' : ''}" onclick="filtrarInbox('todas')">Todas</button>
          <button class="chip ${filtroEstado === 'activa' ? 'chip-activo' : ''}" onclick="filtrarInbox('activa')">Activas</button>
          <button class="chip ${filtroEstado === 'handoff' ? 'chip-activo' : ''}" onclick="filtrarInbox('handoff')">Handoffs</button>
          <button class="chip ${filtroEstado === 'resuelta' ? 'chip-activo' : ''}" onclick="filtrarInbox('resuelta')">Resueltas</button>
        </div>
      </div>
      <section class="lista-inbox">
        ${filas}
      </section>
    </div>
  `;
}
