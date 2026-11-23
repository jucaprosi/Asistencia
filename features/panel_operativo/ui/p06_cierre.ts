// © 2026 Juan Carlos Proaño. Todos los derechos reservados.
/**
 * P-06 Cierre de período y exportación.
 * Requisitos: RF-PAN-05, US-14, CU-07, ADR-0015.
 * Cumple INV_INTERFAZ_PURIFICADA.
 */

export interface ResumenCierre {
  periodo_id: string;
  comisiones_validadas: string;
  comisiones_pendientes: string;
  ventas_validadas: number;
  pendientes_quedaran_fuera: number;
}

export function renderP06Cierre(resumen: ResumenCierre): string {
  const alertaPendientes =
    resumen.pendientes_quedaran_fuera > 0
      ? `
      <div class="banner-alerta" role="alert">
        <strong>Atención:</strong> Existen comisiones pendientes (USD ${resumen.comisiones_pendientes}) que 
        quedarán fuera del cierre y se trasladarán al período siguiente si no se validan antes.
      </div>
    `
      : "";

  return `
    <section class="pantalla-p06-cierre tarjeta" aria-labelledby="titulo-cierre">
      <header class="cierre-cabecera">
        <h2 id="titulo-cierre">Cierre de Período Mensual</h2>
        <span class="subtitulo-cierre">Período: ${resumen.periodo_id}</span>
      </header>

      ${alertaPendientes}

      <div class="cierre-resumen-cajas">
        <div class="caja-dato">
          <span>Ventas validadas:</span>
          <strong>${resumen.ventas_validadas}</strong>
        </div>
        <div class="caja-dato">
          <span>Total comisiones validadas:</span>
          <strong class="texto-exito">USD ${resumen.comisiones_validadas}</strong>
        </div>
        <div class="caja-dato">
          <span>Comisiones pendientes:</span>
          <strong class="texto-alerta">USD ${resumen.comisiones_pendientes}</strong>
        </div>
      </div>

      <div class="cierre-advertencia">
        <p>
          <strong>Acción Inmutable:</strong> Una vez cerrado el período, ninguna venta ni comisión podrá ser editada, 
          validada o recalculada para este mes. Cualquier corrección posterior se registrará como un ajuste en el 
          período abierto siguiente.
        </p>
      </div>

      <form id="form-confirmar-cierre" onsubmit="ejecutarCierrePeriodo(event, '${resumen.periodo_id}')">
        <div class="campo-formulario">
          <label for="entrada-confirmacion-periodo">
            Escribe exactamente <strong>${resumen.periodo_id}</strong> para confirmar:
          </label>
          <input
            type="text"
            id="entrada-confirmacion-periodo"
            class="control-input"
            placeholder="${resumen.periodo_id}"
            required
            autocomplete="off"
          />
        </div>

        <div class="cierre-acciones-botones">
          <button type="button" class="boton boton-secundario" onclick="volverAlTablero()">
            Volver al Tablero
          </button>
          <button type="submit" class="boton boton-peligro">
            Confirmar Cierre Inmutable
          </button>
        </div>
      </form>

      <hr class="separador-seccion" />

      <div class="seccion-exportaciones">
        <h3>Descarga y Exportación Contable</h3>
        <p>Obtén el detalle contable oficial del período en formatos estándar.</p>
        <div class="botones-exportar">
          <button class="boton boton-secundario" onclick="descargarExportacion('${resumen.periodo_id}', 'csv')">
            Descargar CSV
          </button>
          <button class="boton boton-secundario" onclick="descargarExportacion('${resumen.periodo_id}', 'json')">
            Descargar JSON (Auditado)
          </button>
        </div>
      </div>
    </section>
  `;
}
