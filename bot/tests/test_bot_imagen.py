import asyncio
import json
from types import SimpleNamespace as N
from unittest.mock import AsyncMock, Mock
import httpx
import pytest
from bot import adaptador, limites
from bot.bot import recibir_imagen, MENSAJE_IMAGEN_LIMITE, MENSAJE_IMAGEN_FALLO, MENSAJE_IMAGEN_INCIERTA
from comun.imagen import MAX_IMAGEN_BYTES

JPEG = b'\xff\xd8\xffimagen'
TEXTO = 'Descripción automática: tubería con agua. Texto adjunto: Sin agua desde hace 48 horas.'


@pytest.fixture(autouse=True)
def preguntas(monkeypatch):
    monkeypatch.setattr(adaptador, '_preguntas_abiertas', {})
    monkeypatch.setattr(adaptador, 'ACLARACIONES_ACTIVAS', True)


def armar(*, grupo=False, reply=False, caption=None, estado=200, resultado='aceptada'):
    llamadas = []
    def responder(p):
        llamadas.append(p)
        if p.url.path == '/imagenes/analizar':
            return httpx.Response(estado, json={'texto': TEXTO, 'fuente_texto': 'descripcion_imagen'})
        if p.url.path == '/aclaraciones/respuestas':
            return httpx.Response(200, json={'resultado': resultado})
        return httpx.Response(201, json={'reporte_id': '11111111-1111-4111-8111-111111111111'})
    archivo = N(file_size=len(JPEG), download_as_bytearray=AsyncMock(return_value=bytearray(JPEG)))
    foto = N(width=800, height=600, file_size=len(JPEG), get_file=AsyncMock(return_value=archivo))
    mensaje = N(message_id=7, photo=[foto], caption=caption, media_group_id=None, reply_text=AsyncMock(),
                reply_to_message=N(message_id=55, from_user=N(id=900)) if reply else None)
    u = N(effective_chat=N(id=-1001 if grupo else 111, type='group' if grupo else 'private'),
          effective_message=mensaje, effective_user=N(id=111, is_bot=False))
    cliente = httpx.AsyncClient(base_url='http://api.prueba', transport=httpx.MockTransport(responder))
    c = N(bot=N(id=900, username='aguabot'), application=N(bot_data={
        'chats_autorizados': {111, -1001}, 'cliente_api': cliente}))
    return u, c, llamadas, foto, archivo


def test_foto_con_caption_es_reporte_con_procedencia():
    u,c,llamadas,_,_=armar(caption='Sin agua en Escuela El Coco')
    asyncio.run(recibir_imagen(u,c))
    assert [p.url.path for p in llamadas] == ['/imagenes/analizar','/reportes']
    assert json.loads(llamadas[0].content)['caption'] == 'Sin agua en Escuela El Coco'
    assert json.loads(llamadas[1].content)['fuente_texto'] == 'descripcion_imagen'
    assert 'Analizamos tu foto' in u.effective_message.reply_text.await_args.args[0]


@pytest.mark.parametrize('reply,implicita',[(True,False),(False,True)])
def test_foto_responde_aclaracion_sin_crear_reporte(reply,implicita):
    u,c,llamadas,_,_=armar(grupo=True,reply=reply)
    if implicita: adaptador.recordar_pregunta(-1001,55,111)
    asyncio.run(recibir_imagen(u,c))
    assert [p.url.path for p in llamadas] == ['/imagenes/analizar','/aclaraciones/respuestas']
    assert json.loads(llamadas[-1].content)['pregunta_mensaje_id']==55
    assert json.loads(llamadas[-1].content)['fuente_texto']=='descripcion_imagen'


@pytest.mark.parametrize('otra_pregunta',[False,True])
def test_grupo_sin_dirigir_o_pregunta_ajena_no_descarga(otra_pregunta):
    u,c,llamadas,foto,_=armar(grupo=True)
    if otra_pregunta: adaptador.recordar_pregunta(-1001,55,222)
    asyncio.run(recibir_imagen(u,c))
    assert not llamadas
    foto.get_file.assert_not_awaited()


def test_mencion_en_caption_se_quita_antes_de_analizar():
    u,c,llamadas,_,_=armar(grupo=True,caption='@aguabot Sin agua')
    asyncio.run(recibir_imagen(u,c))
    assert json.loads(llamadas[0].content)['caption']=='Sin agua'


@pytest.mark.parametrize('modo',['anunciado','archivo','descarga','album'])
def test_limites_y_album_no_se_envian_al_proveedor(modo):
    u,c,llamadas,foto,archivo=armar()
    if modo=='anunciado': foto.file_size=MAX_IMAGEN_BYTES+1
    if modo=='archivo': archivo.file_size=MAX_IMAGEN_BYTES+1
    if modo=='descarga': archivo.download_as_bytearray.return_value=b'x'*(MAX_IMAGEN_BYTES+1)
    if modo=='album': u.effective_message.media_group_id='album'
    asyncio.run(recibir_imagen(u,c))
    assert not llamadas
    u.effective_message.reply_text.assert_awaited_once_with(MENSAJE_IMAGEN_LIMITE)


@pytest.mark.parametrize('estado,mensaje',[(422,MENSAJE_IMAGEN_INCIERTA),(503,MENSAJE_IMAGEN_FALLO)])
def test_error_no_crea_reporte(estado,mensaje):
    u,c,llamadas,_,_=armar(estado=estado)
    asyncio.run(recibir_imagen(u,c))
    assert len(llamadas)==1
    u.effective_message.reply_text.assert_awaited_once_with(mensaje)


def test_limite_se_cuenta_una_sola_vez():
    u,c,llamadas,_,_=armar()
    limite=Mock(); limite.evaluar.return_value=limites.PERMITIDO
    c.application.bot_data['limite']=limite
    asyncio.run(recibir_imagen(u,c))
    limite.evaluar.assert_called_once_with(111)
    assert len(llamadas)==2


def test_elige_mayor_resolucion_permitida():
    u,c,_,foto,_=armar()
    enorme=N(width=2000,height=2000,file_size=MAX_IMAGEN_BYTES+1,get_file=AsyncMock())
    u.effective_message.photo.append(enorme)
    asyncio.run(recibir_imagen(u,c))
    foto.get_file.assert_awaited_once()
    enorme.get_file.assert_not_awaited()


def test_chat_no_autorizado_no_descarga():
    u,c,llamadas,foto,_=armar()
    c.application.bot_data['chats_autorizados']=set()
    asyncio.run(recibir_imagen(u,c))
    assert not llamadas
    foto.get_file.assert_not_awaited()


@pytest.mark.parametrize('resultado',['autor_distinto','vencida','ya_respondida'])
def test_respuesta_rechazada_no_se_convierte_en_reporte(resultado):
    u,c,llamadas,_,_=armar(reply=True,resultado=resultado)
    asyncio.run(recibir_imagen(u,c))
    assert [p.url.path for p in llamadas]==['/imagenes/analizar','/aclaraciones/respuestas']
