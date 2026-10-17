# Prueba real de Gemini para V0

Emilia ejecutó una llamada real de extracción con Gemini y validó la respuesta
con `ExtraccionReporteLLM`. Entrada y salida son sintéticas. La clave se lee
desde `.env`, no se registra ni se incorpora al resultado.

## Repetir la prueba

Con el entorno instalado desde `requirements.txt`, completar `GEMINI_API_KEY`
en `.env`. El modelo predeterminado es `gemini-3.8-flash`; puede configurarse
mediante `GEMINI_MODEL` en el entorno o `.env`. Desde la raíz:

```bash
.venv/bin/python agentes/probar_gemini_v0.py
```

En Windows: `.venv\Scripts\python.exe agentes/probar_gemini_v0.py`.
Cada ejecución envía un texto sintético a Google, consume cuota del proyecto y
sobrescribe `agentes/evidencias/gemini_v0_resultado.json`. No hay reintentos
automáticos ni se envían reportes de ciudadanos, claves de Supabase o IDs
privados. HTTPX y python-dotenv ya forman parte del entorno V0 instalado.

## Resultado comprobado

- Modelo: `gemini-3.8-flash`, HTTP 200, finalización `STOP`.
- Texto: «En el Punto de prueba A llevamos 48 horas sin agua. Hay 120 personas afectadas.»
- Respuesta validada por Pydantic, sin campos extra.
- Ocho controles de contenido aprobados: horas, población, tipo de problema,
  lugar declarado, institución y vulnerabilidad ausentes, evidencia literal
  y reporte dentro del alcance.
- La ejecución exitosa tardó unos 23 segundos. El JSON registra fecha con
  zona horaria de Panamá y uso de tokens informado por el proveedor.

El intento inicial con `gemini-2.5-flash` recibió 404: Google indicó que ya no
estaba disponible para esta cuenta y recomendó `gemini-3.8-flash`. Un primer
intento con la nueva forma `responseFormat` recibió 400 por `mimeType`; la
llamada aprobada usa `responseMimeType` y `responseJsonSchema` con el esquema
Pydantic. No se añadieron SDKs de Google ni se implementaron los agentes.

Esta prueba acredita conectividad y extracción estructurada de texto para V0.
No acredita cuota futura, modalidades de voz/foto, robustez ante inyección,
las evaluaciones del sistema ni un recorrido completo de agentes. El modelo
no autoriza operaciones ni crea identificadores del backend.

Referencia: [salidas estructuradas de Gemini](https://ai.google.dev/gemini-api/docs/generate-content/structured-output).
