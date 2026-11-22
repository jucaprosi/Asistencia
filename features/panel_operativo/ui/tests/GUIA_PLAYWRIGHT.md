# Guía del arnés de interfaz (Playwright) del panel operativo

Playwright es el árbitro de la interfaz: lo que no pasa aquí no está comprobado. Esta guía es para
cualquier persona o IA que ejecute o escriba pruebas del panel. Todo lo de abajo está comprobado en
este repositorio (Playwright 1.65, Chromium, Windows 11, Node 22, Python 3.14).

El arnés adapta la configuración que usa el equipo de EVYDENTIA (origin/main 41aec2ef de su
repositorio) a la arquitectura de este proyecto: aquí el panel no tiene servidor Node propio, lo
sirve el BFF FastAPI de la sala `panel_operativo` montado en el pasillo central (`/panel`).

## 1. Dónde vive cada cosa

| Qué | Ruta |
|---|---|
| Workspace Node (dependencias, scripts) | `features/panel_operativo/ui/package.json` |
| Configuración del arnés | `features/panel_operativo/ui/playwright.config.ts` |
| Pruebas, una carpeta por pantalla | `features/panel_operativo/ui/tests/<pantalla>/*.spec.ts` |
| Helpers compartidos | `tests/utiles.ts`, `tests/bffSimulado.ts`, `tests/consoleSentinel.ts`, `tests/contraste.ts` |
| Interfaz que se prueba | `features/panel_operativo/estaticos/` (build servido por el BFF) |

Las pruebas de extremo a extremo en Python (`tests/e2e/*.py`, con pytest y servidor en hilo) siguen
siendo las del arnés físico `ejecutar_arnes_glamping`. Este arnés las complementa: verifica lo que la
interfaz hace en el navegador con cada respuesta del BFF, sin backend real.

## 2. Preparación (una vez por máquina)

```powershell
cd features\panel_operativo\ui
npm install
npx playwright install chromium
```

Los navegadores se guardan en `%LOCALAPPDATA%\ms-playwright`, fuera del repositorio. Si una prueba
dice que falta el ejecutable, es este paso. Python y las dependencias del proyecto (`pip install -e
".[dev]"`) también hacen falta: el arnés levanta uvicorn por su cuenta.

## 3. Ejecutar

Siempre desde `features/panel_operativo/ui`. El arnés levanta el servidor con un entorno aislado
(dobles de PMS, CRM y LLM, sin credenciales del desarrollador) y lo apaga al terminar.

| Qué | Comando |
|---|---|
| Todo (escritorio y móvil 360 px) | `npx playwright test` |
| Solo un proyecto | `npx playwright test --project=movil-360` |
| Una carpeta | `npx playwright test tests/acceso` |
| Una prueba por nombre | `npx playwright test -g "código incorrecto"` |
| Ver qué hay sin ejecutar | `npx playwright test --list` |
| Informe de la última ejecución | `npm run test:e2e:report` |
| Tipos | `npm run typecheck` |

### Varias sesiones a la vez: un puerto distinto cada una

El arnés reutiliza un servidor que ya responda en su puerto. Si dos sesiones comparten la carpeta y
el puerto, una prueba lo que compiló la otra. Cada sesión fija el suyo:

```powershell
$env:PLAYWRIGHT_PORT=8103; npx playwright test
```

Usa 8101, 8102, 8103... El 8080 es el de `compose.yaml` y no se usa aquí. Comprueba antes en qué
rama estás: el servidor sirve lo que hay en disco.

## 4. Cómo se escribe una prueba aquí

- **El BFF no existe.** Cada prueba lo simula con `simularBff(page, {...})` (`tests/bffSimulado.ts`),
  que intercepta `/panel/api/**` con `page.route`, responde lo que la prueba declaró y devuelve la
  lista de peticiones que la interfaz hizo. Toda ruta no declarada responde 404 `NO_SIMULADA` y
  queda registrada: una pantalla que llama a algo inesperado se detecta con `rutasLlamadas`.
- **Por qué se simula:** el acceso real exige un código de 6 dígitos que el BFF envía por el canal
  de mensajería y que solo es legible dentro del proceso de pytest. Desde el navegador no hay forma
  honesta de obtenerlo, y tampoco hace falta: lo que se prueba es la interfaz.
- **Selectores por rol y nombre accesible** (`getByRole`, `getByLabel`), no por clase CSS ni por
  texto suelto. Si un elemento no tiene rol que lo identifique, es una falta de accesibilidad de la
  interfaz: corrígela allí, no en la prueba. `getByTestId` es la segunda opción, con `data-testid`
  en kebab-case y en español, para contenedores sin rol.
- **Helpers compartidos** en `tests/utiles.ts`: `abrirPanelLimpio`, `formularioCorreo`,
  `formularioCodigo`, `iniciarSesionSimulada`. Si un cambio de la interfaz los rompe, el arreglo es
  del propietario del helper; no se esquiva con una copia local.
- **Esperas:** nunca `waitForTimeout`. Usa aserciones que reintentan (`await expect(...)`).
- **Cada prueba parte limpia.** Un contexto nuevo por prueba; no dependas del orden ni de datos que
  dejó otra.
- **Centinela de consola** (`ConsoleSentinel`): al menos una prueba por pantalla exige cero errores
  de consola.
- **Contraste** (`medirContraste(page, selector, 4.5)`): al menos una prueba por pantalla exige el
  ratio 4,5:1 de WCAG 2.1 AA que fija el diseño del panel.
- **Interfaz purificada:** ninguna pantalla muestra marcadores de gobernanza. Las pruebas lo
  comprueban con `MARCADORES_GOBERNANZA`, escrito con escapes Unicode a propósito: el árbitro
  `comprobar_interfaz_purificada` también escanea los `.ts` de `ui/`.
- **Prueba negativa obligatoria:** una prueba que nunca ha fallado no demuestra nada. Rompe a
  propósito lo que verifica y comprueba que falla, antes de darla por buena.

## 5. Lo que este arnés no hace (y dónde se hace)

- **Regresión visual por píxel** (`toHaveScreenshot`): descartada, frágil entre Windows y Linux.
  Responsive se verifica con el proyecto `movil-360` y aserciones de desbordamiento y tamaño táctil.
- **axe-core:** no integrado. Si se adopta, la vía es `@axe-core/playwright` con las etiquetas
  `wcag2a` y `wcag2aa`.
- **Modo oscuro:** sin cobertura todavía (`colorScheme: "dark"` en un proyecto aparte sería el camino).
- **Login real** (código por mensajería, cookie HttpOnly, CSRF del servidor): lo prueban
  `tests/e2e/test_handoff_zona.py` y `tests/panel_operativo/` con el BFF real en proceso.
- **CI:** este arnés aún no corre en `.github/workflows/ci.yml` (ruta reservada al coordinador). Un
  Playwright en verde es evidencia local: pega el comando, el puerto y el resultado en el PR.

## 6. Trampas conocidas

- **`estaticos/` está en `.gitignore`.** Es el build servido; si no existe, `/panel` responde un
  esqueleto vacío y todas las pruebas fallan al buscar el formulario. Genera o copia el build antes.
- **Variables de entorno:** el arnés fija `CRM_PROVEEDOR=fake`, `PMS_PROVEEDOR=fake` y vacía las
  credenciales. Los nombres son los de `features/*/config_*.yaml`; un nombre inventado no aísla nada.
- **Fallos lentos:** una aserción fallida espera 15 s. Una suite con varios fallos tarda minutos;
  es normal, no es un cuelgue.
- **Windows:** archivos en UTF-8 sin BOM (lo exige el arnés físico). Rutas con barras normales.
- **Artefactos de fallo** (`test-results/`, `playwright-report/`) están ignorados por git. La traza
  de un fallo se abre con `npx playwright show-trace <ruta/trace.zip>`.
- **Un navegador manejado por un asistente (MCP)** sirve para mirar y depurar; no sustituye al
  arnés. El criterio de éxito es `npx playwright test`.

## 7. Qué entregar en un PR que toca la interfaz

1. `npm run typecheck` sin errores.
2. `npx playwright test` en verde, con el comando exacto y el puerto usado.
3. Las pruebas nuevas, con la comprobación de que fallan cuando rompes lo que verifican.
4. `ejecutar_arnes_glamping.bat` en Exit Code 0.
5. Si algo no se pudo comprobar, dilo como «no verificado»; no lo omitas.
