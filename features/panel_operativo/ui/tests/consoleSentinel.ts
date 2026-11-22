/**
 * Centinela de consola: hace fallar la prueba si la página emitió errores.
 * Detecta regresiones silenciosas que solo aparecen en la consola del navegador.
 *
 * Uso:
 *   const centinela = new ConsoleSentinel();
 *   centinela.adjuntar(page);
 *   ... prueba ...
 *   centinela.exigirCeroErrores();
 */
import { type Page } from "@playwright/test";

export class ConsoleSentinel {
  private errores: string[] = [];
  private avisos: string[] = [];
  private registros: string[] = [];

  /** Mensajes esperados que no cuentan como error (por ejemplo, las 404 del BFF simulado). */
  constructor(private readonly ignorar: RegExp[] = []) {}

  adjuntar(page: Page): void {
    page.on("console", (mensaje) => {
      const texto = mensaje.text();
      if (this.ignorar.some((patron) => patron.test(texto))) return;
      if (mensaje.type() === "error") this.errores.push(texto);
      else if (mensaje.type() === "warning") this.avisos.push(texto);
      else this.registros.push(texto);
    });
    page.on("pageerror", (error) => {
      this.errores.push(`PageError: ${error.message}`);
    });
  }

  exigirCeroErrores(): void {
    if (this.errores.length > 0) {
      throw new Error(
        `El centinela detectó ${this.errores.length} error(es) en consola:\n${this.errores.join("\n")}`,
      );
    }
  }

  informe() {
    return {
      errores: [...this.errores],
      avisos: [...this.avisos],
      registros: this.registros.length,
    };
  }

  limpiar(): void {
    this.errores = [];
    this.avisos = [];
    this.registros = [];
  }
}
