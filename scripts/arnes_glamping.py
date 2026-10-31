# ¤bbap-glamping
# ¤¤qa-engineer
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
EXCLUIDOS = {".git", "transcriptor_tiktok", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist", "data"}
EXTENSIONES_TEXTO = {".py", ".yaml", ".yml", ".md", ".toml", ".json", ".sh", ".bat", ".txt", ".example", ".sql", ".feature"}
OMISIONES: list[str] = []


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
def validar_compose() -> tuple[int, str]:
    """Paso 5: los dos compose son YAML válidos; con docker en el PATH, además ``docker compose config``."""
    import yaml  # dependencia del proyecto; se importa aquí para que el paso falle solo, no el arnés entero

    salidas: list[str] = []
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
def main() -> int:
    RUTA_DATOS.mkdir(parents=True, exist_ok=True)
    inicio = time.time()
    python = sys.executable
    pasos = [
        ("utf8_sin_bom", verificar_utf8),
        ("secretos", lambda: ejecutar([python, "scripts/verificar_secretos.py"])),
        ("pytest", lambda: ejecutar([python, "-m", "pytest", "tests", "-q"])),
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
