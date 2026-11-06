// Pantalla P-02: Inicio por rol (tarjetas de resumen con la accion principal del rol)

export interface TarjetaInicio {
  titulo: string;
  valor: string | number;
  accion: string;
}

export interface EstadoInicio {
  rol: 'gestor' | 'lider' | 'administrador';
  usuario_id: string;
  tarjetas: TarjetaInicio[];
}

export function renderP02Inicio(estado: EstadoInicio): string {
  const tarjetasHtml = estado.tarjetas
    .map(
      (t) => `
      <div class="tarjeta tarjeta-metrica" onclick="navegar('${t.accion}')">
        <div class="metrica-etiqueta">${t.titulo}</div>
        <div class="metrica-valor">${t.valor}</div>
        <div class="metrica-enlace">Ver sección →</div>
      </div>
    `
    )
    .join('');

  return `
    <div class="pantalla-inicio">
      <div class="cabecera-seccion">
        <h2>Panel Principal</h2>
        <span class="chip chip-rol">${estado.rol.toUpperCase()}</span>
      </div>
      <div class="grid-metricas">
        ${tarjetasHtml}
      </div>
    </div>
  `;
}
