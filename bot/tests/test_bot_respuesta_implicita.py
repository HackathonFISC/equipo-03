"""En un chat privado, la respuesta escrita sin pulsar «Responder» contesta la última pregunta abierta."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot import adaptador
from bot.bot import recibir_texto, recibir_ubicacion

BOT_ID = 999
CHAT = 111  # En un chat privado el id del chat es el del usuario (positivo).
USUARIO = 111
GRUPO = -1001
PREGUNTA = 55


@pytest.fixture(autouse=True)
def sin_preguntas_previas():
    adaptador._preguntas_abiertas.clear()
    yield
    adaptador._preguntas_abiertas.clear()


def armar(resultado="aceptada", *, texto="El Colegio José Antonio Remón Cantera en vía Israel", tipo="private",
          chat_id=CHAT, reply_a=None, ubicacion=None, mencion=False):
    llamadas = []

    def manejador(p):
        llamadas.append(p)
        if p.url.path == "/aclaraciones/respuestas":
            return httpx.Response(200, json={"resultado": resultado, "ejecucion_id": None})
        return httpx.Response(201, json={"reporte_id": "2be33e79-1dc1-4a61-8e01-98387f19cef6"})

    cliente = httpx.AsyncClient(base_url="http://api.prueba", transport=httpx.MockTransport(manejador))
    respuestas = AsyncMock()
    original = SimpleNamespace(message_id=reply_a, from_user=SimpleNamespace(id=BOT_ID)) if reply_a else None
    texto = f"@bot_h2oeste {texto}" if mencion else texto
    mensaje = SimpleNamespace(message_id=56, text=texto, reply_text=respuestas,
                              reply_to_message=original, location=ubicacion)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id, type=tipo), effective_message=mensaje,
        effective_user=SimpleNamespace(id=111, is_bot=False),
    )
    contexto = SimpleNamespace(
        bot=SimpleNamespace(id=BOT_ID, username="bot_h2oeste"),
        application=SimpleNamespace(bot_data={"chats_autorizados": {chat_id}, "cliente_api": cliente,
                                             "acceso_publico": False}),
    )
    return update, contexto, llamadas, respuestas


def rutas(llamadas):
    return [p.url.path for p in llamadas]


def test_texto_sin_reply_contesta_la_pregunta_abierta():
    adaptador.recordar_pregunta(CHAT, PREGUNTA, USUARIO)
    update, contexto, llamadas, respuestas = armar()
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas"]
    assert json.loads(llamadas[0].content) == {
        "usuario_telegram_id": 111, "chat_id": CHAT, "pregunta_mensaje_id": PREGUNTA, "message_id": 56,
        "texto": "El Colegio José Antonio Remón Cantera en vía Israel",
    }
    respuestas.assert_awaited_once_with(adaptador.MENSAJE_RESPUESTA_RECIBIDA)


def test_una_pregunta_se_contesta_una_sola_vez():
    adaptador.recordar_pregunta(CHAT, PREGUNTA, USUARIO)
    update, contexto, llamadas, _ = armar()
    asyncio.run(recibir_texto(update, contexto))
    update, contexto, llamadas2, _ = armar()
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas2) == ["/reportes"]  # lo siguiente es un reporte nuevo


def test_sin_pregunta_abierta_es_un_reporte_nuevo():
    update, contexto, llamadas, _ = armar()
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/reportes"]


def test_en_un_grupo_contesta_quien_tiene_la_pregunta_abierta():
    adaptador.recordar_pregunta(GRUPO, PREGUNTA, USUARIO)
    update, contexto, llamadas, respuestas = armar(tipo="supergroup", chat_id=GRUPO)
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas"]
    assert json.loads(llamadas[0].content)["pregunta_mensaje_id"] == PREGUNTA
    respuestas.assert_awaited_once_with(adaptador.MENSAJE_RESPUESTA_RECIBIDA)


def test_en_un_grupo_otra_persona_no_contesta_ni_se_registra():
    adaptador.recordar_pregunta(GRUPO, PREGUNTA, 222)  # la pregunta es de otra persona
    update, contexto, llamadas, respuestas = armar(tipo="supergroup", chat_id=GRUPO)
    asyncio.run(recibir_texto(update, contexto))
    assert llamadas == [] and respuestas.await_count == 0


def test_en_un_grupo_sin_pregunta_abierta_se_ignora():
    update, contexto, llamadas, respuestas = armar(tipo="supergroup", chat_id=GRUPO)
    asyncio.run(recibir_texto(update, contexto))
    assert llamadas == [] and respuestas.await_count == 0


def test_el_reporte_recuerda_su_autor_para_la_pregunta_que_llega_despues():
    # Reporte en un grupo: el mensaje 56 lo envió la persona 111.
    update, contexto, _, _ = armar(texto="Sin agua en la escuela", tipo="supergroup", chat_id=GRUPO, mencion=True)
    asyncio.run(recibir_texto(update, contexto))
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=PREGUNTA)))
    cliente = httpx.AsyncClient(base_url="http://api.prueba",
                                transport=httpx.MockTransport(lambda p: httpx.Response(204)))
    aclaracion = {"aclaracion_id": "a1", "chat_id": GRUPO, "pregunta": "¿Dónde?", "mensaje_original_id": 56}
    asyncio.run(adaptador.enviar_una(bot, cliente, "t1", aclaracion))
    assert adaptador.pregunta_abierta(GRUPO, USUARIO) == PREGUNTA


def test_en_un_grupo_sin_autor_conocido_no_se_deja_pregunta_abierta():
    adaptador.recordar_pregunta(GRUPO, PREGUNTA)
    assert adaptador._preguntas_abiertas == {}


def test_pregunta_vencida_no_se_usa(monkeypatch):
    adaptador.recordar_pregunta(CHAT, PREGUNTA, USUARIO)
    ahora = adaptador.time.monotonic()
    monkeypatch.setattr(adaptador.time, "monotonic", lambda: ahora + adaptador.VIGENCIA_PREGUNTA_SEGUNDOS + 1)
    assert adaptador.pregunta_abierta(CHAT, USUARIO) is None


def test_no_encontrada_cae_a_reporte_nuevo():
    adaptador.recordar_pregunta(CHAT, PREGUNTA, USUARIO)
    update, contexto, llamadas, _ = armar("no_encontrada")
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas", "/reportes"]


def test_el_reply_explicito_manda_sobre_la_pregunta_recordada():
    adaptador.recordar_pregunta(CHAT, PREGUNTA, USUARIO)
    update, contexto, llamadas, _ = armar(reply_a=77)
    asyncio.run(recibir_texto(update, contexto))
    assert json.loads(llamadas[0].content)["pregunta_mensaje_id"] == 77


def test_pin_sin_reply_tambien_contesta_la_pregunta_abierta():
    adaptador.recordar_pregunta(CHAT, PREGUNTA, USUARIO)
    pin = SimpleNamespace(latitude=8.98, longitude=-79.52, horizontal_accuracy=None, live_period=None)
    update, contexto, llamadas, _ = armar(texto=None, ubicacion=pin)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas"]
    assert json.loads(llamadas[0].content)["pregunta_mensaje_id"] == PREGUNTA


def test_pin_sin_pregunta_abierta_pide_texto():
    pin = SimpleNamespace(latitude=8.98, longitude=-79.52, horizontal_accuracy=None, live_period=None)
    update, contexto, llamadas, respuestas = armar(texto=None, ubicacion=pin)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert llamadas == []
    respuestas.assert_awaited_once()


def test_el_envio_de_una_pregunta_la_deja_abierta():
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=PREGUNTA)))
    cliente = httpx.AsyncClient(base_url="http://api.prueba",
                                transport=httpx.MockTransport(lambda p: httpx.Response(204)))
    aclaracion = {"aclaracion_id": "a1", "chat_id": CHAT, "pregunta": "¿Dónde?", "mensaje_original_id": 7}
    asyncio.run(adaptador.enviar_una(bot, cliente, "t1", aclaracion))
    assert adaptador.pregunta_abierta(CHAT, USUARIO) == PREGUNTA
