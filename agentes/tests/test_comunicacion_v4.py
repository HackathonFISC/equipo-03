from unittest.mock import Mock, patch
from uuid import uuid4
import pytest
from pydantic import ValidationError
from agentes.comunicacion import procesar_comunicacion
from agentes.estado_sector import consultar_estado_sector
from contratos.consultas import SolicitudEstadoSector
from orquestador.flujo import avanzar
from orquestador.trabajador import una_vuelta


def test_orquestador_entrega_a_comunicacion_sin_llm():
    eid=uuid4(); db=Mock()
    db.rpc.return_value.execute.return_value.data={'estado':'completada','avisos_creados':2}
    extractor=Mock()
    r=avanzar({'ejecucion_id':str(eid),'etapa':'comunicacion'},db,extractor)
    assert r['avisos_creados']==2
    nombre,params=db.rpc.call_args.args
    assert nombre=='ra_comunicar_plan_v4' and params['p_ejecucion_id']==str(eid)
    assert params['p_trabajador_id'].startswith('comunicacion:')
    extractor.assert_not_called()


def test_no_acepta_identidad_invalida_ni_escribe_directo():
    db=Mock()
    db.rpc.return_value.execute.return_value.data=[]
    with pytest.raises(ValueError): procesar_comunicacion('no-uuid',db,'t')
    assert not db.mock_calls


def test_trabajador_consulta_tambien_comunicacion():
    db=Mock()
    db.rpc.return_value.execute.return_value.data=[];db.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data=[]
    una_vuelta(db,None)
    args=db.table.return_value.select.return_value.eq.return_value.in_.call_args.args
    assert 'comunicacion' in args[1]


def test_lectura_estado_valida_contrato_y_no_inventa_sector():
    db=Mock()
    db.rpc.return_value.execute.return_value.data=[]; db.rpc.return_value.execute.return_value.data={}
    with pytest.raises(ValidationError): consultar_estado_sector(db,SolicitudEstadoSector(sector_id=uuid4()))
    db.table.assert_not_called()


def test_errores_de_bd_no_se_disfrazan_de_sin_plan():
    db=Mock()
    db.rpc.return_value.execute.return_value.data=[];db.rpc.return_value.execute.side_effect=RuntimeError('DB')
    with pytest.raises(RuntimeError): consultar_estado_sector(db,SolicitudEstadoSector(sector_id=uuid4()))
