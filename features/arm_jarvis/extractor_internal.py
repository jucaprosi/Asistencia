# ¤arm-jarvis
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Extractor estructurado de ventas en lenguaje natural (RF-ARM-02)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from features.arm_jarvis.tipos import VentaExtraida

__all__ = ["ExtractorVentas", "normalizar_monto", "extraer_fecha_llegada"]

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

PATRONES_PRODUCTO = [
    (r"\bdomo\s+lago\b", "Domo Lago", "glamping"),
    (r"\bdomo\s+monta[ñn]a\b", "Domo Montaña", "glamping"),
    (r"\btienda\s+safari\b", "Tienda Safari", "glamping"),
    (r"\bsuite\s+colonial\s*101\b", "Suite Colonial 101", "departamento_centro"),
    (r"\bsuite\s+balc[oó]n\s*202\b", "Suite Balcón 202", "departamento_centro"),
    (r"\bdepa(?:\s+del)?\s+centro\b", "depa del centro", "departamento_centro"),
    (r"\bsuites?\s+centro(?:\s+hist[oó]rico)?\b", "Suites Centro Histórico", "departamento_centro"),
    (r"\bglamping(?:\s+san\s+pablo)?\b", "Glamping San Pablo", "glamping"),
    (r"\bdomo\b", "Domo Lago", "glamping"),
    (r"\bcaba[ñn]a\b", "Domo Lago", "glamping"),
    (r"\bsuite\b", "Suite Colonial 101", "departamento_centro"),
]

PATRONES_NO_VENTA = [
    r"^(?:hola|buen(?:as|os)|saludos|qu[eé]\s+tal|buenas\s+(?:tardes|noches|d[ií]as))\b",
    r"^(?:cu[aá]nto\s+llevo|mi\s+comisi[oó]n|mis\s+comisiones|cu[aá]nto\s+he\s+ganado|resumen)\b",
    r"^(?:cu[aá]l\s+es|d[oó]nde|tienen|a\s+qu[eé]\s+hora|qui[eé]n)\b",
    r"^(?:gracias|ok|listo|entendido|de\s+acuerdo)\b",
]


# ¤arm-jarvis
def normalizar_monto(texto_monto: str) -> Decimal | None:
    """Convierte cadenas con diversos formatos de moneda a Decimal('0.00')."""
    limpio = re.sub(r"[^\d,\.]", "", texto_monto)
    if not limpio:
        return None

    # Caso 1.200 o 1,200 sin decimales
    if re.match(r"^\d{1,3}[\.,]\d{3}$", limpio):
        limpio = limpio.replace(".", "").replace(",", "")
        return Decimal(limpio).quantize(Decimal("0.01"))

    # Caso decimal con coma: 450,50 o 1.200,50
    if "," in limpio and "." in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif "," in limpio:
        limpio = limpio.replace(",", ".")

    try:
        val = Decimal(limpio)
        if val <= 0:
            return None
        return val.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


# ¤arm-jarvis
def extraer_fecha_llegada(texto: str, fecha_referencia: date) -> date | None:
    """Calcula la fecha de llegada a partir de expresiones relativas o exactas."""
    # Formato ISO AAAA-MM-DD
    m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", texto)
    if m_iso:
        try:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except ValueError:
            pass

    # Formato DD/MM o DD-MM
    m_ddmm = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", texto)
    if m_ddmm:
        dia, mes = int(m_ddmm.group(1)), int(m_ddmm.group(2))
        anio = int(m_ddmm.group(3)) if m_ddmm.group(3) else fecha_referencia.year
        if anio < 100:
            anio += 2000
        try:
            return date(anio, mes, dia)
        except ValueError:
            pass

    # Expresiones como 'mañana'
    if re.search(r"\bma[ñn]ana\b", texto, re.IGNORECASE):
        return fecha_referencia + timedelta(days=1)

    # Expresiones como 'el 15 de diciembre' o 'el 15 de dic'
    m_mes = re.search(
        r"\b(?:llega|llegada|para|desde)?\s*(?:el)?\s*(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{4}))?\b",
        texto,
        re.IGNORECASE,
    )
    if m_mes:
        dia = int(m_mes.group(1))
        nombre_mes = m_mes.group(2).lower()
        anio = int(m_mes.group(3)) if m_mes.group(3) else fecha_referencia.year
        if nombre_mes in MESES_ES:
            try:
                return date(anio, MESES_ES[nombre_mes], dia)
            except ValueError:
                pass

    # Expresiones como 'llega el 15', 'para el 15', 'el 15'
    m_dia = re.search(
        r"\b(?:llega|llegada|para|desde)\s*(?:el)?\s*(\d{1,2})\b",
        texto,
        re.IGNORECASE,
    )
    if m_dia:
        dia = int(m_dia.group(1))
        # Si el día ya pasó este mes, se asume el próximo mes
        mes = fecha_referencia.month
        anio = fecha_referencia.year
        if dia < fecha_referencia.day:
            mes += 1
            if mes > 12:
                mes = 1
                anio += 1
        try:
            return date(anio, mes, dia)
        except ValueError:
            pass

    return None


# ¤arm-jarvis
class ExtractorVentas:
    """Extrae datos estructurados de ventas a partir de mensajes de vendedores."""

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._config = config or {}

    # ¤arm-jarvis
    def es_mensaje_venta(self, texto: str) -> bool:
        t = texto.strip().lower()
        if not t:
            return False

        # Si es una pregunta de disponibilidad o información general
        if "disponib" in t or "alguien sabe" in t or "tienen" in t or "menú" in t or "reunión" in t:
            if not re.search(r"\b(?:vend[ií]|cerr[eé]|venta\s+de|anotar\s+reserva)\b", t):
                return False

        for p in PATRONES_NO_VENTA:
            if re.search(p, t):
                # Verificar si a pesar del saludo contiene palabras clave de venta explícita
                if not re.search(r"\b(?:vend[ií]|cerr[eé]|venta\s+de|anotar\s+reserva|cobrado)\b", t):
                    return False

        # Si tiene indicadores de venta
        if re.search(r"\b(?:vend[ií]|cerr[eé]|venta|anotar|cliente|noches?|domo|suite|depa|safari|\$\d+|\d+\s*usd)\b", t):
            return True
        return False

    # ¤arm-jarvis
    def dividir_en_ventas_multiples(self, texto: str) -> list[str]:
        """Detecta si un mensaje contiene varias ventas y las divide por segmentos."""
        # 1. Separación por viñetas o numeraciones: 1) ... 2) ... o 1. ... 2. ...
        partes_num = re.split(r"(?:^|\n|\s)(?:\d+[\)\.-]|\*|\-)\s+", texto)
        partes_num = [p.strip() for p in partes_num if p.strip()]
        if len(partes_num) > 1 and all(re.search(r"\b(?:domo|suite|depa|safari|\$\d+|\d+\s*usd|\d+\s*noches?)\b", p, re.IGNORECASE) for p in partes_num):
            return partes_num

        # 2. Separación por 'y además' o 'y también'
        partes_y = re.split(r"\b(?:y\s+adem[aá]s|y\s+tambi[eé]n|otra\s+venta:?)\b", texto, flags=re.IGNORECASE)
        partes_y = [p.strip() for p in partes_y if p.strip()]
        if len(partes_y) > 1 and all(re.search(r"\b(?:domo|suite|depa|safari|\$\d+|\d+\s*usd)\b", p, re.IGNORECASE) for p in partes_y):
            return partes_y

        return [texto]

    # ¤arm-jarvis
    def extraer_venta_individual(self, texto: str, fecha_referencia: date | None = None) -> VentaExtraida:
        ref_fecha = fecha_referencia or date.today()
        t_limpio = texto.strip()

        if not self.es_mensaje_venta(t_limpio):
            return VentaExtraida(
                cliente_token=None,
                telefono_cliente_token=None,
                producto=None,
                propiedad_id=None,
                monto=None,
                moneda="USD",
                fecha_venta=ref_fecha,
                confianza=0.0,
                campos_faltantes=("monto", "producto"),
                es_venta=False,
            )

        confianza_campos: dict[str, float] = {}

        # 1. Extracción de producto y propiedad
        producto_encontrado: str | None = None
        propiedad_id: str | None = None
        t_para_numeros = t_limpio

        for patron, prod_nom, prop in PATRONES_PRODUCTO:
            m_prod = re.search(patron, t_limpio, re.IGNORECASE)
            if m_prod:
                producto_encontrado = prod_nom
                propiedad_id = prop
                confianza_campos["producto"] = 0.98
                confianza_campos["propiedad_id"] = 0.95
                # Enmascarar producto en el texto para no extraer números de habitaciones (ej. 101, 202) como monto
                t_para_numeros = t_para_numeros[:m_prod.start()] + " [PROD] " + t_para_numeros[m_prod.end():]
                break

        # 2. Extracción de fecha de llegada
        fecha_llegada = extraer_fecha_llegada(t_limpio, ref_fecha)
        if fecha_llegada:
            confianza_campos["fecha_llegada"] = 0.92
            # Enmascarar expresiones de fecha para que los días no se confundan con monto
            t_para_numeros = re.sub(
                r"\b(?:llega(?:da)?|para|desde|entra|ingresa)\s*(?:el)?\s*\d{1,2}(?:\s+de\s+[a-záéíóú]+(?:\s+de\s+\d{4})?)?\b",
                " [FECHA] ",
                t_para_numeros,
                flags=re.IGNORECASE,
            )
            t_para_numeros = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", " [FECHA] ", t_para_numeros)
            t_para_numeros = re.sub(r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b", " [FECHA] ", t_para_numeros)

        # 3. Extracción de noches
        noches: int | None = None
        m_noches = re.search(r"\b(\d{1,2})\s*(?:noche(?:s)?|nchs?|nits?)\b", t_limpio, re.IGNORECASE)
        if m_noches:
            noches = int(m_noches.group(1))
            confianza_campos["noches"] = 0.95
            t_para_numeros = re.sub(
                r"\b\d{1,2}\s*(?:noche(?:s)?|nchs?|nits?)\b",
                " [NOCHES] ",
                t_para_numeros,
                flags=re.IGNORECASE,
            )

        # 4. Extracción de monto sobre t_para_numeros
        monto_encontrado: Decimal | None = None

        # Patrón explícito con divisa: $450, 450 USD, 450 dólares, 450.00, etc.
        m_divisa = re.search(
            r"(?:\$|\b)(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+)\s*(?:usd|d[oó]lares|dlrs|\$)",
            t_para_numeros,
            re.IGNORECASE,
        )
        if m_divisa:
            dec = normalizar_monto(m_divisa.group(1))
            if dec:
                monto_encontrado = dec
                confianza_campos["monto"] = 0.98

        # Patrón con prefijos de cobro: cobrado 220, valor 270, total 300, etc.
        if not monto_encontrado:
            m_pref = re.search(
                r"(?:cobrado|valor|total|tarifa|por|precio|monto)\s*(?:\$|usd)?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?|\d+)",
                t_para_numeros,
                re.IGNORECASE,
            )
            if m_pref:
                dec = normalizar_monto(m_pref.group(1))
                if dec:
                    monto_encontrado = dec
                    confianza_campos["monto"] = 0.95

        # Si aún no hay monto, buscar números flotantes o enteros que parezcan precio (> 15)
        if not monto_encontrado:
            candidatos = re.findall(r"\b(\d{2,4}(?:[.,]\d{2})?)\b", t_para_numeros)
            for c in candidatos:
                dec = normalizar_monto(c)
                if dec and dec >= Decimal("20.00"):
                    monto_encontrado = dec
                    confianza_campos["monto"] = 0.88
                    break

        # 5. Extracción de cliente
        cliente: str | None = None
        m_cli = re.search(
            r"\b(?:a|cliente|para)\s+([A-ZÁÉÍÓÚ][a-záéíóú]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóú]+)?)\b",
            t_limpio,
        )
        if m_cli:
            c_nom = m_cli.group(1).strip()
            # Descartar si el cliente coincide con un producto o mes o palabra común
            if c_nom.lower() not in MESES_ES and not any(p in c_nom.lower() for p in ("domo", "suite", "depa", "cabaña", "fin", "este")):
                cliente = c_nom
                confianza_campos["cliente_token"] = 0.90

        # 6. Extracción de teléfono de cliente
        m_tel = re.search(r"(\+?5939\d{8}|09\d{8})", t_limpio)
        tel_cliente = m_tel.group(1) if m_tel else None
        if tel_cliente:
            confianza_campos["telefono_cliente_token"] = 0.98

        # 7. Comprobar campos obligatorios
        faltantes: list[str] = []
        if not monto_encontrado:
            faltantes.append("monto")
        if not producto_encontrado:
            faltantes.append("producto")

        confianza_global = 0.95 if not faltantes else 0.60

        return VentaExtraida(
            cliente_token=cliente,
            telefono_cliente_token=tel_cliente,
            producto=producto_encontrado,
            propiedad_id=propiedad_id,
            monto=monto_encontrado,
            moneda="USD",
            fecha_venta=ref_fecha,
            confianza=confianza_global,
            campos_faltantes=tuple(faltantes),
            es_venta=True,
            noches=noches,
            fecha_llegada=fecha_llegada,
            confianza_campos=confianza_campos,
        )

    # ¤arm-jarvis
    def extraer_todas(self, texto: str, fecha_referencia: date | None = None) -> list[VentaExtraida]:
        """Extrae una o múltiples ventas a partir del texto."""
        segmentos = self.dividir_en_ventas_multiples(texto)
        return [self.extraer_venta_individual(seg, fecha_referencia) for seg in segmentos]

    # ¤arm-jarvis
    def generar_pregunta_faltante(self, faltantes: Sequence[str]) -> str:
        """Formula una pregunta concisa solicitando únicamente los campos faltantes."""
        if "monto" in faltantes and "producto" in faltantes:
            return "¿Qué producto se vendió y cuál fue el monto de la venta?"
        if "monto" in faltantes:
            return "¿Cuál fue el monto de la venta?"
        if "producto" in faltantes:
            return "¿Qué producto o unidad se vendió?"
        return "¿Podrías proporcionar los datos faltantes de la venta?"

    # ¤arm-jarvis
    def evaluar(self, ruta_ventas: Path | str) -> dict[str, float]:
        """Evalúa exactitud de extracción sobre el dataset dorado evals/ventas.jsonl (RF-ARM-02)."""
        archivo = Path(ruta_ventas)
        if not archivo.is_file():
            return {"exactitud": 0.0, "total": 0.0, "aciertos": 0.0}

        lineas = [l for l in archivo.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not lineas:
            return {"exactitud": 0.0, "total": 0.0, "aciertos": 0.0}

        total = 0
        aciertos = 0

        for linea in lineas:
            caso = json.loads(linea)
            texto = caso.get("texto", "")
            espera_venta = caso.get("espera_venta", True)
            extraida = self.extraer_venta_individual(texto)

            total += 1
            if not espera_venta:
                if not extraida.es_venta:
                    aciertos += 1
                continue

            # Para casos que son venta
            if not extraida.es_venta:
                continue

            # Validar si faltaban campos intencionalmente
            faltantes_esperados = set(caso.get("campos_faltantes", []))
            if faltantes_esperados:
                if set(extraida.campos_faltantes) == faltantes_esperados:
                    aciertos += 1
                continue

            # Validar campos correctos
            ok = True
            if "monto" in caso:
                if extraida.monto is None or abs(float(extraida.monto) - float(caso["monto"])) > 0.01:
                    ok = False
            if "producto" in caso:
                if not extraida.producto or caso["producto"].lower() not in extraida.producto.lower():
                    ok = False
            if "noches" in caso and caso["noches"] is not None:
                if extraida.noches != caso["noches"]:
                    ok = False

            if ok:
                aciertos += 1

        exactitud = aciertos / total if total > 0 else 1.0
        return {
            "exactitud": round(exactitud, 4),
            "total": float(total),
            "aciertos": float(aciertos),
        }
