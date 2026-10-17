"""Acceso público y límite de mensajes (API y Telegram simulados, sin red ni claves)."""
import asyncio
import functools
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from bot import limites
from bot.bot import (
    MENSAJE_LIMITE_GLOBAL,
    MENSAJE_LIMITE_USUARIO,
    MENSAJE_RECIBIDO,
    atender_boton,
    leer_acceso_publico,
    mostrar_ayuda,
    recibir_texto,
)
from bot.limites import LimiteMensajes

REPORTE_ID = "2be33e79-1dc1-4a61-8e01-98387f19cef6"


def sincronico(prueba):
    """Corre la prueba asíncrona con asyncio.run, como el resto de las pruebas del bot."""
    @functools.wraps(prueba)
    def envoltura(*args, **kwargs):
        return asyncio.run(prueba(*args, **kwargs))
    return envoltura


def como(update, usuario_id):
    update.effective_user = SimpleNamespace(id=usuario_id, is_bot=False)
    return update


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def armar(*, publico, autorizados=None, limite=None, chat_id=555, usuario_id=111, texto="Sin agua en P1"):
    llamadas = []

    def manejador(peticion: httpx.Request) -> httpx.Response:
        llamadas.append(peticion)
        return httpx.Response(201, json={"reporte_id": REPORTE_ID})

    cliente = httpx.AsyncClient(base_url="http://api.prueba", transport=httpx.MockTransport(manejador))
    respuestas = AsyncMock()
    mensaje = SimpleNamespace(message_id=7, text=texto, reply_text=respuestas)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_message=mensaje,
        effective_user=SimpleNamespace(id=usuario_id, is_bot=False),
    )
    datos = {"chats_autorizados": autorizados if autorizados is not None else set(), "cliente_api": cliente, "acceso_publico": publico}
    if limite is not None:
        datos["limite"] = limite
    return update, SimpleNamespace(application=SimpleNamespace(bot_data=datos)), llamadas, respuestas


@pytest.mark.parametrize("valor,esperado", [("true", True), ("TRUE", True), (" si ", True), ("sí", True), ("1", True),
                                            ("", False), ("false", False), ("no", False), ("quizá", False)])
def test_solo_un_si_explicito_abre_el_bot(valor, esperado):
    assert leer_acceso_publico(valor) is esperado


@sincronico
async def test_en_modo_publico_atiende_a_un_chat_que_no_esta_en_la_lista():
    update, contexto, llamadas, respuestas = armar(publico=True, autorizados={-1001})

    await recibir_texto(update, contexto)

    assert len(llamadas) == 1
    respuestas.assert_awaited_once_with(MENSAJE_RECIBIDO.format(codigo=REPORTE_ID[:8]))


@sincronico
async def test_en_modo_de_prueba_sigue_ignorando_chats_ajenos():
    update, contexto, llamadas, respuestas = armar(publico=False, autorizados={-1001})

    await recibir_texto(update, contexto)

    assert llamadas == []
    respuestas.assert_not_awaited()


@sincronico
async def test_en_modo_publico_la_bienvenida_y_los_botones_funcionan_para_cualquiera():
    update, contexto, _, respuestas = armar(publico=True)
    await mostrar_ayuda(update, contexto)
    respuestas.assert_awaited_once()

    consulta = SimpleNamespace(
        data="instrucciones", answer=AsyncMock(),
        message=SimpleNamespace(chat=SimpleNamespace(id=555), reply_text=AsyncMock()),
        from_user=SimpleNamespace(id=111, is_bot=False, first_name="Ana"),
    )
    await atender_boton(SimpleNamespace(callback_query=consulta), contexto)
    consulta.message.reply_text.assert_awaited_once()


@sincronico
async def test_el_limite_frena_el_noveno_mensaje_y_avisa_una_sola_vez():
    reloj = Reloj()
    limite = LimiteMensajes(por_usuario=8, en_total=1000, ventana=600, reloj=reloj)
    update, contexto, llamadas, respuestas = armar(publico=True, limite=limite)

    for _ in range(8):
        await recibir_texto(update, contexto)
    assert len(llamadas) == 8
    respuestas.reset_mock()

    await recibir_texto(update, contexto)
    await recibir_texto(update, contexto)

    assert len(llamadas) == 8  # Ninguno de los dos llegó a la API.
    respuestas.assert_awaited_once_with(MENSAJE_LIMITE_USUARIO)


@sincronico
async def test_pasada_la_ventana_la_persona_vuelve_a_poder_escribir():
    reloj = Reloj()
    limite = LimiteMensajes(por_usuario=2, en_total=1000, ventana=600, reloj=reloj)
    update, contexto, llamadas, _ = armar(publico=True, limite=limite)

    for _ in range(3):
        await recibir_texto(update, contexto)
    assert len(llamadas) == 2

    reloj.t += 601
    await recibir_texto(update, contexto)

    assert len(llamadas) == 3


@sincronico
async def test_el_limite_de_una_persona_no_afecta_a_otra():
    limite = LimiteMensajes(por_usuario=1, en_total=1000, ventana=600, reloj=Reloj())
    update, contexto, llamadas, _ = armar(publico=True, limite=limite)

    await recibir_texto(como(update, 1), contexto)
    await recibir_texto(como(update, 1), contexto)  # Pasó su límite.
    await recibir_texto(como(update, 2), contexto)

    assert len(llamadas) == 2  # Una de cada persona.


@sincronico
async def test_el_limite_total_protege_a_la_cuota_aunque_cada_persona_escriba_poco():
    limite = LimiteMensajes(por_usuario=8, en_total=2, ventana=600, reloj=Reloj())
    update, contexto, llamadas, respuestas = armar(publico=True, limite=limite)

    for usuario in (1, 2):
        await recibir_texto(como(update, usuario), contexto)
    respuestas.reset_mock()
    await recibir_texto(como(update, 3), contexto)

    assert len(llamadas) == 2
    respuestas.assert_awaited_once_with(MENSAJE_LIMITE_GLOBAL)


def test_un_intento_rechazado_no_cuenta_para_el_limite():
    reloj = Reloj()
    limite = LimiteMensajes(por_usuario=1, en_total=10, ventana=100, reloj=reloj)
    assert limite.evaluar(1) == limites.PERMITIDO
    assert limite.evaluar(1) == limites.AVISO_USUARIO
    assert limite.evaluar(1) == limites.SILENCIO
    reloj.t += 101
    assert limite.evaluar(1) == limites.PERMITIDO


def test_la_memoria_del_limite_tiene_tope(monkeypatch):
    monkeypatch.setattr(limites, "MAX_PERSONAS_EN_MEMORIA", 3)
    reloj = Reloj()
    limite = LimiteMensajes(por_usuario=1, en_total=1000, ventana=10, reloj=reloj)
    for usuario in range(10):
        limite.evaluar(usuario)
    reloj.t += 11
    limite.evaluar(99)
    assert len(limite._usuarios) <= 2
