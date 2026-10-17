# Mensajes de audio de Telegram

El bot acepta notas de voz y archivos OGG, MP3, WAV o FLAC de hasta dos minutos y
2 MiB. Transcribe en el backend con Gemini y entrega el texto al mismo circuito de
reportes, aclaraciones, ubicación y planificación. No conserva la grabación en
disco ni en Supabase; conserva únicamente la transcripción y su procedencia.

## Activación

1. Aplicar `supabase/migrations/0020_transcripciones_audio.sql` después de las
   migraciones existentes hasta 0019. Es aditiva: agrega procedencia de texto y
   una RPC para respuestas de audio. No cambia distribución, ubicaciones o permisos
   de aprobación. La implementación local no aplica SQL al proyecto remoto.
2. Usar `GEMINI_API_KEY` en el `.env` del backend. No se usa la clave de Google Maps
   para transcribir. `GEMINI_MODEL` debe admitir entrada de audio y generateContent
   con salida JSON; el proyecto usa gemini-3.8-flash de forma predeterminada.
3. Opcionalmente, configurar `GEMINI_AUDIO_MODEL` para separar el modelo de audio
   del de extracción. Si se deja vacío, reutiliza `GEMINI_MODEL`.
4. Reiniciar API y bot; reconstruir el frontend para ver la etiqueta de audio.
   Solo debe existir un proceso receptor por token de Telegram.

No hace falta instalar FFmpeg ni otro SDK para estos formatos. La disponibilidad
real y las cuotas dependen del modelo y del proyecto Gemini. Los límites de
mensajes existentes del bot se aplican antes de descargar y transcribir.

## Uso

En privado, enviar un audio como reporte nuevo. En un grupo, responder a un mensaje
del bot; en archivos con descripción también puede mencionarse al bot en esa
descripción. Las conversaciones de audio del grupo que no se dirigen al bot se
ignoran antes de descargar. Los chats y autores no autorizados se ignoran igual
que en el flujo de texto.

Para responder a una aclaración, grabar el audio como respuesta a la pregunta del
bot. Se conservan los controles de autor, pregunta, plazo y repetición. Si la
respuesta no corresponde a una pregunta activa, conserva el comportamiento normal
del bot para reportes nuevos. Los resultados negativos (otro autor, vencida, etc.)
no se convierten en reportes nuevos.

El backend solicita una transcripción fiel, con números pronunciados representados
como dígitos, y no permite completar cantidades ni lugares por suposición. Los
clips sin habla inteligible o cuya transcripción no termina normalmente se rechazan
con una invitación a grabar mejor o escribir. La transcripción puede contener
errores: no constituye validación de población, demanda ni de un sitio de entrega.

## Persistencia y procedencia

Las grabaciones se normalizan a `modalidad=texto` y
`fuente_texto=transcripcion_audio`. Esto permite reutilizar la ingesta existente
sin crear un adjunto privado ficticio. El contrato `modalidad=voz` sigue reservado
para un circuito que conserve el adjunto original. Reportes muestra la etiqueta
«Transcripción automática de un mensaje de audio».

Las respuestas usan `aclaraciones.respuesta_fuente_texto=transcripcion_audio`,
actualizado en la misma transacción que acepta la respuesta. Ingesta registra
estos respaldos con evidencia de tipo audio y aclara que las citas se cotejan
contra la transcripción, no contra una grabación conservada.

`POST /audio/transcribir` exige X-Secreto-Bot, valida formato, tamaño y duración,
y devuelve `{texto, fuente_texto}`. No guarda ni publica el clip. El bot después
usa POST /reportes o POST /aclaraciones/respuestas. Un mensaje ya guardado devuelve
su transcripción con verificación de autor sin volver a consultar Gemini. Si la
transcripción terminó pero todavía no se guardó el mensaje, un reintento puede
consumir otra solicitud; la persistencia del reporte sigue siendo idempotente.
No se registran claves, grabaciones ni transcripciones en los logs de la aplicación.

## Verificación

Las pruebas simulan Telegram y Gemini, sin datos ni cuota real:

```sh
python -m pytest agentes/tests/test_transcripcion.py api/tests/test_audio.py bot/tests/test_bot_audio.py -q
```

La prueba PostgreSQL efímera `supabase/tests/0020_integracion_local.mjs` aplica las
migraciones y verifica procedencia, autoría, reintentos y regresiones de aclaraciones.
Usa RA_PGLITE_PACKAGE para indicar un package.json temporal con @electric-sql/pglite.
No se conecta al Supabase remoto.

Prueba manual tras activar: enviar un audio corto en español describiendo lugar,
horas sin agua y personas; comprobar acuse y transcripción en Reportes. Responder
por audio a una aclaración y comprobar que no crea otro reporte. Probar ruido o
silencio para comprobar la invitación a repetir. La calidad real con notas OGG/Opus
y el modelo de tu proyecto requiere esta prueba con Telegram/Gemini conectados.

Referencia: [audio en Gemini](https://ai.google.dev/gemini-api/docs/audio).
