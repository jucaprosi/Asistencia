# ¤pasillo-central
# ¤¤qa-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-412 (docs/spec/tareas/T-412.md): el arranque productivo falla cerrado en la cuota y en la bóveda PII.

R1: es productivo todo arranque con ``K_SERVICE`` (lo define Cloud Run) o con un entorno resuelto fuera de
{beta, prueba}; ``APP_ENV`` vacío o ausente resuelve a ``beta``. R2: productivo sin PostgreSQL deja la inferencia
sin tope. R3: productivo con clave efímera no arranca. R4: fuera de producción nada cambia. R5: los manifiestos
declaran ``APP_ENV=produccion`` sin borrar las demás variables. R7: el despliegue monta ``PII_VAULT_KEY`` y no
borra secretos (``--update-secrets``, nunca ``--set-secrets``). R6: esta prueba arma su propio entorno y no importa
nada de ``tests/app_core/test_contenedor.py``.
"""
from __future__ import annotations

import secrets
from pathlib import Path

import pytest
import yaml

from app_core import contenedor as modulo_contenedor
from app_core.app_core_service import construir
from app_core.contenedor import ConfiguracionInvalida

RAIZ = Path(__file__).resolve().parents[2]
CLOUDRUN = RAIZ / "infra" / "gcp" / "cloudrun.yaml"
CLOUDBUILD = RAIZ / "infra" / "gcp" / "cloudbuild.yaml"
MENSAJE_SIN_CLAVE = "bóveda PII sin clave configurada en producción"
SERVICIO = "glamping-service-qa"
VARIABLES_DEL_PROCESO = (
    "GOOGLE_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL", "PII_VAULT_KEY", "APP_ENV", "K_SERVICE",
)
ENTORNO_BASE = {
    "META_ACCESS_TOKEN": "x",
    "META_VERIFY_TOKEN": "x",
    "META_APP_SECRET": "x",
    "PANEL_SESSION_SECRET": "x",
    "GOOGLE_CLOUD_PROJECT": "proyecto-de-prueba",
    "VERTEX_LOCATION": "us",
}


# ¤pasillo-central
def _entorno(
    monkeypatch: pytest.MonkeyPatch,
    *,
    app_env: str | None = None,
    k_service: str | None = None,
    con_clave: bool = True,
    database_url: str | None = None,
) -> dict[str, str]:
    """Entorno propio (R6). Limpia también ``os.environ``: ``AlmacenTrazas`` y ``pii_internal`` leen de ahí."""
    for variable in VARIABLES_DEL_PROCESO:
        monkeypatch.delenv(variable, raising=False)
    entorno = dict(ENTORNO_BASE)
    if app_env is not None:
        entorno["APP_ENV"] = app_env
    if k_service is not None:
        entorno["K_SERVICE"] = k_service
    if con_clave:
        entorno["PII_VAULT_KEY"] = secrets.token_hex(16)
    if database_url is not None:
        entorno["DATABASE_URL"] = database_url
    return entorno


# ¤pasillo-central
@pytest.mark.parametrize("app_env", [None, "beta", "prueba", "produccion"])
def test_r1_cloud_run_sin_postgres_niega_sea_cual_sea_app_env(monkeypatch: pytest.MonkeyPatch, app_env: str | None) -> None:
    estado = construir(entorno=_entorno(monkeypatch, app_env=app_env, k_service=SERVICIO)).inferencia.estado()
    assert estado.motivo == "sin_tope_diario"
    assert estado.con_tope_diario is False


# ¤pasillo-central
@pytest.mark.parametrize("app_env", ["prod", "Produccion", "staging"])
def test_r1_app_env_desconocido_sin_postgres_niega(monkeypatch: pytest.MonkeyPatch, app_env: str) -> None:
    estado = construir(entorno=_entorno(monkeypatch, app_env=app_env)).inferencia.estado()
    assert estado.motivo == "sin_tope_diario"
    assert estado.con_tope_diario is False


# ¤pasillo-central
@pytest.mark.parametrize("app_env", [None, "", "beta", "prueba"])
def test_r4_local_y_ci_conservan_la_cuota(monkeypatch: pytest.MonkeyPatch, app_env: str | None) -> None:
    """Guarda: sin K_SERVICE, con APP_ENV ausente, vacío (resuelve a beta), beta o prueba, SQLite conserva su cuota."""
    estado = construir(entorno=_entorno(monkeypatch, app_env=app_env)).inferencia.estado()
    assert estado.motivo != "sin_tope_diario"
    assert estado.con_tope_diario is True


# ¤pasillo-central
def test_r2_con_postgres_no_niega(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Guarda del predicado de R2: se reemplaza ``es_postgres`` para no depender de un servidor ni del orden con T-414."""
    url = f"sqlite:///{(tmp_path / 'cuota.db').as_posix()}"
    entorno = _entorno(monkeypatch, k_service=SERVICIO, database_url=url)
    monkeypatch.setattr(modulo_contenedor, "es_postgres", lambda _url: True)
    estado = construir(entorno=entorno).inferencia.estado()
    assert estado.motivo != "sin_tope_diario"


# ¤pasillo-central
def test_r3_cloud_run_con_clave_efimera_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfiguracionInvalida) as info:
        construir(entorno=_entorno(monkeypatch, k_service=SERVICIO, con_clave=False))
    assert str(info.value) == MENSAJE_SIN_CLAVE


# ¤pasillo-central
def test_r3_produccion_con_clave_efimera_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfiguracionInvalida) as info:
        construir(entorno=_entorno(monkeypatch, app_env="produccion", con_clave=False))
    assert str(info.value) == MENSAJE_SIN_CLAVE


# ¤pasillo-central
def test_r3_entorno_desconocido_con_clave_efimera_no_arranca(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfiguracionInvalida) as info:
        construir(entorno=_entorno(monkeypatch, app_env="staging", con_clave=False))
    assert str(info.value) == MENSAJE_SIN_CLAVE


# ¤pasillo-central
@pytest.mark.parametrize(("app_env", "k_service"), [(None, SERVICIO), ("produccion", None)])
def test_r3_con_clave_configurada_arranca(
    monkeypatch: pytest.MonkeyPatch, app_env: str | None, k_service: str | None
) -> None:
    """Guarda: los entornos de A5 y A6, con una clave de prueba, arrancan."""
    contenedor = construir(entorno=_entorno(monkeypatch, app_env=app_env, k_service=k_service))
    assert contenedor.seguridad.estado()["clave_efimera"] is False


# ¤pasillo-central
@pytest.mark.parametrize("app_env", [None, "beta", "prueba"])
def test_r4_local_y_ci_aceptan_clave_efimera(monkeypatch: pytest.MonkeyPatch, app_env: str | None) -> None:
    """Guarda: desarrollo local y CI arrancan sin clave de bóveda."""
    contenedor = construir(entorno=_entorno(monkeypatch, app_env=app_env, con_clave=False))
    assert contenedor.seguridad.estado()["clave_efimera"] is True


# ¤pasillo-central
def test_r3_mensaje_sin_valores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'secreta.db').as_posix()}"
    entorno = _entorno(monkeypatch, k_service=SERVICIO, con_clave=False, database_url=url)
    with pytest.raises(ConfiguracionInvalida) as info:
        construir(entorno=entorno)
    mensaje = str(info.value)
    for valor in (SERVICIO, url, "secreta.db"):
        assert valor not in mensaje


# ¤pasillo-central
def _env_de_cloudrun(texto: str) -> dict[str, str]:
    doc = yaml.safe_load(texto)
    contenedores = doc["spec"]["template"]["spec"]["containers"]
    return {e["name"]: str(e.get("value", "")) for c in contenedores for e in c.get("env", [])}


# ¤pasillo-central
def _banderas_de_run_deploy(texto: str) -> dict[str, dict[str, str]]:
    """Variables que fija cada bandera de entorno del paso ``gcloud run deploy``, por bandera."""
    banderas: dict[str, dict[str, str]] = {}
    for paso in yaml.safe_load(texto).get("steps", []):
        args = [str(a) for a in paso.get("args", [])]
        if args[:2] != ["run", "deploy"]:
            continue
        for arg in args:
            for bandera in ("--set-env-vars", "--update-env-vars"):
                if arg.startswith(f"{bandera}="):
                    variables = banderas.setdefault(bandera, {})
                    for par in arg[len(bandera) + 1:].split(","):
                        clave, _, valor = par.partition("=")
                        variables[clave.strip()] = valor.strip()
    return banderas


# ¤pasillo-central
def _deploy_fija_produccion_sin_borrar(texto: str) -> bool:
    banderas = _banderas_de_run_deploy(texto)
    return banderas.get("--update-env-vars", {}).get("APP_ENV") == "produccion" and "--set-env-vars" not in banderas


# ¤pasillo-central
def test_r5_cloudrun_declara_app_env_produccion() -> None:
    assert _env_de_cloudrun(CLOUDRUN.read_text(encoding="utf-8")).get("APP_ENV") == "produccion"


# ¤pasillo-central
def test_r5_cloudbuild_fija_app_env_sin_borrar() -> None:
    """``--set-env-vars`` reemplaza todas las variables del servicio; solo vale ``--update-env-vars``."""
    assert _deploy_fija_produccion_sin_borrar(CLOUDBUILD.read_text(encoding="utf-8"))


# ¤pasillo-central
def test_r5_el_arbitro_detecta_manifiestos_malos() -> None:
    """El árbitro mismo: los lectores rechazan un manifiesto sin APP_ENV y un despliegue con ``--set-env-vars``."""
    sin_app_env = "spec:\n  template:\n    spec:\n      containers:\n        - env:\n            - name: LOG_NIVEL\n              value: INFO\n"
    assert _env_de_cloudrun(sin_app_env).get("APP_ENV") != "produccion"
    paso = "steps:\n  - args: ['run', 'deploy', 'svc', '{bandera}']\n"
    assert not _deploy_fija_produccion_sin_borrar(paso.format(bandera="--update-env-vars=LOG_NIVEL=INFO"))
    assert not _deploy_fija_produccion_sin_borrar(paso.format(bandera="--set-env-vars=APP_ENV=produccion"))
    assert _deploy_fija_produccion_sin_borrar(paso.format(bandera="--update-env-vars=APP_ENV=produccion"))
    otro_paso = "steps:\n  - args: ['builds', 'submit', '--update-env-vars=APP_ENV=produccion']\n"
    assert not _deploy_fija_produccion_sin_borrar(otro_paso)

# ¤pasillo-central
def _secretos_de_cloudrun(texto: str) -> dict[str, tuple[str, str]]:
    """Variables montadas desde Secret Manager en ``cloudrun.yaml``: nombre -> (secreto, versión)."""
    doc = yaml.safe_load(texto)
    contenedores = doc["spec"]["template"]["spec"]["containers"]
    montadas: dict[str, tuple[str, str]] = {}
    for c in contenedores:
        for e in c.get("env", []):
            ref = (e.get("valueFrom") or {}).get("secretKeyRef") or {}
            if ref:
                montadas[e["name"]] = (str(ref.get("name", "")), str(ref.get("key", "")))
    return montadas


# ¤pasillo-central
def _secretos_de_run_deploy(texto: str) -> dict[str, dict[str, str]]:
    """Secretos que monta cada bandera de secretos del paso ``gcloud run deploy``, por bandera."""
    secretos: dict[str, dict[str, str]] = {}
    for paso in yaml.safe_load(texto).get("steps", []):
        args = [str(a) for a in paso.get("args", [])]
        if args[:2] != ["run", "deploy"]:
            continue
        for arg in args:
            for bandera in ("--set-secrets", "--update-secrets"):
                if arg.startswith(f"{bandera}="):
                    montados = secretos.setdefault(bandera, {})
                    for par in arg[len(bandera) + 1:].split(","):
                        clave, _, valor = par.partition("=")
                        montados[clave.strip()] = valor.strip()
    return secretos


# ¤pasillo-central
def test_r7_despliegue_monta_la_clave_de_la_boveda() -> None:
    """Sin ``PII_VAULT_KEY`` montada, R3 impide arrancar el primer despliegue posterior a T-412."""
    paso = "steps:\n  - args: ['run', 'deploy', 'svc', '{bandera}']\n"
    assert _secretos_de_run_deploy(paso.format(bandera="--update-secrets=DATABASE_URL=DATABASE_URL:latest")) == {
        "--update-secrets": {"DATABASE_URL": "DATABASE_URL:latest"}
    }
    assert _secretos_de_cloudrun(CLOUDRUN.read_text(encoding="utf-8")).get("PII_VAULT_KEY") == ("PII_VAULT_KEY", "latest")
    montados = _secretos_de_run_deploy(CLOUDBUILD.read_text(encoding="utf-8")).get("--update-secrets", {})
    assert montados.get("PII_VAULT_KEY") == "PII_VAULT_KEY:latest"


# ¤pasillo-central
def test_r7_cloudbuild_no_borra_secretos() -> None:
    """``--set-secrets`` reemplaza todos los secretos del servicio y borra los de ``cloudrun.yaml``."""
    secretos = _secretos_de_run_deploy(CLOUDBUILD.read_text(encoding="utf-8"))
    assert "--set-secrets" not in secretos
    assert secretos.get("--update-secrets", {}).get("DATABASE_URL") == "DATABASE_URL:latest"
