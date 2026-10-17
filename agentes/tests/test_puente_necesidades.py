"""Puente A1 sin red; las demandas de prueba se sustituyen por las de la BD."""
from copy import deepcopy
from unittest.mock import Mock
import pytest
from agentes.escenario_v3 import preparar_escenario
from agentes.puente_necesidades import construir_solicitud, infraestructura_ensayo, preparar_puentes, RevisionPuente
from agentes.planificacion import planificar
from contratos.solicitudes import SolicitudResolverRutas


@pytest.fixture
def snapshot():
    s=preparar_escenario(escenario_id='d60b7afd-c6a5-4786-a989-f83ba30ae001').model_dump(mode='json')
    infra=infraestructura_ensayo()
    puntos=[dict(punto_atencion_id=p['punto_atencion_id'],sector_id=p['sector_id'],nombre=p['nombre'],
        origen=p['origen'],activo=True,latitud=p['ubicacion']['latitud'],longitud=p['ubicacion']['longitud'],
        fuente_ubicacion=p['ubicacion']['fuente'],precision_metros=None,representa_punto_atencion=None) for p in s['puntos']]
    return dict(ejecucion=dict(ejecucion_id=s['ejecucion_id'],creado_en=s['creado_en'],origen='sintetico',
        etapa='priorizacion',estado='espera_validacion',datos_version=s['datos_version'],
        entrada_priorizacion=dict(politica=s['politica'],entradas=[dict(version_incidente=4,
            solicitud_demanda=dict(incidente_id=n['incidente_id'])) for n in s['necesidades']])),
        incidentes=[dict(incidente_id=n['incidente_id'],version=4,origen='sintetico') for n in s['necesidades']],
        evaluaciones=deepcopy(s['necesidades']),politica=deepcopy(s['politica']),infraestructura=infra,
        puntos=puntos,deposito=None,vehiculos=[],fuente={})


def test_no_copia_demanda_identidad_o_politica_del_fixture(snapshot):
    snapshot['evaluaciones'][0]['demanda_litros']=1234.0
    antes=deepcopy(snapshot); salida=construir_solicitud(snapshot)
    assert snapshot==antes
    assert salida['necesidades']==snapshot['evaluaciones']
    assert salida['necesidades'][0]['demanda_litros']==1234
    assert salida['ejecucion_id']==snapshot['ejecucion']['ejecucion_id']
    assert salida['politica']['politica_version']==snapshot['politica']['politica_version']
    assert all(n['origen']=='sintetico' for n in salida['necesidades'])


def test_infraestructura_no_contiene_necesidades_politica_ni_confirmaciones():
    assert set(infraestructura_ensayo())=={'deposito','vehiculos','puntos','matriz','servicios','limite_solver_segundos'}


def test_puente_es_determinista_y_valido_para_tools_reales(snapshot):
    a=construir_solicitud(snapshot);b=construir_solicitud(snapshot)
    assert a==b
    resultado=planificar(SolicitudResolverRutas.model_validate(a))
    assert resultado.informe.valido
    assert sum(p.litros_asignados for r in resultado.propuesta.rutas for p in r.paradas)==15000
    assert resultado.propuesta.aprobacion is None


@pytest.mark.parametrize('origen',['real','estimado'])
def test_conserva_origen_de_hechos_y_rotula_el_escenario_de_ensayo(snapshot,origen):
    snapshot['ejecucion']['origen']=origen
    for i in snapshot['incidentes']:i['origen']=origen
    for n in snapshot['evaluaciones']:n['origen']=origen
    salida=construir_solicitud(snapshot)
    assert salida['origen']=='sintetico'
    assert snapshot['ejecucion']['origen']==origen
    assert all(n['origen']==origen for n in salida['necesidades'])
    assert all(v['origen']=='sintetico' for v in salida['vehiculos'])
    resultado=planificar(salida)
    assert resultado.informe.valido and resultado.propuesta.origen=='sintetico'



def test_no_omite_necesidades_pendientes(snapshot):
    n=snapshot['evaluaciones'][0];n.update(estado_demanda='pendiente',demanda_litros=None,estado_prioridad='pendiente',
        puntaje=None,posicion=None,componentes=None,pendientes=['capacidad_recepcion_litros'])
    resultado=construir_solicitud(snapshot)
    assert len(resultado['necesidades'])==6 and resultado['necesidades'][0]['demanda_litros'] is None
    assert resultado['necesidades'][0]['pendientes']==['capacidad_recepcion_litros']


@pytest.mark.parametrize('cambio',['incompleto','duplicado','version','politica','punto','origen_incidente'])
def test_bloquea_ambito_o_version_incompatible(snapshot,cambio):
    if cambio=='incompleto':snapshot['evaluaciones'].pop()
    if cambio=='duplicado':snapshot['evaluaciones'][1]['punto_atencion_id']=snapshot['evaluaciones'][0]['punto_atencion_id']
    if cambio=='version':snapshot['incidentes'][0]['version']+=1
    if cambio=='politica':snapshot['politica']['politica_version']='otra'
    if cambio=='punto':snapshot['puntos'].pop()
    if cambio=='origen_incidente':snapshot['incidentes'][0]['origen']='real'
    with pytest.raises(RevisionPuente):construir_solicitud(snapshot)


def test_un_subconjunto_conserva_matriz_servicios_y_no_inventa_otras_demandas(snapshot):
    snapshot['evaluaciones']=snapshot['evaluaciones'][:2];ids={n['incidente_id'] for n in snapshot['evaluaciones']}
    snapshot['incidentes']=[i for i in snapshot['incidentes'] if i['incidente_id'] in ids]
    s=construir_solicitud(snapshot)
    assert len(s['puntos'])==len(s['necesidades'])==len(s['servicios'])==2
    assert len(s['matriz']['minutos'])==3
    base=snapshot['infraestructura']['matriz']
    for a,id_a in enumerate(s['matriz']['nodos_ids']):
        for b,id_b in enumerate(s['matriz']['nodos_ids']):
            assert s['matriz']['minutos'][a][b]==base['minutos'][base['nodos_ids'].index(id_a)][base['nodos_ids'].index(id_b)]


def test_cola_vacia_no_construye_escenarios():
    db=Mock();db.rpc.return_value.execute.return_value.data=[]
    assert preparar_puentes(db)==[]
    db.rpc.assert_called_once_with('ra_puentes_pendientes_v3',{'p_limite':20})


def test_cola_malformada_no_se_oculta():
    db=Mock();db.rpc.return_value.execute.return_value.data={}
    with pytest.raises(RuntimeError):preparar_puentes(db)


def test_fallo_de_persistencia_no_se_convierte_en_revision_de_datos(snapshot):
    db=Mock()
    db.rpc.return_value.execute.side_effect=[Mock(data=[{'ejecucion_id':snapshot['ejecucion']['ejecucion_id']}]),
        Mock(data=snapshot),RuntimeError('acuse perdido')]
    with pytest.raises(RuntimeError):preparar_puentes(db)
    assert db.rpc.call_count==3
    assert db.rpc.call_args.args[0]=='ra_registrar_puente_v3'


def test_error_de_dominio_no_envenena_la_cola(snapshot):
    from postgrest.exceptions import APIError
    db=Mock()
    db.rpc.return_value.execute.side_effect=[Mock(data=[{'ejecucion_id':snapshot['ejecucion']['ejecucion_id']}]),
        Mock(data=snapshot),APIError({'message':'No se imprime contenido crudo','code':'55000','hint':None,'details':None}),
        Mock(data={'estado':'espera_revision'})]
    assert preparar_puentes(db)==[{'estado':'espera_revision'}]
    assert db.rpc.call_args.args[0]=='ra_revisar_puente_v3'
    assert 'No se imprime' not in db.rpc.call_args.args[1]['p_motivo']


def test_no_reactiva_cisterna_retirada_y_conserva_deficit(snapshot):
    base=snapshot['infraestructura']
    snapshot['vehiculos']=[dict(vehiculo_id=v['vehiculo_id'],capacidad_litros=v['capacidad_litros'],
        disponible=j==0,turno_inicio=v['turno']['inicio'],turno_fin=v['turno']['fin'],
        deposito_id=base['deposito']['deposito_id'],origen='sintetico') for j,v in enumerate(base['vehiculos'])]
    salida=construir_solicitud(snapshot)
    assert [v['disponible'] for v in salida['vehiculos']]==[True,False]
    resultado=planificar(salida)
    assert resultado.informe.valido and len(resultado.propuesta.no_atendidos)==2
    assert sum(n.demanda_pendiente_litros for n in resultado.propuesta.no_atendidos)==6000


@pytest.mark.parametrize("fecha", ["2026-10-17T05:00:00+00:00", "2026-10-17T00:00:00.123456-05:00"])
def test_conserva_representacion_original_de_confirmacion_para_rpc(snapshot, fecha):
    snapshot['politica']['confirmacion_activacion']['confirmado_en'] = fecha
    snapshot['ejecucion']['entrada_priorizacion']['politica'] = deepcopy(snapshot['politica'])
    antes = deepcopy(snapshot)
    salida = construir_solicitud(snapshot)
    # Postgres compara JSONB: Z y +00:00 son textos distintos aun siendo el mismo instante.
    assert salida['politica'] == snapshot['politica']
    assert snapshot == antes
    SolicitudResolverRutas.model_validate(salida)


def test_conservar_json_original_no_omite_validacion_de_politica(snapshot):
    snapshot['politica']['confirmacion_activacion']['confirmado_en'] = 'fecha-invalida'
    with pytest.raises(ValueError):
        construir_solicitud(snapshot)
