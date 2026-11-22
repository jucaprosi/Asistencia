# ¤herramientas-mcp
# ¤¤backend-developer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Implementación interna del catálogo, validación y ejecución de herramientas MCP (RF-MCP-01..07)."""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
import uuid

import jsonschema

from features.herramientas_glamping.tipos import (
    DefinicionHerramienta,
    EntradaInvalida,
    ErrorHerramientas,
    HerramientaDeshabilitada,
    HerramientaNoAutorizada,
    ReservaNoAutorizada,
    ResultadoHerramienta,
    SalaDestinoFallida,
)

__all__ = [
    "CargadorEsquemas",
    "ValidadorEntrada",
    "GestorIntentosCheckin",
    "EjecutorHerramientas",
]

DIR_ESQUEMAS = Path(__file__).resolve().parent / "esquemas"


# ¤herramientas-mcp
class CargadorEsquemas:
    """Carga y compila esquemas JSON de herramientas."""

    def __init__(self, dir_esquemas: Path = DIR_ESQUEMAS) -> None:
        self._dir = dir_esquemas
        self._cache: dict[str, DefinicionHerramienta] = {}

    def cargar(self, nombre: str, config_item: Mapping[str, Any] | None = None) -> DefinicionHerramienta:
        if nombre in self._cache:
            return self._cache[nombre]

        ruta = self._dir / f"{nombre}.json"
        if not ruta.is_file():
            if config_item and "esquema" in config_item:
                ruta_alt = Path(__file__).resolve().parent / config_item["esquema"]
                if ruta_alt.is_file():
                    ruta = ruta_alt
                else:
                    raise FileNotFoundError(f"No existe el archivo de esquema para {nombre}: {ruta}")
            else:
                raise FileNotFoundError(f"No existe el archivo de esquema para {nombre}: {ruta}")

        with ruta.open(encoding="utf-8") as f:
            contenido = json.load(f)

        descripcion = contenido.get("descripcion", "")
        roles = tuple(contenido.get("roles", []))
        sala_destino = contenido.get("sala_destino", "")
        entrada = contenido.get("entrada", {})
        salida = contenido.get("salida", {})

        if config_item:
            if "roles" in config_item:
                roles = tuple(config_item["roles"])
            if "sala_destino" in config_item:
                sala_destino = config_item["sala_destino"]

        definicion = DefinicionHerramienta(
            nombre=nombre,
            descripcion=descripcion,
            esquema_entrada=entrada,
            esquema_salida=salida,
            roles=roles,
            sala_destino=sala_destino,
        )
        self._cache[nombre] = definicion
        return definicion


# ¤herramientas-mcp
class ValidadorEntrada:
    """Valida los argumentos de entrada contra el JSON Schema de la herramienta."""

    @staticmethod
    def validar(nombre: str, entrada: Mapping[str, Any], esquema: Mapping[str, Any]) -> None:
        try:
            validador = jsonschema.Draft202012Validator(esquema)
            errores = list(validador.iter_errors(entrada))
            if errores:
                primer_error = errores[0]
                campo = ".".join(str(p) for p in primer_error.absolute_path) or "raíz"
                mensaje = f"Error en '{campo}': {primer_error.message}"
                raise EntradaInvalida(
                    mensaje_usuario=f"Entrada inválida para '{nombre}': {mensaje}",
                    detalle_tecnico=f"{campo}: {primer_error.message}",
                )
        except jsonschema.exceptions.SchemaError as exc:
            raise EntradaInvalida(
                mensaje_usuario=f"Esquema inválido para '{nombre}'",
                detalle_tecnico=str(exc),
            ) from exc


# ¤herramientas-mcp
class GestorIntentosCheckin:
    """Rastrea intentos no autorizados de check-in (5 en 24h escalan a humano)."""

    def __init__(self, limite_fallos: int = 5, ventana_horas: int = 24) -> None:
        self._limite = limite_fallos
        self._ventana = timedelta(hours=ventana_horas)
        self._intentos: dict[str, list[datetime]] = {}

    def registrar_fallo(self, remitente_token: str) -> bool:
        """Registra un intento fallido y devuelve True si superó el límite de la ventana."""
        ahora = datetime.now(timezone.utc)
        limite_tiempo = ahora - self._ventana
        historial = self._intentos.setdefault(remitente_token, [])
        historial = [t for t in historial if t >= limite_tiempo]
        historial.append(ahora)
        self._intentos[remitente_token] = historial
        return len(historial) >= self._limite


# ¤herramientas-mcp
class EjecutorHerramientas:
    """Orquesta la autorización, validación y despacho de herramientas a sus salas dueñas."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any,
        pms: Any,
        conocimiento: Any,
        crm: Any,
        arm: Any = None,
        comisiones: Any = None,
        anfitriones: Any = None,
        observabilidad: Any = None,
        cargador: CargadorEsquemas | None = None,
        validador: ValidadorEntrada | None = None,
        gestor_checkin: GestorIntentosCheckin | None = None,
    ) -> None:
        self._config = config
        self._seguridad = seguridad
        self._pms = pms
        self._conocimiento = conocimiento
        self._crm = crm
        self._arm = arm
        self._comisiones = comisiones
        self._anfitriones = anfitriones
        self._observabilidad = observabilidad
        self._cargador = cargador or CargadorEsquemas()
        self._validador = validador or ValidadorEntrada()
        self._gestor_checkin = gestor_checkin or GestorIntentosCheckin()

        self._mapa_config = {
            h.get("nombre"): h for h in self._config.get("herramientas", []) if h.get("nombre")
        }

    # ¤herramientas-mcp
    def obtener_definicion(self, nombre: str) -> DefinicionHerramienta:
        cfg = self._mapa_config.get(nombre)
        return self._cargador.cargar(nombre, cfg)

    # ¤herramientas-mcp
    def listar(self, rol: str, propiedad_id: str | None = None) -> tuple[DefinicionHerramienta, ...]:
        resultado: list[DefinicionHerramienta] = []
        for nombre, cfg in self._mapa_config.items():
            if not cfg.get("habilitada", False):
                continue
            roles_declarados = cfg.get("roles", [])
            if rol in roles_declarados:
                try:
                    definicion = self.obtener_definicion(nombre)
                    resultado.append(definicion)
                except FileNotFoundError:
                    continue
        return tuple(resultado)

    # ¤herramientas-mcp
    def ejecutar(
        self,
        nombre: str,
        entrada: Mapping[str, Any],
        identidad: Any,
        conversacion_id: str,
    ) -> ResultadoHerramienta:
        inicio = time.perf_counter()

        # 1. Verificar existencia y habilitación
        cfg = self._mapa_config.get(nombre)
        if not cfg or not cfg.get("habilitada", False):
            raise HerramientaDeshabilitada(nombre)

        # 2. Cargar definición y validar esquema de entrada
        definicion = self.obtener_definicion(nombre)
        self._validador.validar(nombre, entrada, definicion.esquema_entrada)

        # 3. Autorización de seguridad (INV_ALLOWLIST_POR_ACCION)
        rol_valor = getattr(identidad, "rol", identidad)
        if hasattr(rol_valor, "value"):
            rol_str = str(rol_valor.value)
        else:
            rol_str = str(rol_valor)

        veredicto = self._seguridad.autorizar(rol_str, nombre)
        if not getattr(veredicto, "permitido", False):
            motivo = getattr(veredicto, "motivo", "No permitido por política de seguridad")
            raise HerramientaNoAutorizada(
                mensaje_usuario=f"El rol '{rol_str}' no está autorizado para ejecutar '{nombre}'.",
                detalle_tecnico=motivo,
            )

        # 4. Despacho a sala dueña
        remitente_token = getattr(identidad, "remitente_token", str(identidad))
        try:
            salida = self._despachar(nombre, entrada, remitente_token, rol_str, conversacion_id, identidad=identidad)
        except ErrorHerramientas:
            raise
        except Exception as exc:
            msg = getattr(exc, "mensaje_usuario", f"Fallo en la sala '{definicion.sala_destino}' al procesar '{nombre}'.")
            raise SalaDestinoFallida(
                sala=definicion.sala_destino,
                mensaje_usuario=msg,
                detalle_tecnico=str(exc),
            ) from exc

        duracion_ms = int((time.perf_counter() - inicio) * 1000)
        return ResultadoHerramienta(
            nombre=nombre,
            salida=salida,
            error=None,
            duracion_ms=duracion_ms,
        )

    # ¤herramientas-mcp
    def _despachar(
        self,
        nombre: str,
        entrada: Mapping[str, Any],
        remitente_token: str,
        rol_str: str,
        conversacion_id: str,
        identidad: Any = None,
    ) -> dict[str, Any]:
        if nombre == "consultar_disponibilidad":
            return self._ejecutar_consultar_disponibilidad(entrada)
        elif nombre == "cotizar":
            return self._ejecutar_cotizar(entrada)
        elif nombre == "crear_reserva_preliminar":
            return self._ejecutar_crear_reserva_preliminar(entrada)
        elif nombre == "obtener_instrucciones_checkin":
            return self._ejecutar_obtener_instrucciones_checkin(entrada, remitente_token, rol_str, conversacion_id)
        elif nombre == "reportar_incidencia":
            return self._ejecutar_reportar_incidencia(entrada, conversacion_id)
        elif nombre == "solicitar_humano":
            return self._ejecutar_solicitar_humano(entrada, conversacion_id)
        elif nombre == "buscar_contacto_crm":
            return self._ejecutar_buscar_contacto_crm(entrada)
        elif nombre == "crear_oportunidad_crm":
            return self._ejecutar_crear_oportunidad_crm(entrada)
        elif nombre == "solicitar_reserva":
            return self._ejecutar_solicitar_reserva(entrada)
        elif nombre == "responder_solicitud":
            anfitrion_id = getattr(identidad, "sujeto_id", None) or getattr(identidad, "remitente_token", str(identidad))
            return self._ejecutar_responder_solicitud(entrada, anfitrion_id)
        elif nombre == "reportar_resultado_estadia":
            anfitrion_id = getattr(identidad, "sujeto_id", None) or getattr(identidad, "remitente_token", str(identidad))
            return self._ejecutar_reportar_resultado_estadia(entrada, anfitrion_id)
        elif nombre == "actualizar_calendario":
            anfitrion_id = getattr(identidad, "sujeto_id", None) or getattr(identidad, "remitente_token", str(identidad))
            return self._ejecutar_actualizar_calendario(entrada, anfitrion_id)
        elif nombre == "registrar_venta":
            vendedor_id = getattr(identidad, "sujeto_id", None) or getattr(identidad, "vendedor_id", None) or getattr(identidad, "remitente_token", str(identidad))
            return self._ejecutar_registrar_venta(entrada, vendedor_id)
        elif nombre == "consultar_comision_propia":
            vendedor_id = getattr(identidad, "sujeto_id", None) or getattr(identidad, "vendedor_id", None) or getattr(identidad, "remitente_token", str(identidad))
            return self._ejecutar_consultar_comision_propia(entrada, vendedor_id)
        else:
            raise HerramientaDeshabilitada(nombre)

    # ¤herramientas-mcp
    def _ejecutar_consultar_disponibilidad(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        propiedad_id = str(entrada["propiedad_id"])
        desde = date.fromisoformat(str(entrada["desde"]))
        hasta = date.fromisoformat(str(entrada["hasta"]))
        huespedes = int(entrada["huespedes"])

        disp = self._pms.consultar_disponibilidad(
            propiedad_id=propiedad_id,
            desde=desde,
            hasta=hasta,
            huespedes=huespedes,
        )

        unidades_lista = [
            {
                "unidad_id": getattr(u, "unidad_id", str(u)),
                "nombre": getattr(u, "nombre", "Unidad"),
                "capacidad": getattr(u, "capacidad", huespedes),
            }
            for u in getattr(disp, "unidades", ())
        ]

        alternativas_lista = []
        for alt in getattr(disp, "alternativas", ())[:3]:
            if isinstance(alt, (list, tuple)) and len(alt) >= 3:
                u_id, d_alt, h_alt = alt[0], alt[1], alt[2]
                alternativas_lista.append({
                    "unidad_id": str(u_id),
                    "desde": d_alt.isoformat() if hasattr(d_alt, "isoformat") else str(d_alt),
                    "hasta": h_alt.isoformat() if hasattr(h_alt, "isoformat") else str(h_alt),
                })

        res: dict[str, Any] = {
            "disponible": bool(getattr(disp, "disponible", False)),
            "unidades": unidades_lista,
            "alternativas": alternativas_lista,
        }
        motivo = getattr(disp, "motivo", None)
        if motivo:
            res["motivo"] = str(motivo)
        return res

    # ¤herramientas-mcp
    def _ejecutar_cotizar(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        propiedad_id = str(entrada["propiedad_id"])
        unidad_id = str(entrada["unidad_id"])
        desde = date.fromisoformat(str(entrada["desde"]))
        hasta = date.fromisoformat(str(entrada["hasta"]))
        huespedes = int(entrada["huespedes"])

        cot = self._pms.cotizar(
            propiedad_id=propiedad_id,
            unidad_id=unidad_id,
            desde=desde,
            hasta=hasta,
            huespedes=huespedes,
        )

        total_dec = getattr(cot, "total", Decimal("0.00"))
        if not isinstance(total_dec, Decimal):
            total_dec = Decimal(str(total_dec))

        desglose_lista = []
        for item in getattr(cot, "desglose", ()):
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                concepto, monto = item[0], item[1]
                monto_dec = monto if isinstance(monto, Decimal) else Decimal(str(monto))
                desglose_lista.append({
                    "concepto": str(concepto),
                    "monto": f"{monto_dec:.2f}",
                })

        return {
            "total": f"{total_dec:.2f}",
            "moneda": str(getattr(cot, "moneda", "USD")),
            "desglose": desglose_lista,
            "politica_cancelacion_id": str(getattr(cot, "politica_cancelacion_id", "estricta")),
        }

    # ¤herramientas-mcp
    def _ejecutar_crear_reserva_preliminar(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        propiedad_id = str(entrada["propiedad_id"])
        unidad_id = str(entrada["unidad_id"])
        desde = date.fromisoformat(str(entrada["desde"]))
        hasta = date.fromisoformat(str(entrada["hasta"]))
        huespedes = int(entrada["huespedes"])
        nombre_token = str(entrada["nombre_token"])
        clave_idempotencia = str(entrada["clave_idempotencia"])

        reserva = self._pms.crear_reserva_preliminar(
            propiedad_id=propiedad_id,
            unidad_id=unidad_id,
            desde=desde,
            hasta=hasta,
            huespedes=huespedes,
            huesped_token=nombre_token,
            clave_idempotencia=clave_idempotencia,
        )

        expira_en = getattr(reserva, "expira_en", None)
        if expira_en is None:
            expira_en = datetime.now(timezone.utc) + timedelta(hours=24)
        expira_str = expira_en.isoformat() if hasattr(expira_en, "isoformat") else str(expira_en)

        return {
            "codigo_reserva": str(getattr(reserva, "codigo", "")),
            "estado": "preliminar",
            "expira_en": expira_str,
        }

    # ¤herramientas-mcp
    def _ejecutar_obtener_instrucciones_checkin(
        self,
        entrada: Mapping[str, Any],
        remitente_token: str,
        rol_str: str,
        conversacion_id: str,
    ) -> dict[str, Any]:
        codigo_reserva = str(entrada["codigo_reserva"])

        # Validación estricta de titularidad de la reserva (RF-SEC-08)
        es_titular = False
        if hasattr(self._pms, "validar_titular_local"):
            es_titular = bool(self._pms.validar_titular_local(codigo_reserva, remitente_token))

        if not es_titular:
            # Auditar en seguridad si la compuerta lo soporta
            if hasattr(self._seguridad, "auditar"):
                try:
                    from features.seguridad.seguridad_service import EventoAuditoria, Rol
                    rol_enum = getattr(Rol, rol_str.upper(), Rol.DESCONOCIDO) if hasattr(Rol, rol_str.upper()) else rol_str
                    self._seguridad.auditar(
                        EventoAuditoria(
                            actor_token=remitente_token,
                            rol=rol_enum,
                            accion="obtener_instrucciones_checkin",
                            herramienta="obtener_instrucciones_checkin",
                            resultado="denegado_titular_no_coincide",
                            traza_id="",
                        )
                    )
                except Exception:
                    pass

            # Rastrear intentos fallidos: 5 en 24h escalan a humano
            escalar = self._gestor_checkin.registrar_fallo(remitente_token)
            if escalar and hasattr(self._crm, "solicitar_handoff"):
                try:
                    self._crm.solicitar_handoff(
                        conversacion_id=conversacion_id,
                        zona_id="soporte",
                        resumen=f"5 intentos fallidos de check-in para titular {remitente_token}",
                    )
                except Exception:
                    pass

            raise ReservaNoAutorizada(codigo_reserva)

        instr = self._pms.obtener_instrucciones_checkin(codigo_reserva)
        wifi_ref = getattr(instr, "wifi_clave_token", "[[SECRETO:wifi_clave]]")

        return {
            "propiedad": str(getattr(instr, "propiedad", "")),
            "direccion": str(getattr(instr, "direccion", "")),
            "hora_checkin": str(getattr(instr, "hora_checkin", "15:00")),
            "acceso": list(getattr(instr, "acceso", ())),
            "wifi": {
                "red": str(getattr(instr, "wifi_red", "")),
                "clave_ref": str(wifi_ref),
            },
            "normas": list(getattr(instr, "normas", ())),
            "contacto_emergencia": str(getattr(instr, "contacto_emergencia", "")),
        }

    # ¤herramientas-mcp
    def _ejecutar_reportar_incidencia(
        self,
        entrada: Mapping[str, Any],
        conversacion_id: str,
    ) -> dict[str, Any]:
        propiedad_id = str(entrada["propiedad_id"])
        descripcion = str(entrada["descripcion"])
        categoria = str(entrada["categoria"])
        codigo_reserva = entrada.get("codigo_reserva")

        # Prioridad crítica para fallos de acceso o seguridad física
        if categoria in ("seguridad", "acceso"):
            prioridad = "critica"
            eta_horas = 1.0
        else:
            prioridad = "media"
            eta_horas = 4.0

        # Crear entidad Incidencia para pms_conector
        from features.pms_conector.pms_conector_service import Incidencia
        incidencia_id = f"I-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:4]}"
        incidencia = Incidencia(
            incidencia_id=incidencia_id,
            propiedad_id=propiedad_id,
            unidad_id=None,
            reserva_codigo=str(codigo_reserva) if codigo_reserva else None,
            categoria=categoria,
            prioridad=prioridad,
            descripcion_token=descripcion,
            estado="abierta",
            gestor_id="gestor_zona",
        )

        clave_idem = str(uuid.uuid4())
        inc_creada = self._pms.registrar_incidencia(incidencia, clave_idem)

        # Si es crítica, detona handoff inmediato a humano
        if prioridad == "critica" and hasattr(self._crm, "solicitar_handoff"):
            try:
                self._crm.solicitar_handoff(
                    conversacion_id=conversacion_id,
                    zona_id=propiedad_id,
                    resumen=f"Incidencia crítica de {categoria}: {descripcion}",
                )
            except Exception:
                pass

        return {
            "incidencia_id": str(getattr(inc_creada, "incidencia_id", incidencia_id)),
            "prioridad": prioridad,
            "gestor_asignado": str(getattr(inc_creada, "gestor_id", "gestor_zona") or "gestor_zona"),
            "eta_respuesta_horas": eta_horas,
        }

    # ¤herramientas-mcp
    def _ejecutar_solicitar_humano(
        self,
        entrada: Mapping[str, Any],
        conversacion_id: str,
    ) -> dict[str, Any]:
        propiedad_id = entrada.get("propiedad_id")
        motivo = str(entrada["motivo"])
        resumen = str(entrada["resumen"])

        handoff_id = self._crm.solicitar_handoff(
            conversacion_id=conversacion_id,
            zona_id=str(propiedad_id) if propiedad_id else "general",
            resumen=f"[{motivo}] {resumen}",
        )

        return {
            "handoff_id": str(handoff_id),
            "asignado_a": "gestor_turno",
            "canal": "panel",
            "minutos_estimados": 15,
        }

    # ¤herramientas-mcp
    def _ejecutar_buscar_contacto_crm(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        telefono = entrada.get("telefono_token")
        email = entrada.get("email_token")

        contacto = self._crm.buscar_contacto(
            telefono_token=str(telefono) if telefono else None,
            email_token=str(email) if email else None,
        )

        if contacto:
            return {
                "encontrado": True,
                "contacto_id": str(getattr(contacto, "contacto_id", "")),
            }
        return {"encontrado": False}

    # ¤herramientas-mcp
    def _ejecutar_crear_oportunidad_crm(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        from features.crm_conector.crm_conector_service import Oportunidad

        contacto_id = str(entrada["contacto_id"])
        propiedad_id = str(entrada["propiedad_id"])
        etapa = str(entrada["etapa"])
        monto_raw = entrada.get("monto")
        monto_dec = Decimal(str(monto_raw)) if monto_raw is not None else None

        oportunidad = Oportunidad(
            oportunidad_id=str(uuid.uuid4()),
            contacto_id=contacto_id,
            propiedad_id=propiedad_id,
            etapa=etapa,
            monto=monto_dec,
            crm_ref=None,
        )

        creada = self._crm.crear_oportunidad(oportunidad)
        return {
            "oportunidad_id": str(getattr(creada, "oportunidad_id", oportunidad.oportunidad_id)),
        }

    # ¤herramientas-mcp
    def _ejecutar_solicitar_reserva(self, entrada: Mapping[str, Any]) -> dict[str, Any]:
        codigo_reserva = str(entrada["codigo_reserva"])
        if self._anfitriones is None or not hasattr(self._anfitriones, "solicitar_reserva"):
            raise SalaDestinoFallida(
                sala="anfitriones",
                mensaje_usuario="El servicio de anfitriones no se encuentra disponible.",
            )
        sol = self._anfitriones.solicitar_reserva(codigo_reserva)
        vence_str = sol.vence_en.isoformat() if hasattr(sol.vence_en, "isoformat") else str(sol.vence_en)
        estado_str = sol.estado.value if hasattr(sol.estado, "value") else str(sol.estado)
        return {
            "solicitud": str(sol.solicitud),
            "estado": estado_str,
            "vence_en": vence_str,
        }

    # ¤herramientas-mcp
    def _ejecutar_responder_solicitud(
        self,
        entrada: Mapping[str, Any],
        anfitrion_id: str,
    ) -> dict[str, Any]:
        solicitud = str(entrada["solicitud"])
        acepta = bool(entrada["acepta"])
        motivo = entrada.get("motivo")
        if self._anfitriones is None or not hasattr(self._anfitriones, "responder_solicitud"):
            raise SalaDestinoFallida(
                sala="anfitriones",
                mensaje_usuario="El servicio de anfitriones no se encuentra disponible.",
            )
        sol = self._anfitriones.responder_solicitud(solicitud, anfitrion_id=anfitrion_id, acepta=acepta, motivo=motivo)
        estado_str = sol.estado.value if hasattr(sol.estado, "value") else str(sol.estado)
        return {
            "solicitud": str(sol.solicitud),
            "estado": estado_str,
        }

    # ¤herramientas-mcp
    def _ejecutar_reportar_resultado_estadia(
        self,
        entrada: Mapping[str, Any],
        anfitrion_id: str,
    ) -> dict[str, Any]:
        solicitud = str(entrada["solicitud"])
        resultado = str(entrada["resultado"])
        if self._anfitriones is None or not hasattr(self._anfitriones, "reportar_resultado"):
            raise SalaDestinoFallida(
                sala="anfitriones",
                mensaje_usuario="El servicio de anfitriones no se encuentra disponible.",
            )
        sol = self._anfitriones.reportar_resultado(solicitud, anfitrion_id=anfitrion_id, resultado=resultado)
        estado_str = sol.estado.value if hasattr(sol.estado, "value") else str(sol.estado)
        return {
            "solicitud": str(sol.solicitud),
            "estado": estado_str,
        }

    # ¤herramientas-mcp
    def _ejecutar_actualizar_calendario(
        self,
        entrada: Mapping[str, Any],
        anfitrion_id: str,
    ) -> dict[str, Any]:
        unidad_id = str(entrada["unidad_id"])
        desde = date.fromisoformat(str(entrada["desde"]))
        hasta = date.fromisoformat(str(entrada["hasta"]))
        accion = str(entrada["accion"])
        if self._pms is None or not hasattr(self._pms, "actualizar_calendario"):
            raise SalaDestinoFallida(
                sala="pms_conector",
                mensaje_usuario="El servicio de calendario no se encuentra disponible.",
            )
        afectadas, omitidas = self._pms.actualizar_calendario(
            unidad_id=unidad_id,
            desde=desde,
            hasta=hasta,
            accion=accion,
            actor_id=anfitrion_id,
        )
        return {
            "unidad_id": unidad_id,
            "noches": int(afectadas),
            "omitidas": int(omitidas),
        }

    # ¤herramientas-mcp
    def _ejecutar_registrar_venta(
        self,
        entrada: Mapping[str, Any],
        vendedor_id: str,
    ) -> dict[str, Any]:
        if self._arm is None or not hasattr(self._arm, "registrar_venta"):
            raise SalaDestinoFallida(
                sala="arm_jarvis",
                mensaje_usuario="El servicio ARM Jarvis no se encuentra disponible.",
            )
        texto_original = str(entrada["texto_original"])
        venta_dict = entrada["venta"]

        resultado = self._arm.registrar_venta(
            vendedor_id=vendedor_id,
            texto_original=texto_original,
            venta=venta_dict,
        )

        ticket = str(getattr(resultado, "ticket", resultado.get("ticket") if isinstance(resultado, dict) else ""))
        estado = str(getattr(resultado, "estado", resultado.get("estado") if isinstance(resultado, dict) else "por_validar"))
        if hasattr(estado, "value"):
            estado = estado.value
        posible_dup = bool(getattr(resultado, "posible_duplicado", resultado.get("posible_duplicado", False) if isinstance(resultado, dict) else False))

        com_est_raw = getattr(resultado, "comision_estimada", resultado.get("comision_estimada") if isinstance(resultado, dict) else None)
        salida: dict[str, Any] = {
            "ticket": ticket,
            "estado": "por_validar",
            "posible_duplicado": posible_dup,
        }
        if com_est_raw is not None:
            com_dec = com_est_raw if isinstance(com_est_raw, Decimal) else Decimal(str(com_est_raw))
            salida["comision_estimada"] = f"{com_dec:.2f}"

        return salida

    # ¤herramientas-mcp
    def _ejecutar_consultar_comision_propia(
        self,
        entrada: Mapping[str, Any],
        vendedor_id: str,
    ) -> dict[str, Any]:
        if self._arm is None or not hasattr(self._arm, "consultar_comision_propia"):
            raise SalaDestinoFallida(
                sala="arm_jarvis",
                mensaje_usuario="El servicio ARM Jarvis no se encuentra disponible.",
            )
        periodo = entrada.get("periodo")
        if not periodo:
            hoy = date.today()
            periodo = f"{hoy.year}-{hoy.month:02d}"

        resultado = self._arm.consultar_comision_propia(
            vendedor_id=vendedor_id,
            periodo=periodo,
        )

        validada_raw = getattr(resultado, "validada", resultado.get("validada") if isinstance(resultado, dict) else Decimal("0.00"))
        pendiente_raw = getattr(resultado, "pendiente", resultado.get("pendiente") if isinstance(resultado, dict) else Decimal("0.00"))
        ventas_raw = getattr(resultado, "ventas", resultado.get("ventas") if isinstance(resultado, dict) else 0)
        periodo_res = str(getattr(resultado, "periodo", resultado.get("periodo") if isinstance(resultado, dict) else periodo))

        validada_dec = validada_raw if isinstance(validada_raw, Decimal) else Decimal(str(validada_raw))
        pendiente_dec = pendiente_raw if isinstance(pendiente_raw, Decimal) else Decimal(str(pendiente_raw))

        return {
            "validada": f"{validada_dec:.2f}",
            "pendiente": f"{pendiente_dec:.2f}",
            "ventas": int(ventas_raw),
            "periodo": periodo_res,
        }
