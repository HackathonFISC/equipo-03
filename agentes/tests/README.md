# agentes/tests

**Dueño:** Emilia

Casos 1 a 4

## Robustez de Ingesta A4

`test_ingesta_robusta.py` prueba citas con acentos/caso/espacios preservando la
fuente, unidades de tiempo, cantidades no respaldadas, familias frente a personas,
reintentos acotados y configuración/preflight Gemini. No conecta a servicios reales.

```bash
python -m pytest agentes/tests/test_ingesta.py agentes/tests/test_ingesta_robusta.py agentes/tests/test_gemini_diagnostico.py orquestador/tests -q
```

La persistencia y recuperación tras perder un acuse se comprueban además con
`supabase/tests/0015_ingesta_recuperable_smoke.sql`. Caso oficial de reinicio 24 y
recorrido Telegram completo conservan pendiente su evidencia integrada.

## Puente A1

`test_puente_necesidades.py` comprueba conservación de necesidades/procedencia,
plan de ensayo, ámbito completo, submatrices, retiro ya persistido de una cisterna,
idempotencia de construcción y manejo de errores de la cola. El soporte
`soporte_puente_necesidades.py` usa fixtures para la integración SQL local de 0016;
no contiene datos reales aunque algunos casos lleven origen='real'.

El smoke 0016 verifica snapshots, rol coordinador, procedencia, cola, repetición y
faltantes. `supabase/tests/0016_integracion_local.mjs` ejercita los cinco agentes,
las cuatro herramientas, aprobación simulada y avisos de prueba bajo una ejecución.
Crear la bandeja local no equivale a enviar o recibir Telegram.
