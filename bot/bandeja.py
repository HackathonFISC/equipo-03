"""Envío de avisos aprobados (V4): reserva en la API, envía por Telegram y registra el resultado.

Mismo patrón que el circuito de aclaraciones, con la misma regla de seguridad: nunca reenvía.
- Telegram rechazó el envío (BadRequest/Forbidden): fallido, seguro que no llegó.
- Tiempo agotado o red caída: incierto, pudo llegar. Queda visible y no se reenvía solo.
- Si no se pudo registrar el resultado, la reserva vence y la RPC lo deja incierto.
"""
import asyncio
import logging
from datetime import datetime

import httpx
from telegram.error import BadRequest, Forbidden, TelegramError

from bot.plantillas import texto_aviso

logger = logging.getLogger("bot.bandeja")

# Requiere la migración 0010 aplicada. Con False, el bot no consulta avisos pendientes.
AVISOS_ACTIVOS = False

INTERVALO_SEGUNDOS = 7
MAX_POR_CICLO = 10


async def _registrar(cliente, aviso_id, trabajador_id, estado, mensaje_id=None, error=None) -> None:
    cuerpo = {"trabajador_id": trabajador_id, "estado": estado,
              "proveedor_mensaje_id": mensaje_id, "error": error}
    try:
        respuesta = await cliente.post(f"/avisos/{aviso_id}/envio", json=cuerpo)
    except httpx.HTTPError as fallo:
        respuesta, motivo = None, type(fallo).__name__
    else:
        motivo = f"código {respuesta.status_code}"
    if respuesta is None or respuesta.status_code != 204:
        # Sin reintento: la reserva vencerá y la RPC dejará el aviso como incierto.
        logger.error("No se pudo registrar el envío del aviso %s (%s); quedará incierto", aviso_id, motivo)


def _redactar(aviso: dict) -> str:
    return texto_aviso(
        tipo=aviso["tipo"],
        punto_nombre=aviso["punto_nombre"],
        litros_asignados=float(aviso["litros_asignados"]),
        ventana_inicio=datetime.fromisoformat(aviso["ventana_inicio"]),
        ventana_fin=datetime.fromisoformat(aviso["ventana_fin"]),
        version=int(aviso["version"]),
    )


async def enviar_uno(bot, cliente, trabajador_id: str, aviso: dict) -> None:
    """Envía un aviso reservado y registra enviado, fallido o incierto."""
    try:
        texto = _redactar(aviso)
    except (KeyError, ValueError, TypeError):
        await _registrar(cliente, aviso.get("aviso_id"), trabajador_id, "fallido",
                         error="Datos del aviso incompletos: no se envió")
        return
    try:
        enviado = await bot.send_message(chat_id=aviso["chat_id"], text=texto)
    except (BadRequest, Forbidden) as error:
        await _registrar(cliente, aviso["aviso_id"], trabajador_id, "fallido",
                         error=f"Telegram: {type(error).__name__}")
        return
    except TelegramError as error:
        await _registrar(cliente, aviso["aviso_id"], trabajador_id, "incierto",
                         error=f"Telegram: {type(error).__name__}")
        return
    await _registrar(cliente, aviso["aviso_id"], trabajador_id, "enviado", mensaje_id=str(enviado.message_id))


async def enviar_pendientes(bot, cliente: httpx.AsyncClient, trabajador_id: str) -> int:
    """Reserva y envía hasta MAX_POR_CICLO avisos. Devuelve cuántos atendió."""
    atendidos = 0
    while atendidos < MAX_POR_CICLO:
        try:
            respuesta = await cliente.post("/avisos/reservar", json={"trabajador_id": trabajador_id})
        except httpx.HTTPError as error:
            logger.warning("La API no respondió al reservar avisos: %s", type(error).__name__)
            break
        if respuesta.status_code == 204:
            break
        if respuesta.status_code != 200:
            logger.warning("La API respondió %s al reservar avisos", respuesta.status_code)
            break
        try:
            aviso = respuesta.json()
            aviso["aviso_id"], aviso["chat_id"]
        except (ValueError, KeyError, TypeError):
            logger.error("La API devolvió una reserva de aviso ilegible; se detiene el ciclo")
            break
        await enviar_uno(bot, cliente, trabajador_id, aviso)
        atendidos += 1
    return atendidos


async def ciclo_avisos(bot, cliente: httpx.AsyncClient, trabajador_id: str,
                       intervalo: float = INTERVALO_SEGUNDOS) -> None:
    """Tarea de fondo del bot. Un error en un ciclo no detiene los siguientes."""
    while True:
        try:
            await enviar_pendientes(bot, cliente, trabajador_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 — la tarea no debe morir por un fallo puntual
            logger.error("Fallo en el ciclo de avisos: %s", type(error).__name__)
        await asyncio.sleep(intervalo)
