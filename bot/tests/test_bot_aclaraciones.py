"""Pruebas del circuito de aclaración del bot con API y Telegram simulados."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut

from bot import adaptador
from bot.adaptador import MAX_POR_CICLO, MENSAJES_RESULTADO, ciclo_envio, enviar_pendientes
from bot.bot import (
    MENSAJE_EN_VIVO,
    MENSAJE_FALLO_RESPUESTA,
    MENSAJE_SOLO_TEXTO,
    recibir_texto,
    recibir_ubicacion,
)

BOT_ID = 900


@pytest.fixture(autouse=True)
def aclaraciones_activas(monkeypatch):
    """Estas pruebas cubren el circuito ya activado (después de la migración de Emilia)."""
    monkeypatch.setattr(adaptador, "ACLARACIONES_ACTIVAS", True)
ACLARACION = {
    "aclaracion_id": "11111111-1111-4111-8111-111111111111",
    "pregunta": "¿Cuántas personas son?",
    "chat_id": -1001,
    "mensaje_original_id": 7,
}


def cliente_api(responder):
    """Cliente httpx contra una API simulada. responder(peticion) -> httpx.Response."""
    llamadas = []

    def manejador(peticion):
        llamadas.append(peticion)
        resultado = responder(peticion)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    cliente = httpx.AsyncClient(base_url="http://api.prueba", transport=httpx.MockTransport(manejador))
    return cliente, llamadas


def cuerpo(peticion):
    return json.loads(peticion.content) if peticion.content else None


def rutas(llamadas):
    return [p.url.path for p in llamadas]


# --- Envío de preguntas ---

def api_con_reservas(n_reservas, envio=204):
    pendientes = [dict(ACLARACION) for _ in range(n_reservas)]

    def responder(p):
        if p.url.path == "/aclaraciones/reservar":
            return httpx.Response(200, json=pendientes.pop(0)) if pendientes else httpx.Response(204)
        return httpx.Response(envio)

    return cliente_api(responder)


def test_envia_la_pregunta_como_reply_y_registra_enviado():
    cliente, llamadas = api_con_reservas(1)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=55)))
    assert asyncio.run(enviar_pendientes(bot, cliente, "bot:1")) == 1
    argumentos = bot.send_message.await_args.kwargs
    assert argumentos["chat_id"] == -1001 and argumentos["text"] == "¿Cuántas personas son?"
    assert argumentos["reply_parameters"].message_id == 7
    envio = [p for p in llamadas if p.url.path.endswith("/envio")][0]
    assert envio.url.path == f"/aclaraciones/{ACLARACION['aclaracion_id']}/envio"
    assert cuerpo(envio) == {"trabajador_id": "bot:1", "estado": "enviado",
                             "proveedor_mensaje_id": "55", "error": None}


def test_sin_mensaje_original_envia_sin_reply():
    def responder(p):
        if p.url.path == "/aclaraciones/reservar" and not responder.hecho:
            responder.hecho = True
            return httpx.Response(200, json={**ACLARACION, "mensaje_original_id": None})
        return httpx.Response(204)
    responder.hecho = False
    cliente, _ = cliente_api(responder)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=55)))
    asyncio.run(enviar_pendientes(bot, cliente, "bot:1"))
    assert bot.send_message.await_args.kwargs["reply_parameters"] is None


@pytest.mark.parametrize("error, estado", [
    (BadRequest("chat not found"), "fallido"),
    (Forbidden("bot was blocked"), "fallido"),
    (TimedOut(), "incierto"),
    (NetworkError("conexión"), "incierto"),
])
def test_errores_de_telegram_se_registran_sin_reenviar(error, estado):
    cliente, llamadas = api_con_reservas(1)
    bot = SimpleNamespace(send_message=AsyncMock(side_effect=error))
    asyncio.run(enviar_pendientes(bot, cliente, "bot:1"))
    assert bot.send_message.await_count == 1
    registro = cuerpo([p for p in llamadas if p.url.path.endswith("/envio")][0])
    assert registro["estado"] == estado and registro["proveedor_mensaje_id"] is None
    assert registro["error"].startswith("Telegram: ")


def test_si_no_se_puede_registrar_no_se_reenvia():
    cliente, _ = api_con_reservas(1, envio=503)
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=55)))
    asyncio.run(enviar_pendientes(bot, cliente, "bot:1"))
    assert bot.send_message.await_count == 1


def test_api_caida_al_reservar_no_envia_nada():
    cliente, _ = cliente_api(lambda p: httpx.ConnectError("sin conexión"))
    bot = SimpleNamespace(send_message=AsyncMock())
    assert asyncio.run(enviar_pendientes(bot, cliente, "bot:1")) == 0
    assert bot.send_message.await_count == 0


def test_un_ciclo_envia_como_maximo_el_limite():
    cliente, _ = cliente_api(lambda p: httpx.Response(200, json=ACLARACION)
                             if p.url.path == "/aclaraciones/reservar" else httpx.Response(204))
    bot = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(message_id=55)))
    assert asyncio.run(enviar_pendientes(bot, cliente, "bot:1")) == MAX_POR_CICLO


def test_el_ciclo_sobrevive_a_un_fallo_y_se_puede_detener(monkeypatch):
    llamadas = []

    async def enviar_falso(*_):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise RuntimeError("fallo puntual")
        return 0

    monkeypatch.setattr(adaptador, "enviar_pendientes", enviar_falso)

    async def prueba():
        tarea = asyncio.create_task(ciclo_envio(None, None, "bot:1", intervalo=0.01))
        await asyncio.sleep(0.05)
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea

    asyncio.run(prueba())
    assert len(llamadas) >= 2


# --- Respuestas (replies) ---

def armar(responder, *, texto="Somos unas 80 personas.", reply_de=BOT_ID, chat_id=-1001, ubicacion=None):
    cliente, llamadas = cliente_api(responder)
    respuestas = AsyncMock()
    original = (
        SimpleNamespace(message_id=55, from_user=SimpleNamespace(id=reply_de)) if reply_de else None
    )
    mensaje = SimpleNamespace(message_id=56, text=texto, reply_text=respuestas,
                              reply_to_message=original, location=ubicacion)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_message=mensaje,
        effective_user=SimpleNamespace(id=111, is_bot=False),
    )
    contexto = SimpleNamespace(
        bot=SimpleNamespace(id=BOT_ID),
        application=SimpleNamespace(bot_data={"chats_autorizados": {-1001}, "cliente_api": cliente}),
    )
    return update, contexto, llamadas, respuestas


def api_resultado(resultado, reporte=201):
    def responder(p):
        if p.url.path == "/aclaraciones/respuestas":
            return httpx.Response(200, json={"resultado": resultado, "ejecucion_id": None})
        return httpx.Response(reporte, json={"reporte_id": "2be33e79-1dc1-4a61-8e01-98387f19cef6"})
    return responder


@pytest.mark.parametrize("resultado", ["aceptada", "repetida", "ya_respondida", "autor_distinto", "vencida"])
def test_reply_al_bot_se_entrega_como_respuesta(resultado):
    update, contexto, llamadas, respuestas = armar(api_resultado(resultado))
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas"]
    assert cuerpo(llamadas[0]) == {
        "usuario_telegram_id": 111, "chat_id": -1001, "pregunta_mensaje_id": 55,
        "message_id": 56, "texto": "Somos unas 80 personas.",
    }
    respuestas.assert_awaited_once_with(MENSAJES_RESULTADO[resultado])


def test_reply_a_un_mensaje_que_no_es_pregunta_es_un_reporte_nuevo():
    update, contexto, llamadas, respuestas = armar(api_resultado("no_encontrada"))
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas", "/reportes"]
    respuestas.assert_awaited_once_with("Recibimos tu mensaje. Código: 2be33e79.")


def test_reply_a_otra_persona_es_un_reporte_normal():
    update, contexto, llamadas, _ = armar(api_resultado("aceptada"), reply_de=12345)
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/reportes"]


def test_si_la_respuesta_no_se_entrega_avisa_y_no_crea_reporte():
    update, contexto, llamadas, respuestas = armar(lambda p: httpx.ConnectError("sin conexión"))
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas"]
    respuestas.assert_awaited_once_with(MENSAJE_FALLO_RESPUESTA)


def test_reply_desde_un_chat_no_autorizado_se_ignora():
    update, contexto, llamadas, respuestas = armar(api_resultado("aceptada"), chat_id=-999)
    asyncio.run(recibir_texto(update, contexto))
    assert llamadas == [] and respuestas.await_count == 0


# --- Ubicación ---

UBICACION = SimpleNamespace(latitude=8.9, longitude=-79.7, horizontal_accuracy=12.5, live_period=None)


def test_ubicacion_como_reply_se_entrega_con_coordenadas():
    update, contexto, llamadas, respuestas = armar(api_resultado("aceptada"), texto=None, ubicacion=UBICACION)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert cuerpo(llamadas[0])["ubicacion"] == {"latitud": 8.9, "longitud": -79.7, "precision_metros": 12.5}
    assert "texto" not in cuerpo(llamadas[0])
    assert "localizarlo automáticamente" in respuestas.await_args.args[0]


def test_ubicacion_sin_reply_pide_texto():
    update, contexto, llamadas, respuestas = armar(api_resultado("aceptada"), texto=None,
                                                    ubicacion=UBICACION, reply_de=None)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert llamadas == []
    respuestas.assert_awaited_once_with(MENSAJE_SOLO_TEXTO)


def test_ubicacion_en_vivo_no_se_usa():
    en_vivo = SimpleNamespace(latitude=8.9, longitude=-79.7, horizontal_accuracy=None, live_period=900)
    update, contexto, llamadas, respuestas = armar(api_resultado("aceptada"), texto=None, ubicacion=en_vivo)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert llamadas == []
    respuestas.assert_awaited_once_with(MENSAJE_EN_VIVO)


def test_ubicacion_como_reply_a_un_mensaje_que_no_es_pregunta_pide_texto():
    update, contexto, _, respuestas = armar(api_resultado("no_encontrada"), texto=None, ubicacion=UBICACION)
    asyncio.run(recibir_ubicacion(update, contexto))
    respuestas.assert_awaited_once_with(MENSAJE_SOLO_TEXTO)


# --- Interruptor apagado (antes de la migración) ---

def test_apagado_un_reply_al_bot_es_un_reporte_nuevo(monkeypatch):
    monkeypatch.setattr(adaptador, "ACLARACIONES_ACTIVAS", False)
    update, contexto, llamadas, _ = armar(api_resultado("aceptada"))
    asyncio.run(recibir_texto(update, contexto))
    assert rutas(llamadas) == ["/reportes"]


def test_apagado_una_ubicacion_pide_texto_sin_llamar_a_la_api(monkeypatch):
    monkeypatch.setattr(adaptador, "ACLARACIONES_ACTIVAS", False)
    update, contexto, llamadas, respuestas = armar(api_resultado("aceptada"), texto=None, ubicacion=UBICACION)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert llamadas == []
    respuestas.assert_awaited_once_with(MENSAJE_SOLO_TEXTO)


def test_apagado_no_arranca_la_consulta_periodica(monkeypatch):
    from bot.bot import iniciar_envio

    monkeypatch.setattr(adaptador, "ACLARACIONES_ACTIVAS", False)
    app = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()),
                          bot_data={"cliente_api": None, "trabajador_id": "bot:1"})
    asyncio.run(iniciar_envio(app))
    assert "tarea_envio" not in app.bot_data


def test_pregunta_geografica_ofrece_pin_fuera_del_catalogo():
    from bot.adaptador import pregunta_con_ubicacion
    texto = pregunta_con_ubicacion({**ACLARACION, "campos_solicitados": ["ubicación_declarada"]})
    assert texto.startswith(ACLARACION["pregunta"])
    assert "Adjuntar → Ubicación" in texto and "aunque el lugar" in texto
    assert "solo si estás allí" in texto
    assert "no crea un punto de distribución" in texto


def test_pregunta_mixta_conserva_campos_y_limite_telegram():
    from bot.adaptador import pregunta_con_ubicacion
    texto = pregunta_con_ubicacion({**ACLARACION, "campos_solicitados": ["ubicacion", "personas_afectadas"]})
    assert texto.startswith("¿Cuántas personas son?") and "pin fijo" in texto
    assert len(pregunta_con_ubicacion({**ACLARACION, "pregunta": "x" * 4000,
                                    "campos_solicitados": ["ubicacion"]})) <= 4096


def test_pin_de_otra_persona_no_confirma_asociacion():
    update, contexto, llamadas, respuestas = armar(api_resultado("autor_distinto"), texto=None, ubicacion=UBICACION)
    asyncio.run(recibir_ubicacion(update, contexto))
    assert rutas(llamadas) == ["/aclaraciones/respuestas"]
    respuestas.assert_awaited_once_with(MENSAJES_RESULTADO["autor_distinto"])
