// Pantalla P-10: Incidencias por zona (lista y resolución con nota)

export interface IncidenciaItem {
  incidencia_id: string;
  propiedad_id: string;
  zona_id: string;
  categoria: string;
  prioridad: string;
  descripcion: string;
  estado: string;
  nota: string | null;
  actor: string | null;
}

export function renderP10Incidencias(incidencias: IncidenciaItem[]): string {
  const listaHtml = incidencias.length
    ? incidencias
        .map(
          (inc) => `
      <article class="tarjeta tarjeta-incidencia">
        <div class="incidencia-cabecera">
          <strong>${inc.propiedad_id} · ${inc.categoria}</strong>
          <span class="chip chip-${inc.prioridad}">${inc.prioridad.toUpperCase()}</span>
          <span class="chip chip-${inc.estado}">${inc.estado.toUpperCase()}</span>
        </div>
        <p class="descripcion">${inc.descripcion}</p>
        ${
          inc.estado === 'abierta'
            ? `
          <div class="resolver-caja">
            <input type="text" id="nota-${inc.incidencia_id}" placeholder="Nota de resolución obligatoria..." class="campo-nota">
            <button class="boton boton-primario" onclick="resolverIncidencia('${inc.incidencia_id}')">
              Resolver
            </button>
          </div>
        `
            : `
          <div class="resolucion-info">
            <p><strong>Resuelta por:</strong> ${inc.actor || 'Gestor'}</p>
            <p><strong>Nota:</strong> ${inc.nota || 'Sin nota'}</p>
          </div>
        `
        }
      </article>
    `
        )
        .join('')
    : `<div class="estado-vacio tarjeta"><p>No hay incidencias registradas en tu zona.</p></div>`;

  return `
    <div class="pantalla-incidencias">
      <div class="cabecera-seccion">
        <h2>Incidencias de la Zona</h2>
      </div>
      <div class="lista-incidencias">
        ${listaHtml}
      </div>
    </div>
  `;
}
