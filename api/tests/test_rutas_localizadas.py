from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import obtener_verificador
from api.dependencias import obtener_db
from api.esquemas import PeticionRutaLocalizada
from api.servicios import rutas_google as servicio
from api.errores_http import ErrorApi
from contratos.solicitudes import MatrizTiempos
from geografia.rutas_google import RutasGoogle

AUTH={'Authorization':'Bearer a.b.c'}
D,R1,R2=[str(uuid4()) for _ in range(3)]
U={'latitud':8.9,'longitud':-79.7,'fuente':'compartida'}
OPCIONES={'depositos':[{'deposito_id':D,'nombre':'Depósito','ubicacion':U}],
          'destinos':[{'reporte_id':i,'nombre':i,'ubicacion':U} for i in [R1,R2]]}


def prueba_proveedor(minutos=None):
    p=Mock()
    p.calcular.return_value={'matriz':MatrizTiempos(matriz_version='google-routes-test',origen='estimado',
        nodos_ids=[D,R1,R2],minutos=minutos or [[0,9,1],[1,0,9],[9,1,0]],descripcion='Google Maps test'),
        'metros':[[0,9000,1000],[1000,0,9000],[9000,1000,0]],'consultado_en':'2026-10-17T12:00:00+00:00'}
    return p


@pytest.fixture
def entorno(monkeypatch):
    db=Mock()
    monkeypatch.setattr(servicio,'opciones',lambda base:deepcopy(OPCIONES))
    app.dependency_overrides[obtener_db]=lambda:db
    app.dependency_overrides[obtener_verificador]=lambda:SimpleNamespace(usuario_id=lambda token:uuid4())
    yield db,TestClient(app)
    app.dependency_overrides.clear()


def test_preview_optimiza_por_carretera_y_no_escribe(entorno):
    db,_=entorno;p=prueba_proveedor()
    datos=PeticionRutaLocalizada(deposito_id=D,reportes_ids=[R1,R2])
    resultado=servicio.previsualizar(db,datos,p)
    assert [x['reporte_id'] for x in resultado['paradas']]==[R2,R1]
    assert resultado['duracion_minutos']==3 and resultado['distancia_metros']==3000
    assert len(resultado['tramos_navegacion'])==3
    assert not db.mock_calls


def test_preview_sin_via_no_inventa_conexion(entorno):
    db,_=entorno;p=prueba_proveedor([[0,None,None],[None,0,None],[None,None,0]])
    with pytest.raises(ErrorApi) as e: servicio.previsualizar(db,PeticionRutaLocalizada(deposito_id=D,reportes_ids=[R1,R2]),p)
    assert e.value.codigo=='contrato_invalido'


def test_revalida_coordenadas_en_servidor(entorno):
    db,_=entorno;p=prueba_proveedor()
    with pytest.raises(ErrorApi): servicio.previsualizar(db,PeticionRutaLocalizada(deposito_id=D,reportes_ids=[uuid4()]),p)
    p.calcular.assert_not_called()


@pytest.mark.parametrize('ruta,metodo',[('/planes/destinos-localizados','get'),('/planes/ruta-localizada','post')])
def test_api_requiere_sesion(entorno,ruta,metodo):
    _,cliente=entorno
    assert getattr(cliente,metodo)(ruta).status_code==403


def test_api_valida_duplicados_y_no_admite_coordenadas(entorno,monkeypatch):
    _,cliente=entorno
    p=prueba_proveedor();monkeypatch.setattr(RutasGoogle,'cargar',classmethod(lambda cls,**kw:p))
    assert cliente.post('/planes/ruta-localizada',headers=AUTH,json={'deposito_id':D,'reportes_ids':[R1,R1]}).status_code==422
    assert cliente.post('/planes/ruta-localizada',headers=AUTH,json={'deposito_id':D,'reportes_ids':[R1],'ubicacion':U}).status_code==422
    p.calcular.assert_not_called()


def test_api_preview_y_destinos_sin_datos_internos(entorno,monkeypatch):
    _,cliente=entorno
    p=prueba_proveedor();monkeypatch.setattr(RutasGoogle,'cargar',classmethod(lambda cls,**kw:p))
    assert cliente.get('/planes/destinos-localizados',headers=AUTH).status_code==200
    respuesta=cliente.post('/planes/ruta-localizada',headers=AUTH,json={'deposito_id':D,'reportes_ids':[R1,R2]})
    assert respuesta.status_code==200
    assert respuesta.json()['proveedor']=='Google Maps'
    assert 'clave' not in respuesta.text and 'remitente_ref' not in respuesta.text


def test_opciones_usa_pines_y_omite_google_vencido(monkeypatch):
    from api.servicios.rutas_google import opciones
    extraidos={'resumen':'Sin agua','ubicacion_declarada':'Barrio nuevo',
               'campos':{'tipo_problema':'sin_suministro'},'evidencia_textual':['Sin agua'],
               'faltantes':[],'requiere_aclaracion':False,'fuera_de_alcance':False}
    vigente={'ubicacion':{**U,'fuente':'geocodificada'},'resuelta_en':'2026-10-17T12:00:00+00:00',
             'expira_en':'2099-01-01T00:00:00+00:00','place_id':'place1'}
    reportes=[{'reporte_id':R1,'interpretacion':extraidos,'localizacion_resuelta':vigente},
              {'reporte_id':R2,'interpretacion':extraidos,'localizacion_resuelta':{**vigente,'expira_en':'2000-01-01T00:00:00+00:00'}},
              {'reporte_id':str(uuid4()),'interpretacion':extraidos,'aclaraciones':[
                  {'respondida_en':'2026-10-17T12:00:00+00:00','respuesta_ubicacion':U}]}]
    db=Mock();db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value=SimpleNamespace(data=reportes)
    db.table.return_value.select.return_value.eq.return_value.execute.return_value=SimpleNamespace(data=[
        {'deposito_id':D,'nombre':'Depósito','latitud':'8.9','longitud':'-79.7'},
        {'deposito_id':str(uuid4()),'nombre':'Sin coordenadas','latitud':None,'longitud':None}])
    datos=opciones(db)
    assert len(datos['destinos'])==2 and R2 not in [d['reporte_id'] for d in datos['destinos']]
    assert len(datos['depositos'])==1 and datos['depositos'][0]['ubicacion']['latitud']==8.9


def test_api_limita_seis_destinos_antes_de_consultar_google(entorno,monkeypatch):
    _,cliente=entorno
    p=Mock();monkeypatch.setattr(RutasGoogle,'cargar',classmethod(lambda cls,**kw:p))
    respuesta=cliente.post('/planes/ruta-localizada',headers=AUTH,json={'deposito_id':D,'reportes_ids':[str(uuid4()) for _ in range(7)]})
    assert respuesta.status_code==422
    p.calcular.assert_not_called()


def test_clave_ausente_es_error_claro_sin_fallback(entorno,monkeypatch):
    _,cliente=entorno
    monkeypatch.setattr(RutasGoogle,'cargar',classmethod(lambda cls,**kw:None))
    respuesta=cliente.post('/planes/ruta-localizada',headers=AUTH,json={'deposito_id':D,'reportes_ids':[R1,R2]})
    assert respuesta.status_code==503 and 'habilita Routes API' in respuesta.json()['mensaje']
