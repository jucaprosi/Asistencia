// © 2026 Juan Carlos Proaño. Todos los derechos reservados.
import path from "path";
import { defineConfig, devices } from "@playwright/test";

/**
 * Arnés de verificación de la interfaz del panel operativo. Es el árbitro exógeno
 * del frontend: lo que aquí no esté comprobado, no está comprobado.
 *
 * El panel no tiene servidor propio: lo sirve el BFF FastAPI de la sala
 * (features/panel_operativo/bff_internal.py) montado en el pasillo central.
 * Este arnés levanta uvicorn con el entorno de pruebas (base en memoria y
 * dobles de PMS, CRM y LLM) y simula el BFF con page.route en cada prueba,
 * de modo que las pruebas verifican la interfaz y no el backend.
 *
 * Varias sesiones en la misma carpeta: cada una fija PLAYWRIGHT_PORT distinto
 * (8101, 8102, ...). El 8080 es el de compose y no se usa aquí.
 */
const ES_CI = Boolean(process.env.CI);
const PUERTO = Number(process.env.PLAYWRIGHT_PORT ?? 8101);
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PUERTO}`;
const RAIZ_REPOSITORIO = path.resolve(__dirname, "..", "..", "..");
const PYTHON = process.env.PLAYWRIGHT_PYTHON ?? "python";

/**
 * Entorno aislado, con los nombres que leen los config_*.yaml de las salas. Un valor vacío
 * hace que el YAML tome su valor por omisión (dobles en memoria, sin proveedores reales), así
 * el arnés no hereda credenciales ni bases de datos del desarrollador.
 */
const ENTORNO_PRUEBAS: Record<string, string> = {
  APP_ENV: "beta",
  DATABASE_URL: "",
  PMS_PROVEEDOR: "fake",
  CRM_PROVEEDOR: "fake",
  GEMINI_API_KEY: "",
  ANTHROPIC_API_KEY: "",
  META_ACCESS_TOKEN: "",
  META_APP_SECRET: "",
  META_VERIFY_TOKEN: "",
  CRM_URL: "",
  CRM_TOKEN: "",
  PYTHONUTF8: "1",
};

export default defineConfig({
  testDir: "./tests",
  // Cada spec parte de un estado limpio y no depende del orden de ejecución.
  fullyParallel: true,
  // En local 3 trabajadores: con más contextos simultáneos sobre uvicorn en un hilo
  // el arnés falla por lentitud, no por regresión.
  workers: ES_CI ? 4 : 3,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  // Un test marcado como `only` delata una sesión de depuración a medio cerrar.
  forbidOnly: ES_CI,
  retries: ES_CI ? 1 : 0,
  reporter: ES_CI ? [["github"], ["list"]] : [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: BASE_URL,
    locale: "es-EC",
    timezoneId: "America/Guayaquil",
    // El diagnóstico se guarda solo cuando algo falla; en CI la traza solo en el reintento.
    trace: ES_CI ? "on-first-retry" : "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "escritorio",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      // Punto de corte mínimo de docs/FRONTEND.md §6: el panel es móvil primero.
      name: "movil-360",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 360, height: 740 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: {
    command: `${PYTHON} -m uvicorn app_core.main:crear_app --factory --host 127.0.0.1 --port ${PUERTO} --log-level warning`,
    cwd: RAIZ_REPOSITORIO,
    url: `${BASE_URL}/health`,
    reuseExistingServer: !ES_CI,
    timeout: 120_000,
    stdout: "ignore",
    stderr: "pipe",
    // Playwright añade estas variables al entorno heredado del proceso.
    env: ENTORNO_PRUEBAS,
  },
});
