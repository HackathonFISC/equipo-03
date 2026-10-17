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
| `TELEGRAM_CHAT_IDS_PRUEBA` | Chats que el bot atiende, separados por coma. Un grupo tiene ID negativo; un chat privado tiene el ID del usuario. Los demás chats se ignoran en silencio. |
| `API_SECRETO_BOT` | El mismo valor que usa la API, mínimo 16 caracteres. |
| `API_URL` | Opcional. Por defecto `http://127.0.0.1:8000`. |

Sin token, sin chats autorizados o sin secreto válido, el bot no arranca y explica qué falta.

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
| Mensaje ya registrado | Ya habíamos recibido este mensaje. Código: … |
| API caída o con error | No pudimos guardar tu reporte ahora. Inténtalo de nuevo en unos minutos. |
| Respuesta `aceptada` o `repetida` | Gracias, recibimos tu respuesta. |
| `ya_respondida` | Esta pregunta ya fue respondida. |
| `autor_distinto` | Solo quien envió el reporte puede responder esta pregunta. |
| `vencida` | El plazo para responder esta pregunta venció. Tu reporte sigue pendiente de revisión. |

El acuse es neutral ("mensaje", no "reporte"): si un texto es un reporte de agua lo decide
el agente de Ingesta, no el bot.

## Circuito de aclaración (V2, decisiones D006 y D008)

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
- Los chats no autorizados no reciben respuesta.

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
- `tests/test_bot_avisos.py`: plantilla (cantidad, hora de Panamá, versión), envío, fallido e
  incierto sin reenvío, límite por ciclo y avisos apagados por defecto.

## Pendiente

- V4: activar `AVISOS_ACTIVOS` cuando se aplique la migración 0011 y haya un plan aprobado.
  Envío de un aviso real a un chat de prueba: sin probar contra Telegram.
