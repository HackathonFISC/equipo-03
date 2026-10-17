# Robustez de Ingesta A4

El código del 17 de octubre conserva los contratos y añade comprobaciones de
texto, cantidades y errores recuperables. Requiere **0015 después de 0014**.
Las migraciones anteriores se conservan intactas. No activa avisos ni reabre
reportes históricos fallidos.

## Comportamiento

- Las citas, ubicación, institución y vulnerabilidad se comparan ignorando
  acentos, mayúsculas y espacios repetidos. Se guarda el fragmento exacto de la
  fuente original. No se aceptan paráfrasis, ubicaciones inferidas ni citas
  construidas pegando el reporte y una aclaración. Las fuentes siguen separadas.
- Duración admite dígitos con hora/h/hr/hrs/hs, días y semanas: día = 24 h,
  semana = 168 h. «Medio día» explícito = 12 h. No se convierten otras expresiones
  ambiguas o números en palabras por suposición.
- Población requiere personas/habitantes/residentes/vecinos/afectados explícitos,
  o «somos N» referido a personas. Familias/hogares/viviendas no se convierten a
  población. Tampoco se aceptan partes de decimales, negativos o unidades falsas.
- Una cantidad propuesta sin respaldo queda **null**, agrega su faltante y
  solicita aclaración. No provoca un estado terminal por sí sola. Las citas o
  declaraciones inventadas y los contratos inválidos siguen rechazándose.
- Gemini realiza una sola solicitud por intento. Un 429, 5xx, timeout o error
  declarado recuperable puede programar **dos reintentos** adicionales por
  ejecución. Esperas mínimas: cinco y diez segundos; el sondeo puede demorarlas.
  No se mantienen llamadas abiertas durante la espera.
- El cierre guarda evento, error, contador y próxima fecha en una transacción.
  Estado de espera: `espera_validacion/ingesta`; al vencer el plazo, mantenimiento
  lo devuelve a `pendiente/ingesta`. La toma vuelve a comprobar el plazo.
  El tercer fallo recuperable queda en `espera_revision`, con el error visible.
- Presupuesto persistido en `reintentos_ingesta`: no depende de la memoria del
  proceso ni de intentos de otras etapas. No se reinicia automáticamente por una
  aclaración; el límite vale para toda la ejecución.
- Si el cierre pudo confirmarse pero se perdió su respuesta, no se programa otra
  extracción. 0014 marca revisión solo si la reserva sigue siendo del trabajador.
  Repetir el cierre idéntico es idempotente: no duplica evento ni contador.

## Configuración y arranque

`GEMINI_MODEL` conserva precedencia de entorno sobre `.env`; vacío usa el
predeterminado `gemini-3.8-flash`. El 17/10 se consultaron sus metadatos reales:
HTTP 200 y `generateContent` disponible. No se enviaron reportes ni se hizo una
extracción real para esa comprobación.

Antes de reservar, el trabajador verifica clave/formato, metadatos del modelo y
presencia de las columnas 0015 en PostgREST. No inventa otro modelo si el elegido
no está disponible. La falta de clave o HTTP 400/401/403/404 se informa como
configuración inválida; no convierte cada reporte pendiente en fallida. Una
configuración rechazada durante una extracción queda en revisión sin consumir
el presupuesto automático. Corregir clave/modelo y reiniciar requiere intervención.

Los fallos transitorios del preflight usan el backoff y límite del trabajador,
sin tocar la cola. Una vez confirmado, los metadatos se reutilizan durante ese
proceso. El arranque necesita conexión a Google; la marca local de última vuelta
no sustituye la verificación del recorrido completo.

## Aplicación por Emilia en Supabase

1. Terminar la comprobación de **0014 y su smoke** que el usuario ya está haciendo.
2. Revisar y ejecutar **una vez**, completo,
   `supabase/migrations/0015_ingesta_recuperable.sql`.
3. Ejecutar completo `supabase/tests/0015_ingesta_recuperable_smoke.sql` en un
   entorno de prueba aislado. Termina ROLLBACK, pero llama mantenimiento global
   dentro de su transacción; no ejecutarlo durante procesamiento concurrente.
4. Reiniciar el único trabajador o la API que lo administra, después de que
   PostgREST conozca las columnas. No iniciar un segundo trabajador para probar.
5. Confirmar que una ejecución nueva progresa y conserva su traza. Los reportes
   fallidos históricos requieren revisión individual; no se reactivan en lote.

El smoke histórico 0005 describe la semántica anterior de fallo recuperable
terminal. Se conserva para comprobar aquella versión; con 0015 se usa el nuevo
smoke que comprueba espera, presupuesto, idempotencia y revisión. Las regresiones
0006/0013 de aclaraciones y 0014 de reservas también pasaron después de 0015.

## Evidencia y límites

Base: 743 pruebas + 66 subpruebas. Treinta pruebas Python nuevas; antes del cambio
se reprodujeron 24 fallos en las primeras 28. Candidato final: **773 pruebas y
66 subpruebas aprobadas**, cuatro advertencias conocidas de dependencias.

SQL aplicado en PostgreSQL temporal PGlite 0.5.10 con roles locales de prueba:
cadena de migraciones y semilla, smoke 0014, migración/smoke 0015, regresiones
0006/0013/0014. Incluye presupuesto agotado, acuse repetido, espera antes del plazo,
éxito posterior, configuración inválida, reserva ajena, snapshot obsoleto y
resultado incierto. Esta ejecución no acredita concurrencia de varios servidores
ni permisos/configuración del Supabase remoto. Dependencia SQL temporal fuera del
repositorio; no se cambian requirements ni dependencias del proyecto.

No se ejecutaron SQL remoto, generación real corregida con Gemini, Telegram ni
el recorrido completo. A1, aprobación y mensajería mantienen sus pendientes.
