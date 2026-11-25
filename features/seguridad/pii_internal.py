# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Redacción y rehidratación de PII con bóveda cifrada AES-256-GCM (RF-SEC-05, INV_PII_FUERA_DEL_MODELO)."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from features.seguridad.tipos import ErrorSeguridad, TokenDesconocido

# T-406-b: sin clave configurada la bóveda cifra con una clave aleatoria de este proceso, nunca con una
# constante del repositorio. Lo cifrado deja de ser legible al reiniciar (conducta deliberada; P-1 la
# rechaza en producción). El nombre se conserva porque secretos_internal lo importa como respaldo.
CLAVE_DEFECTO_BOVEDA = secrets.token_hex(32)

MAX_NUMEROS_DESCARTADOS = 5  # T-406-b (C1): tope de reintentos ante IntegrityError

_LOG = logging.getLogger(__name__)

TIPOS_PII = ("nombre", "telefono", "correo", "documento", "tarjeta", "direccion")

# Patrones para detección determinística de PII
RX_CORREO = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
RX_TARJETA = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b")
RX_TELEFONO = re.compile(
    r"(?:\+593[-.\s]?9\d{8}|\+593[-.\s]?\d{8,9}|09\d{8}|\b\+?[1-9]\d{1,2}[-.\s]?(?:\(?\d{1,4}\)?[-.\s]?)\d{3,4}[-.\s]?\d{3,4}\b)"
)
# Cédulas y documentos: si no son teléfonos (no empiezan por 09 ni +)
RX_DOCUMENTO_EXPLICITO = re.compile(
    r"(?:c[eé]dula|c\.?i\.?|dni|documento|pasaporte)\s*[:#]?\s*([A-Za-z0-9]{8,12})\b",
    re.IGNORECASE,
)
RX_CEDULA_10 = re.compile(r"\b([0-1][0-8][0-9]{8})\b")

RX_DIRECCION = re.compile(
    r"\b(?:Av\.|Avenida|Calle|Pasaje|Sector|Barrio|Km|V[ií]a|Carretera)\s+[A-Za-z0-9ÁÉÍÓÚÑáéíóúñ\s.,#-]+?(?=(?:,\s*y\b|\.|$|\n))",
    re.IGNORECASE,
)
RX_NOMBRE = re.compile(
    r"(?:mi\s+nombre\s+es|me\s+llamo|soy|a\s+nombre\s+de|hospedar?\s+a)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)",
    re.IGNORECASE,
)

RX_TOKEN_REHIDRATAR = re.compile(r"\[([A-Z_]+_\d+)\]")


# ¤seguridad-canal
def derivar_clave(clave_secreta: str) -> bytes:
    """Deriva una clave de 256 bits mediante SHA-256."""
    return hashlib.sha256(clave_secreta.encode("utf-8")).digest()


# ¤seguridad-canal
def cifrar_valor(valor: str, clave_32: bytes) -> bytes:
    """Cifra un texto plano usando AES-GCM con nonce aleatorio de 12 bytes."""
    aesgcm = AESGCM(clave_32)
    nonce = os.urandom(12)
    datos_cifrados = aesgcm.encrypt(nonce, valor.encode("utf-8"), None)
    return nonce + datos_cifrados


# ¤seguridad-canal
def descifrar_valor(datos_cifrados: bytes, clave_32: bytes) -> str:
    """Descifra un blob cifrado con AES-GCM."""
    if len(datos_cifrados) < 12:
        raise TokenDesconocido("Blob cifrado inválido en bóveda")
    nonce = datos_cifrados[:12]
    texto_cifrado = datos_cifrados[12:]
    aesgcm = AESGCM(clave_32)
    datos_claros = aesgcm.decrypt(nonce, texto_cifrado, None)
    return datos_claros.decode("utf-8")


# ¤seguridad-canal
class EstructuraNoAdmitida(ErrorSeguridad, TypeError):
    """``tokenizar_estructura`` recibió un valor que no es dict, list, tuple, texto ni escalar JSON."""

    def __init__(self, mensaje: str = "Tipo no admitido en la estructura a tokenizar") -> None:
        super().__init__("EstructuraNoAdmitida", mensaje)


# ¤seguridad-canal
class PIIRedactor:
    """Maneja la tokenización previa a llamadas al LLM y la rehidratación posterior."""

    def __init__(
        self, conexion: sqlite3.Connection, config: Mapping[str, Any] | None = None
    ) -> None:
        self._conn = conexion
        self._config = config or {}
        clave_configurada = self._config.get("clave_boveda") or os.environ.get("PII_VAULT_KEY")
        self.clave_efimera = not clave_configurada
        self._clave = derivar_clave(clave_configurada or CLAVE_DEFECTO_BOVEDA)
        self._tokens_por_conv: dict[str, dict[str, str]] = {}
        self._valores_por_conv: dict[str, dict[str, str]] = {}

    def _guardar_en_boveda(self, token_db: str, titular_hash: str, tipo: str, valor: str) -> None:
        """Inserta la fila; lanza ``sqlite3.IntegrityError`` si ``token_db`` ya existe (colisión) u otra restricción falla."""
        cifrado = cifrar_valor(valor, self._clave)
        ahora = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO seguridad.boveda_tokens (token, titular_hash, tipo, valor_cifrado, creado_en, ultimo_uso_en)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (token_db, titular_hash, tipo, cifrado, ahora, ahora),
        )
        self._conn.commit()

    def _obtener_de_boveda(self, token_db: str) -> str | None:
        cursor = self._conn.execute(
            "SELECT valor_cifrado FROM seguridad.boveda_tokens WHERE token = ?",
            (token_db,),
        )
        fila = cursor.fetchone()
        if fila:
            ahora = datetime.now(timezone.utc).isoformat()
            self._conn.execute(
                "UPDATE seguridad.boveda_tokens SET ultimo_uso_en = ? WHERE token = ?",
                (ahora, token_db),
            )
            self._conn.commit()
            try:
                return descifrar_valor(bytes(fila["valor_cifrado"]), self._clave)
            except InvalidTag:
                _LOG.warning("bóveda: fila ilegible con la clave actual")  # T-406-b (C2): sin token, valor ni conversación
                return None  # T-406-b: cifrado con otra clave (p. ej. la efímera de un arranque anterior)
        return None

    def tokenizar(
        self,
        texto: str,
        conversacion_id: str,
        titular_hash: str | None = None,
    ) -> str:
        """Tokeniza todos los datos personales encontrados en el texto."""
        titular = titular_hash or hashlib.sha256(conversacion_id.encode("utf-8")).hexdigest()

        candidatos_dict: dict[str, str] = {}

        # 1. Correos
        for m in RX_CORREO.finditer(texto):
            candidatos_dict[m.group(0)] = "correo"

        # 2. Tarjetas
        for m in RX_TARJETA.finditer(texto):
            candidatos_dict[m.group(0)] = "tarjeta"

        # 3. Teléfonos (tienen precedencia sobre cédulas con 09...)
        for m in RX_TELEFONO.finditer(texto):
            candidatos_dict[m.group(0)] = "telefono"

        # 4. Documentos explícitos
        for m in RX_DOCUMENTO_EXPLICITO.finditer(texto):
            candidatos_dict[m.group(1)] = "documento"

        # 5. Cédulas 10 dígitos (si no están ya clasificadas como teléfono)
        for m in RX_CEDULA_10.finditer(texto):
            val = m.group(1)
            if val not in candidatos_dict and not val.startswith("09"):
                candidatos_dict[val] = "documento"

        # 6. Direcciones
        for m in RX_DIRECCION.finditer(texto):
            candidatos_dict[m.group(0).strip()] = "direccion"

        # 7. Nombres
        for m in RX_NOMBRE.finditer(texto):
            nom = m.group(1).strip()
            if nom and nom not in candidatos_dict:
                candidatos_dict[nom] = "nombre"

        # Ordenar por longitud descendente
        candidatos_ordenados = sorted(candidatos_dict.items(), key=lambda x: len(x[0]), reverse=True)

        texto_resultado = texto

        for valor, tipo in candidatos_ordenados:
            if not valor or valor not in texto_resultado:
                continue

            token = self._token_para(valor, tipo, conversacion_id, titular)
            texto_resultado = texto_resultado.replace(valor, token)

        return texto_resultado

    def _token_para(self, valor: str, tipo: str, conversacion_id: str, titular: str) -> str:
        """Token del valor en la conversación; si es nuevo, lo numera y lo guarda en la bóveda."""
        tokens_conv = self._tokens_por_conv.setdefault(conversacion_id, {})
        valores_conv = self._valores_por_conv.setdefault(conversacion_id, {})
        if valor in valores_conv:
            return valores_conv[valor]
        # T-406: el número es único dentro de la conversación, también entre llamadas y reinicios;
        # la bóveda solo guarda la clave (conversación, token), nunca un token global.
        # T-406-b: si el INSERT colisiona, el número ya es de otro valor y se prueba el siguiente; tras
        # MAX_NUMEROS_DESCARTADOS el error no es una carrera (NOT NULL, CHECK, FK) y se relanza el original.
        descartados: set[str] = set()
        while True:
            token = self._siguiente_token(conversacion_id, tipo, tokens_conv, descartados)
            try:
                self._guardar_en_boveda(f"{conversacion_id}:{token}", titular, tipo, valor)
                break
            except sqlite3.IntegrityError:
                if len(descartados) >= MAX_NUMEROS_DESCARTADOS:
                    raise
                descartados.add(token)
        valores_conv[valor] = token
        tokens_conv[token] = valor
        return token

    def _siguiente_token(
        self,
        conversacion_id: str,
        tipo: str,
        tokens_conv: Mapping[str, str],
        descartados: Iterable[str] = (),
    ) -> str:
        """Primer ``[TIPO_n]`` libre en la conversación, mirando la caché, los descartados y la bóveda."""
        excluidos = set(descartados)
        numero = 1
        while True:
            token = f"[{tipo.upper()}_{numero}]"
            if (
                token not in tokens_conv
                and token not in excluidos
                and not self._existe_en_boveda(f"{conversacion_id}:{token}")
            ):
                return token
            numero += 1

    def tokenizar_estructura(
        self,
        valor: Any,
        conversacion_id: str,
        titular_hash: str | None = None,
        campos_pii: Iterable[str] | None = None,
        campos_exentos: Mapping[str, str] | None = None,
    ) -> Any:
        """Tokeniza recursivamente dict, list y tuple; las claves nunca se tokenizan.

        Rutas: ``.`` anida campos (``contacto.telefono``) y ``[]`` marca los elementos de una lista o tupla
        (``unidades[].nombre``; los elementos de una raíz lista son ``[]``). Un campo de ``campos_pii`` se
        tokeniza entero; uno de ``campos_exentos`` queda intacto solo si es texto y cumple ``re.fullmatch`` de
        su pattern; el resto del texto pasa por ``tokenizar``. int, float, bool y None pasan sin cambio.
        """
        titular = titular_hash or hashlib.sha256(conversacion_id.encode("utf-8")).hexdigest()
        pii = frozenset(campos_pii or ())
        exentos = {ruta: re.compile(patron) for ruta, patron in (campos_exentos or {}).items()}

        def _recorrer(nodo: Any, ruta: str) -> Any:
            if isinstance(nodo, Mapping):
                return {clave: _recorrer(v, f"{ruta}.{clave}" if ruta else str(clave)) for clave, v in nodo.items()}
            if isinstance(nodo, (list, tuple)):
                elementos = [_recorrer(v, f"{ruta}[]") for v in nodo]
                return elementos if isinstance(nodo, list) else tuple(elementos)
            if nodo is None or isinstance(nodo, (bool, int, float)):
                return nodo
            if not isinstance(nodo, str):
                raise EstructuraNoAdmitida(f"tipo no admitido en {ruta or 'la raíz'}: {type(nodo).__name__}")
            if ruta in pii:
                return self._token_para(nodo, _tipo_de_campo(ruta, nodo), conversacion_id, titular) if nodo else nodo
            patron = exentos.get(ruta)
            if patron is not None and patron.fullmatch(nodo):
                return nodo
            return self.tokenizar(nodo, conversacion_id, titular_hash=titular)

        return _recorrer(valor, "")

    def _existe_en_boveda(self, token_db: str) -> bool:
        cursor = self._conn.execute("SELECT 1 FROM seguridad.boveda_tokens WHERE token = ?", (token_db,))
        return cursor.fetchone() is not None

    def limpiar_cache_titular(self, titular_hash: str | None = None) -> None:
        """Limpia los cachés en memoria para garantizar que el criptoborrado sea efectivo inmediatamente."""
        self._tokens_por_conv.clear()
        self._valores_por_conv.clear()

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        """Restaura los valores originales de los tokens presentes en el texto.
        
        Si el token fue objeto de criptoborrado en la bóveda, devuelve un marcador neutro ([DATO_BORRADO]).
        """
        tokens_conv = self._tokens_por_conv.get(conversacion_id, {})

        def _reemplazar(coincidencia: re.Match[str]) -> str:
            token = f"[{coincidencia.group(1)}]"
            if token in tokens_conv:
                return tokens_conv[token]

            valor = self._obtener_de_boveda(f"{conversacion_id}:{token}")
            if valor is not None:
                return valor

            # T-406: nunca se busca el token sin conversación; uno ajeno no rehidrata datos de otra persona.
            # Marcador neutro ante token borrado, ajeno o no disponible (RF-PRIV-04 b)
            return "[DATO_BORRADO]"

        return RX_TOKEN_REHIDRATAR.sub(_reemplazar, texto)

    def filtrar_salida(self, texto: str, conversacion_id: str) -> str:
        """Rehidrata PII y purifica el mensaje antes de enviarlo a WhatsApp."""
        rehidratado = self.rehidratar(texto, conversacion_id)

        # Rehidratar marcadores de secretos operativos desde la bóveda (RF-SEC-08)
        def _reemplazar_secreto(match: re.Match[str]) -> str:
            token_id = match.group(1)
            for clave in (f"[[SECRETO:{token_id}]]", token_id):
                valor = self._obtener_de_boveda(clave)
                if valor is not None:
                    return valor
            return match.group(0)

        rehidratado = re.sub(r"\[\[SECRETO:([a-zA-Z0-9_\-\:]+)\]\]", _reemplazar_secreto, rehidratado)
        purificado = re.sub(r"[¤¦¬]", "", rehidratado)
        return purificado


# ¤seguridad-canal
def _tipo_de_campo(ruta: str, valor: str) -> str:
    """Tipo de un campo PII declarado: el último segmento de la ruta si nombra un tipo; si no, el detector; si no, nombre."""
    segmento = ruta.rsplit(".", 1)[-1].removesuffix("[]")
    if segmento in TIPOS_PII:
        return segmento
    for tipo, patron in (("correo", RX_CORREO), ("tarjeta", RX_TARJETA), ("telefono", RX_TELEFONO), ("documento", RX_CEDULA_10)):
        if patron.fullmatch(valor):
            return tipo
    return "nombre"


# ¤seguridad-canal
def crear_pii_redactor(
    conexion: sqlite3.Connection, config: Mapping[str, Any] | None = None
) -> PIIRedactor:
    """Crea una instancia de PIIRedactor."""
    return PIIRedactor(conexion, config)
