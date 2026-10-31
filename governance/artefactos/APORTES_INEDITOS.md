# Aportes inéditos
`¤spec-glamping`

Hallazgos verificados de este proyecto que conviene no volver a descubrir.

### A-01. Sumas por tramos: redondear el acumulado, no cada diferencia

**Descripción:** si el monto de cada operación es `F(base + m) − F(base)`, la suma se cancela en cadena y da `F(S)` en cualquier orden. Eso solo se cumple exacto si se redondea `F` antes de restar. Redondear cada diferencia reintroduce la dependencia del orden, por centavos.

**Por qué es útil aquí:** las comisiones escalonadas deben cuadrar al centavo con la exportación. El mismo patrón sirve para cualquier cálculo acumulado por tramos.

**Verificabilidad:** con ventas 333.33, 700.10 y 566.57 y tramos de 5 % y 10 % desde 1000, en las 6 permutaciones: `{total con F redondeada} = {110.00}` y `{total redondeando cada diferencia} = {110.00, 110.01}`. Lo primero lo fija `tests/test_especificacion.py::test_el_escalon_marginal_no_depende_del_orden`.

**Soporte bibliográfico:** sin cita. No se verificó una fuente específica y es mejor omitirla que forzarla.

**Estado:** aplicado en `docs/spec/contratos/dominio.yaml` e `INV_COMISION_REPRODUCIBLE`. Sin concepto nuevo de gobernanza.
