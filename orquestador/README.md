# orquestador

**Dueño:** Emilia

trabajador.py y flujo.py

## V2

Trabajador y flujo implementados. Ver [guía V2](../docs/V2_EMILIA.md) antes de arrancar: procesa ejecuciones pendientes del Supabase configurado. Requiere migraciones 0006/0007.


## V3

Planificación añadida al despacho y al trabajador. Requiere 0009 para registrar y
procesar el ensayo separado. Usar `--una-vuelta --planificacion-id UUID` para
procesar exclusivamente ese escenario sin mantenimiento global ni consumo de la
cola V2. Gemini decide calcular/revisar; `solve_routes` y `verify_plan` hacen el
trabajo determinístico. Sin aprobación ni mensajería. Ver [guía V3](../docs/V3_EMILIA.md).
