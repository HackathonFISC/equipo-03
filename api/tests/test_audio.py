import base64
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.dependencias import obtener_db,secreto_configurado
from api.auth import obtener_verificador
from api.rutas.audio import obtener_transcriptor
from api.tests.test_api_reportes import BaseFalsa,VerificadorFalso,CUERPO,CABECERA,SECRETO,AUTH
from agentes.gemini import ErrorIngesta
from contratos.errores import CodigoError

TEXTO='En Escuela El Coco llevamos 48 horas sin agua. Somos 120 personas.'
AUDIO=base64.b64encode(b'OggS'+b'\x00'*28+b'OpusHead').decode()
ENTRADA={'usuario_telegram_id':111,'chat_id':-1001,'message_id':7,
         'mime_type':'audio/ogg','duracion_segundos':20,'audio_base64':AUDIO}


@pytest.fixture
def entorno():
    db=BaseFalsa();transcriptor=Mock();transcriptor.transcribir.return_value=TEXTO
    app.dependency_overrides[obtener_db]=lambda:db
    app.dependency_overrides[secreto_configurado]=lambda:SECRETO
    app.dependency_overrides[obtener_verificador]=lambda:VerificadorFalso()
    app.dependency_overrides[obtener_transcriptor]=lambda:lambda:transcriptor
    yield db,transcriptor,TestClient(app)
    app.dependency_overrides.clear()


def test_transcripcion_y_registro_reutilizan_pipeline_y_idempotencia(entorno):
    db,p,c=entorno
    respuesta=c.post('/audio/transcribir',json=ENTRADA,headers=CABECERA)
    assert respuesta.status_code==200
    assert respuesta.json()=={'texto':TEXTO,'fuente_texto':'transcripcion_audio'}
    registro=c.post('/reportes',json={**CUERPO,**respuesta.json()},headers=CABECERA)
    assert registro.status_code==201
    assert registro.json()['entrada']['fuente_texto']=='transcripcion_audio'
    assert db.tablas['reportes'][0]['texto']==TEXTO
    assert db.tablas['reportes'][0]['modalidad']=='texto'
    assert c.post('/audio/transcribir',json=ENTRADA,headers=CABECERA).json()['texto']==TEXTO
    p.transcribir.assert_called_once()
    panel=c.get('/reportes',headers=AUTH).json()[0]
    assert panel['registrado']['entrada']['fuente_texto']=='transcripcion_audio'
    assert 'audio_base64' not in str(db.tablas)


def test_no_se_filtra_transcripcion_a_otro_autor(entorno):
    _,p,c=entorno
    c.post('/reportes',json={**CUERPO,'fuente_texto':'transcripcion_audio'},headers=CABECERA)
    respuesta=c.post('/audio/transcribir',json={**ENTRADA,'usuario_telegram_id':222},headers=CABECERA)
    assert respuesta.status_code==403
    assert CUERPO['texto'] not in respuesta.text
    p.transcribir.assert_not_called()


def test_respuesta_audio_guardada_no_se_transcribe_de_nuevo(entorno):
    db,p,c=entorno
    c.post('/reportes',json={**CUERPO,'message_id':1},headers=CABECERA)
    ref=db.tablas['remitentes'][0]['remitente_ref']
    db.tablas['aclaraciones'].append({'respuesta_externo_id':'-1001:7','respuesta_texto':TEXTO,
        'respuesta_remitente_ref':ref,'respuesta_fuente_texto':'transcripcion_audio'})
    assert c.post('/audio/transcribir',json=ENTRADA,headers=CABECERA).json()['texto']==TEXTO
    p.transcribir.assert_not_called()


@pytest.mark.parametrize('cambio',[{'duracion_segundos':121},{'duracion_segundos':0},
    {'audio_base64':'no base64'},{'mime_type':'application/pdf'},{'chat_id':0},
    {'audio_base64':base64.b64encode(b'no audio').decode()},{'duracion_segundos':1.5}])
def test_formato_y_limites_antes_de_gastar_cuota(entorno,cambio):
    _,p,c=entorno
    respuesta=c.post('/audio/transcribir',json={**ENTRADA,**cambio},headers=CABECERA)
    assert respuesta.status_code==422
    p.transcribir.assert_not_called()


def test_endpoint_exige_secreto_bot(entorno):
    _,p,c=entorno
    assert c.post('/audio/transcribir',json=ENTRADA).status_code==403
    assert c.post('/audio/transcribir',json=ENTRADA,headers=AUTH).status_code==403
    p.transcribir.assert_not_called()


def test_audio_incomprensible_no_guarda_reporte(entorno):
    db,p,c=entorno
    p.transcribir.side_effect=ErrorIngesta(CodigoError.CONTRATO_INVALIDO,'No se entendió el audio con claridad.')
    assert c.post('/audio/transcribir',json=ENTRADA,headers=CABECERA).status_code==422
    assert db.tablas['reportes']==[] and db.tablas['ejecuciones']==[]


def test_cuota_agotada_no_fabrica_texto(entorno):
    _,p,c=entorno
    p.transcribir.side_effect=ErrorIngesta(CodigoError.PROVEEDOR_NO_DISPONIBLE,'Cuota no disponible.',True)
    assert c.post('/audio/transcribir',json=ENTRADA,headers=CABECERA).status_code==503


def test_reintento_devuelve_texto_persistido_no_el_cuerpo_nuevo(entorno):
    _,_,c=entorno
    c.post('/reportes',json={**CUERPO,'fuente_texto':'transcripcion_audio'},headers=CABECERA)
    repetido=c.post('/reportes',json={**CUERPO,'texto':'No debe reemplazar el original'},headers=CABECERA)
    assert repetido.json()['entrada']['texto']==CUERPO['texto']
    assert repetido.json()['entrada']['fuente_texto']=='transcripcion_audio'
