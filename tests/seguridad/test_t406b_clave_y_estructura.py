# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""T-406-b: clave de bóveda efímera, reintento ante IntegrityError y ``tokenizar_estructura`` (INV_PII_FUERA_DEL_MODELO).

Defectos reproducidos en e3cc879:
- sin ``clave_boveda`` ni ``PII_VAULT_KEY`` la bóveda cifra con una clave fija publicada en el repositorio;
- ``_guardar_en_boveda`` usa ``ON CONFLICT(token) DO UPDATE``: si dos escritores eligen el mismo número,
  el segundo valor recibe un token que ya pertenece a otro y al rehidratar se entrega el dato ajeno;
- no hay forma de tokenizar una estructura (dict, list, tuple) antes de enviarla al modelo.

Un "arranque" distinto es un proceso distinto: la clave efímera es por proceso, así que la prueba de
aislamiento entre arranques escribe la fila en un subproceso y la intenta leer en el proceso de la prueba.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from features.seguridad import seguridad_service
from features.seguridad.seguridad_service import SeguridadService
from tests.conftest import RAIZ
from tests.seguridad.dobles import DobleObservabilidad

TELEFONO_A = "0991111111"
TELEFONO_B = "0982222222"
CORREO = "ana.torres@example.com"
NOMBRE = "Ana Lucía Torres"
CLAVE_PUBLICADA_ANTERIOR = "glamping-imbabura-pii-vault-master-key-2026"

GUION_ESCRITOR = r"""
import hashlib, json, sys
from features.seguridad.seguridad_service import SeguridadService
config = json.loads(sys.argv[1])
servicio = SeguridadService(config)
texto = servicio.tokenizar("mi telefono es 0991111111", "conv-arranque")
fila = servicio.conexion.execute(
    "SELECT token, titular_hash, tipo, valor_cifrado FROM seguridad.boveda_tokens"
).fetchone()
print(json.dumps({
    "texto": texto,
    "token": fila["token"],
    "titular_hash": fila["titular_hash"],
    "tipo": fila["tipo"],
    "valor_cifrado": bytes(fila["valor_cifrado"]).hex(),
    "huella_clave": hashlib.sha256(servicio._pii._clave).hexdigest(),
    "estado": getattr(servicio, "estado", dict)(),
}))
"""


def _entorno_sin_clave() -> dict[str, str]:
    entorno = {k: v for k, v in os.environ.items() if k != "PII_VAULT_KEY"}
    entorno["PYTHONPATH"] = str(RAIZ)
    entorno["PYTHONIOENCODING"] = "utf-8"
    return entorno


def _arrancar_escritor(config: dict[str, Any]) -> dict[str, Any]:
    """Arranca otro proceso que tokeniza un teléfono y devuelve la fila cifrada de su bóveda."""
    resultado = subprocess.run(
        [sys.executable, "-c", GUION_ESCRITOR, json.dumps(config)],
        cwd=str(RAIZ),
        env=_entorno_sin_clave(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr
    return json.loads(resultado.stdout.strip().splitlines()[-1])


def _importar_fila(servicio: SeguridadService, fila: dict[str, Any]) -> None:
    servicio.conexion.execute(
        "INSERT INTO seguridad.boveda_tokens (token, titular_hash, tipo, valor_cifrado) VALUES (?, ?, ?, ?)",
        (fila["token"], fila["titular_hash"], fila["tipo"], bytes.fromhex(fila["valor_cifrado"])),
    )
    servicio.conexion.commit()


@pytest.fixture
def sin_clave(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PII_VAULT_KEY", raising=False)


@pytest.fixture
def servicio(sin_clave: None) -> SeguridadService:
    return SeguridadService({}, observabilidad=DobleObservabilidad())


# --- 1. Clave efímera ---------------------------------------------------------------------------


def test_t406b_el_codigo_de_la_sala_no_contiene_la_clave_publicada() -> None:
    for ruta in (RAIZ / "features" / "seguridad").glob("*.py"):
        assert CLAVE_PUBLICADA_ANTERIOR not in ruta.read_text(encoding="utf-8"), ruta.name


def test_t406b_sin_clave_configurada_el_estado_reporta_clave_efimera(servicio: SeguridadService) -> None:
    assert servicio.estado()["clave_efimera"] is True


def test_t406b_sin_clave_configurada_la_clave_difiere_entre_dos_arranques(sin_clave: None) -> None:
    primero = _arrancar_escritor({})
    segundo = _arrancar_escritor({})
    assert primero["estado"].get("clave_efimera") is True
    assert primero["huella_clave"] != segundo["huella_clave"]


def test_t406b_dos_arranques_sin_clave_configurada_no_se_leen_entre_si(servicio: SeguridadService) -> None:
    ajeno = _arrancar_escritor({})
    _importar_fila(servicio, ajeno)
    rehidratado = servicio.rehidratar(ajeno["texto"], "conv-arranque")
    assert TELEFONO_A not in rehidratado
    assert rehidratado == "mi telefono es [DATO_BORRADO]"


def test_t406b_con_clave_configurada_no_es_efimera(sin_clave: None) -> None:
    servicio = SeguridadService({"pii": {"clave_boveda": "clave-de-prueba-t406b"}}, observabilidad=DobleObservabilidad())
    assert servicio.estado()["clave_efimera"] is False


def test_t406b_con_clave_en_entorno_no_es_efimera(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PII_VAULT_KEY", "clave-de-entorno-t406b")
    assert SeguridadService({}, observabilidad=DobleObservabilidad()).estado()["clave_efimera"] is False


def test_t406b_con_la_misma_clave_configurada_otro_arranque_si_rehidrata(sin_clave: None) -> None:
    config = {"pii": {"clave_boveda": "clave-de-prueba-t406b"}}
    ajeno = _arrancar_escritor(config)
    assert ajeno["estado"].get("clave_efimera") is False
    servicio = SeguridadService(config, observabilidad=DobleObservabilidad())
    _importar_fila(servicio, ajeno)
    assert servicio.rehidratar(ajeno["texto"], "conv-arranque") == f"mi telefono es {TELEFONO_A}"


def test_t406b_con_la_misma_clave_una_segunda_instancia_sobre_la_misma_conexion_rehidrata(sin_clave: None) -> None:
    config = {"pii": {"clave_boveda": "clave-de-prueba-t406b"}}
    primero = SeguridadService(config, observabilidad=DobleObservabilidad())
    texto = primero.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    segundo = SeguridadService(config, observabilidad=DobleObservabilidad(), conexion=primero.conexion)
    assert segundo.rehidratar(texto, "conv-1") == f"mi telefono es {TELEFONO_A}"


# --- 2. Reintento ante IntegrityError -----------------------------------------------------------


def test_t406b_colision_en_la_boveda_elige_otro_numero_y_cada_token_rehidrata_su_valor(
    servicio: SeguridadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Otro escritor ya guardó conv-1:[TELEFONO_1] con TELEFONO_A, pero esta instancia no lo vio al elegir el
    # número (carrera entre la consulta y el INSERT): se simula cegando la consulta previa, sin hilos.
    escritor = SeguridadService({}, observabilidad=DobleObservabilidad(), conexion=servicio.conexion)
    ajeno = escritor.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    assert ajeno == "mi telefono es [TELEFONO_1]"
    monkeypatch.setattr(servicio._pii, "_existe_en_boveda", lambda token_db: False)

    propio = servicio.tokenizar(f"el de mi esposa es {TELEFONO_B}", "conv-1")

    assert propio == "el de mi esposa es [TELEFONO_2]"
    assert servicio.rehidratar(propio, "conv-1") == f"el de mi esposa es {TELEFONO_B}"
    assert servicio.rehidratar(ajeno, "conv-1") == f"mi telefono es {TELEFONO_A}"
    filas = servicio.conexion.execute(
        "SELECT COUNT(*) AS c FROM seguridad.boveda_tokens WHERE token LIKE 'conv-1:%'"
    ).fetchone()
    assert filas["c"] == 2


class _ConexionQueSiempreViolaRestriccion:
    """Delega en la conexión real, pero todo INSERT en la bóveda viola una restricción (NOT NULL, CHECK, FK)."""

    TOPE_DE_SEGURIDAD = 50  # la prueba no debe colgarse si el código no tiene tope

    def __init__(self, real: Any) -> None:
        self._real = real
        self.inserts = 0

    def execute(self, sql: str, *args: Any) -> Any:
        if "INSERT INTO seguridad.boveda_tokens" in sql:
            self.inserts += 1
            if self.inserts > self.TOPE_DE_SEGURIDAD:
                raise RuntimeError("reintento sin tope")
            raise sqlite3.IntegrityError("NOT NULL constraint failed: boveda_tokens.titular_hash")
        return self._real.execute(sql, *args)

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self._real, nombre)


def test_t406b_un_integrity_error_persistente_no_reintenta_sin_tope(
    servicio: SeguridadService, monkeypatch: pytest.MonkeyPatch
) -> None:
    conexion = _ConexionQueSiempreViolaRestriccion(servicio._pii._conn)
    monkeypatch.setattr(servicio._pii, "_conn", conexion)

    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
        servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")

    assert conexion.inserts == 6  # el primer intento y cinco números descartados


def test_t406b_una_fila_ilegible_con_la_clave_actual_deja_rastro_sin_pii(
    sin_clave: None, caplog: pytest.LogCaptureFixture
) -> None:
    escritor = SeguridadService({"pii": {"clave_boveda": "clave-anterior-t406b"}}, observabilidad=DobleObservabilidad())
    texto = escritor.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-rotada")
    lector = SeguridadService(
        {"pii": {"clave_boveda": "clave-actual-t406b"}}, observabilidad=DobleObservabilidad(), conexion=escritor.conexion
    )

    with caplog.at_level(logging.WARNING, logger="features.seguridad.pii_internal"):
        rehidratado = lector.rehidratar(texto, "conv-rotada")

    assert rehidratado == "mi telefono es [DATO_BORRADO]"
    avisos = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == "features.seguridad.pii_internal"]
    assert [r.getMessage() for r in avisos] == ["bóveda: fila ilegible con la clave actual"]
    for dato in (TELEFONO_A, "[TELEFONO_1]", "conv-rotada"):
        assert dato not in caplog.text


# --- 3. tokenizar_estructura -------------------------------------------------------------------


RESERVA = {
    "codigo": "GI-2026-1234567890",
    "huesped": {"nombre": NOMBRE, "contacto": {"telefono": TELEFONO_A, "correo": CORREO}},
    "unidades": [
        {"nombre": "Domo Cotacachi", "notas": f"llamar al {TELEFONO_B}"},
        {"nombre": "Domo Imbabura", "notas": "sin novedad"},
    ],
    "noches": 2,
    "precio": 120.5,
    "pagada": True,
    "cupon": None,
    "etiquetas": ("vip", f"correo {CORREO}"),
}
CAMPOS_PII = ["huesped.nombre"]
EXENTOS = {"codigo": r"GI-\d{4}-\d{10}"}


def _tokenizada(servicio: SeguridadService) -> Any:
    return servicio.tokenizar_estructura(RESERVA, "conv-1", campos_pii=CAMPOS_PII, campos_exentos=EXENTOS)


@pytest.mark.parametrize("ensure_ascii", [False, True])
def test_t406b_estructura_sin_pii_en_claro_en_ningun_volcado_json(servicio: SeguridadService, ensure_ascii: bool) -> None:
    volcado = json.dumps(_tokenizada(servicio), ensure_ascii=ensure_ascii)
    for valor in (NOMBRE, TELEFONO_A, TELEFONO_B, CORREO):
        assert json.dumps(valor, ensure_ascii=ensure_ascii)[1:-1] not in volcado, valor


def test_t406b_estructura_anidada_conserva_su_forma_y_sus_claves(servicio: SeguridadService) -> None:
    salida = _tokenizada(servicio)
    assert isinstance(salida, dict) and set(salida) == set(RESERVA)
    assert set(salida["huesped"]) == {"nombre", "contacto"}
    assert set(salida["huesped"]["contacto"]) == {"telefono", "correo"}
    assert isinstance(salida["unidades"], list) and len(salida["unidades"]) == 2
    assert all(set(u) == {"nombre", "notas"} for u in salida["unidades"])
    assert isinstance(salida["etiquetas"], tuple) and salida["etiquetas"][0] == "vip"
    assert salida["unidades"][1] == {"nombre": "Domo Imbabura", "notas": "sin novedad"}
    assert salida["unidades"][0]["notas"] == "llamar al [TELEFONO_2]"


def test_t406b_campo_pii_declarado_se_tokeniza_entero(servicio: SeguridadService) -> None:
    salida = _tokenizada(servicio)
    assert salida["huesped"]["nombre"] == "[NOMBRE_1]"
    assert servicio.rehidratar(salida["huesped"]["nombre"], "conv-1") == NOMBRE


def test_t406b_campo_exento_que_cumple_su_pattern_queda_intacto(servicio: SeguridadService) -> None:
    assert _tokenizada(servicio)["codigo"] == "GI-2026-1234567890"


def test_t406b_campo_exento_que_no_cumple_su_pattern_pasa_por_el_detector(servicio: SeguridadService) -> None:
    salida = servicio.tokenizar_estructura(
        {"codigo": f"GI-2026-1234567890 o llama al {TELEFONO_A}"}, "conv-1", campos_exentos=EXENTOS
    )
    assert TELEFONO_A not in salida["codigo"]
    assert salida["codigo"] != f"GI-2026-1234567890 o llama al {TELEFONO_A}"
    assert "[TELEFONO_" in salida["codigo"]


def test_t406b_campo_exento_en_lista_usa_la_ruta_con_corchetes(servicio: SeguridadService) -> None:
    salida = servicio.tokenizar_estructura(
        {"reservas": [{"codigo": "GI-2026-1234567890"}, {"codigo": TELEFONO_A}]},
        "conv-1",
        campos_exentos={"reservas[].codigo": r"GI-\d{4}-\d{10}"},
    )
    assert salida == {"reservas": [{"codigo": "GI-2026-1234567890"}, {"codigo": "[TELEFONO_1]"}]}


def test_t406b_escalares_no_textuales_pasan_sin_cambio(servicio: SeguridadService) -> None:
    salida = _tokenizada(servicio)
    assert salida["noches"] == 2 and type(salida["noches"]) is int
    assert salida["precio"] == 120.5
    assert salida["pagada"] is True
    assert salida["cupon"] is None


def test_t406b_las_claves_nunca_se_tokenizan(servicio: SeguridadService) -> None:
    salida = servicio.tokenizar_estructura({TELEFONO_A: "dato", CORREO: {"x": 1}}, "conv-1")
    assert set(salida) == {TELEFONO_A, CORREO}


def test_t406b_tipo_no_admitido_lanza_error_tipado(servicio: SeguridadService) -> None:
    with pytest.raises(seguridad_service.EstructuraNoAdmitida):
        servicio.tokenizar_estructura({"adjunto": {1, 2}}, "conv-1")
    with pytest.raises(seguridad_service.ErrorSeguridad):
        servicio.tokenizar_estructura({"ruta": Path("x")}, "conv-1")


def test_t406b_mismo_valor_en_texto_y_en_estructura_recibe_el_mismo_token(servicio: SeguridadService) -> None:
    texto = servicio.tokenizar(f"mi telefono es {TELEFONO_A}", "conv-1")
    salida = servicio.tokenizar_estructura({"contacto": {"telefono": TELEFONO_A}}, "conv-1")
    assert salida["contacto"]["telefono"] == texto.removeprefix("mi telefono es ")
