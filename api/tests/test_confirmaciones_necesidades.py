from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.servicios.confirmaciones_necesidades import entradas_confirmadas


@pytest.fixture
def snapshot():
    ambito = {'origen': 'sintetico', 'ensayo_id': None,
              'incidentes': [{'incidente_id': 'a', 'punto_atencion_id': 'p1', 'version': 1},
                             {'incidente_id': 'b', 'punto_atencion_id': 'p2', 'version': 1}],
              'puntos': [{'punto_atencion_id': 'p1'}, {'punto_atencion_id': 'p2'}],
              'reportes': [{'incidente_id': 'a', 'huella': 'original-a'},
                           {'incidente_id': 'b', 'huella': 'original-b'}]}
    return {'ambito': deepcopy(ambito), 'politica': {'politica_version': 'p'},
            'revision': {'ambito': ambito, 'lote': {'politica': {'politica_version': 'p'},
                        'entradas': [{'solicitud_demanda': {'incidente_id': iid}} for iid in ['a', 'b']]}}}


def base(snapshot, motivo=None):
    db = Mock()
    def rpc(nombre, datos):
        return SimpleNamespace(execute=lambda: SimpleNamespace(
            data=snapshot if nombre == 'ra_contexto_lote_confirmado_v2' else motivo))
    db.rpc.side_effect = rpc
    return db


@pytest.mark.parametrize('tipo', ['version', 'reporte', 'punto', 'nuevo_reporte'])
def test_cambiar_b_conserva_solo_a(snapshot, tipo):
    actual = snapshot['ambito']
    if tipo == 'version': actual['incidentes'][1]['version'] = 2
    elif tipo == 'reporte': actual['reportes'][1]['huella'] = 'modificada'
    elif tipo == 'punto': actual['puntos'][1]['activo'] = False
    else: actual['reportes'].append({'incidente_id': 'b', 'huella': 'nueva'})
    original = deepcopy(snapshot)
    db = base(snapshot)
    assert set(entradas_confirmadas(db, 'e', {'politica_version': 'p'})) == {'a'}
    assert snapshot == original
    parcial = db.rpc.call_args.args[1]['s']
    assert len(parcial['ambito']['incidentes']) == 1
    assert len(parcial['revision']['lote']['entradas']) == 1


@pytest.mark.parametrize('motivo', ['Ventana vencida', 'Coordinador inactivo', 'Conflicto pendiente'])
def test_no_reutiliza_si_la_guarda_transaccional_rechaza(snapshot, motivo):
    assert entradas_confirmadas(base(snapshot, motivo), 'e', {'politica_version': 'p'}) == {}


def test_cambio_de_politica_no_reutiliza(snapshot):
    assert entradas_confirmadas(base(snapshot), 'e', {'politica_version': 'otra'}) == {}


def test_cambio_de_origen_no_reutiliza(snapshot):
    snapshot['ambito']['origen'] = 'real'
    assert entradas_confirmadas(base(snapshot), 'e', {'politica_version': 'p'}) == {}
