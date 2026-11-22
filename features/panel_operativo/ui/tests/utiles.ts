/**
 * Utilidades compartidas del arnés de interfaz del panel operativo.
 *
 * Cada spec parte de cero: una prueba que hereda el estado de la anterior comprueba el
 * arrastre, no la regla. Los selectores van por rol y nombre accesible; si un elemento no
 * tiene rol que lo identifique, es una falta de accesibilidad de la interfaz y se corrige allí.
 */
import { expect, type Page } from "@playwright/test";

export { ConsoleSentinel } from "./consoleSentinel";
export { medirContraste, type ElementoIlegible } from "./contraste";
export {
  PREFIJO_BFF,
  SESION_GESTORA_ZONA_A,
  SESION_LIDER,
  TARJETAS_LIDER,
  claveDe,
  esBff,
  ruta,
  rutasLlamadas,
  simularBff,
  type Rol,
  type Rutas,
  type SesionSimulada,
  type TarjetaInicio,
} from "./bffSimulado";

export const RUTA_PANEL = "/panel";
export const TITULO_PANEL = "Panel Operativo — Glamping Imbabura";
export const MARCA = "Glamping Imbabura · Panel";

/**
 * Marcadores de gobernanza que jamás deben verse en pantalla (INV_INTERFAZ_PURIFICADA).
 * Se construyen por punto de código (U+00A4 y U+00A6) para que este archivo tampoco los contenga:
 * el árbitro `comprobar_interfaz_purificada` escanea los .ts de `ui/`.
 */
export const MARCADORES_GOBERNANZA = new RegExp(`[${String.fromCharCode(0xa4, 0xa6)}]`);

/**
 * Abre el panel sin estado previo. La sesión del panel vive en una cookie HttpOnly que el
 * BFF simulado nunca emite y el panel no usa localStorage, así que basta un contexto nuevo
 * por prueba; aun así se limpia por si una pantalla futura guarda algo.
 */
export async function abrirPanelLimpio(page: Page): Promise<void> {
  await page.addInitScript(() => {
    try {
      window.localStorage.clear();
      window.sessionStorage.clear();
    } catch {
      // Un navegador con almacenamiento bloqueado ya arranca limpio.
    }
  });
  await page.goto(RUTA_PANEL);
  await expect(page).toHaveTitle(TITULO_PANEL);
}

/** Pantalla P-01 en su primer paso: pide el correo. */
export function formularioCorreo(page: Page) {
  return {
    correo: page.getByRole("textbox", { name: "Correo electrónico" }),
    enviar: page.getByRole("button", { name: "Enviarme el código" }),
  };
}

/** Pantalla P-01 en su segundo paso: pide el código de 6 dígitos. */
export function formularioCodigo(page: Page) {
  return {
    codigo: page.getByRole("textbox", { name: "Código de 6 dígitos" }),
    entrar: page.getByRole("button", { name: "Entrar al panel" }),
    cambiarCorreo: page.getByRole("button", { name: "Cambiar de correo" }),
  };
}

/** Recorre P-01 completa con el BFF simulado y deja la sesión iniciada en la interfaz. */
export async function iniciarSesionSimulada(
  page: Page,
  correo = "lider@glamping.ec",
  codigo = "123456",
): Promise<void> {
  const paso1 = formularioCorreo(page);
  await paso1.correo.fill(correo);
  await paso1.enviar.click();
  const paso2 = formularioCodigo(page);
  await paso2.codigo.fill(codigo);
  await paso2.entrar.click();
}

/** Texto visible de la página, para comprobar que no muestra marcadores de gobernanza. */
export async function textoVisible(page: Page): Promise<string> {
  return page.locator("body").innerText();
}
