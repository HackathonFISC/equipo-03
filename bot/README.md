# bot

**Dueño:** Noel

Bot de Telegram de H2Oeste. `bot.py` es el único proceso que recibe mensajes
del bot; `adaptador.py` envía las preguntas de aclaración. El bot solo habla con la API
(con un secreto compartido); nunca tiene claves de Supabase ni llama a Gemini.

## Arranque

La API debe estar corriendo. Desde la raíz del repositorio, con el entorno virtual activo:

```bash
python -m bot.bot
```

Solo un proceso por token: dos procesos con el mismo token se roban los mensajes.

## Configuración (`.env` en la raíz)

| Variable | Uso |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token de BotFather. |
| `TELEGRAM_ACCESO_PUBLICO` | `true` abre el bot a cualquier persona o grupo (ver «Acceso público»). Vacío o cualquier otro valor lo deja en modo de prueba. |
| `TELEGRAM_CHAT_IDS_PRUEBA` | Modo de prueba: chats que el bot atiende, separados por coma. Un grupo tiene ID negativo; un chat privado tiene el ID del usuario. Los demás chats se ignoran en silencio. Con el acceso público se ignora. |
| `API_SECRETO_BOT` | El mismo valor que usa la API, mínimo 16 caracteres. |
| `API_URL` | Opcional. Por defecto `http://127.0.0.1:8000`. |
| `BOT_LIMITE_USUARIO` | Opcional. Mensajes por persona en cada ventana (por defecto 8). |
| `BOT_LIMITE_TOTAL` | Opcional. Mensajes de todas las personas en cada ventana (por defecto 120). |
| `BOT_VENTANA_MINUTOS` | Opcional. Largo de la ventana (por defecto 10). |

Sin token, sin secreto válido, o sin acceso público ni chats autorizados, el bot no arranca y explica qué falta.

## Acceso público

El bot atiende a cualquiera solo con `TELEGRAM_ACCESO_PUBLICO=true`. Un valor vacío, mal escrito o
`false` lo deja en modo de prueba, así que un error de configuración nunca lo abre sin querer.

Para abrirlo:

1. En `.env`: `TELEGRAM_ACCESO_PUBLICO=true`. Reinicia el bot; el registro dice `Bot PÚBLICO` y el límite.
2. En BotFather: `/setjoingroups` en *Enable* si quieres que lo agreguen a grupos. Deja `/setprivacy`
   en *Enable*: así en un grupo solo ve comandos, menciones y respuestas dirigidas al bot.
3. Prueba con una cuenta que no esté en la lista: `/start`, un reporte y la respuesta a una pregunta de aclaración.

Qué cambia y qué no:

- **Qué cambia:** el filtro de chats. Cualquier persona o grupo recibe bienvenida, botones y acuse.
- **Los avisos de los planes no se abren.** Salen solo a los destinos autorizados en la base de datos.
  Un chat nuevo se registra como destino sin autorizar, y eso no le da avisos.
- **Límite de mensajes** (`bot/limites.py`): cada reporte llega a la Ingesta y gasta cuota del modelo.
  Cada persona puede enviar 8 mensajes cada 10 minutos y entre todas 120. Al pasarse, el bot avisa una
  sola vez por ventana y calla; esos mensajes no llegan a la API. El intento rechazado no cuenta: pasada
  la ventana, la persona vuelve a poder escribir. Los contadores viven en memoria y se reinician con el bot.
- **No hay moderación de contenido en el bot.** El texto de cualquiera llega a la Ingesta, que decide si
  es un reporte de falta de agua o está fuera de alcance. Lo que digan los desconocidos no se cree: pasa
  por revisión humana antes de afectar un plan.
- **El bot solo atiende mientras su proceso esté corriendo.** Con la laptop apagada, los mensajes esperan
  en Telegram y se procesan al volver (Telegram los guarda unas 24 horas).

## Qué hace con cada mensaje

| Mensaje | Chat privado | Grupo |
| --- | --- | --- |
| `/start`, `/ayuda`, `/help` | Bienvenida con botones. | Igual. |
| Texto | Posible reporte. | Solo si es reply a un mensaje del bot o lo menciona (`@usuario_del_bot`); la mención se quita del texto. El resto de la conversación no se registra. |
| Solo la mención, sin texto | No aplica. | Bienvenida con botones. |
| Reply a una pregunta de aclaración | Respuesta de aclaración. | Igual. |
| Reply a otro mensaje del bot | Reporte nuevo. | Igual. |
| Ubicación fija como reply a una pregunta | Respuesta de aclaración. | Igual. |
| Ubicación sin reply | Pide escribir el problema con texto. | Se ignora. |
| Ubicación en tiempo real | Explica que no se usa. | Igual. |
| Texto de más de 4000 caracteres | Pide acortarlo (límite del contrato). | Igual. |

Un mensaje de un bot o sin una persona identificable no se registra
(`supabase/IDENTIDAD_REPORTES.md`).

### Botones de bienvenida

- **Reportar falta de agua:** el bot menciona a quien pulsó y le abre una respuesta
  (`ForceReply` selectivo, solo para esa persona). Lo que escriba llega como reply al bot
  y se registra, también en grupos.
- **Qué debo escribir:** instrucciones (lugar, desde cuándo, personas y vulnerabilidad).

El menú "/" de Telegram muestra `/ayuda`; se publica al arrancar.

### Respuestas del bot

| Situación | Mensaje |
| --- | --- |
| Reporte nuevo | Recibimos tu mensaje. Código: (8 caracteres del reporte). |
| Mensaje nuevo sin relación con el agua (saludo, prueba) | El mismo acuse, más cuatro preguntas (dónde, desde cuándo, cuántas personas, si hay población vulnerable) y una respuesta enlazada: lo que la persona conteste entra como reporte nuevo. |
| Mensaje ya registrado | Ya habíamos recibido este mensaje. Código: … |
| API caída o con error | No pudimos guardar tu reporte ahora. Inténtalo de nuevo en unos minutos. |
| Respuesta `aceptada` o `repetida` | Gracias, recibimos tu respuesta. |
| `ya_respondida` | Esta pregunta ya fue respondida. |
| `autor_distinto` | Solo quien envió el reporte puede responder esta pregunta. |
| `vencida` | El plazo para responder esta pregunta venció. Tu reporte sigue pendiente de revisión. |

El acuse es neutral ("mensaje", no "reporte"): si un texto es un reporte de agua lo decide
el agente de Ingesta, no el bot. La Ingesta cierra como fuera de alcance lo que no es de agua y no puede
preguntar (su contrato lo prohíbe), así que el bot orienta por su cuenta: `parece_reporte_de_agua` busca
palabras del servicio (agua, tubería, cisterna, fuga…) solo para elegir el texto del acuse. No decide si el
mensaje se guarda: todo se envía a la API igual. Se equivoca a veces (un reporte sin esas palabras recibe las
preguntas; una charla que nombra el agua no). Orientar después de que la Ingesta clasifique requiere coordinarlo
con Emilia.

## Circuito de aclaración (V2, decisiones D006 y D008)

**Responder sin pulsar «Responder».** La API enlaza la respuesta con la pregunta por el id del mensaje del bot, así que un
mensaje suelto se tomaba como reporte nuevo y la aclaración quedaba sin contestar. Ahora el bot recuerda la última
pregunta que envió a cada persona en cada chat (`adaptador.recordar_pregunta`, en memoria, 30 minutos) y toma su siguiente
texto o pin como respuesta, en chat privado y en grupos. Para saber a quién va la pregunta, guarda quién envió cada
mensaje de reporte (`recordar_autor`). Una pregunta se contesta una vez; lo siguiente es un reporte nuevo. Un reply
explícito manda sobre lo recordado. En un grupo, los mensajes de otras personas o sin pregunta abierta siguen
ignorándose y sin registrarse. Si el bot se reinicia, se pierde lo recordado y vuelve a valer solo el reply. La API y la
base no cambian: el autor y el estado los sigue validando la RPC.

**Grupos y modo privacidad:** con el modo privacidad de BotFather activo (`/setprivacy` → Enable), Telegram solo entrega
al bot los comandos, las menciones y los replies a sus mensajes. Por eso en un grupo la respuesta sin «Responder» solo
llega si el modo privacidad está desactivado (Disable). Desactivarlo hace que el bot reciba todo el grupo, aunque descarte
lo que no sea una respuesta a su pregunta; es una decisión de seguridad, no solo de comodidad.

`adaptador.py`, si `ACLARACIONES_ACTIVAS` es `True`:

1. Cada 7 segundos pide a la API la siguiente pregunta pendiente (hasta 10 por ciclo).
2. La envía como reply al mensaje original del reporte.
3. Registra el resultado: `enviado` con el ID del mensaje; `fallido` si Telegram rechazó
   el envío (`BadRequest`, `Forbidden`); `incierto` si hubo tiempo agotado o fallo de red.
4. Nunca reenvía. Si no logra registrar el resultado, la reserva vence y queda para revisión.

Un reply a la pregunta se entrega a `POST /aclaraciones/respuestas` y el bot contesta según
el resultado. Si es `no_encontrada`, el reply no era a una pregunta y sigue como reporte nuevo.
El plazo de 30 minutos y el cambio a `espera_revision` los controla la RPC de Emilia.

## Envío de avisos aprobados (V4)

`bandeja.py`, si `AVISOS_ACTIVOS` es `True` (hoy `False`: requiere la migración 0011):

1. Cada 7 segundos pide a la API el siguiente aviso vigente (hasta 10 por ciclo).
2. Arma el mensaje con `plantillas.py` a partir de lugar, litros, ventana y versión. El bot no
   envía texto libre de un modelo. La hora es de Panamá (UTC-5 fijo) y el mensaje dice que es una
   estimación del plan y que puede cambiar.
3. Lo envía y registra `enviado` con el ID del mensaje, `fallido` si Telegram lo rechazó, o `incierto`
   si hubo tiempo agotado o fallo de red. Del error solo se guarda el tipo.
4. Nunca reenvía. Si no logra registrar el resultado, la reserva vence y la base lo deja `incierto`.

## Interruptor

`ACLARACIONES_ACTIVAS` en `adaptador.py`, en `True`: la migración `0006` está aplicada y la API
tiene `GUARDAR_DESTINO_ORIGEN = True`. Con `False` no se consultan preguntas, un reply al bot se
trata como reporte nuevo y una ubicación pide texto. Al arrancar, el bot indica si está apagado.

## Privacidad y seguridad

- El registro guarda IDs de chat y mensaje y el largo del texto, nunca el texto de una persona.
- Los registros de `httpx` se silencian porque la URL de Telegram contiene el token.
- Los nombres que aparecen en mensajes HTML se escapan.
- En modo de prueba, los chats no autorizados no reciben respuesta.
- En modo público, el límite de mensajes protege la cuota del modelo y la bandeja de reportes.

## Pruebas

```bash
python -m pytest bot/tests -q
```

Con API y Telegram simulados (`httpx.MockTransport`):

- `tests/test_bot_reportes.py`: reportes, errores de la API, autorización, privacidad del
  registro y ayuda.
- `tests/test_bot_aclaraciones.py`: envío, clasificación de errores de Telegram, sin
  reenvío, límite por ciclo, replies, ubicaciones e interruptor apagado.
- `tests/test_bot_botones_grupos.py`: filtro de grupos, menciones y botones.
- `tests/test_bot_publico.py`: modo público frente a modo de prueba, valores de `TELEGRAM_ACCESO_PUBLICO`,
  límite por persona y total, aviso único, reinicio de la ventana y tope de memoria.
- `tests/test_bot_avisos.py`: plantilla (cantidad, hora de Panamá, versión), envío, fallido e
  incierto sin reenvío, límite por ciclo y avisos apagados por defecto.

## Pendiente

- V4: activar `AVISOS_ACTIVOS` cuando se aplique la migración 0011 y haya un plan aprobado.
  Envío de un aviso real a un chat de prueba: sin probar contra Telegram.


## Pines fuera del catálogo

No hace falta una clave de Google Maps. Reportar primero el problema con texto;
si el lugar no se reconoce, responder a la pregunta geográfica del bot con
Adjuntar → Ubicación y seleccionar un pin fijo del lugar donde falta agua.
El pin puede estar fuera del catálogo. La API verifica autor, pregunta y plazo;
no se asocia una ubicación suelta al último reporte por suposición.

El panel Reportes muestra las coordenadas, precisión informada y un enlace al mapa
inmediatamente después de aceptar la respuesta, incluso antes de reprocesarla.
GET /reportes requiere sesión del panel, igual que las consultas de incidentes.
El pin resuelve automáticamente la ubicación del reporte, sin revisión del coordinador. No crea ni aprueba un punto de distribución.
Las preguntas geográficas incluyen instrucciones para adjuntar el pin; las
preguntas mixtas mantienen pendientes los datos no geográficos.

Reiniciar API y bot, y reconstruir el frontend para usar esta mejora. Utiliza
las tablas y RPC existentes de aclaraciones y la nueva migración 0018 de localización automática. Para resolver direcciones sin pin, configurar GOOGLE_MAPS_API_KEY. Ver [guía](../docs/LOCALIZACION_AUTOMATICA.md).
Prueba manual: enviar un reporte con un barrio desconocido, responder a la pregunta
con un pin fijo, y abrir el reporte en el panel con sesión iniciada.


## Audio

Notas de voz y archivos OGG/MP3/WAV/FLAC de hasta 2 minutos y 2 MiB. En grupos, solo replies al bot o menciones en la descripción del archivo. La transcripción se hace en la API y sigue como reporte o aclaración, con los mismos límites y controles. Requiere migración 0020 y GEMINI_API_KEY en el backend. Ver [guía](../docs/AUDIO_TELEGRAM.md).

## Fotos de Telegram

Fotos individuales de hasta 5 MiB con texto adjunto opcional. Requiere migración 0022 y GEMINI_API_KEY. Ver [guía de imágenes](../docs/IMAGENES_TELEGRAM.md).
