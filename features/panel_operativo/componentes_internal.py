# ¤panel-operativo
# ¤¤frontend-developer
"""Componentes de la UI del panel operativo: TarjetaVenta, HojaCorreccion, DialogoMotivo, ChatJarvis (RF-PAN-02, RF-PAN-06)."""
from __future__ import annotations

import html
import math
from typing import Any, Mapping, Sequence


# ¤panel-operativo
def DialogoMotivo(
    venta_id: str,
    accion: str = "rechazar",
    motivos_sugeridos: Sequence[str] = (
        "Monto incorrecto",
        "Cliente duplicado",
        "Fecha fuera de rango",
        "Cancelación solicitada por cliente",
        "Otro motivo",
    ),
) -> str:
    """Componente modal para captura obligatoria de motivos de rechazo o anulación."""
    opciones = "".join(f'<option value="{m}">{m}</option>' for m in motivos_sugeridos)
    titulo = "Rechazar venta" if accion == "rechazar" else "Anular venta"

    return f"""
    <div class="modal-backdrop" id="modal-motivo-{venta_id}">
      <div class="dialogo-modal tarjeta" role="dialog" aria-labelledby="modal-titulo-{venta_id}">
        <h3 id="modal-titulo-{venta_id}">{titulo}</h3>
        <p class="instruccion-modal">Indica el motivo obligatorio para registrar en la auditoría.</p>
        <div class="campo-formulario">
          <label for="motivo-select-{venta_id}">Motivo frecuente</label>
          <select id="motivo-select-{venta_id}" class="control-select" onchange="seleccionarMotivoRapido('{venta_id}')">
            <option value="">Selecciona un motivo...</option>
            {opciones}
          </select>
        </div>
        <div class="campo-formulario">
          <label for="motivo-texto-{venta_id}">Detalle del motivo</label>
          <textarea id="motivo-texto-{venta_id}" class="control-textarea" rows="3" placeholder="Describe la razón..."></textarea>
        </div>
        <div class="acciones-modal">
          <button class="boton boton-secundario" onclick="cerrarModalMotivo('{venta_id}')">Cancelar</button>
          <button class="boton boton-peligro" onclick="confirmarAccionConMotivo('{venta_id}', '{accion}')">Confirmar</button>
        </div>
      </div>
    </div>
    """


# ¤panel-operativo
def HojaCorreccion(venta: Mapping[str, Any]) -> str:
    """Componente de hoja inferior para editar campos dudosos mostrando el fragmento original."""
    vid = venta.get("venta_id", "")
    ticket = venta.get("ticket", "")
    texto_original = html.escape(str(venta.get("texto_original", "")))
    cliente = html.escape(str(venta.get("cliente", "")))
    monto = str(venta.get("monto", "0.00"))
    producto = html.escape(str(venta.get("producto", "")))
    fecha_venta = str(venta.get("fecha_venta", ""))

    return f"""
    <div class="hoja-inferior" id="hoja-correccion-{vid}">
      <div class="hoja-contenido tarjeta">
        <div class="hoja-cabecera">
          <h3>Corregir datos de venta ({ticket})</h3>
          <button class="boton-cerrar" onclick="cerrarHojaCorreccion('{vid}')" aria-label="Cerrar">×</button>
        </div>
        <div class="fragmento-original">
          <span class="etiqueta-pequena">Texto original del vendedor:</span>
          <blockquote class="cita-mensaje">"{texto_original}"</blockquote>
        </div>
        <form id="form-correccion-{vid}" onsubmit="guardarCorreccion(event, '{vid}')">
          <div class="campo-formulario">
            <label for="corr-cliente-{vid}">Cliente</label>
            <input type="text" id="corr-cliente-{vid}" value="{cliente}" class="control-input" required />
          </div>
          <div class="campo-formulario">
            <label for="corr-monto-{vid}">Monto (USD)</label>
            <input type="number" step="0.01" id="corr-monto-{vid}" value="{monto}" class="control-input" required />
          </div>
          <div class="campo-formulario">
            <label for="corr-producto-{vid}">Producto / Hospedaje</label>
            <input type="text" id="corr-producto-{vid}" value="{producto}" class="control-input" required />
          </div>
          <div class="campo-formulario">
            <label for="corr-fecha-{vid}">Fecha de venta</label>
            <input type="date" id="corr-fecha-{vid}" value="{fecha_venta}" class="control-input" required />
          </div>
          <div class="acciones-hoja">
            <button type="button" class="boton boton-secundario" onclick="cerrarHojaCorreccion('{vid}')">Cancelar</button>
            <button type="submit" class="boton boton-primario">Validar con cambios</button>
          </div>
        </form>
      </div>
    </div>
    """


# ¤panel-operativo
def TarjetaVenta(venta: Mapping[str, Any]) -> str:
    """Componente de tarjeta individual para la bandeja de ventas por validar (P-03, US-06)."""
    vid = venta.get("venta_id", "")
    ticket = venta.get("ticket", "")
    vendedor = venta.get("vendedor", "")
    cliente = html.escape(str(venta.get("cliente", "")))
    producto = html.escape(str(venta.get("producto", "")))
    monto = str(venta.get("monto", "0.00"))
    comision_est = str(venta.get("comision_estimada", "0.00"))
    texto_original = html.escape(str(venta.get("texto_original", "")))
    confianza = float(venta.get("confianza", 1.0))
    campos_dudosos = list(venta.get("campos_dudosos", []))

    tiene_dudosos = len(campos_dudosos) > 0
    if tiene_dudosos:
        dudosos_str = ", ".join(campos_dudosos)
        chip_dudosos = f'<span class="chip chip-alerta" title="Campos con baja confianza">Dudoso: {dudosos_str}</span>'
        btn_validar = f'<button class="boton boton-primario" onclick="abrirCorreccion(\'{vid}\')">Revisar y validar</button>'
    else:
        chip_dudosos = '<span class="chip chip-exito">Sin dudas</span>'
        btn_validar = f'<button class="boton boton-primario" onclick="validarVentaDirecta(\'{vid}\')">Validar</button>'

    puntos = round(confianza * 5)
    barra = "●" * puntos + "○" * (5 - puntos)

    hoja_corr = HojaCorreccion(venta)
    modal_motivo = DialogoMotivo(vid, "rechazar")

    return f"""
    <article class="tarjeta tarjeta-venta" id="tarjeta-venta-{vid}">
      <div class="venta-cabecera">
        <div>
          <strong class="ticket-venta">{ticket}</strong>
          <span class="vendedor-venta">{vendedor}</span>
        </div>
        <div>
          {chip_dudosos}
        </div>
      </div>
      <div class="venta-cuerpo">
        <p class="detalle-linea">
          <strong>{cliente}</strong> · {producto}
        </p>
        <p class="monto-linea">
          <span class="monto-valor">USD {monto}</span>
          <span class="comision-est">Comisión estimada: USD {comision_est}</span>
        </p>
        <p class="confianza-linea">
          Confianza: <span class="confianza-puntos">{barra}</span> ({round(confianza * 100)} %)
        </p>
        <div class="texto-original-bloque">
          <span class="etiqueta-pequena">Mensaje recibido:</span>
          <p class="texto-original-contenido">"{texto_original}"</p>
        </div>
      </div>
      <div class="acciones-tarjeta">
        <button class="boton boton-secundario" onclick="verDetalleVenta('{vid}')">
          Detalle
        </button>
        <button class="boton boton-peligro" onclick="abrirRechazo('{vid}')">
          Rechazar
        </button>
        {btn_validar}
      </div>
      {hoja_corr}
      {modal_motivo}
    </article>
    """


# ¤panel-operativo
def ChatJarvis(mensajes: Sequence[Mapping[str, Any]]) -> str:
    """Componente de conversación con el asistente Jarvis (P-07, RF-PAN-06)."""
    burbujas = []
    for m in mensajes:
        autor = m.get("autor", "usuario")
        texto = html.escape(str(m.get("texto", "")))
        hora = str(m.get("hora", ""))
        clase = "mensaje-usuario" if autor == "usuario" else "mensaje-jarvis"

        botones_conf = ""
        if m.get("requiere_confirmacion"):
            botones_conf = """
            <div class="confirmacion-acciones">
              <button class="boton boton-primario" onclick="confirmarCambioJarvis(true)">Confirmar</button>
              <button class="boton boton-secundario" onclick="confirmarCambioJarvis(false)">Cancelar</button>
            </div>
            """

        burbujas.append(
            f"""
            <div class="burbuja-chat {clase}">
              <p class="texto-mensaje">{texto}</p>
              <span class="hora-mensaje">{hora}</span>
              {botones_conf}
            </div>
            """
        )

    burbujas_html = "".join(burbujas)

    return f"""
    <div class="contenedor-chat-jarvis">
      <div class="historial-chat" id="historial-chat-jarvis">
        {burbujas_html}
      </div>
      <form class="formulario-chat" id="form-chat-jarvis" onsubmit="enviarPreguntaJarvis(event)">
        <input
          type="text"
          id="entrada-chat-jarvis"
          class="control-input"
          placeholder="Escribe tu pregunta sobre ventas o comisiones..."
          required
          autocomplete="off"
        />
        <button type="submit" class="boton boton-primario">Enviar</button>
      </form>
    </div>
    """


# ¤panel-operativo
def TarjetaMetrica(
    titulo: str,
    valor: str,
    subtitulo: str = "",
    variante: str = "neutral",
) -> str:
    """Componente para mostrar indicadores numéricos clave en tableros (RF-PAN-04, P-05)."""
    t_esc = html.escape(titulo)
    v_esc = html.escape(valor)
    sub_html = f'<p class="metrica-subtitulo">{html.escape(subtitulo)}</p>' if subtitulo else ""

    return f"""
    <div class="tarjeta tarjeta-metrica variante-{variante}">
      <span class="metrica-titulo">{t_esc}</span>
      <strong class="metrica-valor">{v_esc}</strong>
      {sub_html}
    </div>
    """


# ¤panel-operativo
def GraficoBarras(
    titulo: str,
    datos: Sequence[Mapping[str, Any]],
    eje_x: str = "mes",
    eje_y: str = "total_ventas",
    tabla_accesible: bool = True,
) -> str:
    """Componente de gráfico de barras simple con tabla alternativa accesible (RF-PAN-04 criterio b)."""
    t_esc = html.escape(titulo)

    # Calcular valor máximo para escalar barras
    valores_numericos = []
    for d in datos:
        try:
            valores_numericos.append(float(d.get(eje_y, 0)))
        except (ValueError, TypeError):
            valores_numericos.append(0.0)
    max_val = max(valores_numericos) if valores_numericos and max(valores_numericos) > 0 else 1.0

    barras_html = []
    filas_tabla_html = []

    for d in datos:
        etiqueta = html.escape(str(d.get(eje_x, "")))
        val_raw = d.get(eje_y, 0)
        try:
            val_num = float(val_raw)
        except (ValueError, TypeError):
            val_num = 0.0
        pct = min(100.0, max(0.0, (val_num / max_val) * 100.0))

        barras_html.append(
            f"""
            <div class="barra-item" title="{etiqueta}: {val_raw}">
              <div class="barra-relleno" style="height: {pct:.1f}%;">
                <span class="barra-valor">{val_raw}</span>
              </div>
              <span class="barra-etiqueta">{etiqueta}</span>
            </div>
            """
        )

        filas_tabla_html.append(
            f"""
            <tr>
              <th scope="row">{etiqueta}</th>
              <td>{val_raw}</td>
            </tr>
            """
        )

    tabla_acc_html = ""
    if tabla_accesible:
        tabla_acc_html = f"""
        <details class="tabla-alternativa-contenedor">
          <summary class="enlace-accesibilidad">Ver datos como tabla accesible</summary>
          <table class="tabla-densa tabla-accesible" aria-label="{t_esc}">
            <thead>
              <tr>
                <th scope="col">Período / Categoría</th>
                <th scope="col">Valor</th>
              </tr>
            </thead>
            <tbody>
              {''.join(filas_tabla_html)}
            </tbody>
          </table>
        </details>
        """

    return f"""
    <div class="grafico-barras-tarjeta tarjeta">
      <h3 class="grafico-titulo">{t_esc}</h3>
      <div class="grafico-barras-lienzo" role="img" aria-label="{t_esc}">
        {''.join(barras_html)}
      </div>
      {tabla_acc_html}
    </div>
    """


# ¤panel-operativo
def TablaDensa(
    columnas: Sequence[Mapping[str, str]],
    filas: Sequence[Mapping[str, Any]],
    id_tabla: str = "",
) -> str:
    """Componente de tabla densa de datos para estados de cuenta y listados (RF-PAN-04)."""
    encabezados = []
    for c in columnas:
        encabezados.append(f'<th scope="col" class="th-{c.get("alineacion", "izq")}">{html.escape(c.get("titulo", ""))}</th>')

    filas_html = []
    for f in filas:
        celdas = []
        for c in columnas:
            clave = c.get("clave", "")
            val = html.escape(str(f.get(clave, "")))
            alineacion = c.get("alineacion", "izq")
            celdas.append(f'<td class="td-{alineacion}">{val}</td>')
        filas_html.append(f'<tr>{"".join(celdas)}</tr>')

    id_attr = f' id="{id_tabla}"' if id_tabla else ""

    return f"""
    <div class="contenedor-tabla-densa">
      <table class="tabla-densa"{id_attr}>
        <thead>
          <tr>
            {''.join(encabezados)}
          </tr>
        </thead>
        <tbody>
          {''.join(filas_html)}
        </tbody>
      </table>
    </div>
    """


# ¤panel-operativo
def BannerSinConexion(conectado: bool) -> str:
    """Banner de advertencia en modo offline (P-12, RF-PAN-13)."""
    if conectado:
        return ""
    return """
    <div id="banner-sin-conexion" class="banner-offline" role="alert" aria-live="assertive">
      <span class="icono-alerta" aria-hidden="true">&#x26A0;</span>
      <span>Sin conexión · solo lectura</span>
    </div>
    """


# ¤panel-operativo
def TarjetaInstalacionPWA(descartada: bool = False) -> str:
    """Tarjeta informativa para instalación de la PWA en Android e iPhone (RF-PAN-11)."""
    if descartada:
        return ""
    return """
    <div class="tarjeta tarjeta-pwa-instalacion" id="tarjeta-instalacion-pwa" role="region" aria-label="Instalar aplicacion">
      <div class="cabecera-tarjeta">
        <h3>Instalar en pantalla de inicio</h3>
        <button class="boton-cerrar-tarjeta" onclick="descartarTarjetaInstalacion()" aria-label="Descartar">&times;</button>
      </div>
      <p class="descripcion-pwa">
        Instala el Panel Operativo en tu teléfono Android o iPhone para usarlo a pantalla completa y recibir avisos.
      </p>
      <div class="instrucciones-instalacion">
        <span class="paso-instalacion">En iPhone: Toca <strong>Compartir</strong> &rarr; <strong>Agregar al inicio</strong>.</span>
        <span class="paso-instalacion">En Android: Toca el menú &rarr; <strong>Instalar aplicación</strong>.</span>
      </div>
      <div class="acciones-tarjeta">
        <button class="boton boton-secundario" id="btn-instalar-pwa" onclick="solicitarInstalacionPWA()">Instalar app</button>
      </div>
    </div>
    """


# ¤panel-operativo
def TarjetaAvisosWebPush(activados: bool = False) -> str:
    """Tarjeta para solicitud explícita de permisos Web Push (RF-PAN-12 a)."""
    if activados:
        return """
        <div class="tarjeta tarjeta-avisos-activos">
          <div class="estado-avisos">
            <span class="indicador-verde" aria-hidden="true">&#x2713;</span>
            <span>Avisos activos en este teléfono</span>
          </div>
        </div>
        """
    return """
    <div class="tarjeta tarjeta-avisos-webpush" id="tarjeta-activar-avisos">
      <h3>Avisos al teléfono</h3>
      <p class="descripcion-avisos">
        Recibe notificaciones inmediatas de ventas por validar o handoffs e incidencias de tu zona. Sin datos personales.
      </p>
      <div class="acciones-tarjeta">
        <button class="boton boton-primario" id="btn-activar-avisos" onclick="activarAvisosWebPush()">
          Activar avisos
        </button>
      </div>
    </div>
    """


# ¤panel-operativo
def BarraInferiorNavegacion(rol: str, vista_activa: str = "ventas") -> str:
    """Barra inferior fija para navegación móvil según el rol (docs/FRONTEND.md §3)."""
    enlaces: list[tuple[str, str, str]] = []
    if rol in {"lider", "administrador"}:
        enlaces.append(("ventas", "Ventas", "&#x1F4CB;"))
        enlaces.append(("comisiones", "Comisiones", "&#x1F4CA;"))
    if rol in {"gestor", "administrador"}:
        enlaces.append(("handoffs", "Handoffs", "&#x1F4AC;"))
        enlaces.append(("incidencias", "Incidencias", "&#x26A0;"))
    enlaces.append(("jarvis", "Jarvis", "&#x1F916;"))

    items = "".join(
        f"""
        <button class="item-barra-inferior {'activo' if vista_activa == e[0] else ''}" onclick="navegar('{e[0]}')">
          <span class="icono-barra" aria-hidden="true">{e[2]}</span>
          <span class="texto-barra">{e[1]}</span>
        </button>
        """
        for e in enlaces
    )

    return f"""
    <nav class="barra-inferior-movil" role="navigation" aria-label="Navegacion inferior de la terminal">
      {items}
    </nav>
    """


# ¤panel-operativo
def renderP12TerminalMovil(estado: Any, vista_actual: str = "ventas") -> str:
    """Renderiza el contenedor completo de la terminal móvil P-12 (RF-PAN-11, RF-PAN-13)."""
    conectado = getattr(estado, "conectado", True) if not isinstance(estado, dict) else estado.get("conectado", True)
    rol = getattr(estado, "rol", "lider") if not isinstance(estado, dict) else estado.get("rol", "lider")
    avisos_activos = getattr(estado, "avisos_activados", False) if not isinstance(estado, dict) else estado.get("avisos_activados", False)
    ventas = getattr(estado, "ventas_en_memoria", ()) if not isinstance(estado, dict) else estado.get("ventas_en_memoria", ())

    banner = BannerSinConexion(conectado)
    avisos = TarjetaAvisosWebPush(avisos_activos)
    barra = BarraInferiorNavegacion(rol, vista_actual)

    items_ventas = []
    for v in ventas:
        vid = v.get("venta_id", "") if isinstance(v, dict) else getattr(v, "venta_id", "")
        ticket = v.get("ticket", "") if isinstance(v, dict) else getattr(v, "ticket", "")
        monto = str(v.get("monto", "0.00") if isinstance(v, dict) else getattr(v, "monto", "0.00"))
        btn_validar = (
            f'<button class="boton boton-primario btn-validar" onclick="validarVentaUnToque(\'{vid}\')">Validar</button>'
            if conectado
            else '<button class="boton boton-primario btn-validar" disabled aria-disabled="true">Validar (deshabilitado)</button>'
        )
        items_ventas.append(
            f"""
            <div class="tarjeta item-venta-movil" id="venta-{vid}">
              <div class="fila-ticket">
                <span class="ticket-codigo">&#x25A4; {ticket}</span>
                <span class="ticket-monto">${monto}</span>
              </div>
              <div class="fila-acciones">
                {btn_validar}
              </div>
            </div>
            """
        )

    lista_html = "".join(items_ventas) or '<p class="sin-datos">No hay operaciones pendientes en memoria.</p>'
    modo_clase = "" if conectado else " modo-sin-red"

    return f"""
    <div class="terminal-movil-contenedor{modo_clase}">
      {banner}
      <div class="contenido-terminal">
        {avisos}
        <div class="seccion-lectura-memoria">
          <h3>Bandeja de operaciones (en memoria)</h3>
          <div class="lista-items-memoria">
            {lista_html}
          </div>
        </div>
      </div>
      {barra}
    </div>
    """
