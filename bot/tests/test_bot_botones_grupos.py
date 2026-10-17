"""Pruebas de los botones de bienvenida y del filtro de grupos (API simulada, sin Telegram)."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from telegram import ForceReply
from telegram.constants import ParseMode

from bot import adaptador
from bot.bot import (
    MENSAJE_AYUDA,
    MENSAJE_BIENVENIDA,
    MENSAJE_SOLO_TEXTO,
    atender_boton,
    recibir_texto,
    recibir_ubicacion,
)

BOT_ID, BOT_USUARIO, CHAT = 900, "RutaAguaOesteBot", -1001


def contexto(cliente=None):
    return SimpleNamespace(
        bot=SimpleNamespace(id=BOT_ID, username=BOT_USUARIO),
        application=SimpleNamespace(bot_data={"chats_autorizados": {CHAT}, "cliente_api": cliente}),
    )


def cliente_api():
    llamadas = []

    def manejador(peticion):
        llamadas.append(peticion)
        if peticion.url.path == "/aclaraciones/respuestas":
            return httpx.Response(200, json={"resultado": "no_encontrada"})
        return httpx.Response(201, json={"reporte_id": "2be33e79-1dc1-4a61-8e01-98387f19cef6"})

    return httpx.AsyncClient(base_url="http://api.prueba", transport=httpx.MockTransport(manejador)), llamadas


def mensaje_de_grupo(texto, *, reply_al_bot=False, tipo="supergroup", ubicacion=None):
    original = SimpleNamespace(message_id=55, from_user=SimpleNamespace(id=BOT_ID)) if reply_al_bot else None
    mensaje = SimpleNamespace(message_id=56, text=texto, reply_text=AsyncMock(),
                              reply_to_message=original, location=ubicacion)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=CHAT, type=tipo),
        effective_message=mensaje,
        effective_user=SimpleNamespace(id=111, is_bot=False),
    )
    return update, mensaje


def textos_enviados(llamadas):
    return [json.loads(p.content)["texto"] for p in llamadas if p.url.path == "/reportes"]


# --- Filtro de grupos ---

def test_conversacion_del_grupo_no_se_registra():
    cliente, llamadas = cliente_api()
    update, mensaje = mensaje_de_grupo("Hola a todos")
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert llamadas == [] and mensaje.reply_text.await_count == 0


def test_reply_al_bot_en_el_grupo_se_registra():
    cliente, llamadas = cliente_api()
    update, mensaje = mensaje_de_grupo("Sin agua desde ayer en P2", reply_al_bot=True)
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert textos_enviados(llamadas) == ["Sin agua desde ayer en P2"]
    mensaje.reply_text.assert_awaited_once_with("Recibimos tu mensaje. Código: 2be33e79.")


@pytest.mark.parametrize("texto", [
    f"@{BOT_USUARIO} Sin agua desde ayer en P2",
    f"Sin agua desde ayer en P2 @{BOT_USUARIO.lower()}",
])
def test_mencion_en_el_grupo_se_registra_sin_la_mencion(texto):
    cliente, llamadas = cliente_api()
    update, _ = mensaje_de_grupo(texto)
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert textos_enviados(llamadas) == ["Sin agua desde ayer en P2"]


def test_mencion_de_otro_usuario_no_cuenta():
    cliente, llamadas = cliente_api()
    update, _ = mensaje_de_grupo(f"@{BOT_USUARIO}Falso hola")
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert llamadas == []


def test_solo_la_mencion_muestra_la_bienvenida():
    cliente, llamadas = cliente_api()
    update, mensaje = mensaje_de_grupo(f"@{BOT_USUARIO}")
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert llamadas == []
    assert mensaje.reply_text.await_args.args[0] == MENSAJE_BIENVENIDA


def test_en_privado_cualquier_texto_se_registra():
    cliente, llamadas = cliente_api()
    update, _ = mensaje_de_grupo("Hola", tipo="private")
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert textos_enviados(llamadas) == ["Hola"]


def test_con_aclaraciones_activas_el_reply_al_mensaje_de_reportar_es_un_reporte(monkeypatch):
    monkeypatch.setattr(adaptador, "ACLARACIONES_ACTIVAS", True)
    cliente, llamadas = cliente_api()
    update, _ = mensaje_de_grupo("Sin agua en P2", reply_al_bot=True)
    asyncio.run(recibir_texto(update, contexto(cliente)))
    assert [p.url.path for p in llamadas] == ["/aclaraciones/respuestas", "/reportes"]


UBICACION = SimpleNamespace(latitude=8.9, longitude=-79.7, horizontal_accuracy=None, live_period=None)


def test_ubicacion_en_la_conversacion_del_grupo_se_ignora():
    cliente, llamadas = cliente_api()
    update, mensaje = mensaje_de_grupo(None, ubicacion=UBICACION)
    asyncio.run(recibir_ubicacion(update, contexto(cliente)))
    assert llamadas == [] and mensaje.reply_text.await_count == 0


def test_ubicacion_en_privado_sin_reply_pide_texto():
    cliente, llamadas = cliente_api()
    update, mensaje = mensaje_de_grupo(None, tipo="private", ubicacion=UBICACION)
    asyncio.run(recibir_ubicacion(update, contexto(cliente)))
    mensaje.reply_text.assert_awaited_once_with(MENSAJE_SOLO_TEXTO)


# --- Botones ---

def pulsacion(dato, *, chat_id=CHAT, nombre="Ana <b>"):
    mensaje = SimpleNamespace(chat=SimpleNamespace(id=chat_id), reply_text=AsyncMock())
    consulta = SimpleNamespace(
        data=dato, answer=AsyncMock(), message=mensaje,
        from_user=SimpleNamespace(id=111, is_bot=False, first_name=nombre),
    )
    return SimpleNamespace(callback_query=consulta), consulta, mensaje


def test_boton_instrucciones_muestra_la_ayuda():
    update, consulta, mensaje = pulsacion("instrucciones")
    asyncio.run(atender_boton(update, contexto()))
    consulta.answer.assert_awaited_once()
    mensaje.reply_text.assert_awaited_once_with(MENSAJE_AYUDA)


def test_boton_reportar_abre_la_respuesta_solo_a_quien_pulso():
    update, consulta, mensaje = pulsacion("reportar")
    asyncio.run(atender_boton(update, contexto()))
    texto = mensaje.reply_text.await_args.args[0]
    argumentos = mensaje.reply_text.await_args.kwargs
    assert 'href="tg://user?id=111"' in texto
    assert "Ana &lt;b&gt;" in texto  # el nombre se escapa: no puede inyectar HTML
    assert argumentos["parse_mode"] == ParseMode.HTML
    assert isinstance(argumentos["reply_markup"], ForceReply)
    assert argumentos["reply_markup"].selective is True


def test_boton_en_chat_no_autorizado_solo_se_reconoce():
    update, consulta, mensaje = pulsacion("reportar", chat_id=-999)
    asyncio.run(atender_boton(update, contexto()))
    consulta.answer.assert_awaited_once()
    assert mensaje.reply_text.await_count == 0


def test_boton_desconocido_no_hace_nada():
    update, consulta, mensaje = pulsacion("otra_cosa")
    asyncio.run(atender_boton(update, contexto()))
    consulta.answer.assert_awaited_once()
    assert mensaje.reply_text.await_count == 0
