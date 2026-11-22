// Pantalla P-07: Chat con Jarvis (RF-PAN-06, RF-ARM-09)
// © 2026 Juan Carlos Proaño. Todos los derechos reservados.

export interface MensajeJarvis {
  autor: 'usuario' | 'jarvis';
  texto: string;
  hora: string;
  requiere_confirmacion?: boolean;
  cambio_propuesto?: Record<string, unknown> | null;
}

export function ChatJarvis(mensajes: MensajeJarvis[]): string {
  const burbujas = mensajes
    .map((m) => {
      const claseAutor = m.autor === 'usuario' ? 'mensaje-usuario' : 'mensaje-jarvis';
      const botonesConfirmacion = m.requiere_confirmacion
        ? `
        <div class="confirmacion-acciones">
          <button class="boton boton-primario" onclick="confirmarCambioJarvis(true)">Confirmar</button>
          <button class="boton boton-secundario" onclick="confirmarCambioJarvis(false)">Cancelar</button>
        </div>
      `
        : '';

      return `
        <div class="burbuja-chat ${claseAutor}">
          <p class="texto-mensaje">${m.texto}</p>
          <span class="hora-mensaje">${m.hora}</span>
          ${botonesConfirmacion}
        </div>
      `;
    })
    .join('');

  return `
    <div class="contenedor-chat-jarvis">
      <div class="historial-chat" id="historial-chat-jarvis">
        ${burbujas}
      </div>
      <form class="formulario-chat" id="form-chat-jarvis" onsubmit="enviarPreguntaJarvis(event)">
        <input
          type="text"
          id="entrada-chat-jarvis"
          class="control-input"
          placeholder="Escribe tu pregunta sobre ventas o comisiones..."
          required
          autocomplete="off"
        />
        <button type="submit" class="boton boton-primario">Enviar</button>
      </form>
    </div>
  `;
}

export function renderP07Jarvis(mensajes: MensajeJarvis[]): string {
  return `
    <div class="pantalla-jarvis">
      <div class="cabecera-seccion">
        <h2>Asistente Operativo Jarvis</h2>
        <span class="chip chip-info">Sesión volátil (sin historial en disco)</span>
      </div>
      <div class="tarjeta tarjeta-jarvis">
        ${ChatJarvis(mensajes)}
      </div>
    </div>
  `;
}
