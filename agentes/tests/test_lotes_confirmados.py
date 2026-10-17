from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4
import pytest
from agentes.ensayo_priorizacion_v2 import preparar_paquetes
from agentes.lotes_confirmados import construir_lote_confirmado, preparar_lote_automatico
from agentes.priorizacion import procesar_priorizacion


@pytest.fixture
def snapshot():
    paquete = preparar_paquetes(uuid4(), 'FIXTURE: confirmar reutilización')[0]
    return {'ejecucion': dict(ejecucion_id=str(uuid4()), creado_en=datetime.now(timezone.utc).isoformat(),
                             etapa='priorizacion', estado='pendiente', entrada_priorizacion=None),
            'revision': dict(evento_id=str(uuid4()), lote=paquete['lote'])}


def test_reutiliza_datos_y_confirmaciones_sin_reescribir(snapshot):
    original = deepcopy(snapshot)
    lote = construir_lote_confirmado(snapshot)
    assert snapshot == original
    for nueva, anterior in zip(lote['entradas'], original['revision']['lote']['entradas']):
        for campo in ('solicitud_demanda', 'evaluacion'):
            assert nueva[campo]['ejecucion_id'] == snapshot['ejecucion']['ejecucion_id']
            assert nueva[campo]['datos_version'].startswith('auto-')
            assert {k: v for k, v in nueva[campo].items() if k not in {'ejecucion_id', 'datos_version', 'creado_en'}} == {
                k: v for k, v in anterior[campo].items() if k not in {'ejecucion_id', 'datos_version', 'creado_en'}}
    assert construir_lote_confirmado(snapshot) == lote


@pytest.mark.parametrize('campo', ['capacidad_recepcion_litros', 'reserva_utilizable_litros'])
def test_demanda_o_recepcion_incompletas_no_se_inventan(snapshot, campo):
    entrada = snapshot['revision']['lote']['entradas'][0]['solicitud_demanda']
    if campo == 'capacidad_recepcion_litros':
        entrada[campo] = None
    else:
        entrada['demanda'][campo] = None
    with pytest.raises(ValueError):
        construir_lote_confirmado(snapshot)


def cliente(snapshot, motivo=None):
    db = Mock()
    def rpc(nombre, params):
        if nombre == 'ra_contexto_lote_confirmado_v2': dato = snapshot
        elif nombre == 'ra_motivo_lote_confirmado_v2': dato = motivo
        elif nombre == 'ra_registrar_lote_confirmado_v2': dato = {'estado': 'requiere_revision' if params['p_motivo'] else 'preparado'}
        else: raise AssertionError(nombre)
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=dato))
    db.rpc.side_effect = rpc
    return db


def test_rechazo_bd_no_invoca_tools(snapshot):
    db = cliente(snapshot, 'Cambiaron los incidentes')
    herramientas = Mock()
    assert preparar_lote_automatico(db, snapshot['ejecucion']['ejecucion_id'], herramientas)['estado'] == 'requiere_revision'
    herramientas.validate_need.assert_not_called()
    assert db.rpc.call_args.args[1]['p_lote'] is None


def test_error_demanda_solicita_revision(snapshot):
    db = cliente(snapshot)
    snapshot['revision']['lote']['entradas'][0]['solicitud_demanda']['capacidad_recepcion_litros'] = 1
    assert preparar_lote_automatico(db, snapshot['ejecucion']['ejecucion_id'])['estado'] == 'requiere_revision'
    assert db.rpc.call_args.args[1]['p_lote'] is None


def test_existente_no_reconfirma_ni_recalcula(snapshot):
    snapshot['ejecucion']['entrada_priorizacion'] = {'original': True}
    db = cliente(snapshot)
    assert preparar_lote_automatico(db, 'eid') == {'estado': 'existente'}
    assert db.rpc.call_count == 1


def test_error_transporte_no_es_faltante(snapshot):
    db = cliente(snapshot)
    db.rpc.side_effect = RuntimeError('Conexión incierta')
    with pytest.raises(RuntimeError): preparar_lote_automatico(db, 'eid')
    assert db.rpc.call_count == 1


def test_no_toma_reserva_si_requiere_revision(snapshot):
    db = cliente(snapshot, 'Falta revisión')
    assert procesar_priorizacion('eid', db, 'worker')['estado'] == 'requiere_revision'
    assert all(c.args[0] != 'ra_tomar_etapa_v2' for c in db.rpc.call_args_list)


def test_preparado_continua_hacia_calculo(snapshot):
    db = cliente(snapshot)
    with patch('agentes.lotes_confirmados.preparar_lote_automatico', return_value={'estado': 'preparado'}) as preparar:
        db.rpc.side_effect = lambda nombre, params: SimpleNamespace(execute=lambda: SimpleNamespace(data=None))
        assert procesar_priorizacion('eid', db, 'worker') == {'estado': 'no_tomada'}
    preparar.assert_called_once_with(db, 'eid', None)
    db.rpc.assert_called_once_with('ra_tomar_etapa_v2', {'p_ejecucion_id':'eid','p_trabajador_id':'worker','p_etapa':'priorizacion'})
