import json
from pathlib import Path
import pytest
from contratos.solicitudes import ResultadoValidarNecesidad, ResultadoPriorizarNecesidades
from agentes.priorizacion import evaluar_lote

RAIZ=Path(__file__).resolve().parents[2]


def ejemplo(nombre):
    return json.loads((RAIZ/'contratos/ejemplos'/nombre).read_text())


def test_pendiente_conservado_y_se_invoca_un_solo_lote():
    base=ejemplo('solicitud_priorizar.json')
    evaluacion=ejemplo('evaluacion_pendiente.json')
    entrada=ejemplo('solicitud_validar_formula_pendiente.json')
    contexto={k:base[k] for k in ('esquema_version','ejecucion_id','creado_en','origen')}
    class Tools:
        def validate_need(self,solicitud):
            assert solicitud.incidente_id==evaluacion_model.incidente_id
            return ResultadoValidarNecesidad.model_validate(ejemplo('resultado_validar_pendiente.json'))
        def score_needs(self,solicitud):
            assert len(solicitud.necesidades)==1
            n=solicitud.necesidades[0]
            assert n.demanda_litros is None and n.posicion is None and 'reserva_utilizable_litros' in n.pendientes
            return ResultadoPriorizarNecesidades(**contexto,datos_version=solicitud.datos_version,politica_version=solicitud.politica.politica_version,evaluaciones=solicitud.necesidades,alertas_revision=[])
    from contratos.modelos import EvaluacionNecesidades
    evaluacion_model=EvaluacionNecesidades.model_validate(evaluacion)
    resultado=evaluar_lote(contexto,[dict(solicitud_demanda=entrada,evaluacion=evaluacion)],base['politica'],Tools())
    assert resultado.evaluaciones[0].estado_prioridad=='pendiente'


def test_no_activa_politica_sin_aprobacion():
    with pytest.raises(ValueError,match='politica_no_activa'):
        evaluar_lote({},[],ejemplo('politica_prioridad.json'),None)
