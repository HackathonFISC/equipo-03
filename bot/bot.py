"""Bot de Telegram de RutaAgua Oeste (V2: reportes y aclaraciones).

Único proceso que recibe mensajes del bot. Atiende solo los chats autorizados:
- En chats privados, un texto nuevo se envía a la API como reporte (POST /reportes).
- En grupos, solo se atiende lo dirigido al bot: reply a un mensaje suyo o mención.
- /start, /ayuda y /help muestran botones: «Reportar falta de agua» y «Qué debo escribir».
- Un reply a una pregunta del bot se entrega como respuesta de aclaración.
- Una ubicación solo se acepta como reply a una pregunta (acuerdo D004).
En segundo plano envía las aclaraciones pendientes (bot/adaptador.py).
No habla con Supabase directamente.

Arranque, desde la raíz del repositorio y con el entorno virtual activo
(la API debe estar corriendo):
    python -m bot.bot

Variables de .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS_PRUEBA, API_SECRETO_BOT
y, opcional, API_URL (por defecto http://127.0.0.1:8000).
"""
import asyncio
import html
import logging
import os
import re
import sys
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from telegram import BotCommand, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import adaptador
from bot.adaptador import MENSAJES_RESULTADO, ciclo_envio, entregar_respuesta, es_reply_al_bot

logger = logging.getLogger("bot")

API_URL_POR_DEFECTO = "http://127.0.0.1:8000"
LARGO_MINIMO_SECRETO = 16
MAX_TEXTO = 4000  # Máximo del contrato; Telegram admite hasta 4096.

# Acuse neutral: el bot no sabe si es un reporte hasta que lo analiza la Ingesta.
MENSAJE_RECIBIDO = "Recibimos tu mensaje. Código: {codigo}."
MENSAJE_REPETIDO = "Ya habíamos recibido este mensaje. Código: {codigo}."
MENSAJE_LARGO = f"Tu mensaje es demasiado largo (máximo {MAX_TEXTO} caracteres). Envíalo más corto."
MENSAJE_FALLO = "No pudimos guardar tu reporte ahora. Inténtalo de nuevo en unos minutos."
MENSAJE_FALLO_RESPUESTA = "No pudimos guardar tu respuesta ahora. Inténtalo de nuevo en unos minutos."
MENSAJE_SOLO_TEXTO = (
    "Para reportar, escribe el problema con texto. "
    "La ubicación solo se usa para responder a una pregunta del bot."
)
MENSAJE_AYUDA = (
    "Hola. Soy el bot de RutaAgua Oeste y sirvo para reportar falta de agua.\n\n"
    "Escribe en un solo mensaje:\n"
    "• Dónde: el lugar o punto de atención.\n"
    "• Desde cuándo no llega el agua.\n"
    "• Cuántas personas están afectadas.\n"
    "• Si hay personas con dificultad para conseguir agua, como adultos mayores, "
    "un centro de salud o una escuela.\n\n"
    "Ejemplo: «En la escuela de mi sector no llega agua desde el martes; somos unas 200 personas.»\n\n"
    "En un grupo, pulsa «Reportar falta de agua» o menciona al bot; "
    "los demás mensajes del grupo no se registran.\n"
    "Si te hago una pregunta, respóndela con «Responder» sobre mi mensaje.\n"
    "Tus mensajes se guardan para poder atender el reporte."
)
MENSAJE_BIENVENIDA = (
    "Hola. Soy el bot de RutaAgua Oeste y sirvo para reportar falta de agua. ¿Qué quieres hacer?"
)
# {nombre} es una mención HTML a quien pulsó el botón: así el teclado de respuesta solo se le abre a esa persona.
MENSAJE_PIDE_REPORTE = "{nombre}, escribe tu reporte respondiendo a este mensaje: dónde, desde cuándo y cuántas personas."

BOTON_REPORTAR = "reportar"
BOTON_INSTRUCCIONES = "instrucciones"
TECLADO_INICIO = InlineKeyboardMarkup([
    [InlineKeyboardButton("Reportar falta de agua", callback_data=BOTON_REPORTAR)],
    [InlineKeyboardButton("Qué debo escribir", callback_data=BOTON_INSTRUCCIONES)],
])
TIPOS_GRUPO = {"group", "supergroup"}
MENSAJE_EN_VIVO = "No usamos la ubicación en tiempo real. Comparte una ubicación fija como respuesta a la pregunta."


def leer_chats_autorizados(valor: str) -> set[int]:
    """Convierte '123,-100456' en {123, -100456}. Un valor no numérico lanza ValueError."""
    ids: set[int] = set()
    for parte in valor.split(","):
        parte = parte.strip()
        if parte:
            ids.add(int(parte))
    return ids


def _codigo(respuesta: httpx.Response) -> str | None:
    """Primeros 8 caracteres del reporte_id de la respuesta, o None si no es legible."""
    try:
        return str(respuesta.json()["reporte_id"])[:8]
    except (ValueError, KeyError, TypeError):
        return None


def _origen_valido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(chat, mensaje, usuario) si el mensaje viene de un chat autorizado y de una persona."""
    chat = update.effective_chat
    mensaje = update.effective_message
    usuario = update.effective_user
    if chat is None or mensaje is None:
        return None

    autorizados: set[int] = context.application.bot_data["chats_autorizados"]
    if chat.id not in autorizados:
        # Silencio hacia el remitente: no se responde a chats no autorizados.
        logger.warning("Mensaje ignorado de un chat no autorizado (id=%s)", chat.id)
        return None

    if usuario is None or usuario.is_bot:
        # Convención de supabase/IDENTIDAD_REPORTES.md: sin persona identificable no se registra.
        logger.info("Mensaje ignorado: no tiene una persona identificable como remitente")
        return None
    return chat, mensaje, usuario


def _id_del_bot(context) -> int | None:
    return getattr(getattr(context, "bot", None), "id", None)


def _usuario_del_bot(context) -> str | None:
    return getattr(getattr(context, "bot", None), "username", None)


def _es_grupo(chat) -> bool:
    return getattr(chat, "type", None) in TIPOS_GRUPO


def _sin_mencion(texto: str, usuario_bot: str | None) -> tuple[str, bool]:
    """Quita "@usuario_del_bot" del texto. Devuelve (texto_limpio, había_mención)."""
    if not usuario_bot:
        return texto, False
    patron = re.compile(rf"@{re.escape(usuario_bot)}\b", re.IGNORECASE)
    limpio, cambios = patron.subn("", texto)
    return " ".join(limpio.split()), cambios > 0


async def _responder_aclaracion(mensaje, chat, usuario, cliente, contenido: dict) -> str | None:
    """Entrega un reply a la API. Devuelve el resultado; None si falló (ya avisado)."""
    resultado = await entregar_respuesta(cliente, {
        "usuario_telegram_id": usuario.id,
        "chat_id": chat.id,
        "pregunta_mensaje_id": mensaje.reply_to_message.message_id,
        "message_id": mensaje.message_id,
        **contenido,
    })
    if resultado is None:
        await mensaje.reply_text(MENSAJE_FALLO_RESPUESTA)
    elif resultado in MENSAJES_RESULTADO:
        await mensaje.reply_text(MENSAJES_RESULTADO[resultado])
    return resultado


async def mostrar_ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start, /ayuda y /help: bienvenida con botones. No llama a la API ni guarda nada."""
    origen = _origen_valido(update, context)
    if origen is None:
        return
    _, mensaje, _ = origen
    await mensaje.reply_text(MENSAJE_BIENVENIDA, reply_markup=TECLADO_INICIO)


async def atender_boton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Botones del mensaje de bienvenida. Nunca registra nada: solo orienta."""
    consulta = update.callback_query
    if consulta is None:
        return
    # Responder siempre a la pulsación quita el indicador de carga del botón en Telegram.
    await consulta.answer()
    mensaje = consulta.message
    chat = mensaje.chat if mensaje else None
    usuario = consulta.from_user
    autorizados: set[int] = context.application.bot_data["chats_autorizados"]
    if chat is None or chat.id not in autorizados or usuario is None or usuario.is_bot:
        return
    if consulta.data == BOTON_INSTRUCCIONES:
        await mensaje.reply_text(MENSAJE_AYUDA)
    elif consulta.data == BOTON_REPORTAR:
        nombre = f'<a href="tg://user?id={usuario.id}">{html.escape(usuario.first_name or "Hola")}</a>'
        await mensaje.reply_text(
            MENSAJE_PIDE_REPORTE.format(nombre=nombre),
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(selective=True, input_field_placeholder="Ej.: Sin agua desde el martes en…"),
        )


async def recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Texto de un chat autorizado: respuesta de aclaración si es reply al bot; si no, reporte."""
    origen = _origen_valido(update, context)
    if origen is None:
        return
    chat, mensaje, usuario = origen
    cliente: httpx.AsyncClient = context.application.bot_data["cliente_api"]

    texto = mensaje.text or ""
    dirigido = es_reply_al_bot(mensaje, _id_del_bot(context))
    texto, mencionado = _sin_mencion(texto, _usuario_del_bot(context))
    if _es_grupo(chat) and not (dirigido or mencionado):
        # En grupos solo se atiende lo dirigido al bot; la conversación del grupo no se registra.
        logger.debug("Mensaje de grupo no dirigido al bot: chat=%s", chat.id)
        return
    if mencionado and not texto:
        await mensaje.reply_text(MENSAJE_BIENVENIDA, reply_markup=TECLADO_INICIO)
        return
    if len(texto) > MAX_TEXTO:
        await mensaje.reply_text(MENSAJE_LARGO)
        return

    if adaptador.ACLARACIONES_ACTIVAS and dirigido:
        resultado = await _responder_aclaracion(mensaje, chat, usuario, cliente, {"texto": texto})
        if resultado != "no_encontrada":
            return
        # El reply no era a una pregunta (por ejemplo, a "Recibimos tu reporte"): es un reporte nuevo.

    # Solo se registran identificadores y el largo: el texto es de una persona y no va al registro.
    logger.info(
        "Texto recibido: chat=%s mensaje=%s largo=%d", chat.id, mensaje.message_id, len(texto)
    )
    try:
        respuesta = await cliente.post(
            "/reportes",
            json={
                "usuario_telegram_id": usuario.id,
                "chat_id": chat.id,
                "message_id": mensaje.message_id,
                "texto": texto,
            },
        )
    except httpx.HTTPError as error:
        logger.error("No se pudo llamar a la API: %s", type(error).__name__)
        await mensaje.reply_text(MENSAJE_FALLO)
        return

    codigo = _codigo(respuesta)
    if respuesta.status_code == 201 and codigo:
        await mensaje.reply_text(MENSAJE_RECIBIDO.format(codigo=codigo))
    elif respuesta.status_code == 200 and codigo:
        await mensaje.reply_text(MENSAJE_REPETIDO.format(codigo=codigo))
    else:
        # 403 aquí significa que API_SECRETO_BOT no coincide con el de la API.
        logger.error("La API respondió con el código %s", respuesta.status_code)
        await mensaje.reply_text(MENSAJE_FALLO)


async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ubicación: solo vale como reply a una pregunta del bot y solo si es fija."""
    origen = _origen_valido(update, context)
    if origen is None:
        return
    chat, mensaje, usuario = origen
    ubicacion = mensaje.location
    if getattr(ubicacion, "live_period", None):
        await mensaje.reply_text(MENSAJE_EN_VIVO)
        return
    dirigido = es_reply_al_bot(mensaje, _id_del_bot(context))
    if _es_grupo(chat) and not dirigido:
        return  # En grupos, una ubicación compartida en la conversación no es para el bot.
    if not adaptador.ACLARACIONES_ACTIVAS or not dirigido:
        await mensaje.reply_text(MENSAJE_SOLO_TEXTO)
        return
    cliente: httpx.AsyncClient = context.application.bot_data["cliente_api"]
    resultado = await _responder_aclaracion(mensaje, chat, usuario, cliente, {
        "ubicacion": {
            "latitud": ubicacion.latitude,
            "longitud": ubicacion.longitude,
            "precision_metros": getattr(ubicacion, "horizontal_accuracy", None),
        },
    })
    if resultado == "no_encontrada":
        await mensaje.reply_text(MENSAJE_SOLO_TEXTO)


async def iniciar_envio(app: Application) -> None:
    """Publica el menú de comandos y arranca el envío de aclaraciones (si están activas)."""
    try:
        await app.bot.set_my_commands([BotCommand("ayuda", "Cómo reportar falta de agua")])
    except TelegramError as error:
        # El menú es una ayuda visual: si falla, el bot sigue funcionando.
        logger.warning("No se pudo publicar el menú de comandos: %s", type(error).__name__)
    if not adaptador.ACLARACIONES_ACTIVAS:
        logger.info("Aclaraciones apagadas: no se consultan preguntas pendientes.")
        return
    app.bot_data["tarea_envio"] = asyncio.create_task(
        ciclo_envio(app.bot, app.bot_data["cliente_api"], app.bot_data["trabajador_id"])
    )


async def detener_envio(app: Application) -> None:
    tarea = app.bot_data.get("tarea_envio")
    if tarea:
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass


async def cerrar_cliente(app: Application) -> None:
    await app.bot_data["cliente_api"].aclose()


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    # httpx registra la URL de cada petición y la de Telegram contiene el token del bot.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Falta TELEGRAM_BOT_TOKEN en .env")

    try:
        autorizados = leer_chats_autorizados(os.getenv("TELEGRAM_CHAT_IDS_PRUEBA", ""))
    except ValueError:
        sys.exit("TELEGRAM_CHAT_IDS_PRUEBA debe tener IDs numéricos separados por comas")
    if not autorizados:
        sys.exit(
            "TELEGRAM_CHAT_IDS_PRUEBA está vacío: sin chats autorizados el bot no atiende a nadie"
        )

    secreto = os.getenv("API_SECRETO_BOT", "").strip()
    if len(secreto) < LARGO_MINIMO_SECRETO:
        sys.exit(
            f"Falta API_SECRETO_BOT en .env (mínimo {LARGO_MINIMO_SECRETO} caracteres, "
            "el mismo valor que usa la API)"
        )
    url_api = os.getenv("API_URL", API_URL_POR_DEFECTO).strip().rstrip("/")

    app = (
        Application.builder()
        .token(token)
        .post_init(iniciar_envio)
        .post_stop(detener_envio)
        .post_shutdown(cerrar_cliente)
        .build()
    )
    app.bot_data["chats_autorizados"] = autorizados
    app.bot_data["trabajador_id"] = f"bot:{uuid4()}"
    app.bot_data["cliente_api"] = httpx.AsyncClient(
        base_url=url_api, headers={"X-Secreto-Bot": secreto}, timeout=10
    )
    app.add_handler(CommandHandler(["start", "ayuda", "help"], mostrar_ayuda))
    app.add_handler(CallbackQueryHandler(atender_boton))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_texto))
    app.add_handler(MessageHandler(filters.LOCATION, recibir_ubicacion))

    logger.info("Bot iniciado. Chats autorizados: %d. Ctrl+C para detenerlo.", len(autorizados))
    # callback_query: pulsaciones de los botones del mensaje de bienvenida.
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
