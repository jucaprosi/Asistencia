/**
 * Arnés de interfaz de P-01 Acceso (docs/FRONTEND.md, RF-PAN-01).
 *
 * Correo, código de 6 dígitos por mensajería, sesión. Sin contraseñas. El BFF se simula:
 * estas pruebas verifican lo que la interfaz hace con cada respuesta, no el envío real del código.
 */
import { expect, test } from "@playwright/test";

import {
  ConsoleSentinel,
  MARCA,
  MARCADORES_GOBERNANZA,
  SESION_LIDER,
  abrirPanelLimpio,
  formularioCodigo,
  formularioCorreo,
  iniciarSesionSimulada,
  medirContraste,
  rutasLlamadas,
  simularBff,
  textoVisible,
} from "../utiles";

test.describe("P-01 Acceso al panel", () => {
  test("sin sesión muestra la marca, pide el correo y no llama a nada más que a la sesión", async ({ page }) => {
    const llamadas = await simularBff(page, { sesion: null });

    await abrirPanelLimpio(page);

    await expect(page.getByRole("heading", { name: MARCA })).toBeVisible();
    const paso1 = formularioCorreo(page);
    await expect(paso1.correo).toBeVisible();
    await expect(paso1.enviar).toBeEnabled();
    await expect(page.getByRole("button", { name: "Cerrar sesión" })).toBeHidden();

    expect(rutasLlamadas(llamadas)).toEqual(["GET /sesion"]);
  });

  test("con el código correcto entra al inicio y la sesión queda visible en la cabecera", async ({ page }) => {
    const llamadas = await simularBff(page, {
      sesion: null,
      rutas: {
        "POST /sesion/codigo": { status: 200, cuerpo: { enviado: true } },
        "POST /sesion": { status: 200, cuerpo: SESION_LIDER },
      },
    });

    await abrirPanelLimpio(page);
    await iniciarSesionSimulada(page, "lider@glamping.ec", "123456");

    await expect(page.getByRole("heading", { name: "Panel Principal" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cerrar sesión" })).toBeVisible();
    await expect(page.locator("#etiqueta-usuario")).toContainText("LIDER");

    const envio = llamadas.find((l) => l.method() === "POST" && l.url().endsWith("/sesion/codigo"));
    expect(envio?.postDataJSON()).toEqual({ correo: "lider@glamping.ec" });
    const entrada = llamadas.find((l) => l.method() === "POST" && l.url().endsWith("/panel/api/sesion"));
    expect(entrada?.postDataJSON()).toEqual({ correo: "lider@glamping.ec", codigo: "123456" });
    expect(rutasLlamadas(llamadas)).toEqual(["GET /sesion", "POST /sesion/codigo", "POST /sesion", "GET /inicio"]);
  });

  test("un código incorrecto muestra el mensaje del servidor tal cual y permanece en el paso del código", async ({ page }) => {
    await simularBff(page, {
      sesion: null,
      rutas: {
        "POST /sesion/codigo": { status: 200, cuerpo: { enviado: true } },
        "POST /sesion": { status: 401, cuerpo: { mensaje_usuario: "Código incorrecto." } },
      },
    });

    await abrirPanelLimpio(page);
    await iniciarSesionSimulada(page, "lider@glamping.ec", "000000");

    await expect(page.getByText("Código incorrecto.")).toBeVisible();
    await expect(formularioCodigo(page).entrar).toBeEnabled();
    await expect(page.getByRole("heading", { name: "Panel Principal" })).toHaveCount(0);
  });

  test("«Cambiar de correo» vuelve al primer paso sin llamar al servidor", async ({ page }) => {
    const llamadas = await simularBff(page, {
      sesion: null,
      rutas: { "POST /sesion/codigo": { status: 200, cuerpo: { enviado: true } } },
    });

    await abrirPanelLimpio(page);
    const paso1 = formularioCorreo(page);
    await paso1.correo.fill("gestora@glamping.ec");
    await paso1.enviar.click();
    const paso2 = formularioCodigo(page);
    await expect(paso2.codigo).toBeVisible();
    const antes = rutasLlamadas(llamadas).length;

    await paso2.cambiarCorreo.click();

    await expect(formularioCorreo(page).correo).toBeVisible();
    expect(rutasLlamadas(llamadas).length).toBe(antes);
  });

  test("si el servidor rechaza el correo, lo dice con su mensaje y se queda en el correo", async ({ page }) => {
    await simularBff(page, {
      sesion: null,
      rutas: {
        "POST /sesion/codigo": {
          status: 400,
          cuerpo: { mensaje_usuario: "Debe proporcionar un correo electrónico." },
        },
      },
    });

    await abrirPanelLimpio(page);
    const paso1 = formularioCorreo(page);
    await paso1.correo.fill("alguien@glamping.ec");
    await paso1.enviar.click();

    await expect(page.getByText("Debe proporcionar un correo electrónico.")).toBeVisible();
    await expect(paso1.correo).toBeVisible();
  });

  test("la pantalla de acceso no emite errores de consola ni muestra marcadores de gobernanza", async ({ page }) => {
    const centinela = new ConsoleSentinel([/401/]);
    centinela.adjuntar(page);
    await simularBff(page, { sesion: null });

    await abrirPanelLimpio(page);
    await expect(formularioCorreo(page).correo).toBeVisible();

    centinela.exigirCeroErrores();
    expect(await textoVisible(page)).not.toMatch(MARCADORES_GOBERNANZA);
  });

  test("todo texto de la pantalla de acceso cumple contraste 4,5:1 (WCAG 2.1 AA)", async ({ page }) => {
    await simularBff(page, { sesion: null });

    await abrirPanelLimpio(page);
    await expect(formularioCorreo(page).correo).toBeVisible();

    const ilegibles = await medirContraste(page, ".pantalla-acceso", 4.5);
    expect(ilegibles, "textos con contraste insuficiente").toEqual([]);
  });

  test("en 360 px el formulario cabe sin desplazamiento horizontal", async ({ page }, infoPrueba) => {
    test.skip(infoPrueba.project.name !== "movil-360", "solo tiene sentido en el proyecto móvil");
    await simularBff(page, { sesion: null });

    await abrirPanelLimpio(page);
    await expect(formularioCorreo(page).enviar).toBeVisible();

    const desborda = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
    expect(desborda, "la página desborda horizontalmente").toBe(false);
    const caja = await formularioCorreo(page).enviar.boundingBox();
    expect(caja?.height ?? 0, "objetivo táctil de al menos 44 px").toBeGreaterThanOrEqual(44);
  });
});
