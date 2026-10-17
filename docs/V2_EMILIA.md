# Territorial y aclaraciones de V2

La parte de Emilia procesa Ingesta → Territorial → Priorización con un trabajador
que persiste cada transición. Las aclaraciones esperan al ciudadano en la base
de datos; no dejan una llamada a Gemini abierta. Noel conserva API, bot y panel;
José implementa `validate_need` y `score_needs` y prepara los datos de cálculo.

## Instalar y comprobar

Desde la raíz del repositorio y con el entorno existente:

```bash
source .venv/bin/activate
python -m pytest agentes/tests geografia/tests orquestador/tests contratos/tests comun/tests api/tests calculo/tests -q
```

En Supabase SQL Editor ejecutar los archivos COMPLETOS en este orden:

1. `supabase/migrations/0006_aclaraciones_v2.sql` (una vez).
2. `supabase/tests/0006_aclaraciones_smoke.sql`.
3. `supabase/migrations/0007_territorial_orquestador_v2.sql` (una vez).
4. `supabase/tests/0007_territorial_smoke.sql` (requiere semilla 01).
5. `supabase/tests/0007_priorizacion_smoke.sql`.

Los smoke usan transacción y ROLLBACK: deben ejecutarse enteros y revierten sus
datos sintéticos. «Success. No rows returned» es compatible con éxito; cualquier
incumplimiento lanza una excepción. 0006 requiere 0001/0004/0005 y 0007 requiere
0006. No reinstalar migraciones ya aplicadas. Si 0006 detecta varias aclaraciones
antiguas activas por ejecución, detenerse y revisarlas; no elimina historial.

Después de aplicar 0006, avisar a Noel para que active `destino_origen_id`.
La migración no lo infiere para reportes antiguos. Un reporte sin chat de origen
verificable pasa a revisión si necesita una aclaración.

El trabajador usa las claves backend existentes en `.env`; no copiar claves a
Telegram ni al navegador. Arrancarlo procesa filas pendientes reales del proyecto:

```bash
python -m orquestador.trabajador --una-vuelta
python -m orquestador.trabajador
```

`--una-vuelta` procesa una etapa por ejecución de la selección inicial; varias
vueltas completan el recorrido. El modo continuo consulta cada cinco segundos.
Ctrl+C lo detiene. Una reserva de agente dura 180 segundos. Si vence, queda en
`espera_revision`; no se repite una operación cuyo resultado pueda ser incierto.

## Acuerdo de aclaraciones con Noel

Todas las RPC son SECURITY INVOKER y están concedidas solo a `service_role`.
Bot → API con secreto compartido → RPC. El bot nunca tiene claves Supabase.
La autorización para avisos comunitarios no se utiliza como requisito para
responder al chat original de un reporte.

| RPC | Entrada y resultado |
| --- | --- |
| `ra_reservar_aclaracion(p_trabajador_id text)` | Devuelve fila con `aclaracion_id`, `pregunta`, `chat_id`, `mensaje_externo_id` del reporte, `reserva_hasta`, etc., o null. Reserva exclusiva de 60 segundos. |
| `ra_registrar_envio_aclaracion(p_aclaracion_id uuid, p_trabajador_id text, p_estado text, p_proveedor_mensaje_id text, p_error text)` | Estado enviado/fallido/incierto. Enviado exige ID numérico de Telegram y error null; los otros estados exigen error e ID null. Repetir el mismo acuse no agrega eventos. |
| `ra_aceptar_respuesta_aclaracion(p_chat_id text, p_pregunta_mensaje_id text, p_respuesta_externo_id text, p_remitente_ref uuid, p_texto text, p_ubicacion jsonb)` | Resultado aceptada/repetida/ya_respondida/autor_distinto/no_encontrada/vencida y ejecucion_id cuando aplique. |
| `ra_revisar_aclaraciones()` | Vence preguntas y reservas; también lo ejecuta el trabajador. Devuelve cantidad revisada. |

El bot consulta cada 5–10 segundos. La pregunta se envía como reply al mensaje
original; su message_id sale de `mensaje_externo_id = chat_id:message_id`.
No reenviar automáticamente una reserva vencida ni un envío fallido o incierto.
Pasan a revisión. Un acuse tardío puede conservar el ID real de una pregunta ya
enviada, pero no reabre la ejecución ni habilita una respuesta tardía.

Una respuesta válida exige mismo chat, ID del mensaje de la pregunta y autor del
reporte original. En grupos, el destino puede tener remitente null: se compara
contra `reportes.remitente_ref`. Noel busca el remitente existente por canal e ID
de usuario de Telegram, sin crearlo para aceptar respuestas. La RPC vuelve a
validar chat, pregunta y UUID de autor; no confía solo en el adaptador.

`p_respuesta_externo_id` es el chat y message_id del reply. El primer reply
aceptado cierra la pregunta, guarda contenido/autor/ID, registra traza y devuelve
la ejecución a pendiente/ingesta en una transacción. El mismo ID devuelve
repetida sin escribir, incluso después de transcurrido el plazo; otra respuesta
a la pregunta cerrada devuelve ya_respondida. No sobrescribir una respuesta.

Texto de 1 a 4000 caracteres O ubicación estática, exactamente uno. Ubicación:

```json
{"latitud":8.9,"longitud":-79.7,"fuente":"compartida","precision_metros":null,"representa_punto_atencion":null}
```

`precision_metros` corresponde a horizontal_accuracy si existe. Se guarda en
`aclaraciones.respuesta_ubicacion`; nunca crea ni valida un punto de entrega.
`RespuestaAclaracion` admite ahora texto o ubicación y se incluyen ejemplos y
JSON Schema. No admite ambos contenidos en la misma respuesta.

Noel ignora ubicación en vivo. Una ubicación sin reply no crea reporte en V2:
pide escribir el problema. Reply textual a un mensaje del bot que no corresponde
a una aclaración usa el flujo normal de nuevo reporte.

El plazo aprobado es 1800 segundos desde `enviado_en`. `vence_en` lo persiste;
`plazo_respuesta_segundos` permite configurar cada pregunta antes del envío
(o cambiar el default de la columna para futuras preguntas). Al vencer pasa a
`espera_revision`, conserva evidencia y motivo `aclaracion_vencida`. La RPC de
respuesta comprueba la fecha aunque el mantenimiento todavía no haya corrido.
Noel debe mostrar «El plazo para responder esta pregunta venció. Tu reporte sigue
pendiente de revisión.» No confundir vencida con no_encontrada.

## Resolución territorial y asociación

Se reconocen nombres completos y alias de instalaciones, ignorando acentos,
mayúsculas y puntuación. Un nombre de corregimiento o distrito no elige una
escuela por defecto. Una aclaración explícita prevalece sobre alternativas
anteriores. Desconocida y ambigua solicitan aclaración; no se declaran fuera de
cobertura. Una ubicación compartida queda para revisión de su correspondencia,
sin un umbral de cercanía inventado. El punto conocido conserva su validación
operativa pendiente; identificarlo no acredita capacidad ni descarga.

Se asocian reportes automáticamente solo si comparten punto, origen y tipo de
problema conocido y sus períodos documentados se solapan. La duración declarada
da el comienzo del período; la fecha del reporte es el extremo observado, no una
predicción de restablecimiento. Sin duración no se supone un mismo episodio.
Una entrega confirmada intermedia evita unir automáticamente episodios. Si hay
varios incidentes candidatos, se conserva el conflicto para revisión.

Los reportes originales y vínculos se conservan. Corroboraciones cuentan UUID de
remitentes distintos. Población discrepante queda marcada; no se suman personas,
litros ni puntos de prioridad por cantidad de mensajes. Una institución declarada
como hospital/centro de salud genera una señal de revisión, sin confirmar clase
crítica ni vulnerabilidad. Confianza permanece desconocida en lugar de inventar
un porcentaje.

Corrección desde la API de Noel:
`ra_separar_reporte(p_reporte_id uuid, p_usuario_id uuid, p_motivo text)` requiere
coordinador activo y motivo. Noel deriva usuario_id de la identidad autenticada,
no de un UUID libre enviado por el navegador. Se cierra el vínculo anterior,
se crea otro incidente y vínculo, se recomputan conteos/períodos y se invalidan
cálculos afectados; la traza conserva el motivo y la asociación previa.

## Priorización y entrega de José

El trabajador invoca las funciones de José a través de `agentes/priorizacion.py`.
En este árbol todavía no existen `calculo/demanda.py` y `calculo/prioridad.py`.
No se sustituyen con fórmulas nuevas. Sin herramientas, lote o confirmaciones,
el incidente conserva `pendientes_calculo` y la ejecución espera validación.
Eso no se presenta como una EvaluacionNecesidades calculada.

Para evaluar se necesita un lote explícito, consolidado y versionado. Un
coordinador lo prepara por `ra_preparar_priorizacion_v2(p_ejecucion_id uuid,
p_usuario_id uuid, p_lote jsonb)`. La estructura es:

- `politica`: PoliticaPrioridad activa e idéntica a la registrada en Supabase.
- `entradas`: una por incidente y punto, con `version_incidente`,
  `solicitud_demanda` (campos de SolicitudValidarNecesidad), `evaluacion` (factores
  de EvaluacionNecesidades) y opcionalmente `pendientes` adicionales.
- El contexto ejecución/origen/fecha lo impone el trabajador. No lo toma del LLM.
- La demanda y los factores provienen de la consolidación revisada y las entradas
  de José; no se rellenan desde el conteo de reportes.

Se exige el lote completo y un solo incidente por punto. Si existen episodios
distintos de un punto sin resolución operativa, no se elige uno ni se suman sus
demandas: ese conflicto bloquea el cálculo del lote para revisión. No se mezclan
orígenes. Cambiar entradas exige nueva `datos_version`; versiones de incidentes
deben coincidir. Un lote ya guardado idéntico es idempotente.

Primero validate_need por incidente y después score_needs para TODO el lote,
incluidos los pendientes. La extracción ciudadana no confirma demanda, clase ni
vulnerabilidad. Los resultados se validan con contratos; score_needs no puede
alterar la demanda o los factores consolidados. No se calcula un ranking
independiente por reporte. Se guardan EvaluacionNecesidades en el incidente y
en necesidades, con entrada y traza. Un nuevo reporte o separación invalida el
ranking derivado y obliga a revisar/recalcular el lote. Termina en
espera_validacion: no inicia rutas ni aprueba ni envía avisos comunitarios.

## Evidencia y cierre del equipo

Probado localmente sin servicios externos: suite Python, migraciones en
PostgreSQL temporal, regresión de Ingesta 0005 antes de instalar V2, y smoke V2
de aclaraciones, consolidación/separación y persistencia de evaluación pendiente
y calculada sintéticas. No se probó concurrencia de servidores reales.

Pendiente para cerrar V2 conjunta:

1. Usuario aplica 0006/0007 y ejecuta sus smoke en Supabase.
2. Noel integra las RPC, activa destino_origen_id y muestra incidentes/progreso.
3. José entrega funciones y escenario adaptado a los UUID oeste-1.0; el equipo
   registra las confirmaciones sintéticas de demo de forma explícita.
4. Probar bot → API → Ingesta → Territorial → cálculo → panel; tres reportes,
   ambigüedad/reply, duplicado sin alterar prioridad y separación con historial.

Este documento no acredita un ensayo Telegram real, una migración remota aplicada
ni una validación operativa de los seis lugares.
