from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4
import httpx
import pytest
from geografia.rutas_google import RutasGoogle, ErrorRutas, enlaces_recorrido
from agentes.escenario_v3 import preparar_escenario
from agentes.planificacion import procesar_planificacion
from contratos.solicitudes import MatrizTiempos

U = {'latitud':8.9,'longitud':-79.7,'fuente':'compartida'}


def proveedor(datos=None, codigo=200, error=None, n=2):
    if datos is None:
        datos=[{'originIndex':a,'destinationIndex':b,'status':{},'condition':'ROUTE_EXISTS',
                'duration':'0s' if a==b else ('60.001s' if a<b else '180s'),
                'distanceMeters':0 if a==b else 1234} for a in range(n) for b in range(n)]
    llamadas=[]
    def respuesta(p):
        llamadas.append(p)
        if error:
            raise error
        return httpx.Response(codigo,json=datos)
    return RutasGoogle('clave-prueba',httpx.MockTransport(respuesta)),llamadas


def test_matriz_dirigida_redondeo_y_clave_en_header():
    p,llamadas=proveedor()
    ids=[uuid4(),uuid4()]
    resultado=p.calcular(ids,[U,U])
    assert resultado['matriz'].minutos==[[0,2],[3,0]]
    assert resultado['matriz'].origen=='estimado'
    assert resultado['matriz'].nodos_ids==ids
    assert llamadas[0].headers['X-Goog-Api-Key']=='clave-prueba'
    assert 'clave-prueba' not in str(llamadas[0].url) and 'clave-prueba' not in repr(p)
    import json
    cuerpo=json.loads(llamadas[0].content)
    assert cuerpo['routingPreference']=='TRAFFIC_UNAWARE'
    assert len(cuerpo['origins'])==len(cuerpo['destinations'])==2
    assert 'status' in llamadas[0].headers['X-Goog-FieldMask']


def test_indices_cero_omitidos_y_respuesta_desordenada():
    datos=[{'originIndex':a,'destinationIndex':b,'condition':'ROUTE_EXISTS','duration':'60s','distanceMeters':10}
           for a in range(2) for b in range(2)]
    for f in datos:
        for k in ['originIndex','destinationIndex']:
            if f[k]==0: del f[k]
    p,_=proveedor(list(reversed(datos)))
    assert p.calcular([uuid4(),uuid4()],[U,U])['matriz'].minutos==[[0,1],[1,0]]


def test_tramo_sin_ruta_se_conserva_como_inaccesible():
    datos=[{'originIndex':a,'destinationIndex':b,'condition':'ROUTE_NOT_FOUND','status':{}}
           for a in range(2) for b in range(2)]
    p,_=proveedor(datos)
    assert p.calcular([uuid4(),uuid4()],[U,U])['matriz'].minutos==[[0,None],[None,0]]


@pytest.mark.parametrize('tipo',['incompleta','duplicada','indice','duracion','distancia','estado'])
def test_no_inventa_valores_para_respuesta_invalida(tipo):
    datos=[{'originIndex':a,'destinationIndex':b,'condition':'ROUTE_EXISTS','status':{},'duration':'60s','distanceMeters':1}
           for a in range(2) for b in range(2)]
    if tipo=='incompleta': datos.pop()
    if tipo=='duplicada': datos[-1]=deepcopy(datos[0])
    if tipo=='indice': datos[-1]['originIndex']=9
    if tipo=='duracion': datos[-1]['duration']='NaNs'
    if tipo=='distancia': datos[1]['distanceMeters']=-1
    if tipo=='estado': datos[1]['status']={'code':7}
    p,_=proveedor(datos)
    with pytest.raises(ErrorRutas): p.calcular([uuid4(),uuid4()],[U,U])


@pytest.mark.parametrize('codigo',[403,429,500])
def test_fallo_proveedor_sin_reintentos_o_exposicion(codigo):
    p,llamadas=proveedor(codigo=codigo)
    with pytest.raises(ErrorRutas) as e: p.calcular([uuid4(),uuid4()],[U,U])
    assert 'clave-prueba' not in str(e.value) and len(llamadas)==1


def test_limite_siete_nodos_antes_de_facturar():
    p,llamadas=proveedor()
    with pytest.raises(ErrorRutas): p.calcular([uuid4() for _ in range(8)],[U]*8)
    assert not llamadas


def test_navegacion_respeta_orden_y_regreso():
    a={**U,'latitud':8.91};b={**U,'latitud':8.92}
    enlaces=enlaces_recorrido(U,[a,b])
    parametros=parse_qs(urlsplit(enlaces['navegacion_url']).query)
    assert parametros['origin']==parametros['destination']==['8.9,-79.7']
    assert parametros['waypoints']==['8.91,-79.7|8.92,-79.7']
    assert len(enlaces['tramos_navegacion'])==3
    assert parse_qs(urlsplit(enlaces['tramos_navegacion'][-1]).query)['origin']==['8.92,-79.7']


def test_planificador_actualiza_snapshot_antes_de_solver(monkeypatch):
    s=preparar_escenario();original=s.model_dump(mode='json')
    matriz=s.matriz.model_copy(update={'origen':'estimado','matriz_version':'google-routes-test'})
    actualizado={**original,'matriz':matriz.model_dump(mode='json')}
    p=Mock();p.para_solicitud.return_value=matriz
    monkeypatch.setattr(RutasGoogle,'cargar',classmethod(lambda cls,**kw:p))
    db=Mock()
    db.rpc.return_value.execute.side_effect=[SimpleNamespace(data={'solicitud':original}),
        SimpleNamespace(data={'solicitud':actualizado}),SimpleNamespace(data={'estado':'espera_validacion'})]
    salida=procesar_planificacion(s.ejecucion_id,db,'worker')
    assert salida['estado']=='espera_validacion'
    assert [c.args[0] for c in db.rpc.call_args_list]==['ra_tomar_planificacion_v3','ra_actualizar_matriz_planificacion','ra_finalizar_planificacion_v3']
    cierre=db.rpc.call_args.args[1]
    assert cierre['p_snapshot']['solicitud']['matriz']['origen']=='estimado'
    assert cierre['p_resultado']['informe']['valido']
    assert any('google-routes-test' in x for x in cierre['p_resultado']['propuesta']['supuestos'])


def test_si_google_falla_no_resuelve_con_matriz_sintetica(monkeypatch):
    s=preparar_escenario();p=Mock();p.para_solicitud.side_effect=ErrorRutas('Servicio no disponible')
    monkeypatch.setattr(RutasGoogle,'cargar',classmethod(lambda cls,**kw:p))
    db=Mock();db.rpc.return_value.execute.side_effect=[SimpleNamespace(data={'solicitud':s.model_dump(mode='json')}),SimpleNamespace(data={'estado':'espera_revision'})]
    herramientas=Mock()
    procesar_planificacion(s.ejecucion_id,db,'worker',herramientas)
    herramientas.solve_routes.assert_not_called()
    assert db.rpc.call_args.args[1]['p_resultado']['propuesta'] is None


def test_destinos_coincidentes_admiten_distancia_cero_omitida():
    datos=[{'originIndex':a,'destinationIndex':b,'condition':'ROUTE_EXISTS','duration':'0s'}
           for a in range(2) for b in range(2)]
    p,_=proveedor(datos)
    resultado=p.calcular([uuid4(),uuid4()],[U,U])
    assert resultado['metros']==[[0,0],[0,0]]
    assert resultado['matriz'].minutos==[[0,0],[0,0]]
