"""Un mensaje sin relación con el agua recibe preguntas concretas en vez de un acuse seco."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from telegram import ForceReply

from bot.bot import MENSAJE_ORIENTA, parece_reporte_de_agua, recibir_texto

REPORTE_ID = "2be33e79-1dc1-4a61-8e01-98387f19cef6"


def enviar(texto, estado=201):
    llamadas = []

    def manejador(peticion):
        llamadas.append(peticion)
        return httpx.Response(estado, json={"reporte_id": REPORTE_ID})

    cliente = httpx.AsyncClient(base_url="http://api.prueba", transport=httpx.MockTransport(manejador))
    respuestas = AsyncMock()
    mensaje = SimpleNamespace(message_id=7, text=texto, reply_text=respuestas)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=-1001), effective_message=mensaje,
        effective_user=SimpleNamespace(id=111, is_bot=False),
    )
    contexto = SimpleNamespace(application=SimpleNamespace(
        bot_data={"chats_autorizados": {-1001}, "cliente_api": cliente}))
    asyncio.run(recibir_texto(update, contexto))
    return llamadas, respuestas


@pytest.mark.parametrize("texto", ["Hola", "hola buenas tardes", "probando 123", "¿quién eres?", "gracias"])
def test_mensaje_sin_relacion_con_agua_recibe_preguntas_y_respuesta_enlazada(texto):
    llamadas, respuestas = enviar(texto)
    assert len(llamadas) == 1  # igual se guarda como reporte: la decisión de alcance es de la Ingesta
    assert json.loads(llamadas[0].content)["texto"] == texto
    respuestas.assert_awaited_once()
    args, kwargs = respuestas.await_args
    assert args == (MENSAJE_ORIENTA.format(codigo="2be33e79"),)
    assert "¿Dónde falta el agua?" in args[0] and "¿Cuántas personas" in args[0]
    assert isinstance(kwargs["reply_markup"], ForceReply) and kwargs["reply_markup"].selective


@pytest.mark.parametrize("texto", [
    "Llevamos tres días sin agua en P1", "No llega AGUA desde el martes", "La tubería del barrio está rota",
    "Necesitamos un camión cisterna", "Hay una fuga grande", "Sin servicio hace dos días",
])
def test_reporte_de_agua_mantiene_el_acuse_breve(texto):
    _, respuestas = enviar(texto)
    respuestas.assert_awaited_once_with("Recibimos tu mensaje. Código: 2be33e79.")


def test_mensaje_repetido_no_vuelve_a_orientar():
    _, respuestas = enviar("Hola", estado=200)
    respuestas.assert_awaited_once_with("Ya habíamos recibido este mensaje. Código: 2be33e79.")


def test_clasificador_ignora_acentos_y_mayusculas():
    assert parece_reporte_de_agua("TUBERÍA ROTA") and parece_reporte_de_agua("Presión baja")
    assert not parece_reporte_de_agua("Hola") and not parece_reporte_de_agua("")
