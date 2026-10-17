from unittest.mock import Mock,patch
from orquestador.trabajador import una_vuelta


def test_mantenimiento_y_error_no_provocan_reintento_ciego():
    db=Mock()
    db.rpc.return_value.execute.return_value.data=[]
    db.table.return_value.select.return_value.eq.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data=[{'ejecucion_id':'a','etapa':'ingesta'}]
    with patch('orquestador.trabajador.avanzar',side_effect=RuntimeError('No imprimir secreto')) as avanzar:
        salida=una_vuelta(db,None)
    avanzar.assert_called_once()
    assert salida==[{'estado':'requiere_revision','ejecucion_id':'a'}]
    db.rpc.assert_any_call('ra_mantenimiento_v2',{})
