"""Pruebas de la plantilla de avisos y del envío de la bandeja con API y Telegram simulados."""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut

from bot import bandeja
from bot.bandeja import MAX_POR_CICLO, ciclo_avisos, enviar_pendientes
from bot.plantillas import texto_aviso

AVISO = {
    "aviso_id": "11111111-1111-4111-8111-111111111111",
    "chat_id": -1001,
    "tipo": "distribucion",
    "version": 2,
    "punto_nombre": "Escuela El Coco",
    "litros_asignados": 2500,
    "ventana_inicio": "2026-10-17T13:10:00+00:00",  # 08:10 en Panamá
    "ventana_fin": "2026-10-17T13:20:00+00:00",
}


def cliente_api(responder):
    llamadas = []

    def manejador(peticion):
        llamadas.append(peticion)
        resultado = responder(peticion)
        if isinstance(resultado, Exception):
            raise resultado
        return resultado

    return httpx.AsyncClient(base_url="http://api.prueba", transport=httpx.MockTransport(manejador)), llamadas


def cuerpo(peticion):
    return json.loads(peticion.content) if peticion.content else None


def bot_falso(resultado=None):
    enviar = AsyncMock(side_effect=resultado) if isinstance(resultado, Exception) else AsyncMock(
        return_value=resultado or SimpleNamespace(message_id=555))
    return SimpleNamespace(send_message=enviar)


# --- Plantilla ---

def fecha(texto):
    return datetime.fromisoformat(texto)


def test_distribucion_conserva_cantidad_lugar_hora_y_version():
    t = texto_aviso(tipo="distribucion", punto_nombre="Escuela El Coco", litros_asignados=2500.0,
                    ventana_inicio=fecha("2026-10-17T13:10:00+00:00"),
                    ventana_fin=fecha("2026-10-17T13:20:00+00:00"), version=2)
    assert "Escuela El Coco" in t and "2500 litros" in t
    assert "08:10" in t and "08:20" in t and "17/10/2026" in t and "hora de Panamá" in t
    assert "versión 2" in t and "estimación" in t and "puede cambiar" in t


def test_actualizacion_dice_que_reemplaza_el_aviso_anterior():
    t = texto_aviso(tipo="actualizacion", punto_nombre="Escuela El Coco", litros_asignados=1500.0,
                    ventana_inicio=fecha("2026-10-17T14:00:00+00:00"),
                    ventana_fin=fecha("2026-10-17T14:10:00+00:00"), version=3)
    assert t.startswith("Actualización") and "Reemplaza el aviso anterior" in t and "1500 litros" in t


def test_hora_en_panama_cuando_la_fecha_cruza_la_medianoche_utc():
    # 02:30 UTC del 18 es 21:30 del 17 en Panamá.
    t = texto_aviso(tipo="distribucion", punto_nombre="X", litros_asignados=100.0,
                    ventana_inicio=fecha("2026-10-18T02:30:00+00:00"),
                    ventana_fin=fecha("2026-10-18T02:40:00+00:00"), version=1)
    assert "21:30" in t and "17/10/2026" in t


def test_litros_con_decimales_usan_coma_y_nunca_se_redondean_a_cero():
    t = texto_aviso(tipo="distribucion", punto_nombre="X", litros_asignados=2500.5,
                    ventana_inicio=fecha("2026-10-17T13:10:00+00:00"),
                    ventana_fin=fecha("2026-10-17T13:20:00+00:00"), version=1)
    assert "2500,5 litros" in t


def test_tipo_desconocido_no_genera_texto():
    with pytest.raises(ValueError):
        texto_aviso(tipo="otro", punto_nombre="X", litros_asignados=1.0,
                    ventana_inicio=datetime.now(timezone.utc), ventana_fin=datetime.now(timezone.utc), version=1)


def test_el_texto_cabe_en_un_mensaje_de_telegram():
    t = texto_aviso(tipo="actualizacion", punto_nombre="N" * 200, litros_asignados=1.0,
                    ventana_inicio=datetime.now(timezone.utc), ventana_fin=datetime.now(timezone.utc), version=1)
    assert len(t) < 4096


# --- Envío ---

def reserva_y_registro(aviso, registro):
    pendiente = [aviso]

    def responder(p):
        if p.url.path == "/avisos/reservar":
            return httpx.Response(200, json=pendiente.pop(0)) if pendiente else httpx.Response(204)
        return httpx.Response(204)

    return responder


def test_envia_con_la_plantilla_y_registra_el_id_del_mensaje():
    async def caso():
        cliente, llamadas = cliente_api(reserva_y_registro(AVISO, None))
        bot = bot_falso(SimpleNamespace(message_id=555))
        n = await enviar_pendientes(bot, cliente, "bot:1")
        assert n == 1
        enviado = bot.send_message.await_args.kwargs
        assert enviado["chat_id"] == -1001
        assert "2500 litros" in enviado["text"] and "08:10" in enviado["text"]
        envio = [p for p in llamadas if p.url.path.endswith("/envio")]
        assert cuerpo(envio[0]) == {"trabajador_id": "bot:1", "estado": "enviado",
                                    "proveedor_mensaje_id": "555", "error": None}
        await cliente.aclose()
    asyncio.run(caso())


@pytest.mark.parametrize("error,estado", [
    (BadRequest("chat no encontrado"), "fallido"),
    (Forbidden("bot expulsado"), "fallido"),
    (TimedOut(), "incierto"),
    (NetworkError("sin red"), "incierto"),
], ids=["badrequest", "forbidden", "timeout", "red"])
def test_rechazo_es_fallido_y_duda_es_incierto_sin_reenviar(error, estado):
    async def caso():
        cliente, llamadas = cliente_api(reserva_y_registro(AVISO, None))
        bot = bot_falso(error)
        await enviar_pendientes(bot, cliente, "bot:1")
        assert bot.send_message.await_count == 1  # nunca reenvía
        envio = [p for p in llamadas if p.url.path.endswith("/envio")]
        datos = cuerpo(envio[0])
        assert datos["estado"] == estado and datos["proveedor_mensaje_id"] is None
        assert datos["error"].startswith("Telegram: ")
        # El texto del error de Telegram puede traer datos del chat: solo se guarda el tipo.
        assert "chat no encontrado" not in datos["error"] and "expulsado" not in datos["error"]
        await cliente.aclose()
    asyncio.run(caso())


def test_si_no_se_puede_registrar_el_envio_no_reenvia():
    async def caso():
        pendientes = [dict(AVISO)]

        def responder(p):
            if p.url.path == "/avisos/reservar":
                return httpx.Response(200, json=pendientes.pop(0)) if pendientes else httpx.Response(204)
            return httpx.ConnectError("api caida")

        cliente, _ = cliente_api(responder)
        bot = bot_falso()
        await enviar_pendientes(bot, cliente, "bot:1")
        assert bot.send_message.await_count == 1
        await cliente.aclose()
    asyncio.run(caso())


def test_aviso_con_datos_incompletos_no_se_envia_y_queda_fallido():
    async def caso():
        raro = {k: v for k, v in AVISO.items() if k != "punto_nombre"}
        cliente, llamadas = cliente_api(reserva_y_registro(raro, None))
        bot = bot_falso()
        await enviar_pendientes(bot, cliente, "bot:1")
        assert bot.send_message.await_count == 0
        envio = [p for p in llamadas if p.url.path.endswith("/envio")]
        assert cuerpo(envio[0])["estado"] == "fallido"
        await cliente.aclose()
    asyncio.run(caso())


def test_sin_avisos_no_envia_nada():
    async def caso():
        cliente, llamadas = cliente_api(lambda p: httpx.Response(204))
        bot = bot_falso()
        assert await enviar_pendientes(bot, cliente, "bot:1") == 0
        assert bot.send_message.await_count == 0 and len(llamadas) == 1
        await cliente.aclose()
    asyncio.run(caso())


def test_api_caida_o_con_error_detiene_el_ciclo_sin_romper():
    async def caso():
        for respuesta in (httpx.ConnectError("caida"), httpx.Response(503), httpx.Response(200, text="no es json")):
            cliente, _ = cliente_api(lambda p, r=respuesta: r)
            assert await enviar_pendientes(bot_falso(), cliente, "bot:1") == 0
            await cliente.aclose()
    asyncio.run(caso())


def test_un_ciclo_atiende_como_maximo_el_limite():
    async def caso():
        cliente, llamadas = cliente_api(
            lambda p: httpx.Response(200, json=AVISO) if p.url.path == "/avisos/reservar" else httpx.Response(204))
        bot = bot_falso()
        assert await enviar_pendientes(bot, cliente, "bot:1") == MAX_POR_CICLO
        await cliente.aclose()
    asyncio.run(caso())


def test_el_ciclo_sigue_aunque_una_vuelta_falle():
    async def caso():
        cliente, _ = cliente_api(lambda p: httpx.Response(204))
        llamadas = []

        async def falla_una_vez(*a, **k):
            llamadas.append(1)
            if len(llamadas) == 1:
                raise RuntimeError("fallo puntual")
            return 0

        original = bandeja.enviar_pendientes
        bandeja.enviar_pendientes = falla_una_vez
        try:
            tarea = asyncio.create_task(ciclo_avisos(bot_falso(), cliente, "bot:1", intervalo=0.01))
            await asyncio.sleep(0.1)
            tarea.cancel()
            with pytest.raises(asyncio.CancelledError):
                await tarea
        finally:
            bandeja.enviar_pendientes = original
        assert len(llamadas) >= 2
        await cliente.aclose()
    asyncio.run(caso())


def test_los_avisos_arrancan_apagados():
    assert bandeja.AVISOS_ACTIVOS is False
