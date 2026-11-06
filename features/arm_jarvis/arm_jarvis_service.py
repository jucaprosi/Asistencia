# ¤arm-jarvis
# ¤¤backend-developer
"""Compuerta pública de la sala arm_jarvis (RF-ARM-01..10, INV_ESTADOS_VENTA, INV_COMISION_PROPIA, INV_TICKET_UNICO)."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import threading
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from features.arm_jarvis.asistente_lider_internal import AsistenteLider
from features.arm_jarvis.dobles_internal import (
    DobleCanalWhatsApp,
    DobleComisiones,
    DobleCrm,
    DobleObservabilidad,
    DobleSeguridad,
)
from features.arm_jarvis.estados_internal import GestorEstados
from features.arm_jarvis.extractor_internal import ExtractorVentas
from features.arm_jarvis.notificador_internal import NotificadorVendedor
from features.arm_jarvis.persistencia_internal import RepositorioArm
from features.arm_jarvis.ticket_internal import GeneradorTickets
from features.arm_jarvis.tipos import (
    CamposFaltantes,
    ComisionAjena,
    ErrorArm,
    EstadoVenta,
    NoEsVenta,
    ResumenComision,
    Tablero,
    Transicion,
    TransicionInvalida,
    Vendedor,
    VendedorNoRegistrado,
    Venta,
    VentaExtraida,
    VentaNoEncontrada,
)

__all__ = [
    "EstadoVenta",
    "ResumenComision",
    "Tablero",
    "Transicion",
    "Vendedor",
    "Venta",
    "VentaExtraida",
    "ErrorArm",
    "VendedorNoRegistrado",
    "TransicionInvalida",
    "CamposFaltantes",
    "NoEsVenta",
    "ComisionAjena",
    "ArmJarvisService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_arm_jarvis.yaml")


# ¤arm-jarvis
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤arm-jarvis
class ArmJarvisService:
    """Compuerta del Automated Revenue Manager (ARM «Jarvis»)."""

    def __init__(
        self,
        config: Mapping[str, Any] | None = None,
        *,
        seguridad: Any = None,
        comisiones: Any = None,
        crm: Any = None,
        canal: Any = None,
        observabilidad: Any = None,
        conexion: Any = None,
    ) -> None:
        self._config = config or cargar_config()
        self._seguridad = seguridad or DobleSeguridad()
        self._comisiones = comisiones or DobleComisiones()
        self._crm = crm or DobleCrm()
        self._canal = canal or DobleCanalWhatsApp()
        self._observabilidad = observabilidad or DobleObservabilidad()
        self._repo = RepositorioArm(conexion=conexion)
        self._generador_tickets = GeneradorTickets(self._repo.conexion, lock=self._repo.lock)
        self._extractor = ExtractorVentas(self._config)
        self._estados = GestorEstados(self._repo)
        self._notificador = NotificadorVendedor(self._canal, self._config)
        self._asistente_lider = AsistenteLider(self._repo, self._config)
        self._locks_vendedor: dict[str, threading.RLock] = {}
        self._lock_general = threading.RLock()

    # ¤arm-jarvis
    @property
    def repositorio(self) -> RepositorioArm:
        return self._repo

    # ¤arm-jarvis
    def _obtener_lock_vendedor(self, vendedor_id: str) -> threading.RLock:
        with self._lock_general:
            if vendedor_id not in self._locks_vendedor:
                self._locks_vendedor[vendedor_id] = threading.RLock()
            return self._locks_vendedor[vendedor_id]

    # ¤arm-jarvis
    def registrar_vendedor(
        self,
        telefono_token: str,
        nombre: str,
        activo: bool = True,
        vendedor_id: str | None = None,
        regla_comision_default_id: str | None = None,
    ) -> Vendedor:
        """Crea o actualiza un vendedor activo en arm.vendedores."""
        vid = vendedor_id or str(uuid.uuid4())
        v = Vendedor(
            vendedor_id=vid,
            telefono_token=telefono_token,
            nombre=nombre,
            activo=activo,
            regla_comision_default_id=regla_comision_default_id,
        )
        self._repo.registrar_vendedor(v)
        return v

    # ¤arm-jarvis
    def procesar(self, mensaje: Any) -> str:
        """Procesa mensajes entrantes en el canal de vendedores (RF-ARM-01, 02, 05, 07, 10)."""
        # Extraer campos de mensaje (compatible con MensajeLimpio o dicts)
        if hasattr(mensaje, "identidad"):
            remitente_token = mensaje.identidad.remitente_token
            rol = getattr(mensaje.identidad, "rol", "vendedor")
        elif isinstance(mensaje, dict):
            remitente_token = mensaje.get("remitente", mensaje.get("telefono_token", ""))
            rol = mensaje.get("rol", "vendedor")
        else:
            remitente_token = getattr(mensaje, "remitente", str(mensaje))
            rol = "vendedor"

        texto = getattr(mensaje, "texto_tokenizado", getattr(mensaje, "texto", str(mensaje)))
        mensaje_id = getattr(mensaje, "mensaje_id", getattr(mensaje, "conversacion_id", str(uuid.uuid4())))
        conversacion_id = getattr(mensaje, "conversacion_id", mensaje_id)

        # 1. RF-ARM-01: Validar si el remitente es un vendedor registrado y activo
        vendedor = self._repo.obtener_vendedor_por_telefono(remitente_token)
        if not vendedor:
            # Registrar por hash y descartar sin respuesta
            hash_remitente = hashlib.sha256(remitente_token.encode("utf-8")).hexdigest()
            if hasattr(self._seguridad, "auditar"):
                self._seguridad.auditar({
                    "evento": "remitente_no_vendedor_descartado",
                    "hash_remitente": hash_remitente,
                    "texto_resumen": texto[:30],
                })
            return ""

        t_min = texto.strip().lower()

        # 2. RF-ARM-07: Consulta de comisión propia vs ajena
        if re.search(r"\b(?:cu[aá]nto\s+llevo|comisi[oó]n|comisiones|cu[aá]nto\s+he\s+ganado|liquidaci[oó]n)\b", t_min):
            # Detectar si pregunta por otro vendedor
            m_ajeno = re.search(r"\b(?:de|para)\s+([A-ZÁÉÍÓÚa-záéíóú]+)\b", texto)
            if m_ajeno:
                nombre_candidato = m_ajeno.group(1).strip()
                if nombre_candidato.lower() not in ("mi", "yo", "mí", "este", "la", "las", "un", "una", vendedor.nombre.lower()):
                    if hasattr(self._seguridad, "auditar"):
                        self._seguridad.auditar({
                            "evento": "intento_consulta_comision_ajena",
                            "vendedor_id": vendedor.vendedor_id,
                            "vendedor_consultado": nombre_candidato,
                        })
                    return "Solo puedes consultar tu propia comisión."

            # Consulta propia
            periodo = f"{date.today().year}-{date.today().month:02d}"
            resumen = self.consultar_comision_propia(vendedor.vendedor_id, periodo)
            return (
                f"Resumen de comisiones para {vendedor.nombre} ({resumen.periodo}):\n"
                f"• Validadas: {resumen.validada:.2f} USD\n"
                f"• Pendientes: {resumen.pendiente:.2f} USD\n"
                f"• Total ventas: {resumen.ventas}"
            )

        # 3. RF-ARM-02: Extracción estructurada de ventas
        if not self._extractor.es_mensaje_venta(texto):
            return "Hola, soy el asistente de ventas. Puedes registrar ventas indicando cliente, noches, producto, monto y fecha de llegada."

        ventas_extraidas = self._extractor.extraer_todas(texto)
        if not ventas_extraidas:
            return "No se pudo identificar una venta válida en el mensaje."

        respuestas_tickets: list[str] = []

        for idx, extraida in enumerate(ventas_extraidas):
            # Si faltan campos obligatorios, preguntar y no registrar
            if extraida.campos_faltantes:
                return self._extractor.generar_pregunta_faltante(extraida.campos_faltantes)

            # Idempotencia: Verificar si este mensaje e índice ya fue procesado
            venta_existente = self._repo.buscar_por_mensaje_e_indice(mensaje_id, idx)
            if venta_existente:
                respuestas_tickets.append(
                    f"Venta ya registrada previamente. Ticket: {venta_existente.ticket} ({venta_existente.estado.value})"
                )
                continue

            # Detectar posible duplicado
            posible_dup_id = self._repo.buscar_posible_duplicado(
                cliente_token=extraida.cliente_token,
                producto=extraida.producto or "",
                monto=extraida.monto or Decimal("0"),
                fecha_venta=extraida.fecha_venta or date.today(),
            )

            nueva_venta_id = str(uuid.uuid4())

            # Calcular comisión estimada inicial
            monto_venta = extraida.monto or Decimal("0")
            comision_estimada: Decimal | None = None
            if hasattr(self._comisiones, "calcular"):
                try:
                    c_sim = self._comisiones.calcular(
                        venta_id=nueva_venta_id,
                        vendedor_id=vendedor.vendedor_id,
                        propiedad_id=extraida.propiedad_id,
                        producto=extraida.producto or "",
                        monto=monto_venta,
                        fecha_venta=extraida.fecha_venta or date.today(),
                    )
                    comision_estimada = getattr(c_sim, "monto", getattr(c_sim, "comision", Decimal("0")))
                except Exception:
                    comision_estimada = (monto_venta * Decimal("0.10")).quantize(Decimal("0.01"))

            # Inserción con generación atómica de ticket (INV_TICKET_UNICO)
            anio = (extraida.fecha_venta or date.today()).year

            def _accion_insertar(ticket_asignado: str) -> Venta:
                nueva_venta = Venta(
                    venta_id=nueva_venta_id,
                    ticket=ticket_asignado,
                    vendedor_id=vendedor.vendedor_id,
                    extraida=extraida,
                    texto_original_token=texto,
                    estado=EstadoVenta.POR_VALIDAR,
                    creada=datetime.now(timezone.utc),
                    actualizada=datetime.now(timezone.utc),
                    comision_estimada=comision_estimada,
                    posible_duplicado=bool(posible_dup_id),
                    posible_duplicado_de=posible_dup_id,
                    mensaje_id=mensaje_id,
                    indice_en_mensaje=idx,
                )
                self._repo.insertar_venta(nueva_venta)
                return nueva_venta

            ticket_generado, venta_creada = self._generador_tickets.generar_ticket_con_transaccion(
                anio=anio,
                accion_insercion=_accion_insertar,
            )

            # Formatear confirmación para el canal
            com_txt = f"{comision_estimada:.2f} USD" if comision_estimada is not None else "Por calcular"
            cli_txt = extraida.cliente_token or "No especificado"
            llegada_txt = extraida.fecha_llegada.isoformat() if extraida.fecha_llegada else "No especificada"
            noches_txt = f"{extraida.noches}" if extraida.noches else "No especificadas"

            aviso_dup = " (Atención: Posible duplicado detectado)" if posible_dup_id else ""
            resumen = (
                f"Venta registrada.{aviso_dup}\n"
                f"Ticket: {ticket_generado}\n"
                f"Cliente: {cli_txt}\n"
                f"Producto: {extraida.producto}\n"
                f"Monto: {monto_venta:.2f} USD\n"
                f"Noches: {noches_txt}\n"
                f"Llegada: {llegada_txt}\n"
                f"Comisión estimada: {com_txt}"
            )
            respuestas_tickets.append(resumen)

        return "\n\n".join(respuestas_tickets)

    # ¤arm-jarvis
    def extraer(self, texto: str) -> VentaExtraida:
        """Extrae directamente una venta de texto libre (RF-ARM-02)."""
        return self._extractor.extraer_venta_individual(texto)

    # ¤arm-jarvis
    def validar(
        self,
        venta_id: str,
        actor: Any,
        correcciones: Mapping[str, Any] | None = None,
    ) -> Venta:
        """Pasa una venta a 'validada', fija la comisión y notifica al vendedor (RF-ARM-03, 04, 06)."""
        actor_id = getattr(actor, "sujeto_id", getattr(actor, "remitente_token", str(actor)))
        actor_rol = getattr(actor, "rol", "lider")
        if hasattr(actor_rol, "value"):
            actor_rol = actor_rol.value

        # Concurrencia por vendedor: serializar para INV_COMISION_REPRODUCIBLE
        with self._lock_general:
            venta = self._repo.obtener_venta(venta_id)
            lock_vendedor = self._obtener_lock_vendedor(venta.vendedor_id)
        with lock_vendedor:
            # 1. Fijar comisión
            comision_fijada: Decimal = Decimal("0.00")
            if hasattr(self._comisiones, "fijar"):
                try:
                    c_fij = self._comisiones.fijar(f"com_{venta_id}")
                    comision_fijada = getattr(c_fij, "monto", getattr(c_fij, "comision", Decimal("0.00")))
                except Exception:
                    comision_fijada = venta.comision_estimada or Decimal("45.00")
            else:
                comision_fijada = venta.comision_estimada or Decimal("45.00")

            # 2. Transición de estado a 'validada'
            venta_validada = self._estados.ejecutar_transicion(
                venta_id=venta_id,
                nuevo_estado=EstadoVenta.VALIDADA,
                actor_id=actor_id,
                actor_rol=actor_rol,
                motivo=None,
                comision_fijada=comision_fijada,
            )

            # 3. Notificación privada al vendedor
            vendedor = self._repo.obtener_vendedor_por_id(venta.vendedor_id)
            if vendedor:
                self._notificador.notificar_validacion(venta_validada, vendedor)

            # 4. Encolar / publicar en CRM si conector está disponible
            if hasattr(self._crm, "publicar_venta"):
                try:
                    self._crm.publicar_venta(venta_validada)
                except Exception:
                    pass

            return venta_validada

    # ¤arm-jarvis
    def rechazar(self, venta_id: str, actor: Any, motivo: str) -> Venta:
        """Pasa una venta a 'rechazada' con motivo obligatorio y notifica al vendedor."""
        venta = self._repo.obtener_venta(venta_id)
        actor_id = getattr(actor, "sujeto_id", getattr(actor, "remitente_token", str(actor)))
        actor_rol = getattr(actor, "rol", "lider")
        if hasattr(actor_rol, "value"):
            actor_rol = actor_rol.value

        venta_rechazada = self._estados.ejecutar_transicion(
            venta_id=venta_id,
            nuevo_estado=EstadoVenta.RECHAZADA,
            actor_id=actor_id,
            actor_rol=actor_rol,
            motivo=motivo,
            comision_fijada=Decimal("0.00"),
        )

        vendedor = self._repo.obtener_vendedor_por_id(venta.vendedor_id)
        if vendedor:
            self._notificador.notificar_rechazo(venta_rechazada, vendedor, motivo=motivo)

        return venta_rechazada

    # ¤arm-jarvis
    def anular(self, venta_id: str, actor: Any, motivo: str) -> Venta:
        """Anula una venta (solo rol administrador, con motivo obligatorio)."""
        venta = self._repo.obtener_venta(venta_id)
        actor_id = getattr(actor, "sujeto_id", getattr(actor, "remitente_token", str(actor)))
        actor_rol = getattr(actor, "rol", "administrador")
        if hasattr(actor_rol, "value"):
            actor_rol = actor_rol.value

        venta_anulada = self._estados.ejecutar_transicion(
            venta_id=venta_id,
            nuevo_estado=EstadoVenta.ANULADA,
            actor_id=actor_id,
            actor_rol=actor_rol,
            motivo=motivo,
        )

        # Si ya estaba publicada, publicar anulación en CRM
        if venta.estado == EstadoVenta.PUBLICADA and hasattr(self._crm, "publicar_anulacion"):
            try:
                self._crm.publicar_anulacion(venta_anulada)
            except Exception:
                pass

        return venta_anulada

    # ¤arm-jarvis
    def editar_venta(self, venta_id: str, actor: Any, nuevo_monto: Decimal) -> None:
        """Impide editar ventas validadas, requiriendo anulación formal."""
        venta = self._repo.obtener_venta(venta_id)
        if venta.estado == EstadoVenta.VALIDADA or venta.estado == EstadoVenta.PUBLICADA:
            raise TransicionInvalida(
                estado_actual=venta.estado.value,
                estado_nuevo="editada",
                motivo="Una venta validada no se puede editar. Solicita anulación al administrador.",
            )

    # ¤arm-jarvis
    def marcar_publicacion(self, venta_id: str, ok: bool, detalle: str | None = None) -> Venta:
        """Receptor de callbacks o resultados del conector CRM (RF-CRM-04, INV_VENTA_NO_SE_PIERDE)."""
        venta = self._repo.obtener_venta(venta_id)
        if ok:
            nuevo = EstadoVenta.PUBLICADA
        else:
            nuevo = EstadoVenta.NO_PUBLICADA

        if venta.estado == nuevo:
            return venta

        venta_act = self._estados.ejecutar_transicion(
            venta_id=venta_id,
            nuevo_estado=nuevo,
            actor_id="crm_conector",
            actor_rol="sistema",
            motivo=detalle or ("Publicación exitosa en CRM" if ok else "Fallo de publicación en CRM"),
        )

        if not ok and self._observabilidad and hasattr(self._observabilidad, "alertar"):
            try:
                self._observabilidad.alertar(
                    tipo="venta_no_publicada",
                    mensaje=f"La venta {venta.ticket} ({venta_id}) no pudo publicarse en CRM: {detalle}",
                    datos={"venta_id": venta_id, "ticket": venta.ticket, "detalle": detalle},
                )
            except Exception:
                pass

        return venta_act

    # ¤arm-jarvis
    def consultar_comision_propia(self, vendedor_id: str, periodo: str | None = None) -> ResumenComision:
        """Calcula el total validado y pendiente exclusivo del vendedor (RF-ARM-07)."""
        per = periodo or f"{date.today().year}-{date.today().month:02d}"
        val, pend, cnt = self._repo.obtener_resumen_comisiones(vendedor_id, per)
        return ResumenComision(
            vendedor_id=vendedor_id,
            periodo=per,
            validada=val,
            pendiente=pend,
            ventas=cnt,
        )

    # ¤arm-jarvis
    def listar(
        self,
        estado: EstadoVenta | None = None,
        vendedor_id: str | None = None,
        periodo: str | None = None,
        pagina: int = 1,
    ) -> tuple[Venta, ...]:
        return self._repo.listar_ventas(
            estado=estado,
            vendedor_id=vendedor_id,
            periodo=periodo,
            pagina=pagina,
        )

    # ¤arm-jarvis
    def detalle(self, venta_id: str) -> tuple[Venta, tuple[Transicion, ...]]:
        venta = self._repo.obtener_venta(venta_id)
        transiciones = self._repo.listar_transiciones(venta_id)
        return venta, transiciones

    # ¤arm-jarvis
    def tablero(self, periodo: str) -> Tablero:
        """Genera el tablero consolidado por período con comisiones y ventas agregadas (RF-ARM-08)."""
        tab = self._repo.obtener_tablero(periodo)
        if self._comisiones and hasattr(self._comisiones, "resumen"):
            try:
                res_com = self._comisiones.resumen(None, periodo)
                if isinstance(res_com, dict) and "validada" in res_com:
                    val_dec = res_com["validada"]
                    if not isinstance(val_dec, Decimal):
                        val_dec = Decimal(str(val_dec)).quantize(Decimal("0.01"))
                    pend_dec = tab.comisiones_pendientes
                    return Tablero(
                        periodo=tab.periodo,
                        ventas_por_mes=tab.ventas_por_mes,
                        ventas_por_vendedor=tab.ventas_por_vendedor,
                        ventas_por_propiedad=tab.ventas_por_propiedad,
                        comisiones_validadas=val_dec,
                        comisiones_pendientes=pend_dec,
                        por_validar=tab.por_validar,
                    )
            except Exception:
                pass
        return tab

    # ¤arm-jarvis
    def exportar_csv(self, periodo: str) -> str:
        """Exporta las filas del tablero a CSV reproduciendo exactamente sus métricas (RF-ARM-08)."""
        tab = self.tablero(periodo)
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["seccion", "concepto", "monto", "cantidad"])
        writer.writerow(["totales", "comisiones_validadas", f"{tab.comisiones_validadas:.2f}", ""])
        writer.writerow(["totales", "comisiones_pendientes", f"{tab.comisiones_pendientes:.2f}", ""])
        writer.writerow(["totales", "por_validar", "", str(tab.por_validar)])
        for mes, total in tab.ventas_por_mes:
            writer.writerow(["ventas_por_mes", mes, f"{total:.2f}", ""])
        for nombre_vend, total, cnt in tab.ventas_por_vendedor:
            writer.writerow(["ventas_por_vendedor", nombre_vend, f"{total:.2f}", str(cnt)])
        for prop, total in tab.ventas_por_propiedad:
            writer.writerow(["ventas_por_propiedad", prop, f"{total:.2f}", ""])
        return output.getvalue()

    # ¤arm-jarvis
    def exportar_ventas_csv(self, periodo: str) -> str:
        """Exporta las ventas individuales del período a formato CSV."""
        ventas = self._repo.listar_ventas(periodo=periodo)
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow([
            "venta_id", "ticket", "vendedor_id", "producto", "propiedad_id",
            "monto", "moneda", "fecha_venta", "estado", "comision_estimada", "comision_fijada",
        ])
        for v in ventas:
            monto_str = f"{v.extraida.monto:.2f}" if v.extraida.monto is not None else "0.00"
            com_est = f"{v.comision_estimada:.2f}" if v.comision_estimada is not None else ""
            com_fij = f"{v.comision_fijada:.2f}" if v.comision_fijada is not None else ""
            writer.writerow([
                v.venta_id,
                v.ticket,
                v.vendedor_id,
                v.extraida.producto or "",
                v.extraida.propiedad_id or "",
                monto_str,
                v.extraida.moneda,
                v.extraida.fecha_venta.isoformat() if v.extraida.fecha_venta else "",
                v.estado.value,
                com_est,
                com_fij,
            ])
        return output.getvalue()

    # ¤arm-jarvis
    def preguntar_jarvis(self, actor: Any, pregunta: str, conversacion_id: str = "") -> str:
        """Atiende consultas del líder o administrador mediante el asistente Jarvis."""
        actor_id = getattr(actor, "sujeto_id", getattr(actor, "remitente_token", str(actor)))
        actor_rol = getattr(actor, "rol", "lider")
        if hasattr(actor_rol, "value"):
            actor_rol = actor_rol.value

        return self._asistente_lider.atender_consulta(
            actor_id=actor_id,
            actor_rol=actor_rol,
            pregunta=pregunta,
            conversacion_id=conversacion_id,
        )

    # ¤arm-jarvis
    def aplicar_cambio_configuracion(self, actor: Any, cambio: Mapping[str, Any], confirmado: bool) -> None:
        actor_id = getattr(actor, "sujeto_id", getattr(actor, "remitente_token", str(actor)))
        actor_rol = getattr(actor, "rol", "lider")
        if hasattr(actor_rol, "value"):
            actor_rol = actor_rol.value

        self._asistente_lider.aplicar_cambio(
            actor_id=actor_id,
            actor_rol=actor_rol,
            cambio=cambio,
            confirmado=confirmado,
        )

    # ¤arm-jarvis
    def evaluar(self, ruta_ventas: Path | str) -> dict[str, float]:
        """Ejecuta la suite de evaluación de ventas doradas (RF-ARM-02)."""
        return self._extractor.evaluar(ruta_ventas)
