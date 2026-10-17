"""Pruebas del bot con la API simulada (sin red, sin Telegram y sin claves)."""
import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot.bot import (
    MAX_TEXTO,
    MENSAJE_FALLO,
    MENSAJE_LARGO,
    leer_chats_autorizados,
    recibir_texto,
)

TEXTO = "Llevamos tres días sin agua en P1"
REPORTE_ID = "2be33e79-1dc1-4a61-8e01-98387f19cef6"


def armar(responder, *, chat_id=-1001, usuario="persona", texto=TEXTO, autorizados=None):
    llamadas = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        llamadas.append(peticion)
        resultado = responder(peticion)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    cliente = httpx.AsyncClient(
        base_url="http://api.prueba",
        headers={"X-Secreto-Bot": "secreto-de-prueba-0123"},
        transport=httpx.MockTransport(manejador),
    )
    respuestas = AsyncMock()
    mensaje = SimpleNamespace(message_id=7, text=texto, reply_text=respuestas)
    if usuario == "persona":
        usuario = SimpleNamespace(id=111, is_bot=False)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_message=mensaje,
        effective_user=usuario,
    )
    contexto = SimpleNamespace(
        application=SimpleNamespace(
            bot_data={
                "chats_autorizados": {-1001} if autorizados is None else autorizados,
                "cliente_api": cliente,
            }
        )
    )
    return update, contexto, llamadas, respuestas


def ejecutar(update, contexto):
    asyncio.run(recibir_texto(update, contexto))


def json_de(codigo):
    return httpx.Response(codigo, json={"reporte_id": REPORTE_ID})


def test_texto_nuevo_se_envia_a_la_api_y_se_confirma():
    update, contexto, llamadas, respuestas = armar(lambda p: json_de(201))
    ejecutar(update, contexto)
    assert len(llamadas) == 1
    assert llamadas[0].method == "POST" and llamadas[0].url.path == "/reportes"
    assert llamadas[0].headers["X-Secreto-Bot"] == "secreto-de-prueba-0123"
    assert json.loads(llamadas[0].content) == {
        "usuario_telegram_id": 111, "chat_id": -1001, "message_id": 7, "texto": TEXTO,
    }
    respuestas.assert_awaited_once_with("Recibimos tu reporte. Código: 2be33e79.")


def test_mensaje_ya_registrado_responde_distinto():
    update, contexto, _, respuestas = armar(lambda p: json_de(200))
    ejecutar(update, contexto)
    respuestas.assert_awaited_once_with("Ya habíamos registrado este mensaje. Código: 2be33e79.")


def test_chat_no_autorizado_no_llama_a_la_api_ni_responde():
    update, contexto, llamadas, respuestas = armar(lambda p: json_de(201), chat_id=-999)
    ejecutar(update, contexto)
    assert llamadas == [] and respuestas.await_count == 0


@pytest.mark.parametrize(
    "usuario", [None, SimpleNamespace(id=5, is_bot=True)], ids=["sin_usuario", "es_bot"]
)
def test_sin_persona_identificable_se_ignora(usuario):
    update, contexto, llamadas, respuestas = armar(lambda p: json_de(201), usuario=usuario)
    ejecutar(update, contexto)
    assert llamadas == [] and respuestas.await_count == 0


def test_texto_demasiado_largo_no_llama_a_la_api():
    update, contexto, llamadas, respuestas = armar(
        lambda p: json_de(201), texto="a" * (MAX_TEXTO + 1)
    )
    ejecutar(update, contexto)
    assert llamadas == []
    respuestas.assert_awaited_once_with(MENSAJE_LARGO)


@pytest.mark.parametrize("codigo", [403, 422, 503, 500])
def test_errores_de_la_api_dan_un_mensaje_generico(codigo):
    update, contexto, _, respuestas = armar(
        lambda p: httpx.Response(codigo, json={"codigo": "x", "mensaje": "detalle interno"})
    )
    ejecutar(update, contexto)
    respuestas.assert_awaited_once_with(MENSAJE_FALLO)


def test_api_caida_da_un_mensaje_generico():
    update, contexto, _, respuestas = armar(lambda p: httpx.ConnectError("sin conexión"))
    ejecutar(update, contexto)
    respuestas.assert_awaited_once_with(MENSAJE_FALLO)


def test_respuesta_ilegible_no_se_toma_por_exito():
    update, contexto, _, respuestas = armar(lambda p: httpx.Response(201, text="no es json"))
    ejecutar(update, contexto)
    respuestas.assert_awaited_once_with(MENSAJE_FALLO)


def test_el_texto_de_la_persona_no_llega_al_registro(caplog):
    update, contexto, _, _ = armar(lambda p: json_de(201))
    with caplog.at_level(logging.DEBUG):
        ejecutar(update, contexto)
    assert TEXTO not in caplog.text


def test_leer_chats_autorizados():
    assert leer_chats_autorizados("123, -100456,") == {123, -100456}
    assert leer_chats_autorizados("") == set()
    with pytest.raises(ValueError):
        leer_chats_autorizados("123,abc")
