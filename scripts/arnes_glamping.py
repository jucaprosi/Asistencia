# ¤bbap-glamping
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Arnés físico del proyecto: único árbitro de «fase completada».

Ejecuta en orden: codificación UTF-8 sin BOM → escáner de secretos → suite de pruebas → evaluaciones → validación
de compose. Escribe el certificado ``governance/artefactos/data/.test_verdict.json`` con el Exit Code global y el
SHA-256 del registro de la corrida. Devuelve 0 solo si todos los pasos devolvieron 0. Un control que no pudo correr
no se declara verde: queda en ``omisiones`` y el veredicto pasa a ``APROBADO_CON_OMISIONES``.

Uso: ``python scripts/arnes_glamping.py`` (lo invocan ejecutar_arnes_glamping.bat y .sh).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RUTA_DATOS = RAIZ / "governance" / "artefactos" / "data"
RUTA_CERTIFICADO = RUTA_DATOS / ".test_verdict.json"
RUTA_LOG = RUTA_DATOS / "arnes.log"
RUTA_COBERTURA = RUTA_DATOS / "cobertura.json"
RUTA_COBERTURA_BASE = RAIZ / "governance" / "artefactos" / "COBERTURA_BASE.json"
EXCLUIDOS = {".git", "transcriptor_tiktok", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "data"}
EXTENSIONES_TEXTO = {".py", ".yaml", ".yml", ".md", ".toml", ".json", ".sh", ".bat", ".txt", ".example", ".sql", ".feature"}
OMISIONES: list[str] = []
COBERTURA_MEDIDA: dict[str, object] = {}


# ¤bbap-glamping
def verificar_utf8() -> tuple[int, str]:
    """Paso 1: todo archivo de texto es UTF-8 válido y sin BOM."""
    errores: list[str] = []
    for ruta in RAIZ.rglob("*"):
        if not ruta.is_file() or any(parte in EXCLUIDOS for parte in ruta.parts):
            continue
        if ruta.suffix.lower() not in EXTENSIONES_TEXTO and ruta.name != ".env.example":
            continue
        datos = ruta.read_bytes()
        if datos.startswith(b"\xef\xbb\xbf"):
            errores.append(f"BOM: {ruta.relative_to(RAIZ)}")
            continue
        try:
            datos.decode("utf-8")
        except UnicodeDecodeError as exc:
            errores.append(f"UTF-8 inválido: {ruta.relative_to(RAIZ)} ({exc})")
    return (1 if errores else 0), "\n".join(errores) or "UTF-8 sin BOM en todos los archivos de texto"


# ¤bbap-glamping
def ejecutar(comando: list[str]) -> tuple[int, str]:
    """Corre un comando en la raíz del repositorio y devuelve (exit code, salida combinada)."""
    proceso = subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proceso.returncode, (proceso.stdout + proceso.stderr).strip()


# ¤bbap-glamping
def verificar_egreso() -> tuple[int, str]:
    """Verifica que la lista de egreso documentada en config_app.yaml incluya PMS y embeddings (RNF-10)."""
    import yaml

    ruta_cfg = RAIZ / "app_core" / "config_app.yaml"
    if not ruta_cfg.is_file():
        return 1, f"Falta {ruta_cfg.relative_to(RAIZ)}"
    try:
        cfg = yaml.safe_load(ruta_cfg.read_text(encoding="utf-8"))
    except Exception as exc:
        return 1, f"Error leyendo {ruta_cfg.name}: {exc}"

    egreso = cfg.get("egreso_permitido", [])
    if not isinstance(egreso, list) or not egreso:
        return 1, "egreso_permitido debe ser una lista no vacía en config_app.yaml"

    tiene_pms = any("PMS" in item or "pms" in item for item in egreso)
    tiene_embeddings = any("anthropic" in item or "embedding" in item for item in egreso)
    if not tiene_pms:
        return 1, "La lista de egreso no incluye el PMS"
    if not tiene_embeddings:
        return 1, "La lista de egreso no incluye embeddings/modelo"

    contables = [item for item in egreso if any(c in item.lower() for c in ("contab", "erp", "sap", "accounting"))]
    if contables:
        return 1, f"RNF-10 violación: servicios contables en lista de egreso: {contables}"

    return 0, f"egreso_permitido: {len(egreso)} destinos autorizados (PMS, embeddings, 0 contables)"


# ¤bbap-glamping
def ejecutar_semilla_rag() -> tuple[int, str]:
    """Paso de semilla sintética del RAG: ejecuta seed_knowledge.py --sintetico y la evaluación rag (T-210)."""
    python = sys.executable
    cod_semilla, out_semilla = ejecutar([python, "scripts/seed_knowledge.py", "--sintetico"])
    if cod_semilla != 0:
        return cod_semilla, f"Error en seed_knowledge.py:\n{out_semilla}"

    cod_eval, out_eval = ejecutar([python, "scripts/run_evals.py", "--suite", "rag"])
    if cod_eval != 0:
        return cod_eval, f"Error en evaluación rag:\n{out_eval}"

    salida = f"{out_semilla}\n{out_eval}".strip()
    return 0, salida


# ¤bbap-glamping
def validar_compose() -> tuple[int, str]:
    """Paso 5: los dos compose son YAML válidos; con docker en el PATH, además ``docker compose config``."""
    import yaml  # dependencia del proyecto; se importa aquí para que el paso falle solo, no el arnés entero

    salidas: list[str] = []
    # Validar lista de egreso (RNF-10)
    cod_egr, out_egr = verificar_egreso()
    if cod_egr != 0:
        return cod_egr, out_egr
    salidas.append(out_egr)

    for nombre in ("compose.yaml", "compose.production.yaml"):
        try:
            yaml.safe_load((RAIZ / nombre).read_text(encoding="utf-8"))
            salidas.append(f"{nombre}: YAML válido")
        except (OSError, yaml.YAMLError) as exc:
            return 1, f"{nombre}: {exc}"
    if not shutil.which("docker"):
        OMISIONES.append("docker compose config: docker no está en el PATH; solo lo verifica la CI")
        salidas.append(f"OMITIDO {OMISIONES[-1]}")
        return 0, "\n".join(salidas)
    # compose.yaml exige .env; sin él se valida con la plantilla pública y el archivo temporal se retira siempre.
    ruta_env = RAIZ / ".env"
    temporal = not ruta_env.exists()
    if temporal:
        shutil.copyfile(RAIZ / ".env.example", ruta_env)
    try:
        codigo, salida = ejecutar(["docker", "compose", "-f", "compose.yaml", "-f", "compose.production.yaml", "config", "-q"])
    finally:
        if temporal:
            ruta_env.unlink(missing_ok=True)
    salidas.append(f"docker compose config: exit {codigo}\n{salida}".strip())
    return codigo, "\n".join(salidas)


# ¤bbap-glamping
def calcular_cobertura(ruta_json: Path) -> dict[str, object]:
    """Extrae el porcentaje total y por sala del reporte json generado por pytest-cov."""
    if not ruta_json.is_file():
        raise FileNotFoundError(f"No existe el archivo de cobertura: {ruta_json}")
    data = json.loads(ruta_json.read_text(encoding="utf-8"))
    total_pct = round(data.get("totals", {}).get("percent_covered", 0.0), 2)
    salas: dict[str, dict[str, int]] = {}
    for path_str, file_data in data.get("files", {}).items():
        norm = path_str.replace("\\", "/")
        parts = norm.split("/")
        if len(parts) >= 2 and parts[0] == "features" and not parts[1].endswith(".py"):
            sala = parts[1]
            s = file_data.get("summary", {})
            salas.setdefault(sala, {"covered": 0, "statements": 0})
            salas[sala]["covered"] += s.get("covered_lines", 0)
            salas[sala]["statements"] += s.get("num_statements", 0)

    pcts_sala = {
        sala: round(v["covered"] / v["statements"] * 100, 2) if v["statements"] > 0 else 100.0
        for sala, v in sorted(salas.items())
    }
    return {
        "total": total_pct,
        "salas": pcts_sala,
    }


# ¤bbap-glamping
def verificar_cobertura_contra_piso(medida: dict[str, object], ruta_base: Path) -> tuple[int, str]:
    """Compara la cobertura medida contra el piso congelado en COBERTURA_BASE.json."""
    if not ruta_base.is_file():
        return 1, f"Falta el archivo de línea base de cobertura: {ruta_base}"
    base = json.loads(ruta_base.read_text(encoding="utf-8"))
    piso_global = base.get("piso_global", 0.0)
    pisos_sala = base.get("pisos_por_sala", {})

    total = float(medida.get("total", 0.0))
    salas = medida.get("salas", {})

    fallos: list[str] = []
    if total < piso_global - 0.001:
        fallos.append(f"Cobertura global {total:.2f}% por debajo del piso {piso_global:.2f}%")

    for sala, piso in pisos_sala.items():
        actual = salas.get(sala)
        if actual is None:
            fallos.append(f"Sala '{sala}' no tiene medición de cobertura")
        elif actual < piso - 0.001:
            fallos.append(f"Sala '{sala}' con cobertura {actual:.2f}% por debajo del piso {piso:.2f}%")

    if fallos:
        return 1, "\n".join(fallos)
    return 0, f"Cobertura global {total:.2f}% (piso {piso_global:.2f}%) y {len(pisos_sala)} salas cumplen el piso"


# ¤bbap-glamping
def verificar_cobertura() -> tuple[int, str]:
    """Paso 4: valida que la cobertura no haya bajado del piso congelado."""
    global COBERTURA_MEDIDA
    try:
        COBERTURA_MEDIDA = calcular_cobertura(RUTA_COBERTURA)
    except Exception as exc:
        return 1, f"Error calculando cobertura: {exc}"
    return verificar_cobertura_contra_piso(COBERTURA_MEDIDA, RUTA_COBERTURA_BASE)


# ¤bbap-glamping
def main() -> int:
    RUTA_DATOS.mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    python = sys.executable
    pasos = [
        ("utf8_sin_bom", verificar_utf8),
        ("secretos", lambda: ejecutar([python, "scripts/verificar_secretos.py"])),
        ("semilla_sintetica_rag", ejecutar_semilla_rag),
        ("humo_playwright", lambda: ejecutar([python, "-m", "pytest", "tests/e2e/test_humo_playwright.py", "-q", "--maxfail=1"])),
        ("pytest", lambda: ejecutar([python, "-m", "pytest", "--cov=features", f"--cov-report=json:{RUTA_COBERTURA}", "tests", "-q"])),
        ("cobertura", verificar_cobertura),
        ("evaluaciones", lambda: ejecutar([python, "scripts/run_evals.py"])),
        ("compose", validar_compose),
    ]
    registro: list[str] = [f"arnes_glamping {datetime.now(timezone.utc).isoformat()}"]
    resultados: list[dict[str, object]] = []
    codigo_global = 0
    for nombre, accion in pasos:
        t0 = time.time()
        codigo, salida = accion()
        duracion = int((time.time() - t0) * 1000)
        estado = "OK" if codigo == 0 else "FALLO"
        print(f"[{estado}] {nombre} ({duracion} ms)")
        if codigo != 0:
            print(salida)
            registro.append(f"== {nombre} exit={codigo} {duracion}ms ==\n{salida}")
            resultados.append({"nombre": nombre, "exit_code": codigo, "duracion_ms": duracion})
            codigo_global = codigo_global or codigo
            if nombre == "humo_playwright":
                print("[DETENCIÓN INMEDIATA]: Fallo en la suite de humo de Playwright; se suspende la suite completa.")
                break
            continue
        registro.append(f"== {nombre} exit={codigo} {duracion}ms ==\n{salida}")
        resultados.append({"nombre": nombre, "exit_code": codigo, "duracion_ms": duracion})
        codigo_global = codigo_global or codigo

    texto_log = "\n".join(registro) + "\n"
    RUTA_LOG.write_text(texto_log, encoding="utf-8")
    veredicto = "RECHAZADO" if codigo_global else ("APROBADO_CON_OMISIONES" if OMISIONES else "APROBADO")
    certificado = {
        "proyecto": "glamping-imbabura-agent",
        "arnes": "ejecutar_arnes_glamping",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "exit_code": codigo_global,
        "veredicto": veredicto,
        "omisiones": OMISIONES,
        "cobertura_total": COBERTURA_MEDIDA.get("total"),
        "cobertura_por_sala": COBERTURA_MEDIDA.get("salas", {}),
        "pasos": resultados,
        "duracion_total_ms": int((time.time() - inicio) * 1000),
        "sha256_log": hashlib.sha256(texto_log.encode("utf-8")).hexdigest(),
        "log": RUTA_LOG.relative_to(RAIZ).as_posix(),
    }
    RUTA_CERTIFICADO.write_text(json.dumps(certificado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"certificado: {RUTA_CERTIFICADO.relative_to(RAIZ)} → {certificado['veredicto']} (exit {codigo_global})")
    return codigo_global


if __name__ == "__main__":
    raise SystemExit(main())
