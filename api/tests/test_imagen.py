import base64
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.dependencias import obtener_db,secreto_configurado
from api.auth import obtener_verificador
from api.rutas.imagen import obtener_lector
from api.tests.test_api_reportes import BaseFalsa,VerificadorFalso,CUERPO,CABECERA,SECRETO,AUTH
from agentes.gemini import ErrorIngesta
from contratos.errores import CodigoError

TEXTO='En Escuela El Coco llevamos 48 horas sin agua. Somos 120 personas.'
IMAGEN=base64.b64encode(b'\xff\xd8\xffimagen').decode()
ENTRADA={'usuario_telegram_id':111,'chat_id':-1001,'message_id':7,
         'mime_type':'image/jpeg','caption':'Sin agua desde hace 48 horas','imagen_base64':IMAGEN}


@pytest.fixture
def entorno():
    db=BaseFalsa();lector=Mock();lector.analizar.return_value=TEXTO
    app.dependency_overrides[obtener_db]=lambda:db
    app.dependency_overrides[secreto_configurado]=lambda:SECRETO
    app.dependency_overrides[obtener_verificador]=lambda:VerificadorFalso()
    app.dependency_overrides[obtener_lector]=lambda:lambda:lector
    yield db,lector,TestClient(app)
    app.dependency_overrides.clear()


def test_descripcion_y_registro_reutilizan_pipeline_y_idempotencia(entorno):
    db,p,c=entorno
    respuesta=c.post('/imagenes/analizar',json=ENTRADA,headers=CABECERA)
    assert respuesta.status_code==200
    assert TEXTO in respuesta.json()['texto']
    assert ENTRADA['caption'] in respuesta.json()['texto']
    assert respuesta.json()['fuente_texto']=='descripcion_imagen'
    registro=c.post('/reportes',json={**CUERPO,**respuesta.json()},headers=CABECERA)
    assert registro.status_code==201
    assert registro.json()['entrada']['fuente_texto']=='descripcion_imagen'
    assert db.tablas['reportes'][0]['texto']==respuesta.json()['texto']
    assert db.tablas['reportes'][0]['modalidad']=='texto'
    assert c.post('/imagenes/analizar',json=ENTRADA,headers=CABECERA).json()['texto']==db.tablas['reportes'][0]['texto']
    p.analizar.assert_called_once()
    panel=c.get('/reportes',headers=AUTH).json()[0]
    assert panel['registrado']['entrada']['fuente_texto']=='descripcion_imagen'
    assert 'imagen_base64' not in str(db.tablas)


def test_no_se_filtra_descripcion_a_otro_autor(entorno):
    _,p,c=entorno
    c.post('/reportes',json={**CUERPO,'fuente_texto':'descripcion_imagen'},headers=CABECERA)
    respuesta=c.post('/imagenes/analizar',json={**ENTRADA,'usuario_telegram_id':222},headers=CABECERA)
    assert respuesta.status_code==403
    assert CUERPO['texto'] not in respuesta.text
    p.analizar.assert_not_called()


def test_respuesta_audio_guardada_no_se_transcribe_de_nuevo(entorno):
    db,p,c=entorno
    c.post('/reportes',json={**CUERPO,'message_id':1},headers=CABECERA)
    ref=db.tablas['remitentes'][0]['remitente_ref']
    db.tablas['aclaraciones'].append({'respuesta_externo_id':'-1001:7','respuesta_texto':TEXTO,
        'respuesta_remitente_ref':ref,'respuesta_fuente_texto':'descripcion_imagen'})
    assert c.post('/imagenes/analizar',json=ENTRADA,headers=CABECERA).json()['texto']==TEXTO
    p.analizar.assert_not_called()


@pytest.mark.parametrize('cambio', [
    {'imagen_base64': 'no base64'}, {'mime_type': 'application/pdf'}, {'chat_id': 0},
    {'imagen_base64': base64.b64encode(b'not an image').decode()}, {'caption': 'x' * 1025},
    {'imagen_base64': base64.b64encode(b'\xff\xd8\xff' + b'x' * (5 * 1024 * 1024)).decode()},
])

def test_formato_y_limites_antes_de_gastar_cuota(entorno,cambio):
    _,p,c=entorno
    respuesta=c.post('/imagenes/analizar',json={**ENTRADA,**cambio},headers=CABECERA)
    assert respuesta.status_code==422
    p.analizar.assert_not_called()


def test_endpoint_exige_secreto_bot(entorno):
    _,p,c=entorno
    assert c.post('/imagenes/analizar',json=ENTRADA).status_code==403
    assert c.post('/imagenes/analizar',json=ENTRADA,headers=AUTH).status_code==403
    p.analizar.assert_not_called()


def test_imagen_incomprensible_no_guarda_reporte(entorno):
    db,p,c=entorno
    p.analizar.side_effect=ErrorIngesta(CodigoError.CONTRATO_INVALIDO,'No se entendió el audio con claridad.')
    assert c.post('/imagenes/analizar',json=ENTRADA,headers=CABECERA).status_code==422
    assert db.tablas['reportes']==[] and db.tablas['ejecuciones']==[]


def test_cuota_agotada_no_fabrica_texto(entorno):
    _,p,c=entorno
    p.analizar.side_effect=ErrorIngesta(CodigoError.PROVEEDOR_NO_DISPONIBLE,'Cuota no disponible.',True)
    assert c.post('/imagenes/analizar',json=ENTRADA,headers=CABECERA).status_code==503


def test_reintento_devuelve_texto_persistido_no_el_cuerpo_nuevo(entorno):
    _,_,c=entorno
    c.post('/reportes',json={**CUERPO,'fuente_texto':'descripcion_imagen'},headers=CABECERA)
    repetido=c.post('/reportes',json={**CUERPO,'texto':'No debe reemplazar el original'},headers=CABECERA)
    assert repetido.json()['entrada']['texto']==CUERPO['texto']
    assert repetido.json()['entrada']['fuente_texto']=='descripcion_imagen'


def test_rpc_imagen_conserva_controles_y_procedencia():
    from api.tests.test_api_aclaraciones import BaseFalsa as BaseRPC, REMITENTE, RESPUESTA
    base = BaseRPC()
    base.respuestas['ra_aceptar_respuesta_imagen'] = {'resultado': 'aceptada', 'ejecucion_id': None}
    app.dependency_overrides[obtener_db] = lambda: base
    app.dependency_overrides[secreto_configurado] = lambda: SECRETO
    try:
        respuesta = TestClient(app).post('/aclaraciones/respuestas',
            json={**RESPUESTA, 'fuente_texto': 'descripcion_imagen'}, headers=CABECERA)
        assert respuesta.status_code == 200
        nombre, parametros = base.llamadas[-1]
        assert nombre == 'ra_aceptar_respuesta_imagen'
        assert parametros['p_remitente_ref'] == REMITENTE
        assert parametros['p_pregunta_mensaje_id'] == '55'
    finally:
        app.dependency_overrides.clear()


def test_imagen_no_admite_fuente_sin_texto(entorno):
    _,p,c=entorno
    respuesta=c.post('/aclaraciones/respuestas', json={
        'usuario_telegram_id':111,'chat_id':-1001,'message_id':8,'pregunta_mensaje_id':55,
        'ubicacion':{'latitud':8.9,'longitud':-79.5},'fuente_texto':'descripcion_imagen'}, headers=CABECERA)
    assert respuesta.status_code == 422


def test_png_valido_se_analiza(entorno):
    _,p,c=entorno
    respuesta=c.post('/imagenes/analizar',json={**ENTRADA,'mime_type':'image/png',
        'imagen_base64':base64.b64encode(b'\x89PNG\r\n\x1a\ncontenido').decode()},headers=CABECERA)
    assert respuesta.status_code==200
    p.analizar.assert_called_once()
