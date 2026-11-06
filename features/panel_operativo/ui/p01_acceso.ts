// Pantalla P-01: Acceso al panel operativo
// Autenticacion por correo y codigo de un solo uso de 6 digitos enviado por WhatsApp

export interface EstadoAcceso {
  paso: 'correo' | 'codigo';
  correo: string;
  cargando: boolean;
  error: string | null;
}

export function renderP01Acceso(estado: EstadoAcceso): string {
  if (estado.paso === 'correo') {
    return `
      <div class="pantalla-acceso tarjeta">
        <h1 class="marca">Glamping Imbabura · Panel</h1>
        <p class="subtitulo">Ingresa tu correo registrado para recibir tu código de acceso.</p>
        ${estado.error ? `<div class="alerta alerta-error">${estado.error}</div>` : ''}
        <form id="form-solicitar-codigo" onsubmit="event.preventDefault(); solicitarCodigo();">
          <div class="campo">
            <label for="campo-correo">Correo electrónico</label>
            <input type="email" id="campo-correo" required placeholder="nombre@glampingimbabura.ec" value="${estado.correo}">
          </div>
          <button type="submit" class="boton boton-primario" ${estado.cargando ? 'disabled' : ''}>
            ${estado.cargando ? 'Enviando...' : 'Enviarme el código'}
          </button>
        </form>
        <p class="pie-nota">Te llegará por WhatsApp al número registrado.</p>
      </div>
    `;
  }

  return `
    <div class="pantalla-acceso tarjeta">
      <h1 class="marca">Verificación de Código</h1>
      <p class="subtitulo">Ingresa el código de 6 dígitos enviado por WhatsApp a tu número.</p>
      ${estado.error ? `<div class="alerta alerta-error">${estado.error}</div>` : ''}
      <form id="form-verificar-codigo" onsubmit="event.preventDefault(); verificarCodigo();">
        <div class="campo">
          <label for="campo-codigo">Código de 6 dígitos</label>
          <input type="text" id="campo-codigo" maxlength="6" pattern="[0-9]{6}" required placeholder="123456" autofocus>
        </div>
        <button type="submit" class="boton boton-primario" ${estado.cargando ? 'disabled' : ''}>
          ${estado.cargando ? 'Verificando...' : 'Entrar al panel'}
        </button>
        <button type="button" class="boton boton-secundario" onclick="cambiarPaso('correo')">
          Cambiar de correo
        </button>
      </form>
    </div>
  `;
}
