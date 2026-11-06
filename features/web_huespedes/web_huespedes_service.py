# ¤web-huespedes
# ¤¤frontend-developer
"""Compuerta pública de la sala web_huespedes (RF-WEB-01..06). Solo lectura: la reserva termina en WhatsApp."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import string
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.web_huespedes.repositorio import RepositorioWeb
from features.web_huespedes.tipos import Busqueda, EnlaceContacto, FichaPropiedad, OpcionDisponible

__all__ = [
    "Busqueda",
    "EnlaceContacto",
    "FichaPropiedad",
    "OpcionDisponible",
    "ErrorWebHuespedes",
    "WebHuespedesService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_web_huespedes.yaml")
ALFABETO_CODIGO = string.ascii_uppercase + string.digits


# ¤web-huespedes
class ErrorWebHuespedes(Exception):
    """Error tipado: el visitante ve solo mensaje_usuario."""

    def __init__(self, codigo: str, mensaje_usuario: str, detalle_tecnico: str | None = None) -> None:
        super().__init__(detalle_tecnico or mensaje_usuario)
        self.codigo = codigo
        self.mensaje_usuario = mensaje_usuario
        self.detalle_tecnico = detalle_tecnico


# ¤web-huespedes
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


# ¤web-huespedes
def _resolver_valor_config(valor: Any, defecto: str = "") -> str:
    if not isinstance(valor, str):
        return str(valor) if valor is not None else defecto
    patron = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")
    match = patron.fullmatch(valor)
    if match:
        var, def_val = match.group(1), match.group(2)
        return os.environ.get(var, def_val if def_val is not None else defecto)
    return valor


# ¤web-huespedes
class WebHuespedesService:
    """Catálogo, búsqueda, comparación y paso a WhatsApp."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        pms: Any = None,
        observabilidad: Any = None,
        anfitriones: Any = None,
        repositorio: RepositorioWeb | None = None,
    ) -> None:
        self._config = config
        self._pms = pms
        self._observabilidad = observabilidad
        self._anfitriones = anfitriones
        self._repositorio = repositorio or RepositorioWeb()

        # Configuración de límites y seguridad
        limites_cfg = config.get("limites", {})
        self._limite_ip_minuto = int(limites_cfg.get("por_ip_minuto", 30))
        secreto_cfg = limites_cfg.get("ip_hmac_secreto", "")
        self._secreto_hmac = _resolver_valor_config(secreto_cfg, "glamping_default_ip_salt_2026")
        if not self._secreto_hmac:
            self._secreto_hmac = "glamping_default_ip_salt_2026"

        self._validez_h = int(config.get("enlace_contacto_validez_h", 72))
        raw_whatsapp = config.get("whatsapp_numero", "")
        self._whatsapp_numero = _resolver_valor_config(raw_whatsapp, "593999999999")
        if not self._whatsapp_numero:
            self._whatsapp_numero = "593999999999"

        # Cargar catálogo de propiedades
        self._fichas: dict[str, FichaPropiedad] = {}
        self._cargar_catalogo()

    def _cargar_catalogo(self) -> None:
        origen_catalogo = self._config.get("catalogo", "features/web_huespedes/catalogo_ejemplo.yaml")
        datos: dict[str, Any] = {}

        if isinstance(origen_catalogo, dict):
            datos = origen_catalogo
        elif isinstance(origen_catalogo, str):
            ruta_str = _resolver_valor_config(origen_catalogo, "features/web_huespedes/catalogo_ejemplo.yaml")
            ruta = Path(ruta_str)
            if not ruta.is_absolute():
                raiz = Path(__file__).resolve().parent.parent.parent
                if (raiz / ruta).is_file():
                    ruta = raiz / ruta
                elif (Path(__file__).resolve().parent / ruta.name).is_file():
                    ruta = Path(__file__).resolve().parent / ruta.name

            if ruta.is_file():
                datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}

        props = datos.get("propiedades", [])
        for item in props:
            ficha = FichaPropiedad(
                propiedad_id=str(item["propiedad_id"]),
                tipo=str(item.get("tipo", "glamping")),
                nombre=str(item["nombre"]),
                zona=str(item.get("zona", "")),
                capacidad=int(item.get("capacidad", 1)),
                resumen=str(item.get("resumen", "")),
                comodidades=tuple(str(c) for c in item.get("comodidades", ())),
                fotos=tuple(str(f) for f in item.get("fotos", ())),
            )
            self._fichas[ficha.propiedad_id] = ficha

    def _obtener_publicados_map(self) -> dict[str, Any] | None:
        """Consulta anfitriones.publicados() (INV_SOLO_PUBLICADO). Si no hay anfitriones inyectado, retorna None."""
        if self._anfitriones is None:
            return None
        publicados_lista = self._anfitriones.publicados()
        mapa: dict[str, Any] = {}
        for h in publicados_lista:
            estado = getattr(h, "estado", None)
            if estado is not None:
                estado_str = str(getattr(estado, "value", estado)).lower()
                if estado_str != "publicado":
                    continue
            pid = getattr(h, "propiedad_id", None)
            if pid:
                mapa[str(pid)] = h
        return mapa

    def _enriquecer_ficha(self, ficha: FichaPropiedad, hospedaje: Any) -> FichaPropiedad:
        from dataclasses import replace

        anfitrion_id = getattr(hospedaje, "anfitrion_id", None)
        ofrecido_por = getattr(hospedaje, "ofrecido_por", None) or getattr(hospedaje, "anfitrion_nombre", None)
        if not ofrecido_por and hasattr(self._anfitriones, "obtener_anfitrion") and anfitrion_id:
            try:
                anf = self._anfitriones.obtener_anfitrion(anfitrion_id)
                if anf:
                    ofrecido_por = getattr(anf, "nombre_comercial", None) or getattr(anf, "nombre", None)
            except Exception:
                pass
        if not ofrecido_por and anfitrion_id:
            ofrecido_por = anfitrion_id

        return replace(
            ficha,
            anfitrion_id=anfitrion_id,
            ofrecido_por=ofrecido_por,
        )

    def catalogo(self) -> tuple[FichaPropiedad, ...]:
        """Inicio y ficha por propiedad sin precios ni cupos (RF-WEB-01, RF-ANF-03).
        Filtra solo hospedajes publicados de anfitriones activos (INV_SOLO_PUBLICADO)."""
        pub_map = self._obtener_publicados_map()
        if pub_map is None:
            return tuple(self._fichas.values())

        resultado: list[FichaPropiedad] = []
        for pid, h in pub_map.items():
            if pid in self._fichas:
                ficha = self._enriquecer_ficha(self._fichas[pid], h)
                resultado.append(ficha)
        return tuple(resultado)

    def ficha(self, propiedad_id: str) -> FichaPropiedad:
        """Devuelve la ficha detallada de una propiedad publicada."""
        if propiedad_id not in self._fichas:
            raise ErrorWebHuespedes(
                "PROPIEDAD_NO_ENCONTRADA",
                f"La propiedad solicitada no existe en el catálogo.",
                f"Propiedad '{propiedad_id}' no encontrada en el catálogo",
            )
        pub_map = self._obtener_publicados_map()
        if pub_map is not None:
            if propiedad_id not in pub_map:
                raise ErrorWebHuespedes(
                    "PROPIEDAD_NO_PUBLICADA",
                    "La propiedad solicitada no se encuentra disponible.",
                    f"Propiedad '{propiedad_id}' no está publicada o su anfitrión está suspendido",
                )
            return self._enriquecer_ficha(self._fichas[propiedad_id], pub_map[propiedad_id])
        return self._fichas[propiedad_id]

    def filtrar_catalogo(self, busqueda: Busqueda) -> tuple[FichaPropiedad, ...]:
        """Filtra el catálogo publicado por capacidad, tipo y zona sin consultar el PMS."""
        candidatas: list[FichaPropiedad] = []
        for ficha in self.catalogo():
            if busqueda.tipo and ficha.tipo.strip().lower() != busqueda.tipo.strip().lower():
                continue
            if busqueda.zona and busqueda.zona.strip().lower() not in ficha.zona.strip().lower():
                continue
            if ficha.capacidad < busqueda.huespedes:
                continue
            candidatas.append(ficha)
        return tuple(candidatas)

    def buscar(self, busqueda: Busqueda) -> tuple[OpcionDisponible, ...]:
        """Consulta tarifas y disponibilidad en vivo contra el PMS (RF-WEB-02, INV_WEB_PRECIO_EN_VIVO)."""
        if busqueda.hasta <= busqueda.desde:
            raise ErrorWebHuespedes(
                "FECHAS_INVALIDAS",
                "La fecha de salida debe ser posterior a la fecha de llegada.",
            )
        if busqueda.huespedes < 1:
            raise ErrorWebHuespedes(
                "HUESPEDES_INVALIDO",
                "El número de huéspedes debe ser al menos 1.",
            )
        if self._pms is None:
            raise ErrorWebHuespedes(
                "PMS_NO_DISPONIBLE",
                "El servicio de reservas no está disponible en este momento.",
            )

        candidatas = self.filtrar_catalogo(busqueda)
        opciones: list[OpcionDisponible] = []

        for ficha in candidatas:
            try:
                disp = self._pms.consultar_disponibilidad(
                    ficha.propiedad_id,
                    busqueda.desde,
                    busqueda.hasta,
                    busqueda.huespedes,
                )
            except Exception as exc:
                if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                    self._observabilidad.log(
                        "ERROR",
                        "web_pms_error_disponibilidad",
                        propiedad_id=ficha.propiedad_id,
                        error=str(exc),
                    )
                raise ErrorWebHuespedes(
                    "PMS_ERROR",
                    "No fue posible consultar la disponibilidad en vivo.",
                    str(exc),
                ) from exc

            if not getattr(disp, "disponible", False):
                continue

            unidades = getattr(disp, "unidades", ())
            if not unidades:
                continue

            unidad = unidades[0]
            try:
                cot = self._pms.cotizar(
                    ficha.propiedad_id,
                    unidad.unidad_id,
                    busqueda.desde,
                    busqueda.hasta,
                    busqueda.huespedes,
                )
            except Exception as exc:
                if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                    self._observabilidad.log(
                        "ERROR",
                        "web_pms_error_cotizacion",
                        propiedad_id=ficha.propiedad_id,
                        error=str(exc),
                    )
                raise ErrorWebHuespedes(
                    "PMS_ERROR",
                    "No fue posible cotizar la estadía en vivo.",
                    str(exc),
                ) from exc

            opciones.append(
                OpcionDisponible(
                    ficha=ficha,
                    unidad_id=str(unidad.unidad_id),
                    total=cot.total,
                    moneda=getattr(cot, "moneda", "USD"),
                )
            )

        return tuple(opciones)

    def comparar(self, propiedades: tuple[str, ...], busqueda: Busqueda) -> tuple[OpcionDisponible, ...]:
        """Compara hasta 3 hospedajes publicados lado a lado con precios en vivo (RF-WEB-03)."""
        max_comparar = int(self._config.get("comparar_max", 3))
        if len(propiedades) > max_comparar:
            raise ErrorWebHuespedes(
                "LIMITE_COMPARACION_EXCEDIDO",
                f"No es posible comparar más de {max_comparar} propiedades simultáneamente.",
            )
        if not propiedades:
            raise ErrorWebHuespedes(
                "COMPARACION_VACIA",
                "Debe seleccionar al menos una propiedad para comparar.",
            )
        if busqueda.hasta <= busqueda.desde:
            raise ErrorWebHuespedes(
                "FECHAS_INVALIDAS",
                "La fecha de salida debe ser posterior a la fecha de llegada.",
            )
        if busqueda.huespedes < 1:
            raise ErrorWebHuespedes(
                "HUESPEDES_INVALIDO",
                "El número de huéspedes debe ser al menos 1.",
            )
        if self._pms is None:
            raise ErrorWebHuespedes(
                "PMS_NO_DISPONIBLE",
                "El servicio de reservas no está disponible en este momento.",
            )

        # Solo hospedajes publicados en el catálogo
        catalogo_actual = {f.propiedad_id: f for f in self.catalogo()}
        fichas_validas = [catalogo_actual[pid] for pid in propiedades if pid in catalogo_actual]

        opciones: list[OpcionDisponible] = []
        for ficha in fichas_validas:
            if ficha.capacidad < busqueda.huespedes:
                continue

            try:
                disp = self._pms.consultar_disponibilidad(
                    ficha.propiedad_id,
                    busqueda.desde,
                    busqueda.hasta,
                    busqueda.huespedes,
                )
            except Exception as exc:
                if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                    self._observabilidad.log(
                        "ERROR",
                        "web_pms_error_disponibilidad",
                        propiedad_id=ficha.propiedad_id,
                        error=str(exc),
                    )
                raise ErrorWebHuespedes(
                    "PMS_ERROR",
                    "No fue posible consultar la disponibilidad para la comparación.",
                    str(exc),
                ) from exc

            if not getattr(disp, "disponible", False):
                continue

            unidades = getattr(disp, "unidades", ())
            if not unidades:
                continue

            unidad = unidades[0]
            try:
                cot = self._pms.cotizar(
                    ficha.propiedad_id,
                    unidad.unidad_id,
                    busqueda.desde,
                    busqueda.hasta,
                    busqueda.huespedes,
                )
            except Exception as exc:
                if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
                    self._observabilidad.log(
                        "ERROR",
                        "web_pms_error_cotizacion",
                        propiedad_id=ficha.propiedad_id,
                        error=str(exc),
                    )
                raise ErrorWebHuespedes(
                    "PMS_ERROR",
                    "No fue posible cotizar la propiedad para la comparación.",
                    str(exc),
                ) from exc

            opciones.append(
                OpcionDisponible(
                    ficha=ficha,
                    unidad_id=str(unidad.unidad_id),
                    total=cot.total,
                    moneda=getattr(cot, "moneda", "USD"),
                )
            )

        return tuple(opciones)

    def crear_enlace_contacto(self, propiedad_id: str, busqueda: Busqueda | None = None) -> str:
        """Genera un código W-XXXXXXXX, lo guarda con contexto y devuelve el enlace a WhatsApp (RF-WEB-04)."""
        propiedad = self.ficha(propiedad_id)

        # Generar código con secrets que cumpla ^W-[A-Z0-9]{8}$
        codigo_aleatorio = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(8))
        codigo = f"W-{codigo_aleatorio}"

        ahora = datetime.now(timezone.utc)
        expira_en = ahora + timedelta(hours=self._validez_h)

        desde = busqueda.desde if busqueda else None
        hasta = busqueda.hasta if busqueda else None
        huespedes = busqueda.huespedes if busqueda else None

        enlace = EnlaceContacto(
            codigo=codigo,
            propiedad_id=propiedad.propiedad_id,
            desde=desde,
            hasta=hasta,
            huespedes=huespedes,
        )

        self._repositorio.guardar_enlace(enlace, creado_en=ahora, expira_en=expira_en)

        if self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "INFO",
                "web_contacto_creado",
                codigo=codigo,
                propiedad_id=propiedad.propiedad_id,
            )

        # Construir enlace de WhatsApp sin PII
        numero_limpio = re.sub(r"\D", "", self._whatsapp_numero)
        mensaje = f"Hola, me interesa reservar {propiedad.nombre}. Mi código de consulta es {codigo}."
        texto_codificado = urllib.parse.quote(mensaje)
        return f"https://wa.me/{numero_limpio}?text={texto_codificado}"

    def resolver_contacto(self, codigo: str) -> EnlaceContacto | None:
        """Recupera el contexto de contacto a partir del código W-XXXXXXXX."""
        return self._repositorio.obtener_enlace(codigo)

    def verificar_limite_ip(self, ip: str) -> tuple[bool, int, str]:
        """Calcula el HMAC de la IP y valida la cuota por minuto (RF-WEB-05, INV_WEB_LIMITE_POR_IP)."""
        ip_hash = hmac.new(
            self._secreto_hmac.encode("utf-8"),
            ip.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        ahora = datetime.now(timezone.utc)
        ventana_iso = ahora.replace(second=0, microsecond=0).isoformat()
        conteo = self._repositorio.registrar_solicitud_ip(ip_hash, ventana_iso)
        permitido = conteo <= self._limite_ip_minuto

        if not permitido and self._observabilidad is not None and hasattr(self._observabilidad, "log"):
            self._observabilidad.log(
                "WARNING",
                "web_limite_ip_excedido",
                ip_hash=ip_hash,
                conteo=conteo,
            )

        return permitido, conteo, ip_hash

    def crear_app(self) -> Any:
        from features.web_huespedes.rutas import crear_app_web

        return crear_app_web(self)
