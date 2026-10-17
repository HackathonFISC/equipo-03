# Ingesta de texto V1

Emilia mantiene `ingesta.py`, `gemini.py`, `trazas.py` y las RPC de la migración
0005. Noel crea reportes y ejecuciones; el bot y la API continúan siendo suyos.
Ingesta lee directamente Supabase mediante `comun.db`; no necesita un endpoint
de la API ni un proceso del bot abierto para ejecutar una fila ya persistida.

## Entradas y salidas acordadas con Noel

- Noel guarda el reporte y crea una ejecución `pendiente`, etapa `ingesta`, con
  clave `ingesta:<reporte_id>`. El UUID de ejecución se conserva durante el flujo.
- La extracción de Gemini se valida como `ExtraccionReporteLLM`. IDs, origen,
  referencia al texto y eventos los compone Python; el modelo no los decide.
- En `reportes.interpretacion` se guarda **ExtraccionReporteLLM directamente**,
  no el wrapper ReporteInterpretado. Las columnas `requiere_aclaracion`,
  `fuera_de_alcance` y `evidencias` se actualizan en la misma transacción.
- La traza usa `agente='ingesta'`, `actor_tipo='agente'`, referencias al reporte,
  decisión, resultado, duración y siguiente estado. No guarda el prompt, la
  respuesta cruda del proveedor, su razonamiento ni credenciales.

## Ejecutar con Supabase

1. Instalar dependencias con el entorno V0. Esta entrega usa HTTPX, ya presente
   en el entorno y declarado como dependencia directa para el adaptador Gemini.
2. Revisar y aplicar **una vez** `supabase/migrations/0005_ingesta_transaccional.sql`
   con el rol administrativo en el SQL Editor. Requiere 0001; no renumera ni
   reemplaza 0002/0003 de Noel y no procesa reportes al instalarse.
3. Ejecutar `supabase/tests/0005_ingesta_smoke.sql`. Sus filas son sintéticas y
   terminan en ROLLBACK. La instalación real de 0005 no se acredita con pruebas
   en un PostgreSQL temporal.
4. Completar `.env` con la URL y clave de servidor de Supabase, `GEMINI_API_KEY`
   y opcionalmente `GEMINI_MODEL` (predeterminado: `gemini-3.8-flash`). No enviar
   estas claves a React. No se usa una clave anon para estas operaciones.
5. Pedir a Noel el UUID de una ejecución pendiente de texto creada con su API.

```bash
.venv/bin/python -m agentes.ingesta --ejecucion-id UUID_DE_EJECUCION
```

En Windows sustituir `.venv/bin/python` por `.venv\Scripts\python.exe`.
Es un comando síncrono por ejecución, sin bucle ni selección automática de
otras filas. Consume una llamada de Gemini sobre el texto de ese reporte.
No envía Telegram ni inicia Territorial. El trabajador automático llega en V2.

Para probar un ReporteRegistrado local con Gemini **sin escribir en Supabase**:

```bash
.venv/bin/python -m agentes.ingesta --reporte-json agentes/ejemplos/reporte_texto_v1.json --salida /tmp/ingesta_v1.json
```

`--salida` guarda el reporte interpretado completo y su traza. Puede contener
texto ciudadano: usarlo solo con fixtures o en un destino privado. El comando
normal de BD solo imprime estado, etapa e ID de ejecución, sin el reporte.

## Toma y cierre

`ra_tomar_ingesta` bloquea la fila de ejecución y comprueba estado `pendiente`
y etapa `ingesta`. Solo un consumidor obtiene la fila; los demás reciben null
y no llaman a Gemini. La toma registra trabajador, intento y reserva de 180
segundos. Gemini tiene un timeout de 45 segundos y no se reintenta automáticamente.

`ra_finalizar_ingesta` comprueba dueño de la reserva, vencimiento y snapshot del
reporte. Guarda extracción/evidencias, evento y transición en **una transacción**.
Un fallo de traza revierte también la escritura del reporte. Solo service_role
puede ejecutar estas RPC; usan SECURITY INVOKER y no habilitan acceso público.

| Resultado | Estado de ejecución | Etapa |
| --- | --- | --- |
| Texto de agua interpretado | pendiente | territorial |
| Necesita aclaración | espera_aclaracion | ingesta |
| Fuera del alcance de agua | completada | terminada |
| Entrada o proveedor inválido | fallida | ingesta |

La rama fuera de alcance es una decisión conservadora de implementación: no
avanza ni envía una aclaración de agua a una entrada ajena al problema. Revisar
con Noel/José al aceptar la integración. Esperar aclaración **no envía ninguna
pregunta en V1**: quedan guardados los faltantes para la integración de V2.
Una ubicación no reconocida no se declara fuera del área: la resuelve Territorial.

Un error controlado genera `ErrorDominio` en `ultimo_error` y una traza de fallo,
sin una interpretación parcialmente persistida. Una excepción inesperada de BD
o del proceso no se convierte en éxito ni desencadena llamadas repetidas.

Si se pierde la respuesta después de confirmar un cierre, consultar primero la
ejecución y sus eventos. La RPC admite repetir **exactamente el mismo cierre**
sin duplicarlo y rechaza reutilizar el ID de evento con otro contenido.
Volver a lanzar el comando para una ejecución ya avanzada devuelve `no_tomada`.

Si el proceso muere antes del cierre, permanece `ejecutando` con reserva vencida.
No se recupera automáticamente en V1. El operador revisa estado, evento y dueño
antes de restablecerla manualmente como `pendiente/ingesta` si corresponde. No
reabrir una ejecución cuyo cierre ya existe. Al retomarla se crea otro token de
trabajador: un consumidor anterior no puede finalizar con una reserva obsoleta.

## Validación y límites

- Solo texto en V1. Voz, foto y ubicación aislada terminan en error controlado;
  no se accede a Storage ni se supone que ya se transcribieron.
- Fechas con zona, unidades y UUID según los contratos existentes. No se
  alteran contratos, semilla, prioridad, planes, aprobaciones ni avisos.
- Cada cita debe ser fragmento literal del original. Ubicación, institución y
  vulnerabilidad declaradas también son texto literal. La evidencia estructurada
  referencia el original; cotejar una cita no demuestra que una afirmación sea
  verdadera en el mundo real ni que todos los matices semánticos sean correctos.
- Guardia numérica V1: dígitos con horas/días (conversión a horas) y población
  expresada como personas/habitantes/residentes/vecinos/afectados o «somos N».
  No acepta cifras extraídas sin respaldo en esas formas. Cantidades solo en
  palabras o expresiones ambiguas se dejan en null y requieren aclaración.
  No se convierte desconocido en cero. Ampliar el lenguaje requiere pruebas.
- El sistema separa instrucciones del reporte, rechaza campos extra y nunca
  concede herramientas de aprobación o mensajería al modelo. Estas medidas y
  las pruebas sintéticas no acreditan resistencia completa a inyección; las
  evaluaciones adversas del equipo siguen siendo necesarias.
- El origen se conserva desde el reporte de Noel; Ingesta no decide que un
  dato es real por aparecer en Telegram ni cambia la política del chat de prueba.

## Verificación e integración pendientes

```bash
.venv/bin/python -m pytest agentes/tests contratos/tests comun/tests -q
```

Las pruebas Python usan dobles y HTTPX MockTransport. El smoke SQL comprueba
toma excluyente, transiciones, reserva, snapshot, rollback e idempotencia de
cierre; no reproduce carga concurrente de servidores reales. Antes de cerrar
V1, aplicar 0005, ejecutar smoke en Supabase y usar un reporte creado por el
POST real de Noel. Comprobar en su GET/panel la extracción y en eventos la traza.

Referencias: [Gemini y JSON Schema](https://ai.google.dev/gemini-api/docs/generate-content/structured-output)
y [funciones de base de datos de Supabase](https://supabase.com/docs/guides/database/functions).

## Extensión V2

Con 0006 instalada, el cierre que necesita aclaración crea la pregunta en la misma transacción. La toma devuelve respuestas aceptadas; se reprocesan con el texto original y evidencias separadas. Si falta destino verificable, pasa a revisión. Ver [V2](../docs/V2_EMILIA.md). Los límites anteriores describen V1 antes de esa migración.
