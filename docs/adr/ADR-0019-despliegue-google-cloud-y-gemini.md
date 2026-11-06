# ADR-0019 — Despliegue en Google Cloud Platform (Cloud Run, Cloud SQL pgvector, Cloud Tasks) y Adopción de Google Gemini como Motor de IA
`¤infra-cloud` `¤agente-enrutador`

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado** (decisión del propietario, 2026-11-04) |
| Fecha | 2026-11-04 |
| Decisores | Propietario del proyecto, Arquitecto de Soluciones |
| Fuente | Solicitud formal de Glamping Imbabura; aprovechamiento del bono de \$300 USD de Google Cloud |
| Sustituye | Sustituye la parte on-premise de [ADR-0004](ADR-0004-infraestructura-hibrida-aislada.md); complementa [ADR-0001](ADR-0001-construir-vs-adoptar.md) |
| Bloquea | — (desbloquea el despliegue en nube / Ola 13) |

## Contexto
El diseño original contemplaba ejecutar la lógica stateless en un servidor propio Ubuntu on-premise con disco SATA único (ADR-0004) y el consumo de modelos Claude vía Anthropic API.
Tras evaluar los requerimientos operativos de alta disponibilidad 24/7 para el Webhook de WhatsApp de Meta ($< 3$ s de respuesta), la eliminación de costos y riesgos de hardware local (cortes de energía, apertura de puertos en router), y la disponibilidad del **bono de \$300 USD de Google Cloud Platform (GCP)** con su *Always Free Tier*, se determinó migrar el despliegue a una arquitectura 100% Cloud-Native y unificar el motor de IA con la familia **Google Gemini** a través de Vertex AI / Google AI Studio.

## Opciones consideradas
1. **Servidor Híbrido On-Premise (Ubuntu local + PC SATA)**: Requiere mantenimiento manual de Linux, IP pública fija o túneles frágiles, y expone el flujo contable existente a riesgos operativos.
2. **PaaS de Terceros (Render / Railway) con facturación externa**: Mantiene servidores despiertos por \$14/mes pero no aprovecha el crédito gratuito de \$300 de Google ni unifica la facturación con el LLM.
3. **Google Cloud Platform (GCP) + Google Gemini (Aceptada)**:
   - **Cómputo**: **Google Cloud Run** con `min-instances: 1` para respuesta instantánea de Webhook ($< 50$ ms) y escalado automático sin gestionar VMs.
   - **Desacoplamiento asíncrono**: **Google Cloud Tasks** para encolar el procesamiento de WhatsApp y ejecutar la inferencia de IA sin riesgo de duplicación.
   - **Persistencia**: **Google Cloud SQL for PostgreSQL 16** con extensión `pgvector` nativa para RAG y datos relacionales.
   - **Secretos**: **Google Secret Manager** para inyección segura de credenciales sin archivos `.env` en disco.
   - **Motor LLM**: **Google Gemini 3.8 Flash** (razonamiento principal, tool use con MCP y lectura multimodal nativa de vouchers de venta) y **Gemini 3.5 Flash-Lite** (enrutamiento económico de $< 400$ ms), cubiertos al 100% por el bono de \$300 USD de GCP.

## Decisión
Se aprueba la **Opción 3**:
1. Desplegar Glamping Imbabura en **Google Cloud Platform** bajo arquitectura Serverless Containerized.
2. Adoptar **Google Gemini** (`gemini-3.8-flash` y `gemini-3.5-flash-lite`; la familia 1.5 fue retirada por Google) como motor de IA principal para el agente de WhatsApp y la extracción de ventas en ARM Jarvis, manteniendo la abstracción en `features/agente/cliente_modelo_internal.py` para permitir fallback a Claude si fuere necesario.
3. Aprovechar el bono de \$300 USD para cubrir la totalidad del costo de infraestructura y tokens de IA durante el primer trimestre de producción.

## Consecuencias
- **Cero Mantenimiento de VMs**: No se crea ni administra ninguna máquina virtual en Ubuntu.
- **Cero Costo en Fase de Lanzamiento**: Tanto el cómputo como los tokens del modelo de lenguaje quedan cubiertos a costo \$0 durante los primeros 90 días.
- **Ventana de Contexto Ampliada y Multimodalidad**: Gemini procesa imágenes de comprobantes de pago de los vendedores directamente sin necesidad de OCR adicional.
- **Desacoplamiento de Proveedor Preservado**: La sala `agente` conserva su contrato ADPA y sus tipos `RespuestaModelo`, pudiendo alternar modelos mediante variables de entorno (`PROVEEDOR_LLM`, `MODELO_PRINCIPAL`, `MODELO_ECONOMICO`).

## Criterios de verificación (árbitro)
- Despliegue en Cloud Run respondiendo con HTTP 200 al handshake `hub.challenge` de Meta.
- Conexión a Cloud SQL con `pgvector` superando el set dorado de evaluaciones RAG ($\ge 0.85$).
- Inferencia exitosa de `gemini-3.8-flash` y `gemini-3.5-flash-lite` con telemetría de tokens y costo asentada en trazas de observabilidad.
- Suite completa de 665 pruebas y arnés físico pasando con Exit Code 0.

`¤infra-cloud/` `¤agente-enrutador/`
