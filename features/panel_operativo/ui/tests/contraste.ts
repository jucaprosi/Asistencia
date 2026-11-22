import type { Page } from "@playwright/test";

export interface ElementoIlegible {
  texto: string;
  ratio: number;
}

export interface OpcionesContraste {
  minRatio?: number;
  selectorExcluir?: string;
}

/**
 * Mide el contraste de cada texto visible dentro de `selectorRaiz` contra el fondo efectivo
 * que tiene detrás. Exige ratio >= 4.5:1 (WCAG 2.1, criterio 1.4.3), el umbral que fija
 * docs/FRONTEND.md para el panel.
 *
 * Usa un lienzo canvas de 1 px en el navegador para normalizar cualquier formato de color
 * (rgb, rgba, lab, oklch) a sRGB y calcular la luminancia relativa.
 */
export async function medirContraste(
  page: Page,
  selectorRaiz: string,
  opcionesOMinRatio: number | OpcionesContraste = 4.5,
): Promise<ElementoIlegible[]> {
  const opciones: OpcionesContraste =
    typeof opcionesOMinRatio === "number" ? { minRatio: opcionesOMinRatio } : opcionesOMinRatio;
  const minRatio = opciones.minRatio ?? 4.5;
  const excluir = opciones.selectorExcluir;

  return page.evaluate(
    ({ selector, ratioExigido, selectorExcluir }) => {
      const lienzo = document.createElement("canvas").getContext("2d", { willReadFrequently: true });
      if (!lienzo) return [{ texto: "sin soporte canvas", ratio: 0 }];

      const rgb = (c: string): number[] | null => {
        if (!c || c === "transparent") return null;
        lienzo.clearRect(0, 0, 1, 1);
        lienzo.fillStyle = c;
        lienzo.fillRect(0, 0, 1, 1);
        const [r, g, b, a] = lienzo.getImageData(0, 0, 1, 1).data;
        return [r, g, b, a / 255];
      };

      const fondo = (el: Element | null): number[] => {
        for (let n = el; n; n = n.parentElement) {
          const c = rgb(getComputedStyle(n).backgroundColor);
          if (c && c[3] > 0.5) return c;
        }
        const cuerpo = rgb(getComputedStyle(document.body).backgroundColor);
        return cuerpo && cuerpo[3] > 0.5 ? cuerpo : [255, 255, 255, 1];
      };

      const lum = ([r, g, b]: number[]) => {
        const f = (v: number) => {
          const s = v / 255;
          return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        };
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
      };

      const raiz = document.querySelector(selector);
      if (!raiz) return [{ texto: `sin contenedor ${selector}`, ratio: 0 }];

      const elementos = Array.from(
        raiz.querySelectorAll("button, a, span, td, th, p, label, h1, h2, h3, h4, dt, dd, li"),
      );

      return elementos
        .filter((el) => {
          if (selectorExcluir && el.closest(selectorExcluir)) return false;
          const h = el as HTMLElement;
          return (h.innerText ?? "").trim() !== "" && h.offsetParent !== null && !(el as HTMLButtonElement).disabled;
        })
        .map((el) => {
          const a = lum(rgb(getComputedStyle(el).color) ?? [0, 0, 0]);
          const b = lum(fondo(el));
          const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
          return {
            texto: (el as HTMLElement).innerText.trim().slice(0, 40),
            ratio: Math.round(ratio * 100) / 100,
          };
        })
        .filter((m) => m.ratio < ratioExigido);
    },
    { selector: selectorRaiz, ratioExigido: minRatio, selectorExcluir: excluir },
  );
}
