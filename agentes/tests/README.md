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
