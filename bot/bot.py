"""Bot de Telegram de RutaAgua Oeste (V1, paso 2).

Único proceso que recibe mensajes del bot. Atiende solo los chats autorizados y
envía cada texto a la API (POST /reportes). No habla con Supabase directamente.

Arranque, desde la raíz del repositorio y con el entorno virtual activo
(la API debe estar corriendo):
    python -m bot.bot

Variables de .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS_PRUEBA, API_SECRETO_BOT
y, opcional, API_URL (por defecto http://127.0.0.1:8000).
"""
import logging
import os
import sys

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger("bot")

API_URL_POR_DEFECTO = "http://127.0.0.1:8000"
LARGO_MINIMO_SECRETO = 16
MAX_TEXTO = 4000  # Máximo del contrato; Telegram admite hasta 4096.

MENSAJE_RECIBIDO = "Recibimos tu reporte. Código: {codigo}."
MENSAJE_REPETIDO = "Ya habíamos registrado este mensaje. Código: {codigo}."
MENSAJE_LARGO = f"Tu mensaje es demasiado largo (máximo {MAX_TEXTO} caracteres). Envíalo más corto."
MENSAJE_FALLO = "No pudimos guardar tu reporte ahora. Inténtalo de nuevo en unos minutos."


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


async def recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envía un texto a la API solo si viene de un chat autorizado y de una persona."""
    chat = update.effective_chat
    mensaje = update.effective_message
    usuario = update.effective_user
    if chat is None or mensaje is None:
        return

    autorizados: set[int] = context.application.bot_data["chats_autorizados"]
    if chat.id not in autorizados:
        # Silencio hacia el remitente: no se responde a chats no autorizados.
        logger.warning("Mensaje ignorado de un chat no autorizado (id=%s)", chat.id)
        return

    if usuario is None or usuario.is_bot:
        # Convención de supabase/IDENTIDAD_REPORTES.md: sin persona identificable no se registra.
        logger.info("Mensaje ignorado: no tiene una persona identificable como remitente")
        return

    texto = mensaje.text or ""
    if len(texto) > MAX_TEXTO:
        await mensaje.reply_text(MENSAJE_LARGO)
        return

    # Solo se registran identificadores y el largo: el texto es de una persona y no va al registro.
    logger.info(
        "Texto recibido: chat=%s mensaje=%s largo=%d", chat.id, mensaje.message_id, len(texto)
    )
    cliente: httpx.AsyncClient = context.application.bot_data["cliente_api"]
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

    app = Application.builder().token(token).post_shutdown(cerrar_cliente).build()
    app.bot_data["chats_autorizados"] = autorizados
    app.bot_data["cliente_api"] = httpx.AsyncClient(
        base_url=url_api, headers={"X-Secreto-Bot": secreto}, timeout=10
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_texto))

    logger.info("Bot iniciado. Chats autorizados: %d. Ctrl+C para detenerlo.", len(autorizados))
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
