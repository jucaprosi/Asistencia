/**
 * BFF simulado del panel operativo.
 *
 * El panel llama a /panel/api/* (contrato en docs/FRONTEND.md). Aquí el navegador nunca llega
 * al BFF real: `page.route` intercepta cada llamada, responde lo que la prueba declaró y
 * registra todas las peticiones. Toda ruta no declarada responde 404 con el código
 * NO_SIMULADA y queda registrada: una pantalla que llama a algo inesperado se detecta.
 *
 * Esto es lo que permite probar la interfaz sin el código de acceso que el BFF real envía
 * por el canal de mensajería: la prueba decide qué responde cada ruta.
 */
import { type Page, type Request, type Route } from "@playwright/test";

export const PREFIJO_BFF = "/panel/api";

export type Rol = "lider" | "gestor" | "administrador";

export interface SesionSimulada {
  usuario_id: string;
  rol: Rol;
  zonas: string[];
  csrf: string;
}

export interface TarjetaInicio {
  titulo: string;
  valor: number | string;
  accion: string;
}

export interface RespuestaSimulada {
  status?: number;
  cuerpo?: unknown;
}

/** Clave de ruta: "GET /sesion", "POST /sesion/codigo"... Sin el prefijo /panel/api. */
export type Rutas = Record<string, RespuestaSimulada | ((peticion: Request) => RespuestaSimulada)>;

export interface OpcionesBff {
  /** Sesión que GET /sesion devuelve. Si falta o es null, responde 401 (sin sesión). */
  sesion?: SesionSimulada | null;
  /** Tarjetas de P-02 que GET /inicio devuelve. */
  tarjetas?: TarjetaInicio[];
  /** Rutas adicionales o sobrescritas por la prueba. */
  rutas?: Rutas;
}

export const SESION_LIDER: SesionSimulada = {
  usuario_id: "usuario-lider-0001",
  rol: "lider",
  zonas: [],
  csrf: "csrf-de-prueba",
};

export const SESION_GESTORA_ZONA_A: SesionSimulada = {
  usuario_id: "usuario-gestora-0001",
  rol: "gestor",
  zonas: ["zona_a"],
  csrf: "csrf-de-prueba",
};

export const TARJETAS_LIDER: TarjetaInicio[] = [
  { titulo: "Ventas por validar", valor: 3, accion: "/ventas" },
  { titulo: "Conversaciones esperando", valor: 1, accion: "/handoffs" },
];

/** Ruta sin prefijo ni query: "/panel/api/sesion?x=1" pasa a "/sesion". */
export function ruta(url: string): string {
  const pathname = new URL(url).pathname;
  return pathname.startsWith(PREFIJO_BFF) ? pathname.slice(PREFIJO_BFF.length) || "/" : pathname;
}

export function esBff(peticion: Request): boolean {
  return new URL(peticion.url()).pathname.startsWith(PREFIJO_BFF);
}

export function claveDe(peticion: Request): string {
  return `${peticion.method()} ${ruta(peticion.url())}`;
}

function json(status: number, cuerpo: unknown) {
  return { status, contentType: "application/json", body: JSON.stringify(cuerpo ?? {}) };
}

/**
 * Simula el BFF y devuelve la lista viva de peticiones que la interfaz hizo.
 * Las rutas de `opciones.rutas` tienen prioridad sobre las que derivan de `sesion` y `tarjetas`.
 */
export async function simularBff(page: Page, opciones: OpcionesBff = {}): Promise<Request[]> {
  const llamadas: Request[] = [];
  const sesion = opciones.sesion ?? null;

  const base: Rutas = {
    "GET /sesion": sesion
      ? { status: 200, cuerpo: sesion }
      : { status: 401, cuerpo: { mensaje_usuario: "Sesión no iniciada." } },
    "GET /inicio": { status: 200, cuerpo: { tarjetas: opciones.tarjetas ?? TARJETAS_LIDER } },
    "GET /dispositivos/vapid-public-key": {
      status: 404,
      cuerpo: { mensaje_usuario: "Sin avisos push en pruebas." },
    },
  };
  const rutas: Rutas = { ...base, ...(opciones.rutas ?? {}) };

  await page.route(`**${PREFIJO_BFF}/**`, async (route: Route) => {
    const peticion = route.request();
    llamadas.push(peticion);
    const respuesta = rutas[claveDe(peticion)];
    if (!respuesta) {
      return route.fulfill(
        json(404, { codigo: "NO_SIMULADA", mensaje_usuario: `Ruta no simulada: ${claveDe(peticion)}` }),
      );
    }
    const resuelta = typeof respuesta === "function" ? respuesta(peticion) : respuesta;
    return route.fulfill(json(resuelta.status ?? 200, resuelta.cuerpo));
  });

  return llamadas;
}

/** Rutas del BFF que la interfaz llamó, en orden y sin repetir. */
export function rutasLlamadas(llamadas: Request[]): string[] {
  return [...new Set(llamadas.filter(esBff).map(claveDe))];
}
