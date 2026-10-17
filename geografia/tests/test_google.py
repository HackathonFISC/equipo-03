"""Google simulado: sin red, sin facturación y sin secretos reales."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from geografia.google import GeocodificadorGoogle
from agentes.territorial import resolver_reporte, procesar_territorial

LUGAR = {'placeId': 'google-place-1', 'location': {'latitude': 8.91, 'longitude': -79.71},
         'granularity': 'ROOFTOP', 'types': ['street_address'], 'postalAddress': {'regionCode': 'PA'}}


def google(datos=None, codigo=200, error=None):
    peticiones=[]
    def responder(p):
        peticiones.append(p)
        if error:
            raise error
        return httpx.Response(codigo,json=datos if datos is not None else {'results':[LUGAR]})
    return GeocodificadorGoogle('clave-simulada',httpx.MockTransport(responder)), peticiones


def filas():
    return {'reporte': {'texto': 'Falta agua en Calle Nueva 123, Arraiján.',
            'creado_en':'2026-10-17T12:00:00+00:00', 'interpretacion': {
            'resumen':'Falta agua', 'ubicacion_declarada':'Calle Nueva 123, Arraiján',
            'campos':{'tipo_problema':'sin_suministro'}, 'evidencia_textual':['Falta agua'],
            'faltantes':[], 'requiere_aclaracion':False, 'fuera_de_alcance':False}},
            'catalogo':[], 'aclaraciones':[]}


def test_direccion_nueva_resuelta_sin_revision_y_clave_fuera_de_url():
    proveedor, peticiones=google()
    salida=resolver_reporte(filas(),proveedor)
    assert salida['estado']=='localizada'
    assert salida['ubicacion']['fuente']=='geocodificada'
    assert salida['place_id']=='google-place-1'
    assert 'punto_atencion_id' not in salida
    p=peticiones[0]
    assert p.headers['X-Goog-Api-Key']=='clave-simulada'
    assert 'clave-simulada' not in str(p.url)
    assert 'clave-simulada' not in repr(proveedor)
    assert p.url.params['address.addressLines']=='Calle Nueva 123, Arraiján'
    assert p.url.params['address.regionCode']=='PA'


@pytest.mark.parametrize('cambios',[
    {'granularity':'APPROXIMATE'}, {'types':['locality']}, {'postalAddress':{'regionCode':'US'}},
    {'location':{'latitude':999.0,'longitude':-79.7}}, {'placeId':''},
])
def test_resultado_impreciso_o_invalido_pide_pin_al_remitente(cambios):
    lugar={**deepcopy(LUGAR),**cambios}
    proveedor,_=google({'results':[lugar]})
    assert resolver_reporte(filas(),proveedor)['estado']=='desconocida'


@pytest.mark.parametrize('datos',[{'results':[]},{'results':[LUGAR,LUGAR]}, {'error':'no disponible'}, None])
def test_no_elige_arbitrariamente_entre_resultados(datos):
    if datos is None:
        datos={'results':None}
    proveedor,_=google(datos)
    assert resolver_reporte(filas(),proveedor)['estado']=='desconocida'


@pytest.mark.parametrize('codigo',[403,429,500])
def test_proveedor_no_disponible_no_interrumpe_reporte(codigo,caplog):
    proveedor,_=google(codigo=codigo)
    assert resolver_reporte(filas(),proveedor)['estado']=='desconocida'
    assert 'clave-simulada' not in caplog.text
    assert 'Calle Nueva' not in caplog.text


def test_timeout_pide_pin_sin_reintentos():
    proveedor,llamadas=google(error=httpx.ReadTimeout('fallo simulado'))
    assert resolver_reporte(filas(),proveedor)['estado']=='desconocida'
    assert len(llamadas)==1


def test_pin_tiene_precedencia_y_no_consume_google():
    f=filas()
    f['aclaraciones']=[{'respuesta_ubicacion':{'latitud':8.95,'longitud':-79.75,'fuente':'compartida'}}]
    proveedor=Mock()
    salida=resolver_reporte(f,proveedor)
    assert salida['estado']=='localizada' and salida['ubicacion']['latitud']==8.95
    proveedor.resolver.assert_not_called()


def test_sin_direccion_no_envia_texto_completo_a_google():
    f=filas();f['reporte']['interpretacion']['ubicacion_declarada']=None
    proveedor=Mock()
    assert resolver_reporte(f,proveedor)['estado']=='desconocida'
    proveedor.resolver.assert_not_called()


def test_trabajador_guarda_localizacion_por_rpc_atomica(monkeypatch):
    proveedor,_=google()
    monkeypatch.setattr(GeocodificadorGoogle,'cargar',classmethod(lambda cls:proveedor))
    db=Mock()
    db.rpc.return_value.execute.side_effect=[SimpleNamespace(data=filas()),SimpleNamespace(data={'estado':'completada'})]
    assert procesar_territorial('id',db,'worker')['estado']=='completada'
    llamada=db.rpc.call_args
    assert llamada.args[0]=='ra_finalizar_localizacion'
    assert llamada.args[1]['p_resolucion']['estado']=='localizada'
    assert llamada.args[1]['p_snapshot']['reporte']['texto'].startswith('Falta agua')


def test_sin_clave_no_crea_cliente_real(monkeypatch):
    monkeypatch.setenv('GOOGLE_MAPS_API_KEY','')
    assert GeocodificadorGoogle.cargar() is None
