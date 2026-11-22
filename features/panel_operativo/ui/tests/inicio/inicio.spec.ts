/**
 * Arnés de interfaz de P-02 Inicio por rol (docs/FRONTEND.md, RF-PAN-02).
 *
 * Con sesión ya iniciada (GET /sesion responde 200), el panel pinta las tarjetas que el BFF
 * entrega y no decide nada por su cuenta (INV_PANEL_SIN_LOGICA).
 */
import { expect, test } from "@playwright/test";

import {
  ConsoleSentinel,
  MARCADORES_GOBERNANZA,
  SESION_GESTORA_ZONA_A,
  SESION_LIDER,
  abrirPanelLimpio,
  rutasLlamadas,
  simularBff,
  textoVisible,
} from "../utiles";

test.describe("P-02 Inicio por rol", () => {
  test("con sesión de líder pinta las tarjetas tal como llegan del BFF", async ({ page }) => {
    const llamadas = await simularBff(page, {
      sesion: SESION_LIDER,
      tarjetas: [
        { titulo: "Ventas por validar", valor: 7, accion: "/ventas" },
        { titulo: "Conversaciones esperando", valor: 0, accion: "/handoffs" },
      ],
    });

    await abrirPanelLimpio(page);

    await expect(page.getByRole("heading", { name: "Panel Principal" })).toBeVisible();
    await expect(page.getByText("Ventas por validar")).toBeVisible();
    await expect(page.getByText("7", { exact: true })).toBeVisible();
    await expect(page.getByText("Conversaciones esperando")).toBeVisible();
    await expect(page.locator("#etiqueta-usuario")).toContainText("LIDER");
    expect(rutasLlamadas(llamadas)).toEqual(["GET /sesion", "GET /inicio"]);
  });

  test("con sesión de gestora la cabecera muestra su rol y el inicio es el mismo contrato", async ({ page }) => {
    await simularBff(page, {
      sesion: SESION_GESTORA_ZONA_A,
      tarjetas: [{ titulo: "Conversaciones esperando en tu zona", valor: 2, accion: "/handoffs" }],
    });

    await abrirPanelLimpio(page);

    await expect(page.locator("#etiqueta-usuario")).toContainText("GESTOR");
    await expect(page.getByText("Conversaciones esperando en tu zona")).toBeVisible();
  });

  test("si el inicio falla, la interfaz lo dice y no se queda cargando", async ({ page }) => {
    await simularBff(page, {
      sesion: SESION_LIDER,
      rutas: {
        "GET /inicio": { status: 500, cuerpo: { mensaje_usuario: "No pudimos cargar el inicio." } },
      },
    });

    await abrirPanelLimpio(page);

    await expect(page.getByText("No pudimos cargar el inicio.")).toBeVisible();
    await expect(page.getByText("Cargando panel operativo...")).toHaveCount(0);
  });

  test("«Cerrar sesión» llama a DELETE /sesion con la cabecera CSRF y vuelve al acceso", async ({ page }) => {
    const llamadas = await simularBff(page, {
      sesion: SESION_LIDER,
      rutas: { "DELETE /sesion": { status: 200, cuerpo: { cerrada: true } } },
    });

    await abrirPanelLimpio(page);
    await expect(page.getByRole("heading", { name: "Panel Principal" })).toBeVisible();
    await page.getByRole("button", { name: "Cerrar sesión" }).click();

    await expect(page.getByRole("textbox", { name: "Correo electrónico" })).toBeVisible();
    const cierre = llamadas.find((l) => l.method() === "DELETE");
    expect(cierre, "se esperaba DELETE /sesion").toBeTruthy();
    expect(cierre?.headers()["x-csrf-token"]).toBe(SESION_LIDER.csrf);
  });

  test("el inicio no emite errores de consola ni muestra marcadores de gobernanza", async ({ page }) => {
    const centinela = new ConsoleSentinel();
    centinela.adjuntar(page);
    await simularBff(page, { sesion: SESION_LIDER });

    await abrirPanelLimpio(page);
    await expect(page.getByRole("heading", { name: "Panel Principal" })).toBeVisible();

    centinela.exigirCeroErrores();
    expect(await textoVisible(page)).not.toMatch(MARCADORES_GOBERNANZA);
  });
});
