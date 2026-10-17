# Fotos de Telegram

El bot recibe una foto individual enviada como foto de Telegram (no documento ni álbum),
con texto adjunto opcional de hasta 1024 caracteres. Elige la versión de mayor resolución
que no supere 5 MiB. En grupos requiere mención, reply al bot o pregunta abierta de ese autor.

Gemini describe lo visible y lee texto legible. El texto adjunto se conserva separado de
la descripción automática. No se deducen población, duración, vulnerabilidad, coordenadas
ni prioridad a partir de la apariencia de una imagen. El resultado sigue el flujo existente
de reportes o aclaraciones, ubicación y evaluación de prioridad; faltantes se preguntan.
No se guardan la foto, identificadores de archivo ni base64: solo la descripción y el texto
adjunto, con fuente_texto=descripcion_imagen y evidencia tipo foto. La descripción automática
puede contener errores y no equivale a verificar el contenido de la foto o de un aviso.

## Activación

1. Aplicar migraciones existentes, incluida 0020_transcripciones_audio.sql y luego
   0022_descripciones_imagen.sql. Esta implementación no modifica Supabase remoto.
2. Configurar GEMINI_API_KEY en el backend. GEMINI_IMAGE_MODEL es opcional; vacío
   reutiliza GEMINI_MODEL. No se usa una clave de Google Maps.
3. Reiniciar API y bot, y reconstruir el frontend. Solo un receptor por token Telegram.
4. Enviar en privado una foto con un texto como «Sin agua desde hace 48 horas en
   Escuela El Coco; somos 120 personas». Verificar el acuse y la procedencia en Reportes.
   Responder también con foto a una aclaración y comprobar que no crea otro reporte.

POST /imagenes/analizar exige secreto del bot, valida tamaño, firma JPEG/PNG e identidad
y reutiliza descripciones ya guardadas en reintentos sin consultar Gemini otra vez.
El endpoint no crea reportes; el bot guarda el resultado después. Un reintento previo
al guardado puede consumir otra solicitud Gemini. Fallos o imágenes ilegibles no generan
reportes ficticios. Las pruebas usan proveedores simulados, sin consumir cuota real.

Referencia: [imágenes en Gemini](https://ai.google.dev/gemini-api/docs/image-understanding).
