# ¤agente-enrutador
# ¤¤machine-learning-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Compuerta pública de la sala agente (RF-AG-01..07)."""
from __future__ import annotations

import threading
import uuid
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from features.agente.bucle_herramientas_internal import BucleHerramientas
from features.agente.cache_internal import (
    CacheSemantico,
    contiene_precio_o_disponibilidad,
    seleccionar_modelo,
)
from features.agente.cliente_modelo_internal import ClienteModelo
from features.agente.enrutador_internal import EnrutadorPropiedad
from features.agente.memoria_internal import MemoriaConversacion
from features.agente.prompts_internal import PromptsManager
from features.agente.tipos import (
    ContextoConversacion,
    ConversacionEnSilencio,
    ErrorAgente,
    EstadoAsistente,
    HerramientaFallida,
    ModoAgente,
    ModeloNoDisponible,
    PropiedadAmbigua,
    PropiedadRequeridaNoResuelta,
    ResolucionPropiedad,
    Respuesta,
    TimeoutModelo,
    TopeIteraciones,
)

__all__ = [
    "ContextoConversacion",
    "ModoAgente",
    "ResolucionPropiedad",
    "Respuesta",
    "EstadoAsistente",
    "ErrorAgente",
    "TopeIteraciones",
    "HerramientaFallida",
    "ModeloNoDisponible",
    "TimeoutModelo",
    "PropiedadRequeridaNoResuelta",
    "ConversacionEnSilencio",
    "PropiedadAmbigua",
    "AgenteService",
    "cargar_config",
]

RUTA_CONFIG = Path(__file__).with_name("config_agente.yaml")


# ¤agente-enrutador
def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ¤agente-enrutador
class _DobleObservabilidadNulo:
    def iniciar_traza(self, *args: Any, **kwargs: Any) -> str:
        return "traza-nula"

    def cerrar_traza(self, *args: Any, **kwargs: Any) -> None:
        pass

    def log(self, *args: Any, **kwargs: Any) -> None:
        pass

    def span(self, *args: Any, **kwargs: Any) -> Any:
        return nullcontext()


# ¤agente-enrutador
class _DobleSeguridadNulo:
    def tokenizar(self, texto: str, conversacion_id: str = "") -> str:
        return texto

    def rehidratar(self, texto: str, conversacion_id: str = "") -> str:
        return texto

    def filtrar_salida(self, texto: str, conversacion_id: str = "") -> str:
        return texto


# ¤agente-enrutador
class _DobleHerramientasNulo:
    def listar(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        return ()

    def ejecutar(self, *args: Any, **kwargs: Any) -> Any:
        return None


# ¤agente-enrutador
def cargar_config(ruta: Path = RUTA_CONFIG) -> Mapping[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        return yaml.safe_load(archivo) or {}


# ¤agente-enrutador
class AgenteService:
    """Atiende conversaciones de huéspedes: resuelve prompt, orquesta herramientas, memoria y degradación."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        seguridad: Any = None,
        herramientas: Any = None,
        conocimiento: Any = None,
        canal: Any = None,
        observabilidad: Any = None,
        pms: Any = None,
        memoria: Any = None,
        cliente_modelo: Any = None,
        inferencia: Any = None,
    ) -> None:
        self._config = config
        self._seguridad = seguridad or _DobleSeguridadNulo()
        self._herramientas = herramientas or _DobleHerramientasNulo()
        self._conocimiento = conocimiento
        self._canal = canal
        self._observabilidad = observabilidad or _DobleObservabilidadNulo()
        self._pms = pms
        self._memoria = memoria or MemoriaConversacion(db_path=config.get("db_path"))
        # Estado del asistente (T-417): Cloud Run atiende varias solicitudes a la vez, así que el estado va bajo candado.
        self._inferencia = inferencia
        self._candado_estado = threading.Lock()
        self._indisponible_desde: datetime | None = None
        self._derivadas = 0
        self._prompts = PromptsManager(config)
        self._enrutador = EnrutadorPropiedad(config)
        # La compuerta de inferencia la construye e inyecta app_core (ADPA §3, ADR-0021); sin ella, falla cerrada.
        self._cliente_modelo = cliente_modelo or ClienteModelo(
            config, observabilidad=self._observabilidad, inferencia=inferencia
        )
        self._cache = CacheSemantico(
            conexion=getattr(self._memoria, "_con_memoria", None),
            db_path=config.get("db_path"),
            config=config,
            conocimiento_service=self._conocimiento,
        )
        self._bucle = BucleHerramientas(
            config=config,
            cliente_modelo=self._cliente_modelo,
            herramientas_service=self._herramientas,
            observabilidad=self._observabilidad,
        )

    # ¤agente-enrutador
    def atender(self, mensaje: Any) -> Respuesta:
        """Entrada principal para procesar un mensaje de usuario (RF-AG-04, RF-AG-05)."""
        conversacion_id = getattr(mensaje, "conversacion_id", None)
        if not conversacion_id:
            conversacion_id = mensaje.get("conversacion_id") if isinstance(mensaje, dict) else str(uuid.uuid4())

        identidad = getattr(mensaje, "identidad", None)
        identidad_token = getattr(identidad, "remitente_token", "token_anonimo") if identidad else "token_anonimo"
        rol = getattr(identidad, "rol", "huesped_potencial")
        rol_valor = rol.value if hasattr(rol, "value") else str(rol)

        # Iniciar traza por mensaje en observabilidad
        mensaje_id = str(uuid.uuid4())
        traza_id = self._observabilidad.iniciar_traza(
            mensaje_id=mensaje_id,
            conversacion_id=conversacion_id,
            canal="huespedes",
        )

        # Contexto persistido en memoria (INV_PII_FUERA_DEL_MODELO)
        contexto = self._memoria.obtener_conversacion(conversacion_id)
        if contexto is None:
            contexto = ContextoConversacion(
                conversacion_id=conversacion_id,
                identidad_token=identidad_token,
                rol=rol_valor,
                propiedad_id="glamping",
                modo=ModoAgente.ACTIVO,
                ventana_24h_hasta=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            self._memoria.guardar_conversacion(contexto)

        # Si la conversación está en silencio por handoff activo
        if contexto.modo == ModoAgente.SILENCIO:
            self._observabilidad.log(
                "INFO",
                "conversacion_en_silencio",
                conversacion_id=conversacion_id,
                traza_id=traza_id,
            )
            self._observabilidad.cerrar_traza(traza_id, "silencio")
            return Respuesta(texto="", degradada=True)

        # Extraer texto tokenizado del mensaje (INV_PII_FUERA_DEL_MODELO)
        if hasattr(mensaje, "texto_tokenizado") and mensaje.texto_tokenizado:
            texto_tokenizado = mensaje.texto_tokenizado
        elif isinstance(mensaje, dict) and "texto_tokenizado" in mensaje:
            texto_tokenizado = mensaje["texto_tokenizado"]
        else:
            texto_crudo = getattr(mensaje, "texto", str(mensaje))
            texto_tokenizado = self._seguridad.tokenizar(texto_crudo, conversacion_id)

        # Resolver propiedad con el enrutador multi-propiedad (RF-AG-01)
        resolucion = self.resolver_propiedad(texto_tokenizado, contexto)

        # Ante ambigüedad entre dos o más propiedades, preguntar con lista sin invocar herramientas (INV_PROPIEDAD_RESUELTA)
        if resolucion.metodo == "pregunta":
            lista_opciones = tuple(
                (p_id, self._config.get("propiedades", {}).get(p_id, {}).get("nombre", p_id))
                for p_id in (resolucion.candidatas or ("glamping", "departamento_centro"))
            )
            texto_pregunta = "Contamos con varias opciones de hospedaje. ¿A cuál de nuestras propiedades te refieres?"

            self._memoria.guardar_mensaje(
                mensaje_id=mensaje_id,
                conversacion_id=conversacion_id,
                direccion="in",
                tipo="texto",
                contenido_token=texto_tokenizado,
                traza_id=traza_id,
            )
            salida_msg_id = str(uuid.uuid4())
            self._memoria.guardar_mensaje(
                mensaje_id=salida_msg_id,
                conversacion_id=conversacion_id,
                direccion="out",
                tipo="lista",
                contenido_token=texto_pregunta,
                traza_id=traza_id,
            )
            self._observabilidad.cerrar_traza(traza_id, "pregunta_propiedad")
            return Respuesta(
                texto=texto_pregunta,
                lista=lista_opciones,
            )

        propiedad_id = resolucion.propiedad_id or contexto.propiedad_id or "glamping"

        # Persistir propiedad resuelta en memoria si cambió (RF-AG-01 c)
        if contexto.propiedad_id != propiedad_id:
            self._memoria.actualizar_propiedad(conversacion_id, propiedad_id)
            contexto = ContextoConversacion(
                conversacion_id=contexto.conversacion_id,
                identidad_token=contexto.identidad_token,
                rol=contexto.rol,
                propiedad_id=propiedad_id,
                modo=contexto.modo,
                ventana_24h_hasta=contexto.ventana_24h_hasta,
            )

        # Persistir mensaje de entrada en el historial antes de llamar al modelo
        self._memoria.guardar_mensaje(
            mensaje_id=mensaje_id,
            conversacion_id=conversacion_id,
            direccion="in",
            tipo="texto",
            contenido_token=texto_tokenizado,
            traza_id=traza_id,
        )

        # Armar prompt de la propiedad resuelta y registrar hash en la traza (RF-AG-02)
        prompt_texto, prompt_hash = self._prompts.armar_prompt(propiedad_id)
        self._observabilidad.log(
            "INFO",
            "prompt_cargado",
            propiedad_id=propiedad_id,
            hash_prompt=prompt_hash,
            traza_id=traza_id,
        )

        # Listar herramientas autorizadas para el rol y la propiedad (RF-AG-03)
        herramientas_disp = self._herramientas.listar(rol=contexto.rol, propiedad_id=propiedad_id)
        self._observabilidad.log(
            "INFO",
            "herramientas_expuestas",
            rol=contexto.rol,
            propiedad_id=propiedad_id,
            herramientas=[getattr(h, "nombre", str(h)) for h in herramientas_disp],
            traza_id=traza_id,
        )

        # Consulta previa en Caché Semántico (RF-AG-07, INV_CACHE_SIN_PRECIOS)
        resp_cache, sim_cache = self._cache.buscar(texto_tokenizado, propiedad_id=propiedad_id)
        if resp_cache is not None:
            self._observabilidad.log(
                "INFO",
                "cache_semantico_hit",
                conversacion_id=conversacion_id,
                traza_id=traza_id,
                similitud=sim_cache,
                propiedad_id=propiedad_id,
            )
            salida_msg_id = str(uuid.uuid4())
            self._memoria.guardar_mensaje(
                mensaje_id=salida_msg_id,
                conversacion_id=conversacion_id,
                direccion="out",
                tipo="texto",
                contenido_token=resp_cache,
                traza_id=traza_id,
            )
            self._observabilidad.cerrar_traza(traza_id, "cache_hit")
            texto_rehidratado = self._seguridad.filtrar_salida(resp_cache, conversacion_id)
            return Respuesta(
                texto=texto_rehidratado,
                herramientas_usadas=(),
                modelo="cache_semantico",
                tokens_in=0,
                tokens_out=0,
                costo_usd=Decimal("0"),
                degradada=False,
            )

        # Enrutamiento de modelos y registro de decisión en traza (RF-AG-07, OP-09)
        modelo_elegido, razon_enrutamiento = seleccionar_modelo(
            texto=texto_tokenizado,
            herramientas_requeridas=(),
            config=self._config,
        )
        self._observabilidad.log(
            "INFO",
            "decision_enrutamiento_modelo",
            conversacion_id=conversacion_id,
            traza_id=traza_id,
            modelo_elegido=modelo_elegido,
            razon=razon_enrutamiento,
            propiedad_id=propiedad_id,
        )

        # Obtener historial reciente para el modelo (últimos 30 mensajes o 24h, sin el actual)
        historial_completo = self._memoria.obtener_historial_para_modelo(
            conversacion_id=conversacion_id,
            limite=int(self._config.get("memoria", {}).get("mensajes", 30)),
            horas=int(self._config.get("memoria", {}).get("horas", 24)),
        )
        historial_previo = [m for m in historial_completo[:-1]] if historial_completo else []

        # Ejecutar el bucle de herramientas
        respuesta_cruda = self._bucle.ejecutar(
            system_prompt=prompt_texto,
            mensajes_historial=historial_previo,
            mensaje_actual_token=texto_tokenizado,
            identidad=identidad,
            conversacion_id=conversacion_id,
            propiedad_id=propiedad_id,
            herramientas_disponibles=herramientas_disp,
            traza_id=traza_id,
            modelo=modelo_elegido,
            canal=self._canal,
        )

        # Actualizar caché semántico si la respuesta no es degradada y cumple INV_CACHE_SIN_PRECIOS
        if not respuesta_cruda.degradada:
            guardado = self._cache.guardar(
                consulta=texto_tokenizado,
                respuesta=respuesta_cruda.texto,
                propiedad_id=propiedad_id,
            )
            if guardado:
                self._observabilidad.log(
                    "INFO",
                    "cache_semantico_guardado",
                    conversacion_id=conversacion_id,
                    traza_id=traza_id,
                    propiedad_id=propiedad_id,
                )
            else:
                if contiene_precio_o_disponibilidad(respuesta_cruda.texto) or contiene_precio_o_disponibilidad(texto_tokenizado):
                    self._observabilidad.log(
                        "INFO",
                        "cache_semantico_rechazado_por_precio_o_disponibilidad",
                        conversacion_id=conversacion_id,
                        traza_id=traza_id,
                        invariante="INV_CACHE_SIN_PRECIOS",
                    )

        # Rehidratar salida con filtrado de seguridad antes de entregar al usuario (INV_PII_FUERA_DEL_MODELO)
        texto_rehidratado = self._seguridad.filtrar_salida(respuesta_cruda.texto, conversacion_id)

        # Guardar mensaje saliente tokenizado en memoria (sin PII)
        salida_msg_id = str(uuid.uuid4())
        self._memoria.guardar_mensaje(
            mensaje_id=salida_msg_id,
            conversacion_id=conversacion_id,
            direccion="out",
            tipo="texto",
            contenido_token=respuesta_cruda.texto,
            traza_id=traza_id,
        )

        # Cerrar traza
        resultado_traza = "degradada" if respuesta_cruda.degradada else "resuelta"
        self._observabilidad.cerrar_traza(traza_id, resultado_traza)

        # R4 de T-417: una respuesta degradada con texto es un huésped enviado al contacto humano.
        if respuesta_cruda.degradada and texto_rehidratado:
            self._observar_estado(derivada=True)

        return Respuesta(
            texto=texto_rehidratado,
            botones=respuesta_cruda.botones,
            lista=respuesta_cruda.lista,
            herramientas_usadas=respuesta_cruda.herramientas_usadas,
            chunks_citados=respuesta_cruda.chunks_citados,
            modelo=respuesta_cruda.modelo,
            tokens_in=respuesta_cruda.tokens_in,
            tokens_out=respuesta_cruda.tokens_out,
            costo_usd=respuesta_cruda.costo_usd,
            degradada=respuesta_cruda.degradada,
            acuse_emitido=respuesta_cruda.acuse_emitido,
        )

    # ¤agente-enrutador
    def estado_asistente(self) -> EstadoAsistente:
        """Informa si el asistente está disponible y por qué (RF-AG-05). No llama al modelo ni escribe nada."""
        return self._observar_estado(derivada=False)

    def _observar_estado(self, derivada: bool) -> EstadoAsistente:
        disponible, motivo = self._leer_inferencia()
        with self._candado_estado:
            if disponible:
                self._indisponible_desde = None
                self._derivadas = 0
                return EstadoAsistente(True, "", None, 0)
            if self._indisponible_desde is None:
                self._indisponible_desde = _ahora()
            if derivada:
                self._derivadas += 1
            return EstadoAsistente(False, motivo, self._indisponible_desde, self._derivadas)

    def _leer_inferencia(self) -> tuple[bool, str]:
        if self._inferencia is None:
            return False, "sin_inferencia"
        try:
            estado = self._inferencia.estado()
            return bool(estado.disponible), str(estado.motivo or "")
        except Exception:
            return False, "estado_inferencia_ilegible"

    # ¤agente-enrutador
    def contexto(self, conversacion_id: str) -> ContextoConversacion:
        """Devuelve el contexto de una conversación (RF-AG-06)."""
        ctx = self._memoria.obtener_conversacion(conversacion_id)
        if ctx is None:
            raise ErrorAgente("conversacion_no_encontrada", f"No se encontró conversación con id {conversacion_id}")
        return ctx

    # ¤agente-enrutador
    def entrar_en_silencio(self, conversacion_id: str, motivo: str) -> None:
        """Pone la conversación en modo silencio debido a escalamiento/handoff."""
        self._memoria.actualizar_modo(conversacion_id, ModoAgente.SILENCIO)
        self._observabilidad.log("INFO", "entrar_en_silencio", conversacion_id=conversacion_id, motivo=motivo)

    # ¤agente-enrutador
    def reanudar(self, conversacion_id: str) -> None:
        """Reanuda la conversación tras terminar el handoff."""
        self._memoria.actualizar_modo(conversacion_id, ModoAgente.ACTIVO)
        self._observabilidad.log("INFO", "reanudar_conversacion", conversacion_id=conversacion_id)

    # ¤agente-enrutador
    def resolver_propiedad(
        self,
        mensaje: Any,
        contexto: ContextoConversacion | None = None,
    ) -> ResolucionPropiedad:
        """RF-AG-01: Determina la propiedad (glamping o departamento) por código, nombre, dirección o contexto."""
        return self._enrutador.resolver(mensaje, contexto)

    # ¤agente-enrutador
    def herramientas_para(self, rol: str, propiedad_id: str | None = None) -> tuple[str, ...]:
        """RF-AG-03: Retorna las herramientas autorizadas para el rol según la allowlist canónica."""
        from features.seguridad.seguridad_service import ALLOWLIST_CANONICA
        rol_clave = rol.value if hasattr(rol, "value") else str(rol)
        return tuple(ALLOWLIST_CANONICA.get(rol_clave, ()))

    # ¤agente-enrutador
    def enviar_checkins_del_dia(self, fecha: date) -> int:
        """RF-AG-08, US-03: Envía instrucciones de check-in para reservas que llegan hoy (INV_ENVIO_UNICO)."""
        reservas: Sequence[Any] = ()
        if self._pms is not None and hasattr(self._pms, "reservas_con_llegada"):
            reservas = self._pms.reservas_con_llegada(fecha)
        elif hasattr(self._herramientas, "reservas_con_llegada"):
            reservas = self._herramientas.reservas_con_llegada(fecha)
        elif hasattr(self._herramientas, "_pms") and hasattr(self._herramientas._pms, "reservas_con_llegada"):
            reservas = self._herramientas._pms.reservas_con_llegada(fecha)

        enviados = 0
        fecha_str = fecha.isoformat()
        plantilla_nombre = "instrucciones_checkin"

        for r in reservas:
            codigo = getattr(r, "codigo", None) or (r.get("codigo") if isinstance(r, dict) else None)
            if not codigo:
                continue

            insertado = self._memoria.registrar_envio_programado(
                codigo_reserva=codigo,
                plantilla=plantilla_nombre,
                fecha=fecha_str,
            )
            if not insertado:
                continue

            telefono = getattr(r, "huesped_telefono", None) or (r.get("huesped_telefono") if isinstance(r, dict) else "")
            nombre = getattr(r, "huesped_nombre", None) or (r.get("huesped_nombre") if isinstance(r, dict) else "Huésped")
            propiedad = getattr(r, "propiedad_id", None) or (r.get("propiedad_id") if isinstance(r, dict) else "glamping")

            if self._canal is not None and hasattr(self._canal, "enviar_plantilla"):
                try:
                    from features.canal_whatsapp.canal_whatsapp_service import Plantilla
                    self._canal.enviar_plantilla(
                        destinatario=str(telefono),
                        plantilla=Plantilla(
                            nombre=plantilla_nombre,
                            idioma="es",
                            variables=(str(nombre), str(propiedad), "15:00"),
                        ),
                    )
                except Exception as exc:
                    self._observabilidad.log(
                        "ERROR",
                        "error_envio_checkin_programado",
                        codigo_reserva=codigo,
                        error=str(exc),
                    )
            enviados += 1

        self._observabilidad.log(
            "INFO",
            "checkins_del_dia_enviados",
            fecha=fecha_str,
            enviados=enviados,
        )
        return enviados

    # ¤agente-enrutador
    def evaluar(self, archivo_casos: Path) -> dict[str, float]:
        """Evalúa el set de casos de prueba del enrutador y retorna precisión."""
        return self._enrutador.evaluar(archivo_casos)
