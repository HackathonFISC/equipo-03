import json
from pathlib import Path

import pytest

from calculo.prioridad import score_needs
from contratos.errores import CodigoError, ExcepcionContrato
from contratos.modelos import PoliticaPrioridad
from contratos.solicitudes import SolicitudPriorizarNecesidades
from scripts.verificar_escenario_v3 import verificar

ROOT = Path(__file__).resolve().parents[2]


def cargar(ruta):
    return json.loads((ROOT / ruta).read_text(encoding='utf-8'))


def entrada_de_prueba(*, activa=False):
    # Solo en memoria: confirmación ficticia ya identificada por el fixture.
    base = cargar('contratos/ejemplos/solicitud_resolver_rutas.json')
    politica = cargar('datos/escenario/politica_apoyo_panama_v1.json')
    if activa:
        politica.update(estado='activa', confirmacion_activacion=base['politica']['confirmacion_activacion'])
    necesidades = base['necesidades'][:2]
    for n in necesidades:
        n['politica_version'] = politica['politica_version']
    return {**{k: base[k] for k in ('esquema_version', 'ejecucion_id', 'creado_en', 'origen', 'datos_version')},
            'politica': politica, 'necesidades': necesidades}


@pytest.mark.parametrize('nivel,esperado', [('sin_condicion_identificada', 30), ('moderada', 50), ('alta', 70)])
def test_pesos_con_factores_controlados(nivel, esperado):
    datos = entrada_de_prueba(activa=True)
    datos['necesidades'] = datos['necesidades'][1:]
    datos['necesidades'][0].update(horas_sin_agua=84.0, personas_atendidas=250, vulnerabilidad=nivel)
    r = score_needs(SolicitudPriorizarNecesidades.model_validate(datos))
    n = r.evaluaciones[0]
    assert n.puntaje == pytest.approx(esperado)
    assert n.componentes.aporte_duracion == 20 and n.componentes.aporte_poblacion == 10


def test_critico_no_es_desplazado_por_puntaje_general():
    datos = entrada_de_prueba(activa=True)
    datos['necesidades'][0].update(horas_sin_agua=0.0, personas_atendidas=0,
                                   vulnerabilidad='sin_condicion_identificada')
    datos['necesidades'][1].update(horas_sin_agua=168.0, personas_atendidas=500, vulnerabilidad='alta')
    r = score_needs(SolicitudPriorizarNecesidades.model_validate(datos))
    assert [(n.clase_prioridad, n.puntaje) for n in r.evaluaciones] == [('critico', 0), ('general', 100)]


def test_archivo_sin_activacion_no_habilita_calculo():
    datos = entrada_de_prueba()
    politica = PoliticaPrioridad.model_validate(datos['politica'])
    assert politica.estado == 'propuesta_demo' and politica.confirmacion_activacion is None
    with pytest.raises(ExcepcionContrato) as error:
        score_needs(SolicitudPriorizarNecesidades.model_validate(datos))
    assert error.value.detalle.codigo == CodigoError.POLITICA_NO_ACTIVA


def test_nueva_version_coherente_sin_confirmar_demandas():
    r = verificar(ROOT / 'datos/escenario/oeste-1.0-ensayo-2')
    assert r['datos_version'] == 'oeste-1.0-ensayo-2'
    assert r['necesidades_pendientes'] == 6 and r['demanda_ensayo_litros'] == 18000
