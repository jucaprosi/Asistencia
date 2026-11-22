# ¤seguridad-canal
# ¤¤security-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Row-Level Security por propiedad_id y aislamiento de inquilinos (RF-SEC-07, INV_SIN_FUGA_ENTRE_PROPIEDADES).

Define el rol de aplicación NOBYPASSRLS, las migraciones de políticas RLS para todas las
tablas con propiedad_id, y las guardas de contexto de inquilino para prevenir filtraciones.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Generator, Mapping, Sequence

__all__ = [
    "TABLAS_CON_RLS",
    "ROL_APLICACION_RLS",
    "obtener_propiedad_actual",
    "contexto_inquilino",
    "GuardiaContextoInquilino",
    "generar_ddl_migraciones_rls",
]

# Rol canónico de aplicación restringido por RLS
ROL_APLICACION_RLS = "app_glamping"

# Catálogo canónico de todas las tablas con propiedad_id en el sistema
TABLAS_CON_RLS: tuple[str, ...] = (
    "conocimiento.chunks",
    "conocimiento.documentos",
    "pms.propiedades",
    "pms.unidades",
    "pms.reservas_ref",
    "pms.incidencias",
    "agente.conversaciones",
    "arm.ventas",
    "web.enlaces_contacto",
    "anfitriones.solicitudes",
    "anfitriones.hospedajes",
    "comisiones.reglas",
    "seguridad.audit_log",
)

_propiedad_contexto: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "propiedad_contexto", default=None
)


# ¤seguridad-canal
def obtener_propiedad_actual() -> str | None:
    """Devuelve el ID de la propiedad activa en el contexto de ejecución actual."""
    return _propiedad_contexto.get()


# ¤seguridad-canal
@contextmanager
def contexto_inquilino(
    propiedad_id: str | None,
    conexion: Any = None,
) -> Generator[str | None, None, None]:
    """Establece la propiedad activa en el contexto de ejecución (guardas de inquilino).

    Si se proporciona una conexión compatible con PostgreSQL, ejecuta SET LOCAL app.propiedad_id.
    Si se proporciona una conexión SQLite, registra la función current_propiedad_id().
    """
    token = _propiedad_contexto.set(propiedad_id)
    es_pg = False

    if conexion is not None:
        # Detectar si es conexión PostgreSQL
        modulo_conn = getattr(conexion.__class__, "__module__", "")
        if "psycopg" in modulo_conn or "asyncpg" in modulo_conn or "pg" in modulo_conn:
            es_pg = True
            try:
                cursor = conexion.cursor()
                if propiedad_id:
                    cursor.execute("SELECT set_config('app.propiedad_id', %s, true);", (propiedad_id,))
                else:
                    cursor.execute("SELECT set_config('app.propiedad_id', '', true);")
            except Exception:
                pass
        elif hasattr(conexion, "create_function"):
            # Conexión SQLite
            try:
                conexion.create_function("current_propiedad_id", 0, lambda: _propiedad_contexto.get() or "")
            except Exception:
                pass

    try:
        yield propiedad_id
    finally:
        _propiedad_contexto.reset(token)
        if es_pg and conexion is not None:
            try:
                cursor = conexion.cursor()
                cursor.execute("RESET app.propiedad_id;")
            except Exception:
                pass


# ¤seguridad-canal
class GuardiaContextoInquilino:
    """Valida y filtra el acceso a filas según la propiedad activa (RF-SEC-07)."""

    def __init__(self, propiedad_id: str | None = None) -> None:
        self._propiedad_id = propiedad_id

    # ¤seguridad-canal
    @property
    def propiedad_id(self) -> str | None:
        return self._propiedad_id or obtener_propiedad_actual()

    # ¤seguridad-canal
    def verificar_aislamiento_filas(
        self,
        filas: Sequence[Mapping[str, Any]],
        propiedad_esperada: str | None = None,
    ) -> bool:
        """Verifica que ninguna fila pertenezca a otra propiedad diferente a la esperada o 'global'."""
        esperada = propiedad_esperada or self.propiedad_id
        if not esperada:
            return True
        for fila in filas:
            prop_fila = fila.get("propiedad_id")
            if prop_fila is not None and prop_fila != "global" and prop_fila != esperada:
                return False
        return True

    # ¤seguridad-canal
    def filtrar_filas(
        self,
        filas: Sequence[Mapping[str, Any]],
        propiedad_activa: str | None = None,
    ) -> list[Mapping[str, Any]]:
        """Aplica la regla RLS en memoria: solo devuelve filas de la propiedad activa o 'global'."""
        activa = propiedad_activa or self.propiedad_id
        if not activa:
            return list(filas)
        return [
            f for f in filas
            if f.get("propiedad_id") is None or f.get("propiedad_id") in (activa, "global")
        ]


# ¤seguridad-canal
def generar_ddl_migraciones_rls(
    rol_aplicacion: str = ROL_APLICACION_RLS,
    tablas: Sequence[str] = TABLAS_CON_RLS,
) -> str:
    """Genera las sentencias SQL completas de migración de políticas RLS y rol NOBYPASSRLS."""
    bloques: list[str] = [
        "-- ¤seguridad-canal",
        "-- Migración RLS por propiedad_id con rol de aplicación NOBYPASSRLS (RF-SEC-07)",
        "",
        "DO $$ BEGIN",
        f"  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol_aplicacion}') THEN",
        f"    CREATE ROLE {rol_aplicacion} NOLOGIN NOBYPASSRLS;",
        "  ELSE",
        f"    ALTER ROLE {rol_aplicacion} NOBYPASSRLS;",
        "  END IF;",
        "END $$;",
        "",
    ]

    esquemas_unicos = sorted({t.split(".")[0] for t in tablas})
    for esq in esquemas_unicos:
        bloques.append(f"GRANT USAGE ON SCHEMA {esq} TO {rol_aplicacion};")
    bloques.append("")

    for tabla_completa in tablas:
        esquema, nombre_tabla = tabla_completa.split(".")
        politica_nombre = f"rls_{nombre_tabla}_por_propiedad"

        bloques.extend([
            f"-- RLS para {tabla_completa}",
            f"ALTER TABLE {tabla_completa} ENABLE ROW LEVEL SECURITY;",
            f"ALTER TABLE {tabla_completa} FORCE ROW LEVEL SECURITY;",
            f"DROP POLICY IF EXISTS {politica_nombre} ON {tabla_completa};",
            f"CREATE POLICY {politica_nombre} ON {tabla_completa}",
            f"  FOR ALL",
            f"  TO {rol_aplicacion}",
            f"  USING (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true))",
            f"  WITH CHECK (propiedad_id = 'global' OR propiedad_id = current_setting('app.propiedad_id', true));",
            "",
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tabla_completa} TO {rol_aplicacion};",
            "",
        ])

    # Invariante INV_AUDIT_APPEND_ONLY: revocar modificaciones sobre audit_log
    bloques.extend([
        "-- INV_AUDIT_APPEND_ONLY: audit_log es solo inserción",
        f"REVOKE UPDATE, DELETE, TRUNCATE ON seguridad.audit_log FROM {rol_aplicacion};",
        "",
    ])

    return "\n".join(bloques)
