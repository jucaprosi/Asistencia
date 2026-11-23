# ¤conocimiento-rag
# ¤¤data-engineer
# © 2026 Juan Carlos Proaño. Todos los derechos reservados.
"""Indexación del corpus de conocimiento en la base de datos (RF-RAG-01).

Uso: ``python scripts/seed_knowledge.py [--corpus-dir RUTA] [--sintetico]``
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from features.conocimiento.conocimiento_service import ConocimientoService, cargar_config

CORPUS_SINTETICO_DEFINICIONES = {
    "glamping.md": """---
propiedad: glamping
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: politicas
---
# Glamping Imbabura — Experiencia y Normas

## Descripción del Glamping
Glamping Imbabura ofrece una experiencia inmersiva en la naturaleza frente al lago San Pablo y el volcán Imbabura. Contamos con domos geodésicos de lujo con jacuzzi privado, cama king-size, calefacción ecológica, terraza panorámica y baño privado con agua caliente.

## Ubicación y Cómo Llegar
Estamos ubicados en las faldas del volcán Imbabura, sector Rey Loma, a 15 minutos del centro de Otavalo y a 90 minutos de Quito por la vía Panamericana Norte (E35). El acceso final es un camino lastrado transitable para todo tipo de vehículo. Ofrecemos parqueadero vigilado gratuito en el predio.

## Horarios y Normas Generales
El horario de silencio estricto es de 22:00 a 08:00 para garantizar la tranquilidad y el descanso de todos los huéspedes. Se admiten mascotas educadas (pet-friendly) en los domos estándar previo aviso, con un suplemento único de limpieza de 20 USD. Está prohibido fumar dentro de los domos por normas de seguridad contra incendios.

## Clima y Qué Llevar
El clima en la zona andina es templado durante el día (18 a 22 °C) y frío por la noche (8 a 12 °C). Se recomienda llevar ropa abrigada, chaqueta impermeable, calzado cómodo de senderismo, repelente de insectos y protector solar.
""",
    "departamentos.md": """---
propiedad: depto-centro-01
dueno: Gestor Urbano
revisado: 2026-11-01
tipo: politicas
---
# Departamento Urbano Centro 01 — Ibarra

## Características del Departamento
Departamento ejecutivo moderno de dos dormitorios ubicado en el centro de Ibarra, edificio Los Ceibos, piso 4. Cuenta con sala de estar, cocina equipada, WiFi de alta velocidad (300 Mbps), Smart TV y parqueadero subterráneo asignado (espacio #12). Capacidad máxima: 4 personas.

## Normas del Condominio
No se permiten fiestas ni eventos ruidosos. Las visitas no registradas deben retirarse antes de las 21:00. El uso de áreas comunes (terraza comunal y gimnasio) está disponible de 06:00 a 20:00. No se permiten mascotas en el departamento por reglamento interno del condominio.

## Recolección de Basura y Limpieza
La recolección de basura se realiza depositando las fundas cerradas en el ducto del piso antes de las 19:00. La limpieza intermedia para estancias superiores a 7 noches se coordina sin costo adicional los días martes.
""",
    "precios-y-temporadas.md": """---
propiedad: global
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: precios
---
# Tarifas de Referencia y Temporadas

## Temporadas del Año
Temporada Alta: fines de semana (viernes a domingo), feriados nacionales del Ecuador, época navideña y fin de año (20 de diciembre al 2 de enero) y temporada vacacional de julio y agosto.
Temporada Baja: días entre semana (lunes a jueves) que no coincidan con feriados nacionales.

## Tarifas de Referencia Glamping
La tarifa base referencial por noche en domo geodésico de lujo es de 140 USD en temporada baja (lunes a jueves) y 180 USD en temporada alta o fines de semana para 2 personas. Incluye desayuno andino artesanal y acceso a senderos. Huésped adicional: 35 USD por noche (máximo 1 huésped adicional por domo).
Nota importante: La tarifa exacta y vigente en tiempo real es calculada y confirmada únicamente por el PMS.

## Tarifas de Referencia Departamento Centro
La tarifa referencial es de 65 USD por noche de domingo a jueves y 85 USD viernes y sábado. Estancias de más de 7 noches tienen un descuento automático del 10% aplicado por el PMS.
""",
    "politicas-cancelacion.md": """---
propiedad: global
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: politicas
---
# Políticas de Cancelación y Reembolso

## Cancelación con Reembolso Total
El huésped puede cancelar su reserva y recibir el 100% de reembolso si la notificación se realiza con al menos 7 días de anticipación a la fecha de llegada (check-in a las 15:00). Se aplicará una tarifa administrativa no reembolsable del 3% por cargos de pasarela bancaria.

## Cancelación Parcial
Si la cancelación se realiza entre 6 días y 48 horas antes de la llegada, se reembolsa el 50% del valor total de la reserva, o se ofrece un bono de crédito por el 100% para ser utilizado en los siguientes 6 meses.

## Cancelación Tardía y No-Show
Las cancelaciones realizadas con menos de 48 horas de anticipación a la fecha de llegada o los casos de no presentación (no-show) no tienen derecho a reembolso monetario ni reprogramación de fecha.

## Casos de Fuerza Mayor
En caso de emergencias médicas comprobables o desastres naturales que impidan el tránsito vial en la provincia de Imbabura, se permite el cambio de fecha sin penalización durante los siguientes 90 días previa presentación de justificativos válidos.
""",
    "checkin-checkout.md": """---
propiedad: glamping
dueno: Gestor Operativo
revisado: 2026-11-01
tipo: checkin
---
# Protocolo de Check-in y Check-out

## Horarios Oficiales
Hora de Check-in: a partir de las 15:00 horas.
Hora de Check-out: hasta las 11:00 horas.
Llegadas tempranas (early check-in a partir de las 12:00) o salidas tardías (late check-out hasta las 14:00) están sujetas a disponibilidad del domo y acarrean un costo adicional de 25 USD previa confirmación con recepción.

## Procedimiento de Llegada y Entrega de Domo
A su llegada, el anfitrión recibirá al huésped en recepción principal para la verificación de identidad (cédula o pasaporte original). Se entregará la llave del domo y el control del jacuzzi, acompañándolos con una breve inducción de funcionamiento de los equipos térmicos.

## Procedimiento de Salida
Antes de retirarse a las 11:00, el huésped debe entregar las llaves en recepción. Nuestro personal realizará una rápida inspección de inventario del domo. En caso de pérdida de llave física se aplica un cargo de 15 USD.
""",
    "atractivos-turisticos.md": """---
propiedad: glamping
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: atractivos
---
# Atractivos Turísticos Cercanos en Imbabura

## Lago San Pablo y Parque Acuático Araque
Ubicado a tan solo 10 minutos en vehículo desde el glamping. Es el lago más grande de la provincia de Imbabura, a los pies del volcán. Se ofrecen paseos en lancha, kayak, vela y paseos a caballo por la orilla. Hay restaurantes típicos con gastronomía local.

## Cascada de Peguche
Ubicada a 20 minutos del glamping en la comunidad de Faccha Llacta. Es un sitio sagrado indígena rodeado por un bosque de eucaliptos de 40 hectáreas. Entrada libre con aporte voluntario. Ideal para caminatas familiares matutinas.

## Plaza de Ponchos en Otavalo
El mercado artesanal más famoso de Sudamérica, ubicado a 15 minutos en el centro de Otavalo. El día de mayor movimiento ferial es el sábado, aunque funciona todos los días del año con venta de textiles andinos, tapices, ponchos y joyería de plata.

## Laguna de Cuicocha
Ubicada a 40 minutos dentro de la Reserva Ecológica Cotacachi-Cayapas. Es una caldera volcánica activa con dos islotes interiores y un sendero panorámico perimetral de 12 km de dificultad media-alta.
""",
    "faq-huespedes.md": """---
propiedad: global
dueno: Administrador Glamping
revisado: 2026-11-01
tipo: faq
---
# Preguntas Frecuentes de Huéspedes

## ¿Hay señal de internet y telefonía móvil?
Sí, contamos con conectividad WiFi de fibra óptica en todos los domos y áreas sociales. La cobertura de telefonía celular móvil (Claro y Movistar) es estable y de velocidad 4G en toda la propiedad.

## ¿El desayuno está incluido en la tarifa?
Sí, todas nuestras tarifas de hospedaje en el glamping incluyen desayuno andino artesanal servido entre las 08:00 y las 10:00 en la terraza panorámica o entregado directamente en el domo bajo pedido previo.

## ¿Tienen servicio de restaurante o cenas?
Ofrecemos servicio de cenas a la carta con reserva previa antes de las 17:00. El menú incluye opciones vegetarianas, carnes andinas y tablas de quesos y vinos locales. No está permitido cocinar con artefactos de gas dentro de los domos.

## ¿Cómo funciona el jacuzzi de hidromasaje?
Cada domo cuenta con jacuzzi privado con sistema hidromasaje y calentamiento continuo de agua. El agua se cambia y desinfecta minuciosamente entre cada estancia de huéspedes.
""",
    "aviso-privacidad.md": """---
propiedad: global
dueno: Propietario Legal
revisado: 2026-11-01
tipo: privacidad
---
# Aviso de Privacidad y Tratamiento de Datos Personales

## Responsable del Tratamiento
Glamping Imbabura es el responsable del tratamiento de los datos personales suministrados por huéspedes y clientes, en estricto cumplimiento de la Ley Orgánica de Protección de Datos Personales de la República del Ecuador.

## Finalidad de los Datos Recolectados
Los datos personales (nombre completo, número de teléfono, correo electrónico, documento de identidad y comprobantes de pago) se solicitan exclusivamente para la confirmación de reservas, facturación electrónica, envío de instrucciones de llegada y comunicación operativa durante la estancia.

## No Divulgación a Terceros
En ningún caso comercializamos, alquilamos ni transferimos sus datos personales a terceros con fines publicitarios ajenos a nuestra operación hotelera. Usted puede solicitar el acceso, rectificación o eliminación de sus datos en cualquier momento escribiendo a nuestro canal oficial.
""",
}


# ¤conocimiento-rag
def generar_corpus_sintetico(directorio: Path) -> int:
    """Crea los documentos del corpus sintético determinista en el directorio especificado."""
    directorio.mkdir(parents=True, exist_ok=True)
    creados = 0
    for nombre, contenido in CORPUS_SINTETICO_DEFINICIONES.items():
        ruta = directorio / nombre
        ruta.write_text(contenido.strip() + "\n", encoding="utf-8")
        creados += 1
    return creados


# ¤conocimiento-rag
def sembrar_corpus(raiz: Path | None = None, forzar_sintetico: bool = False) -> int:
    """Ejecuta la indexación del corpus y devuelve 0 en éxito."""
    config = cargar_config()
    directorio = raiz or Path(config.get("corpus_dir", "datos_privados/corpus"))

    if forzar_sintetico or not directorio.is_dir() or not any(directorio.glob("*.md")):
        print(f"Generando corpus sintético determinista en: {directorio}")
        generar_corpus_sintetico(directorio)

    ruta_bd = Path("datos_privados/conocimiento.db")
    servicio = ConocimientoService(config, ruta_bd=ruta_bd)
    resumen = servicio.indexar(directorio)
    print(
        f"[OK] Indexación completada: {resumen.documentos} documentos, "
        f"{resumen.chunks_nuevos} chunks nuevos, {resumen.chunks_reemplazados} reemplazados "
        f"en {resumen.duracion_ms} ms."
    )
    return 0


# ¤conocimiento-rag
def main(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(description="Indexador de conocimiento Glamping Imbabura (RAG)")
    analizador.add_argument("--corpus-dir", type=Path, default=None, help="Ruta al directorio de corpus")
    analizador.add_argument("--sintetico", action="store_true", help="Forzar generación de corpus sintético")
    opciones = analizador.parse_args(argumentos)
    return sembrar_corpus(opciones.corpus_dir, opciones.sintetico)


if __name__ == "__main__":
    raise SystemExit(main())
