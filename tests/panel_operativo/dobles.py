"""Dobles de prueba para las compuertas consumidas por panel_operativo."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

from features.arm_jarvis.arm_jarvis_service import (
    ErrorArm,
    EstadoVenta,
    Transicion,
    Venta,
    VentaExtraida,
)
from features.comisiones.comisiones_service import ErrorComisiones, PeriodoCerrado


@dataclass(frozen=True)
class Veredicto:
    permitido: bool
    motivo: str | None = None


class DobleSeguridadService:
    def __init__(self) -> None:
        self.usuarios: dict[str, dict[str, Any]] = {
            "gestor_a@glamping.ec": {
                "usuario_id": "usr_gestor_a",
                "correo": "gestor_a@glamping.ec",
                "rol": "gestor",
                "zonas": ("zona_a",),
                "telefono": "+593991111111",
                "activo": True,
            },
            "gestor_b@glamping.ec": {
                "usuario_id": "usr_gestor_b",
                "correo": "gestor_b@glamping.ec",
                "rol": "gestor",
                "zonas": ("zona_b",),
                "telefono": "+593992222222",
                "activo": True,
            },
            "lider@glamping.ec": {
                "usuario_id": "usr_lider",
                "correo": "lider@glamping.ec",
                "rol": "lider",
                "zonas": ("zona_a", "zona_b"),
                "telefono": "+593993333333",
                "activo": True,
            },
            "admin@glamping.ec": {
                "usuario_id": "usr_admin",
                "correo": "admin@glamping.ec",
                "rol": "administrador",
                "zonas": ("zona_a", "zona_b"),
                "telefono": "+593994444444",
                "activo": True,
            },
            "anfitrion@glamping.ec": {
                "usuario_id": "anf_1",
                "correo": "anfitrion@glamping.ec",
                "rol": "anfitrion",
                "zonas": (),
                "telefono": "+593996666666",
                "activo": True,
            },
            "anfitrion_ajeno@glamping.ec": {
                "usuario_id": "anf_2",
                "correo": "anfitrion_ajeno@glamping.ec",
                "rol": "anfitrion",
                "zonas": (),
                "telefono": "+593997777777",
                "activo": True,
            },
            "inactivo@glamping.ec": {
                "usuario_id": "usr_inactivo",
                "correo": "inactivo@glamping.ec",
                "rol": "gestor",
                "zonas": ("zona_a",),
                "telefono": "+593995555555",
                "activo": False,
            },
        }
        self.audit_log: list[Any] = []
        self.bloqueos: set[str] = set()
        self.tokens_prueba: dict[tuple[str, str], str] = {}

    def registrar_token_prueba(self, conversacion_id: str, token: str, valor_real: str) -> None:
        self.tokens_prueba[(conversacion_id, token)] = valor_real

    def obtener_usuario_por_correo(self, correo: str) -> dict[str, Any] | None:
        return self.usuarios.get(correo.strip().lower())

    def autorizar(self, rol: str, accion: str) -> Veredicto:
        if accion == "zona_prohibida":
            return Veredicto(permitido=False, motivo="Acción prohibida para este rol")
        return Veredicto(permitido=True)

    def rehidratar(self, texto: str, conversacion_id: str) -> str:
        resultado = texto.replace("[token_huesped]", "María López").replace("[token_telefono]", "+593998888888")
        for (conv_id, tok), val in self.tokens_prueba.items():
            if conv_id == conversacion_id and tok in resultado:
                resultado = resultado.replace(tok, val)
        return resultado

    def tokenizar(self, texto: str, conversacion_id: str = "") -> str:
        return f"tok_{texto[-4:]}" if len(texto) >= 4 else "tok_anon"

    def auditar(self, evento: Any) -> None:
        self.audit_log.append(evento)

    def administrar_usuarios(
        self,
        actor: Any,
        numero: str,
        rol: Any,
        alta: bool,
        sujeto_id: str | None = None,
        correo: str | None = None,
    ) -> None:
        actor_id = getattr(actor, "remitente_token", str(actor))
        c = correo or f"usr_{numero[-4:]}@glamping.ec"
        r_val = rol.value if hasattr(rol, "value") else str(rol)
        if alta:
            self.usuarios[c] = {
                "usuario_id": sujeto_id or f"usr_{numero[-4:]}",
                "correo": c,
                "rol": r_val,
                "zonas": ("zona_a",),
                "telefono": numero,
                "activo": True,
            }
        else:
            if c in self.usuarios:
                self.usuarios[c]["activo"] = False
        self.audit_log.append({
            "actor_id": actor_id,
            "accion": "alta_usuario" if alta else "baja_usuario",
            "numero": numero,
            "rol": r_val,
            "usuario_id": actor_id,
        })

    def bloquear_numero(self, actor: Any, numero: str, motivo: str) -> None:
        actor_id = getattr(actor, "remitente_token", str(actor))
        self.bloqueos.add(numero)
        self.audit_log.append({
            "actor_id": actor_id,
            "accion": "bloquear_numero",
            "numero": numero,
            "motivo": motivo,
            "usuario_id": actor_id,
        })

    def desbloquear_numero(self, actor: Any, numero: str) -> None:
        actor_id = getattr(actor, "remitente_token", str(actor))
        self.bloqueos.discard(numero)
        self.audit_log.append({
            "actor_id": actor_id,
            "accion": "desbloquear_numero",
            "numero": numero,
            "usuario_id": actor_id,
        })


class DobleAgenteService:
    def __init__(self) -> None:
        self.silenciadas: dict[str, str] = {}
        self.reanudadas: list[str] = []

    def entrar_en_silencio(self, conversacion_id: str, motivo: str) -> None:
        self.silenciadas[conversacion_id] = motivo

    def reanudar(self, conversacion_id: str) -> None:
        self.reanudadas.append(conversacion_id)
        self.silenciadas.pop(conversacion_id, None)


class DobleCanalWhatsappService:
    def __init__(self) -> None:
        self.enviados: list[Any] = []
        self.mensajes_enviados: list[Any] = self.enviados
        self.plantillas_enviadas: list[tuple[str, Any]] = []
        self.en_ventana = True

    def enviar(self, mensaje: Any) -> None:
        self.enviados.append(mensaje)

    def enviar_plantilla(self, destinatario: str, plantilla: Any) -> None:
        self.plantillas_enviadas.append((destinatario, plantilla))

    def en_ventana_24h(self, destinatario: str) -> bool:
        return self.en_ventana


class DobleCRMConectorService:
    def __init__(self) -> None:
        self.mensajes: list[tuple[str, str]] = []

    def enviar_mensaje(self, conversacion_id: str, texto: str) -> str:
        self.mensajes.append((conversacion_id, texto))
        return "msg_ok"


class DoblePMSConectorService:
    def __init__(self) -> None:
        self.incidencias_resueltas: list[tuple[str, str, str]] = []

    def resolver_incidencia(self, incidencia_id: str, nota: str, actor_id: str) -> None:
        self.incidencias_resueltas.append((incidencia_id, nota, actor_id))


class DobleComisionesService:
    def __init__(self) -> None:
        self.comisiones_fijadas: list[str] = []
        self.ajustes: list[dict[str, Any]] = []
        self.periodos_cerrados: set[str] = set()

        # Datos sintéticos reproducibles para el período 2026-10
        self._lineas_periodo: dict[str, list[dict[str, Any]]] = {
            "2026-10": [
                {
                    "comision_id": "com_1",
                    "venta_id": "V-2026-0001",
                    "vendedor_id": "usr_vendedor_juan",
                    "fecha_venta": "2026-10-10",
                    "monto_venta": "400.00",
                    "monto_comision": "30.00",
                    "estado": "FIJADA",
                    "periodo_id": "2026-10",
                    "periodo_origen": "2026-10",
                    "ajuste_de": None,
                    "motivo": None,
                },
                {
                    "comision_id": "com_2",
                    "venta_id": "V-2026-0003",
                    "vendedor_id": "usr_vendedor_juan",
                    "fecha_venta": "2026-10-12",
                    "monto_venta": "250.00",
                    "monto_comision": "25.00",
                    "estado": "FIJADA",
                    "periodo_id": "2026-10",
                    "periodo_origen": "2026-10",
                    "ajuste_de": None,
                    "motivo": None,
                },
                {
                    "comision_id": "com_ajuste_1",
                    "venta_id": "V-2026-0001",
                    "vendedor_id": "usr_vendedor_juan",
                    "fecha_venta": "2026-10-15",
                    "monto_venta": "0.00",
                    "monto_comision": "-10.00",
                    "estado": "AJUSTADA",
                    "periodo_id": "2026-10",
                    "periodo_origen": "2026-10",
                    "ajuste_de": "com_1",
                    "motivo": "Ajuste por anulación parcial",
                },
                {
                    "comision_id": "com_3",
                    "venta_id": "V-2026-0106",
                    "vendedor_id": "usr_vendedor_ana",
                    "fecha_venta": "2026-10-15",
                    "monto_venta": "200.00",
                    "monto_comision": "20.00",
                    "estado": "FIJADA",
                    "periodo_id": "2026-10",
                    "periodo_origen": "2026-10",
                    "ajuste_de": None,
                    "motivo": None,
                },
            ]
        }
        self._pendientes: dict[str, list[dict[str, Any]]] = {
            "2026-10": [
                {
                    "comision_id": "com_4",
                    "venta_id": "V-2026-0107",
                    "vendedor_id": "usr_vendedor_juan",
                    "fecha_venta": "2026-10-15",
                    "monto_venta": "450.00",
                    "monto_comision": "45.00",
                    "estado": "ESTIMADA",
                    "periodo_id": "2026-10",
                }
            ]
        }

    def desglose(self, venta_id: str) -> Mapping[str, Any]:
        return {
            "venta_id": venta_id,
            "regla": "Regla Depa Centro",
            "version": 3,
            "modo": "por_tramos",
            "acumulado": Decimal("800.00"),
            "tramos": (
                {"monto": Decimal("200.00"), "porcentaje": 5, "comision": Decimal("10.00")},
                {"monto": Decimal("200.00"), "porcentaje": 10, "comision": Decimal("20.00")},
            ),
            "total_comision": Decimal("30.00"),
        }

    def fijar(self, comision_id: str) -> dict[str, Any]:
        if "2026-10" in self.periodos_cerrados:
            raise PeriodoCerrado("El período 2026-10 ya se encuentra cerrado")
        self.comisiones_fijadas.append(comision_id)
        return {"comision_id": comision_id, "estado": "FIJADA", "monto": Decimal("45.00")}

    def ajustar(self, comision_id: str, actor: Any, nuevo_monto: Decimal, motivo: str) -> dict[str, Any]:
        if "2026-10" in self.periodos_cerrados:
            raise PeriodoCerrado("El período 2026-10 ya se encuentra cerrado")
        self.ajustes.append({"comision_id": comision_id, "actor": actor, "nuevo_monto": nuevo_monto, "motivo": motivo})
        return {"comision_id": f"ajuste_{comision_id}", "estado": "AJUSTADA", "monto": nuevo_monto, "motivo": motivo}

    def resumen(self, vendedor_id: str | None, periodo_id: str) -> Mapping[str, Any]:
        lineas = self._lineas_periodo.get(periodo_id, [])
        if vendedor_id:
            lineas = [l for l in lineas if l["vendedor_id"] == vendedor_id]

        total_validada = sum((Decimal(l["monto_comision"]) for l in lineas), Decimal("0.00"))
        base_acumulada = sum((Decimal(l["monto_venta"]) for l in lineas), Decimal("0.00"))
        num_ventas = sum((1 for l in lineas if l["ajuste_de"] is None))
        total_ajustes = sum((Decimal(l["monto_comision"]) for l in lineas if l["ajuste_de"] is not None), Decimal("0.00"))

        pendientes = self._pendientes.get(periodo_id, [])
        if vendedor_id:
            pendientes = [p for p in pendientes if p["vendedor_id"] == vendedor_id]
        total_pendiente = sum((Decimal(p["monto_comision"]) for p in pendientes), Decimal("0.00"))

        return {
            "periodo_id": periodo_id,
            "vendedor_id": vendedor_id,
            "validada": total_validada,
            "pendiente": total_pendiente,
            "ventas": num_ventas,
            "ajustes": total_ajustes,
            "base_acumulada": base_acumulada,
        }

    def estado_cuenta(self, vendedor_id: str, periodo_id: str) -> Mapping[str, Any]:
        lineas = [l for l in self._lineas_periodo.get(periodo_id, []) if l["vendedor_id"] == vendedor_id]

        lineas_formateadas = []
        total_ventas = Decimal("0.00")
        total_comisiones = Decimal("0.00")
        num_ventas = 0
        num_ajustes = 0

        for l in lineas:
            tipo = "ajuste" if l["ajuste_de"] is not None else "venta"
            if tipo == "venta":
                num_ventas += 1
            else:
                num_ajustes += 1

            mv = Decimal(l["monto_venta"])
            mc = Decimal(l["monto_comision"])
            total_ventas += mv
            total_comisiones += mc

            lineas_formateadas.append({
                "tipo": tipo,
                "comision_id": l["comision_id"],
                "venta_id": l["venta_id"],
                "fecha_venta": l["fecha_venta"],
                "monto_venta": str(mv),
                "monto_comision": str(mc),
                "estado": l["estado"],
                "periodo_origen": l["periodo_origen"],
                "motivo": l["motivo"],
            })

        return {
            "vendedor_id": vendedor_id,
            "periodo_id": periodo_id,
            "lineas": lineas_formateadas,
            "total_ventas": f"{total_ventas:.2f}",
            "total_comisiones": f"{total_comisiones:.2f}",
            "numero_ventas": num_ventas,
            "numero_ajustes": num_ajustes,
        }

    def cerrar_periodo(self, periodo_id: str, actor: Any) -> Mapping[str, Any]:
        if periodo_id in self.periodos_cerrados:
            raise PeriodoCerrado(f"El período {periodo_id} ya se encuentra cerrado")

        self.periodos_cerrados.add(periodo_id)
        actor_id = getattr(actor, "remitente_token", str(actor))
        return {
            "periodo_id": periodo_id,
            "cerrado_en": datetime.now(timezone.utc).isoformat(),
            "cerrado_por": actor_id,
            "estado": "cerrado",
        }

    def exportar(self, periodo_id: str, formato: str) -> bytes:
        lineas = self._lineas_periodo.get(periodo_id, [])
        total_ventas = sum((Decimal(l["monto_venta"]) for l in lineas), Decimal("0.00"))
        total_comisiones = sum((Decimal(l["monto_comision"]) for l in lineas), Decimal("0.00"))

        if formato.lower() == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                "comision_id",
                "venta_id",
                "vendedor_id",
                "fecha_venta",
                "monto_venta",
                "monto_comision",
                "estado",
                "periodo_id",
                "periodo_origen",
                "ajuste_de",
                "motivo",
            ])
            for l in lineas:
                writer.writerow([
                    l["comision_id"],
                    l["venta_id"],
                    l["vendedor_id"],
                    l["fecha_venta"],
                    l["monto_venta"],
                    l["monto_comision"],
                    l["estado"],
                    l["periodo_id"],
                    l["periodo_origen"],
                    l["ajuste_de"] or "",
                    l["motivo"] or "",
                ])
            return buf.getvalue().encode("utf-8")

        elif formato.lower() == "json":
            payload = {
                "periodo_id": periodo_id,
                "moneda": "USD",
                "lineas": lineas,
                "totales": {
                    "total_comisiones": f"{total_comisiones:.2f}",
                    "total_ventas": f"{total_ventas:.2f}",
                    "numero_lineas": len(lineas),
                },
            }
            return json.dumps(payload, indent=2).encode("utf-8")
        else:
            raise ValueError(f"Formato no soportado: {formato}")


class DobleAnfitrionesService:
    """Doble de anfitriones para pruebas de cobro y pausa (RF-ANF-08)."""

    def __init__(self) -> None:
        hoy = date.today()
        self.estados_cuenta: dict[str, dict[str, Any]] = {
            "ec_octubre": {
                "estado_cuenta_id": "ec_octubre",
                "anfitrion_id": "anf_1",
                "periodo": "2026-10",
                "total": Decimal("150.00"),
                "estado": "emitido",
                "vence_en": hoy + timedelta(days=14),
                "pagado_en": None,
                "pagado_por": None,
            },
            "ec_vencido": {
                "estado_cuenta_id": "ec_vencido",
                "anfitrion_id": "anf_2",
                "periodo": "2026-09",
                "total": Decimal("220.00"),
                "estado": "vencido",
                "vence_en": hoy - timedelta(days=16),
                "pagado_en": None,
                "pagado_por": None,
            },
        }
        self.hospedajes_pausados: set[str] = set()

    def registrar_pago(self, estado_cuenta_id: str, actor_id: str) -> dict[str, Any]:
        if estado_cuenta_id not in self.estados_cuenta:
            raise ValueError(f"Estado de cuenta {estado_cuenta_id} no encontrado")
        ec = self.estados_cuenta[estado_cuenta_id]
        ahora = datetime.now(timezone.utc)
        ec["estado"] = "pagado"
        ec["pagado_en"] = ahora
        ec["pagado_por"] = actor_id
        return dict(ec)

    def pausar_hospedajes_por_cobro_vencido(self, dias_tolerancia: int = 15) -> list[str]:
        hoy = date.today()
        pausados = []
        for ec_id, ec in self.estados_cuenta.items():
            if ec["estado"] in {"emitido", "vencido"}:
                dias_vencido = (hoy - ec["vence_en"]).days
                if dias_vencido >= dias_tolerancia:
                    ec["estado"] = "vencido"
                    hosp_id = f"hosp_{ec['anfitrion_id']}"
                    self.hospedajes_pausados.add(hosp_id)
                    pausados.append(hosp_id)
        return pausados


class DobleArmJarvisService:
    """Doble de arm_jarvis para pruebas de panel_operativo (RF-PAN-02, RF-PAN-03, RF-PAN-06)."""

    def __init__(
        self,
        comisiones: Any = None,
        canal: Any = None,
        crm: Any = None,
    ) -> None:
        self.comisiones = comisiones
        self.canal = canal
        self.crm = crm
        self.sin_regla: set[str] = set()
        self.publicaciones_crm: list[dict[str, Any]] = []
        self.alertas_crm: list[str] = []
        self.notificaciones_vendedor: list[dict[str, Any]] = []
        self.configuracion: dict[str, Any] = {
            "notificaciones": {"al_validar": True, "al_rechazar": True}
        }

        # Inicializar ventas sintéticas
        ahora = datetime.now(timezone.utc)
        self.ventas: dict[str, Venta] = {
            "V-2026-0106": Venta(
                venta_id="V-2026-0106",
                ticket="V-2026-0106",
                vendedor_id="usr_vendedor_ana",
                extraida=VentaExtraida(
                    cliente_token="Carlos Soto",
                    telefono_cliente_token="+593991234567",
                    producto="Glamping San Pablo",
                    propiedad_id="glamping",
                    monto=Decimal("200.00"),
                    moneda="USD",
                    fecha_venta=date(2026, 10, 15),
                    confianza=0.98,
                    campos_faltantes=(),
                    es_venta=True,
                ),
                texto_original_token="reserva domo 200 usd pagado por Carlos Soto",
                estado=EstadoVenta.POR_VALIDAR,
                comision_estimada=Decimal("20.00"),
                comision_fijada=None,
                reserva_ref="RES-GLAMP-106",
                creada=ahora,
                actualizada=ahora,
            ),
            "V-2026-0107": Venta(
                venta_id="V-2026-0107",
                ticket="V-2026-0107",
                vendedor_id="usr_vendedor_juan",
                extraida=VentaExtraida(
                    cliente_token="María López",
                    telefono_cliente_token="+593998888888",
                    producto="Depa Centro",
                    propiedad_id="departamento_centro",
                    monto=Decimal("450.00"),
                    moneda="USD",
                    fecha_venta=date(2026, 10, 15),
                    confianza=0.85,
                    campos_faltantes=("fecha",),
                    es_venta=True,
                ),
                texto_original_token="vendí 3 noches depa centro a María López, 450, llega el 15",
                estado=EstadoVenta.POR_VALIDAR,
                comision_estimada=Decimal("45.00"),
                comision_fijada=None,
                reserva_ref=None,
                creada=ahora,
                actualizada=ahora,
            ),
            "V-2026-0001": Venta(
                venta_id="V-2026-0001",
                ticket="V-2026-0001",
                vendedor_id="usr_vendedor_juan",
                extraida=VentaExtraida(
                    cliente_token="Pedro Gómez",
                    telefono_cliente_token="+593997777777",
                    producto="Depa Centro",
                    propiedad_id="departamento_centro",
                    monto=Decimal("400.00"),
                    moneda="USD",
                    fecha_venta=date(2026, 10, 10),
                    confianza=0.95,
                    campos_faltantes=(),
                    es_venta=True,
                ),
                texto_original_token="Pedro Gómez depa centro 400",
                estado=EstadoVenta.VALIDADA,
                comision_estimada=Decimal("30.00"),
                comision_fijada=Decimal("30.00"),
                reserva_ref="RES-DEP-101",
                creada=ahora,
                actualizada=ahora,
            ),
            "V-2026-0002": Venta(
                venta_id="V-2026-0002",
                ticket="V-2026-0002",
                vendedor_id="usr_vendedor_ana",
                extraida=VentaExtraida(
                    cliente_token="Elena Castro",
                    telefono_cliente_token="+593996666666",
                    producto="Glamping San Pablo",
                    propiedad_id="glamping",
                    monto=Decimal("300.00"),
                    moneda="USD",
                    fecha_venta=date(2026, 9, 20),
                    confianza=0.99,
                    campos_faltantes=(),
                    es_venta=True,
                ),
                texto_original_token="Elena Castro glamping 300 usd",
                estado=EstadoVenta.PUBLICADA,
                comision_estimada=Decimal("30.00"),
                comision_fijada=Decimal("30.00"),
                reserva_ref="RES-GLAMP-102",
                creada=ahora,
                actualizada=ahora,
            ),
            "V-2026-0003": Venta(
                venta_id="V-2026-0003",
                ticket="V-2026-0003",
                vendedor_id="usr_vendedor_juan",
                extraida=VentaExtraida(
                    cliente_token="Luis Mera",
                    telefono_cliente_token="+593995555555",
                    producto="Depa Centro",
                    propiedad_id="departamento_centro",
                    monto=Decimal("250.00"),
                    moneda="USD",
                    fecha_venta=date(2026, 10, 12),
                    confianza=0.90,
                    campos_faltantes=(),
                    es_venta=True,
                ),
                texto_original_token="Luis Mera 250 depa",
                estado=EstadoVenta.NO_PUBLICADA,
                comision_estimada=Decimal("25.00"),
                comision_fijada=Decimal("25.00"),
                reserva_ref=None,
                creada=ahora,
                actualizada=ahora,
            ),
        }

        self.transiciones: dict[str, list[Transicion]] = {
            vid: [
                Transicion(
                    venta_id=vid,
                    de=EstadoVenta.POR_VALIDAR,
                    a=v.estado,
                    actor_id="sistema",
                    rol="sistema",
                    motivo="Ingesta automática",
                    timestamp=ahora,
                )
            ]
            for vid, v in self.ventas.items()
        }

    def listar(
        self,
        estado: EstadoVenta | None = None,
        vendedor_id: str | None = None,
        periodo: str | None = None,
        pagina: int = 1,
    ) -> tuple[Venta, ...]:
        resultado = []
        for v in self.ventas.values():
            if estado is not None and v.estado != estado:
                continue
            if vendedor_id is not None and v.vendedor_id != vendedor_id:
                continue
            resultado.append(v)
        return tuple(resultado)

    def detalle(self, venta_id: str) -> tuple[Venta, tuple[Transicion, ...]]:
        if venta_id not in self.ventas:
            raise ErrorArm("venta_no_encontrada", f"No se encontró la venta {venta_id}")
        return self.ventas[venta_id], tuple(self.transiciones.get(venta_id, []))

    def validar(self, venta_id: str, actor: Any, correcciones: Mapping[str, Any] | None = None) -> Venta:
        if venta_id not in self.ventas:
            raise ErrorArm("venta_no_encontrada", f"No se encontró la venta {venta_id}")
        venta = self.ventas[venta_id]
        if venta.estado != EstadoVenta.POR_VALIDAR:
            raise ErrorArm("conflicto_estado", f"La venta ya fue procesada (estado actual: {venta.estado.value})")
        if venta_id in self.sin_regla:
            raise ErrorArm("sin_regla_vigente", "Sin regla de comisión aplicable")

        if self.comisiones is not None and getattr(self.comisiones, "periodos_cerrados", None):
            fecha_v = venta.extraida.fecha_venta
            p_id = f"{fecha_v.year}-{fecha_v.month:02d}" if fecha_v else "2026-10"
            if p_id in self.comisiones.periodos_cerrados:
                raise PeriodoCerrado(f"El período {p_id} se encuentra cerrado e inmutable")

        actor_id = getattr(actor, "remitente_token", str(actor))
        rol = getattr(actor, "rol", "lider")
        rol_str = rol.value if hasattr(rol, "value") else str(rol)

        nueva_extraida = venta.extraida
        if correcciones:
            # Aplicar correcciones a campos extraídos
            campos_dict = {
                "cliente_token": correcciones.get("cliente", venta.extraida.cliente_token),
                "monto": Decimal(str(correcciones["monto"])) if "monto" in correcciones else venta.extraida.monto,
                "producto": correcciones.get("producto", venta.extraida.producto),
                "fecha_venta": correcciones.get("fecha_venta", venta.extraida.fecha_venta),
                "campos_faltantes": (),
            }
            nueva_extraida = replace(nueva_extraida, **campos_dict)

        fijada = venta.comision_estimada or Decimal("45.00")
        if self.comisiones is not None and hasattr(self.comisiones, "fijar"):
            self.comisiones.fijar(venta_id)

        ahora = datetime.now(timezone.utc)
        nueva_venta = replace(
            venta,
            estado=EstadoVenta.VALIDADA,
            extraida=nueva_extraida,
            comision_fijada=fijada,
            actualizada=ahora,
        )
        self.ventas[venta_id] = nueva_venta

        self.transiciones.setdefault(venta_id, []).append(
            Transicion(
                venta_id=venta_id,
                de=EstadoVenta.POR_VALIDAR,
                a=EstadoVenta.VALIDADA,
                actor_id=actor_id,
                rol=rol_str,
                motivo="Validación manual por líder comercial",
                timestamp=ahora,
            )
        )

        # Notificar al vendedor de forma privada
        self.notificaciones_vendedor.append({
            "vendedor_id": venta.vendedor_id,
            "evento": "comision_validada",
            "comision": fijada,
            "ticket": venta.ticket,
        })
        if self.canal is not None and hasattr(self.canal, "enviar_plantilla"):
            from features.canal_whatsapp.canal_whatsapp_service import Plantilla
            self.canal.enviar_plantilla(
                destinatario="+593998888888",
                plantilla=Plantilla(
                    nombre="comision_validada",
                    idioma="es",
                    variables=(venta.ticket, str(fijada)),
                ),
            )

        # Encolar publicación en CRM firmada e idempotente
        self.publicaciones_crm.append({
            "venta_id": venta_id,
            "ticket": venta.ticket,
            "monto": nueva_extraida.monto,
            "estado": "encolada",
        })

        return nueva_venta

    def rechazar(self, venta_id: str, actor: Any, motivo: str) -> Venta:
        if venta_id not in self.ventas:
            raise ErrorArm("venta_no_encontrada", f"No se encontró la venta {venta_id}")
        venta = self.ventas[venta_id]
        if venta.estado != EstadoVenta.POR_VALIDAR:
            raise ErrorArm("conflicto_estado", f"La venta ya fue procesada (estado actual: {venta.estado.value})")

        if self.comisiones is not None and getattr(self.comisiones, "periodos_cerrados", None):
            fecha_v = venta.extraida.fecha_venta
            p_id = f"{fecha_v.year}-{fecha_v.month:02d}" if fecha_v else "2026-10"
            if p_id in self.comisiones.periodos_cerrados:
                raise PeriodoCerrado(f"El período {p_id} se encuentra cerrado e inmutable")

        actor_id = getattr(actor, "remitente_token", str(actor))
        rol = getattr(actor, "rol", "lider")
        rol_str = rol.value if hasattr(rol, "value") else str(rol)

        ahora = datetime.now(timezone.utc)
        nueva_venta = replace(
            venta,
            estado=EstadoVenta.RECHAZADA,
            comision_estimada=Decimal("0"),
            comision_fijada=Decimal("0"),
            actualizada=ahora,
        )
        self.ventas[venta_id] = nueva_venta

        self.transiciones.setdefault(venta_id, []).append(
            Transicion(
                venta_id=venta_id,
                de=EstadoVenta.POR_VALIDAR,
                a=EstadoVenta.RECHAZADA,
                actor_id=actor_id,
                rol=rol_str,
                motivo=motivo,
                timestamp=ahora,
            )
        )

        # Notificar motivo al vendedor
        self.notificaciones_vendedor.append({
            "vendedor_id": venta.vendedor_id,
            "evento": "venta_rechazada",
            "motivo": motivo,
            "ticket": venta.ticket,
        })
        if self.canal is not None:
            # Si fuera de ventana, usa plantilla
            en_ventana = getattr(self.canal, "en_ventana_24h", lambda _: True)("+593998888888")
            if not en_ventana and hasattr(self.canal, "enviar_plantilla"):
                from features.canal_whatsapp.canal_whatsapp_service import Plantilla
                self.canal.enviar_plantilla(
                    destinatario="+593998888888",
                    plantilla=Plantilla(
                        nombre="venta_rechazada",
                        idioma="es",
                        variables=(venta.ticket, motivo),
                    ),
                )

        return nueva_venta

    def anular(self, venta_id: str, actor: Any, motivo: str) -> Venta:
        if venta_id not in self.ventas:
            raise ErrorArm("venta_no_encontrada", f"No se encontró la venta {venta_id}")
        venta = self.ventas[venta_id]

        actor_id = getattr(actor, "remitente_token", str(actor))
        rol = getattr(actor, "rol", "lider")
        rol_str = rol.value if hasattr(rol, "value") else str(rol)
        if rol_str != "administrador":
            raise ErrorArm("rol_no_autorizado", "Solo el administrador puede anular una venta.")

        if self.comisiones is not None and getattr(self.comisiones, "periodos_cerrados", None):
            fecha_v = venta.extraida.fecha_venta
            p_id = f"{fecha_v.year}-{fecha_v.month:02d}" if fecha_v else "2026-10"
            if p_id in self.comisiones.periodos_cerrados:
                raise PeriodoCerrado(f"El período {p_id} se encuentra cerrado e inmutable")

        ahora = datetime.now(timezone.utc)
        estado_previo = venta.estado
        nueva_venta = replace(
            venta,
            estado=EstadoVenta.ANULADA,
            actualizada=ahora,
        )
        self.ventas[venta_id] = nueva_venta

        self.transiciones.setdefault(venta_id, []).append(
            Transicion(
                venta_id=venta_id,
                de=estado_previo,
                a=EstadoVenta.ANULADA,
                actor_id=actor_id,
                rol=rol_str,
                motivo=motivo,
                timestamp=ahora,
            )
        )

        # Ajuste negativo en comisiones
        if self.comisiones is not None and hasattr(self.comisiones, "ajustar"):
            monto_negativo = -(venta.comision_fijada or Decimal("0"))
            self.comisiones.ajustar(venta_id, actor, monto_negativo, motivo)

        # Publicar evento venta_anulada al CRM
        self.publicaciones_crm.append({
            "venta_id": venta_id,
            "evento": "venta_anulada",
            "motivo": motivo,
        })

        return nueva_venta

    def reintentar_publicacion(self, venta_id: str) -> bool:
        if venta_id not in self.ventas:
            return False
        venta = self.ventas[venta_id]
        if venta.estado == EstadoVenta.NO_PUBLICADA:
            ahora = datetime.now(timezone.utc)
            self.ventas[venta_id] = replace(venta, estado=EstadoVenta.PUBLICADA, actualizada=ahora)
            self.transiciones.setdefault(venta_id, []).append(
                Transicion(
                    venta_id=venta_id,
                    de=EstadoVenta.NO_PUBLICADA,
                    a=EstadoVenta.PUBLICADA,
                    actor_id="sistema",
                    rol="sistema",
                    motivo="Reintento manual exitoso desde panel operativo",
                    timestamp=ahora,
                )
            )
            return True
        return False

    def preguntar_jarvis(self, actor: Any, pregunta: str, conversacion_id: str = "") -> str:
        # RF-PAN-06: solo responde datos del alcance del rol
        rol = getattr(actor, "rol", "lider")
        rol_str = rol.value if hasattr(rol, "value") else str(rol)
        if rol_str not in {"lider", "administrador"}:
            raise ErrorArm("rol_no_autorizado", "Solo líderes y administradores pueden consultar a Jarvis.")

        preg_norm = pregunta.lower()
        if "vendió" in preg_norm or "ventas" in preg_norm:
            return "Ana R. vendió USD 2 250 en 5 ventas validadas en septiembre 2026."

        if "activa" in preg_norm and "aviso" in preg_norm:
            return "Voy a activar «aviso al validar». ¿Confirmas?"

        return "Hola, soy Jarvis. Puedo informarte sobre ventas, comisiones de tu equipo o configuración operativa."

    def aplicar_cambio_configuracion(self, actor: Any, cambio: Mapping[str, Any], confirmado: bool) -> None:
        if not confirmado:
            raise ErrorArm("confirmacion_requerida", "Todo cambio de configuración exige confirmación explícita.")
        for k, v in cambio.items():
            self.configuracion[k] = v


class DobleObservabilidadService:
    def __init__(self) -> None:
        self.logs: list[dict[str, Any]] = []

    def log(self, nivel: str, evento: str, **campos: Any) -> None:
        self.logs.append({"nivel": nivel, "evento": evento, **campos})
