# evals

**Dueño:** José

`ejecutar.py` reúne las pruebas de contratos, cálculo, servicios compartidos,
API, bot, agentes, geografía, orquestador y las evaluaciones independientes.
`metricas.py` separa aprobados, fallidos, errores y pendientes con denominadores
explícitos. Incluye métricas de comparación local de V5, sin acreditar su cierre integrado.

Para comparar prioridad y orden de llegada con el mismo escenario y probar el retiro de una cisterna:

```powershell
.\.venv\Scripts\python.exe -m evals.comparar_v5
```

Consultar [metodología, métricas y pendientes V5](V5.md). La demo conserva los
resultados desfavorables y rechazos por cobertura crítica; no publica planes.

Desde la raíz del repositorio, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m evals.ejecutar --salida ../tmp/evaluacion_v4_01
```

La carpeta debe ser nueva. Guarda `informe.json` y `regresion.xml`. El ejecutor
no lee `.env`, no inicia el trabajador ni llama Gemini, Supabase o Telegram.
Los servicios externos usados por las pruebas se sustituyen explícitamente.

Código de salida **2**: comprobación incompleta por integración pendiente.
**1**: fallo o error; **0** queda reservado para una compuerta completa futura
y actualmente no se emite. Una regresión local verde no cierra V4.

Se pueden ejecutar peticiones a una API con `--perfil-http archivo_local.json`.
Es opcional y requiere preparar/revisar el perfil con el equipo: puede contener
POST que cambien el escenario de prueba. No hay reintentos ni envío directo al
proveedor. Los resultados de esos guiones se registran como sondeos y no se
promocionan automáticamente a cierre de casos oficiales.

Ver [preparación V4 y pendientes de integración](V4.md) y
[pruebas independientes](independientes/README.md).
