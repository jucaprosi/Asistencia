// Pantalla P-09: Detalle de conversación (hilo de mensajes, respuesta WhatsApp, devolver al asistente)

export interface MensajeChat {
  remitente: string;
  texto: string;
  hora: string;
}

export interface DetalleConversacion {
  conversacion_id: string;
  propiedad: string;
  zona_id: string;
  motivo: string;
  resumen: string;
  huesped_nombre: string;
  huesped_telefono: string;
  mensajes: MensajeChat[];
}

export function renderP09Conversacion(d: DetalleConversacion): string {
  const mensajesHtml = d.mensajes
    .map(
      (m) => `
      <div class="mensaje-burbuja mensaje-${m.remitente}">
        <div class="mensaje-remitente">${m.remitente.toUpperCase()} · ${m.hora}</div>
        <div class="mensaje-texto">${m.texto}</div>
      </div>
    `
    )
    .join('');

  return `
    <div class="pantalla-conversacion">
      <div class="cabecera-conversacion">
        <button class="boton boton-secundario" onclick="volverHandoffs()">← Volver</button>
        <h3>${d.propiedad} · ${d.huesped_nombre} (${d.huesped_telefono})</h3>
        <button class="boton boton-aviso" onclick="devolverAlAsistente('${d.conversacion_id}')">
          Devolver al asistente
        </button>
      </div>

      <div class="hilo-chat tarjeta">
        ${mensajesHtml}
      </div>

      <div class="caja-respuesta tarjeta">
        <label for="campo-respuesta">Responder al huésped por WhatsApp:</label>
        <textarea id="campo-respuesta" rows="3" placeholder="Escribe tu respuesta aquí..."></textarea>
        <div class="acciones-respuesta">
          <button class="boton boton-primario" onclick="enviarRespuesta('${d.conversacion_id}')">
            Enviar por WhatsApp
          </button>
        </div>
      </div>
    </div>
  `;
}
