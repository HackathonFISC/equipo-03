# agentes

**Dueño:** Emilia

Los 5 agentes, herramientas.py y trazas.py

## Verificación V0 de Gemini

Ver [prueba real y reproducción](PRUEBA_GEMINI_V0.md). Script: `probar_gemini_v0.py`; evidencia sintética: `evidencias/gemini_v0_resultado.json`. No implementa los cinco agentes.

## Ingesta de texto V1

Implementación: `ingesta.py`, `gemini.py` y `trazas.py`. Ver
[guía de ejecución e integración con Noel](INGESTA_V1.md).
Requiere aplicar `0005_ingesta_transaccional.sql` para persistir en Supabase;
el modo fixture con Gemini funciona sin esa migración y no escribe en BD.
No implementa el trabajador de V2 ni envía mensajes al bot.
