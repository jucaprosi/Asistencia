# ¤seguridad-canal
# ¤¤security-engineer
"""Gestión de aviso de privacidad y consentimientos LOPDP (RF-PRIV-01)."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from features.seguridad.tipos import RegistroConsentimiento

VERSION_AVISO_VIGENTE = "1.0"
TEXTO_AVISO_PRIVACIDAD = (
    "Glamping Imbabura informa: Tratamos tus datos para gestionar tu solicitud y estadía "
    "conforme a la LOPDP de Ecuador. Puedes ejercer tus derechos ARCOP escribiéndonos. "
    "Consulta nuestra política en docs/privacidad/INVENTARIO.md."
)


# ¤seguridad-canal
class ConsentimientoManager:
    """Administra el registro y verificación de consentimientos por titular."""

    def __init__(self, conexion: sqlite3.Connection) -> None:
        self._conn = conexion

    def tiene_consentimiento(self, titular_hash: str, version_aviso: str = VERSION_AVISO_VIGENTE) -> bool:
        """Verifica si el titular cuenta con un consentimiento activo para la versión indicada."""
        cursor = self._conn.execute(
            """
            SELECT consentimiento_id FROM seguridad.consentimientos
            WHERE titular_hash = ? AND version_aviso = ? AND revocado_en IS NULL
            """,
            (titular_hash, version_aviso),
        )
        return cursor.fetchone() is not None

    def registrar_consentimiento(
        self,
        titular_hash: str,
        base: str = "aviso_primer_contacto",
        version_aviso: str = VERSION_AVISO_VIGENTE,
    ) -> RegistroConsentimiento:
        """Registra un nuevo consentimiento para el titular."""
        consentimiento_id = str(uuid.uuid4())
        otorgado_en = datetime.now(timezone.utc)

        self._conn.execute(
            """
            INSERT INTO seguridad.consentimientos (
                consentimiento_id, titular_hash, base, version_aviso, otorgado_en, revocado_en
            ) VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (consentimiento_id, titular_hash, base, version_aviso, otorgado_en.isoformat()),
        )
        self._conn.commit()

        return RegistroConsentimiento(
            consentimiento_id=consentimiento_id,
            titular_hash=titular_hash,
            base=base,
            version_aviso=version_aviso,
            otorgado_en=otorgado_en,
        )

    def revocar_consentimiento(self, titular_hash: str) -> None:
        """Revoca los consentimientos activos del titular."""
        ahora = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            UPDATE seguridad.consentimientos
            SET revocado_en = ?
            WHERE titular_hash = ? AND revocado_en IS NULL
            """,
            (ahora, titular_hash),
        )
        self._conn.commit()

    def obtener_aviso_vigente(self) -> str:
        """Devuelve el texto legal del aviso vigente."""
        return TEXTO_AVISO_PRIVACIDAD


# ¤seguridad-canal
def crear_consentimiento_manager(conexion: sqlite3.Connection) -> ConsentimientoManager:
    """Crea una instancia de ConsentimientoManager."""
    return ConsentimientoManager(conexion)
