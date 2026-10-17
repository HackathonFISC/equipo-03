"""Adaptador del circuito de aclaración (V2, acuerdo D004 con Emilia).

- Envío: cada pocos segundos reserva aclaraciones pendientes en la API, envía la
  pregunta como reply al mensaje original del reporte y registra el resultado.
  Nunca reenvía: un envío incierto o sin registrar queda para revisión.
- Respuesta: un reply a una pregunta del bot se entrega a la API, que llama a la
  RPC de Emilia. El bot no cambia estados ni guarda nada por su cuenta.
"""
import asyncio
import logging

import httpx
from telegram import ForceReply, ReplyParameters
from telegram.error import BadRequest, Forbidden, TelegramError

logger = logging.getLogger("bot.adaptador")

# Requiere la migración 0006 de Emilia (ya aplicada) y GUARDAR_DESTINO_ORIGEN = True en la API.
# Con False: no se consultan pendientes y un reply al bot se trata como reporte nuevo.
ACLARACIONES_ACTIVAS = True

INTERVALO_SEGUNDOS = 7  # Acordado: consultar cada 5–10 s.
MAX_POR_CICLO = 10  # Evita que un lote grande bloquee el bot en un solo ciclo.

MENSAJE_RESPUESTA_RECIBIDA = "Gracias, recibimos tu respuesta."
MENSAJES_RESULTADO = {
    "aceptada": MENSAJE_RESPUESTA_RECIBIDA,
    "repetida": MENSAJE_RESPUESTA_RECIBIDA,
    "ya_respondida": "Esta pregunta ya fue respondida.",
    "autor_distinto": "Solo quien envió el reporte puede responder esta pregunta.",
    "vencida": "El plazo para responder esta pregunta venció. Tu reporte sigue pendiente de revisión.",
}
# "no_encontrada" no tiene mensaje: el reply no era a una pregunta y sigue el flujo de reporte.


def es_reply_al_bot(mensaje, bot_id) -> bool:
    """True si el mensaje responde (reply) a un mensaje enviado por este bot."""
    original = getattr(mensaje, "reply_to_message", None)
    autor = getattr(original, "from_user", None) if original else None
    return bool(bot_id) and autor is not None and autor.id == bot_id


async def entregar_respuesta(cliente: httpx.AsyncClient, cuerpo: dict) -> str | None:
    """Devuelve el resultado de la API, o None si no se pudo entregar."""
    try:
        respuesta = await cliente.post("/aclaraciones/respuestas", json=cuerpo)
    except httpx.HTTPError as error:
        logger.error("No se pudo entregar la respuesta a la API: %s", type(error).__name__)
        return None
    if respuesta.status_code != 200:
        logger.error("La API rechazó la respuesta con el código %s", respuesta.status_code)
        return None
    try:
        resultado = respuesta.json()["resultado"]
    except (ValueError, KeyError, TypeError):
        logger.error("La API devolvió una respuesta ilegible")
        return None
    if resultado not in MENSAJES_RESULTADO and resultado != "no_encontrada":
        logger.error("Resultado desconocido de la API")
        return None
    return resultado


async def _registrar_envio(cliente, aclaracion_id, trabajador_id, estado, mensaje_id=None, error=None):
    cuerpo = {"trabajador_id": trabajador_id, "estado": estado,
              "proveedor_mensaje_id": mensaje_id, "error": error}
    try:
        respuesta = await cliente.post(f"/aclaraciones/{aclaracion_id}/envio", json=cuerpo)
    except httpx.HTTPError as fallo:
        respuesta, motivo = None, type(fallo).__name__
    else:
        motivo = f"código {respuesta.status_code}"
    if respuesta is None or respuesta.status_code != 204:
        # Sin reintento: la reserva vencerá y la aclaración quedará para revisión (D004).
        logger.error("No se pudo registrar el envío de %s (%s); queda para revisión",
                     aclaracion_id, motivo)


async def enviar_una(bot, cliente, trabajador_id: str, aclaracion: dict) -> None:
    """Envía una pregunta reservada y registra enviado, fallido o incierto."""
    original = aclaracion.get("mensaje_original_id")
    respuesta_a = (
        ReplyParameters(message_id=original, allow_sending_without_reply=True)
        if original else None
    )
    try:
        enviado = await bot.send_message(
            chat_id=aclaracion["chat_id"],
            text=aclaracion["pregunta"],
            reply_parameters=respuesta_a,
            # Telegram abre la respuesta ya enlazada a la pregunta: sin esto, quien escribe sin pulsar
            # «Responder» crea un reporte nuevo en lugar de contestar.
            reply_markup=ForceReply(selective=True, input_field_placeholder="Escribe tu respuesta aquí"),
        )
    except (BadRequest, Forbidden) as error:
        # Telegram rechazó el envío: es seguro que no llegó.
        await _registrar_envio(cliente, aclaracion["aclaracion_id"], trabajador_id,
                               "fallido", error=f"Telegram: {type(error).__name__}")
        return
    except TelegramError as error:
        # Tiempo agotado o red: pudo haber llegado. Incierto y sin reenvío.
        await _registrar_envio(cliente, aclaracion["aclaracion_id"], trabajador_id,
                               "incierto", error=f"Telegram: {type(error).__name__}")
        return
    await _registrar_envio(cliente, aclaracion["aclaracion_id"], trabajador_id,
                           "enviado", mensaje_id=str(enviado.message_id))


async def enviar_pendientes(bot, cliente: httpx.AsyncClient, trabajador_id: str) -> int:
    """Reserva y envía hasta MAX_POR_CICLO aclaraciones. Devuelve cuántas envió o intentó."""
    atendidas = 0
    while atendidas < MAX_POR_CICLO:
        try:
            respuesta = await cliente.post("/aclaraciones/reservar", json={"trabajador_id": trabajador_id})
        except httpx.HTTPError as error:
            logger.warning("La API no respondió al reservar: %s", type(error).__name__)
            break
        if respuesta.status_code == 204:
            break
        if respuesta.status_code != 200:
            logger.warning("La API respondió %s al reservar", respuesta.status_code)
            break
        try:
            aclaracion = respuesta.json()
            aclaracion["aclaracion_id"], aclaracion["chat_id"], aclaracion["pregunta"]
        except (ValueError, KeyError, TypeError):
            logger.error("La API devolvió una reserva ilegible; se detiene el ciclo")
            break
        await enviar_una(bot, cliente, trabajador_id, aclaracion)
        atendidas += 1
    return atendidas


async def ciclo_envio(bot, cliente: httpx.AsyncClient, trabajador_id: str,
                      intervalo: float = INTERVALO_SEGUNDOS) -> None:
    """Tarea de fondo del bot. Un error en un ciclo no detiene los siguientes."""
    while True:
        try:
            await enviar_pendientes(bot, cliente, trabajador_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 — la tarea no debe morir por un fallo puntual
            logger.error("Fallo en el ciclo de aclaraciones: %s", type(error).__name__)
        await asyncio.sleep(intervalo)
