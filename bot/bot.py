"""Bot de Telegram de RutaAgua Oeste (V1, paso 1).

Único proceso que recibe mensajes del bot. Por ahora solo atiende los chats
autorizados y confirma la recepción: todavía no llama a la API ni a Supabase.

Arranque, desde la raíz del repositorio y con el entorno virtual activo:
    python -m bot.bot
"""
import logging
import os
import sys

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger("bot")


def leer_chats_autorizados(valor: str) -> set[int]:
    """Convierte '123,-100456' en {123, -100456}. Un valor no numérico lanza ValueError."""
    ids: set[int] = set()
    for parte in valor.split(","):
        parte = parte.strip()
        if parte:
            ids.add(int(parte))
    return ids


async def recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Atiende un mensaje de texto solo si viene de un chat autorizado."""
    chat = update.effective_chat
    mensaje = update.effective_message
    if chat is None or mensaje is None:
        return

    autorizados: set[int] = context.application.bot_data["chats_autorizados"]
    if chat.id not in autorizados:
        # Silencio hacia el remitente: no se responde a chats no autorizados.
        logger.warning("Mensaje ignorado de un chat no autorizado (id=%s)", chat.id)
        return

    logger.info(
        "Texto recibido: chat=%s mensaje=%s texto=%r",
        chat.id,
        mensaje.message_id,
        mensaje.text,
    )
    await mensaje.reply_text(
        "Mensaje recibido. Todavía no se guarda: el bot está en modo de prueba."
    )


def main() -> None:
    load_dotenv()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    # httpx registra la URL de cada petición y esa URL contiene el token del bot.
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

    app = Application.builder().token(token).build()
    app.bot_data["chats_autorizados"] = autorizados
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_texto))

    logger.info("Bot iniciado. Chats autorizados: %d. Ctrl+C para detenerlo.", len(autorizados))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
