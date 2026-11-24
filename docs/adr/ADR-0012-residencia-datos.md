# ADR-0012 — Residencia de datos en Ecuador
`¤infra-hibrida`

| Campo | Valor |
| :--- | :--- |
| Estado | **Aceptado en lo funcional** (2026-11-23, criterio de Evydentia aceptado por el propietario); pendientes legales abiertos |
| Fecha | 2026-10-30 |
| Decisores | Propietario del proyecto con asesoría legal |
| Fuente | [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md) §9.1, §14.6 |
| Bloquea | Confirmar o revisar Neon; indexación de datos reales (fase 2); ubicación de reservas y datos de huéspedes |

## Contexto
El modelo híbrido (ADR-0004) lleva pgvector, historial, ventas y auditoría a una nube gestionada fuera de Ecuador. El sistema trata datos personales de huéspedes y vendedores (teléfonos, nombres, documentos en algún caso). Ecuador cuenta con legislación de protección de datos personales; hay que confirmar si impone condiciones a la transferencia internacional o a la ubicación de algún dato, y qué exige en cuanto a consentimiento e información al titular.

## Opciones consideradas
1. Todo en nube gestionada (región más cercana disponible), con tokenización de PII antes de salir del servidor propio.
2. PII y reservas on-prem (PostgreSQL adicional en `agent-net`), resto en nube.
3. Todo on-prem (pierde PITR gestionado; sube el riesgo R-01).

## Criterio de decisión propuesto
Inventario de datos por entidad (PRD §9) con clasificación (personal / sensible / operativo) y una opinión legal escrita sobre transferencia internacional. Si solo la PII está restringida, la opción 1 ya la mantiene tokenizada en la bóveda de `seguridad`; esa bóveda puede ubicarse on-prem (opción 2) sin tocar otras salas.

## Avance 2026-11-23: decisiones del propietario y consulta externa
Decisiones del propietario para el tratamiento por el modelo (ver [ADR-0021](ADR-0021-inferencia-gemini-vertex.md)):
- La inferencia se hace en Vertex AI, ubicación `us` (Estados Unidos). La PII se tokeniza antes de enviarse al modelo.
- **Basta con informar** al titular sobre la transferencia internacional; no se pide consentimiento expreso.
- Si el titular rechaza la transferencia, **todo su caso pasa a atención humana**.

**Consulta de protección de datos.** Se pidió criterio a **CTO Evydentia**, el equipo de la plataforma LOPDP 360 con quien Glamping Imbabura implementa su app de protección de datos personales. La consulta cubre:
- base de legitimación y artículos aplicables de la LOPDP (arts. 55 a 57 a confirmar);
- garantías para la transferencia a EE. UU.;
- contenido mínimo del aviso y cómo dejar prueba de que se informó;
- efecto de la tokenización;
- plazos de retención;
- su especificación IA-15 como referencia.

Respuesta de CTO Evydentia (2026-11-23). Es **criterio técnico de cumplimiento, no dictamen legal**: los textos legales de Evydentia siguen en borrador hasta que los aprueben su propietario y su abogado.

**Fuente que citan:** LOPDP, R.O. Quinto Suplemento 459 (26-may-2021), PDF de la SPDP. Verificaron el epígrafe y la frase inicial de los arts. 7, 8, 10, 12, 34, 35, 37, 56 y 57. La estructura de los arts. 55 a 61 la tomaron de una compilación (Lexis): 56 nivel adecuado, 57 garantías adecuadas, 58 normas corporativas vinculantes, 59 autorización, 60 casos excepcionales, 61 control. El epígrafe del art. 55 **no está verificado**.

1. **Informar no basta, según su criterio.** Son tres capas distintas:
   - informar al titular (art. 12);
   - tener una base que legitime el tratamiento (art. 7): proponen la ejecución del contrato o medidas precontractuales, con el numeral por confirmar;
   - tener una vía legal para la transferencia (arts. 56 a 60). No conocen ninguna declaración de nivel adecuado para EE. UU. (art. 56). Lo realista es la vía de garantías adecuadas (art. 57) o un caso excepcional (art. 60).
2. **Encargado en el extranjero.** El art. 34 dice que el acceso del encargado no es transferencia. Si eso alcanza cuando Google está fuera del país lo debe valorar el abogado.
3. **Garantía del art. 57.** Documentar el contrato de encargo y el Cloud Data Processing Addendum de Google, archivados con versión y fecha. Si hace falta autorización de la SPDP (art. 59), lo decide el abogado.
4. **Aviso y prueba.** El aviso debe indicar:
   - responsable y contacto, y DPO si lo hay;
   - finalidad y base;
   - destinatario (Google, como encargado);
   - país y región, leídos de la configuración;
   - plazo de conservación;
   - derechos;
   - la alternativa sin IA.

   No debe calificar la transferencia como «adecuada», «conforme» ni «garantiza». Por cada conversación se registra la versión del aviso, su hash, la fecha, el canal y la respuesta del huésped.
5. **Tokenización.** Es seudonimización, no anonimización: sigue habiendo datos personales y transferencia. Suma minimización (art. 10 lit. e) y seguridad (art. 37). Los **comprobantes de pago en imagen no deben llegar al modelo**.
6. **Retención.** Evydentia no ha verificado la retención cero en Vertex. Hay que revisar la caché, el registro por abuso y el grounding en la documentación de Google y fijar los plazos en el RAT.

**Decisión del propietario (2026-11-23): acepta el criterio de Evydentia** y deja sin efecto «basta con informar». La transferencia a Vertex `us` se apoya en:
1. el aviso al titular (art. 12), con el contenido mínimo del punto 4 y registro por conversación;
2. una base contractual: ejecución del contrato o medidas precontractuales (art. 7, numeral por confirmar);
3. la garantía del art. 57 documentada: contrato de encargo y Cloud Data Processing Addendum de Google, archivados con versión y fecha;
4. una alternativa humana real si el huésped rechaza la transferencia.

**Condición para el tráfico real:**
- los documentos del punto 3 deben estar archivados;
- el abogado debe resolver el art. 34 con el encargado en el extranjero, el art. 59, el art. 55 y la retención en Vertex.

**Pendiente del abogado:**
- el art. 34 con el encargado en el extranjero;
- el art. 59;
- el art. 55;
- la retención en Vertex.

Hasta que este ADR pase a Aceptado, ningún mensaje de huéspedes reales se envía a Vertex.

## Decisión
Pendiente. Fecha límite: antes de indexar o almacenar datos reales (fase 2).

## Consecuencias previstas
- Puede fijar el proveedor de PostgreSQL (ADR-0002) por región.
- Puede exigir un aviso de privacidad en el primer contacto con el huésped (texto del system prompt, fase 1) y un registro de consentimiento en `seguridad`.

## Criterios de verificación (árbitro)
- Inventario de datos por ubicación versionado en este ADR y referenciado desde `INVARIANTS.md`.
- `tests/seguridad/test_pii.py`: ningún valor de PII en claro sale hacia servicios fuera de la ubicación aprobada.

`¤infra-hibrida/`

---

© 2026 Juan Carlos Proaño. Todos los derechos reservados.
