import asyncio
import json
from datetime import timedelta
from types import SimpleNamespace as N
from unittest.mock import AsyncMock,Mock
import httpx
import pytest
from bot.bot import recibir_audio,MENSAJE_AUDIO_LIMITE,MENSAJE_AUDIO_FALLO,MENSAJE_AUDIO_INCIERTO
from bot import adaptador,limites

TEXTO='En Escuela El Coco llevamos 48 horas sin agua.'
REPORTE='11111111-1111-4111-8111-111111111111'
AUDIO=b'OggS'+b'\x00'*28+b'OpusHead'


def armar(*,grupo=False,reply=False,caption=None,duracion=20,tamano=len(AUDIO),estado=200,resultado='aceptada'):
    llamadas=[]
    def responder(p):
        llamadas.append(p)
        if p.url.path=='/audio/transcribir':
            return httpx.Response(estado,json={'texto':TEXTO,'fuente_texto':'transcripcion_audio'})
        if p.url.path=='/aclaraciones/respuestas':
            return httpx.Response(200,json={'resultado':resultado})
        return httpx.Response(201,json={'reporte_id':REPORTE})
    archivo=N(file_size=tamano,download_as_bytearray=AsyncMock(return_value=bytearray(AUDIO)))
    media=N(duration=duracion,file_size=tamano,mime_type='audio/ogg',get_file=AsyncMock(return_value=archivo))
    mensaje=N(message_id=7,voice=media,audio=None,caption=caption,reply_text=AsyncMock(),
        reply_to_message=N(message_id=55,from_user=N(id=900)) if reply else None)
    update=N(effective_chat=N(id=-1001 if grupo else 111,type='group' if grupo else 'private'),effective_message=mensaje,effective_user=N(id=111,is_bot=False))
    cliente=httpx.AsyncClient(base_url='http://api.prueba',transport=httpx.MockTransport(responder))
    contexto=N(bot=N(id=900,username='aguabot'),application=N(bot_data={'chats_autorizados':{111,-1001},'cliente_api':cliente}))
    return update,contexto,llamadas,media


def test_nota_de_voz_transcrita_se_registra_con_procedencia():
    u,c,llamadas,media=armar()
    asyncio.run(recibir_audio(u,c))
    assert [p.url.path for p in llamadas]==['/audio/transcribir','/reportes']
    assert json.loads(llamadas[-1].content)['fuente_texto']=='transcripcion_audio'
    assert json.loads(llamadas[-1].content)['texto']==TEXTO
    assert 'Transcribimos tu audio' in u.effective_message.reply_text.await_args.args[0]
    media.get_file.assert_awaited_once()


def test_audio_no_dirigido_en_grupo_se_ignora_sin_descargar():
    u,c,llamadas,media=armar(grupo=True)
    asyncio.run(recibir_audio(u,c))
    assert llamadas==[]
    media.get_file.assert_not_awaited()


def test_audio_en_grupo_con_mencion_en_caption_se_admite():
    u,c,llamadas,_=armar(grupo=True,caption='@aguabot')
    asyncio.run(recibir_audio(u,c))
    assert llamadas[-1].url.path=='/reportes'


def test_audio_responde_pregunta_sin_crear_reporte(monkeypatch):
    monkeypatch.setattr(adaptador,'ACLARACIONES_ACTIVAS',True)
    u,c,llamadas,_=armar(grupo=True,reply=True)
    asyncio.run(recibir_audio(u,c))
    assert [p.url.path for p in llamadas]==['/audio/transcribir','/aclaraciones/respuestas']
    cuerpo=json.loads(llamadas[-1].content)
    assert cuerpo['pregunta_mensaje_id']==55 and cuerpo['fuente_texto']=='transcripcion_audio'


@pytest.mark.parametrize('duracion,tamano',[(121,10),(20,2097153)])
def test_limites_antes_de_descargar(duracion,tamano):
    u,c,llamadas,media=armar(duracion=duracion,tamano=tamano)
    asyncio.run(recibir_audio(u,c))
    assert llamadas==[]
    media.get_file.assert_not_awaited()
    u.effective_message.reply_text.assert_awaited_once_with(MENSAJE_AUDIO_LIMITE)


def test_duracion_timedelta_y_archivos_audio_se_admiten():
    u,c,llamadas,_=armar(duracion=timedelta(seconds=20))
    u.effective_message.audio=u.effective_message.voice;u.effective_message.voice=None
    asyncio.run(recibir_audio(u,c))
    assert json.loads(llamadas[0].content)['duracion_segundos']==20


@pytest.mark.parametrize('estado,mensaje',[(422,MENSAJE_AUDIO_INCIERTO),(503,MENSAJE_AUDIO_FALLO)])
def test_transcripcion_fallida_no_crea_reporte(estado,mensaje):
    u,c,llamadas,_=armar(estado=estado)
    asyncio.run(recibir_audio(u,c))
    assert len(llamadas)==1
    u.effective_message.reply_text.assert_awaited_once_with(mensaje)


def test_cuenta_limite_una_sola_vez_antes_de_descargar():
    u,c,llamadas,_=armar()
    limite=Mock();limite.evaluar.return_value=limites.PERMITIDO
    c.application.bot_data['limite']=limite
    asyncio.run(recibir_audio(u,c))
    limite.evaluar.assert_called_once_with(111)
    assert len(llamadas)==2


def test_remitente_no_autorizado_no_descarga_audio():
    u,c,llamadas,media=armar();c.application.bot_data['chats_autorizados']=set()
    asyncio.run(recibir_audio(u,c))
    assert not llamadas
    media.get_file.assert_not_awaited()
