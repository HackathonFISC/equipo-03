import copy
import json
from pathlib import Path

import pytest

from calculo.demo_escenario_v3 import construir, recepcion_libre, simular

ROOT = Path(__file__).resolve().parents[2]


def entradas():
    def leer(ruta):
        return json.loads((ROOT / ruta).read_text(encoding='utf-8'))
    return (leer('datos/escenario/oeste-1.0-ensayo-3/parametros.json'),
            leer('datos/escenario/oeste-1.0-ensayo-2/solicitud_rutas.json'),
            leer('datos/escenario/politica_apoyo_panama_v1.json'))


def test_cantidades_recepcion_y_publicacion_del_fixture():
    r = construir()
    assert [n['demanda_litros'] for n in r['resumen']] == [3000, 3000, 2000, 2500, 3000, 1500]
    assert [n['recepcion_litros'] for n in r['resumen']] == [4550, 8900, 4350, 4450, 9300, 4250]
    assert sum(n['personas'] for n in r['resumen']) == 860
    assert sum(n['demanda_litros'] for n in r['resumen']) == 15000
    assert all(n['estado_demanda'] == 'validada' for n in r['resumen'])
    assert not r['autorizacion_operativa'] and r['bloqueos_publicacion']
    assert [s['descarga_minutos'] for s in r['solicitud_rutas']['servicios']] == [15, 15, 12, 14, 15, 10]


def test_criticidad_puntaje_y_origen_sin_inferir_del_nombre():
    r = construir()
    ranking = r['resultado_prioridad']['evaluaciones']
    assert [n['punto_atencion_id'] for n in ranking] == [
        r['resumen'][i]['punto_atencion_id'] for i in (4, 2, 3, 0, 5, 1)]
    assert [n['puntaje'] for n in ranking] == pytest.approx([
        60.68571428571428, 53.371428571428574, 48.457142857142856,
        43.542857142857144, 29.714285714285715, 18.628571428571426])
    assert [n['clase_prioridad'] for n in ranking] == ['critico'] * 2 + ['general'] * 4
    assert all(n['origen'] == 'sintetico' for n in ranking)
    assert all(p['origen'] == 'real' and p['ubicacion']['representa_punto_atencion'] is None
               for p in r['solicitud_rutas']['puntos'])


def test_resultado_reproducible_sin_mutacion_y_politica_fuente_sin_activar():
    args = entradas()
    antes = copy.deepcopy(args)
    a = simular(*args)
    assert args == antes and a == simular(*args)
    assert args[2]['estado'] == 'propuesta_demo' and args[2]['confirmacion_activacion'] is None
    assert a['solicitud_rutas']['politica']['estado'] == 'activa'
    assert 'FIXTURE SINTÉTICO' in a['solicitud_rutas']['politica']['confirmacion_activacion']['motivo']
    archivado = json.loads((ROOT / 'datos/escenario/oeste-1.0-ensayo-3/escenario_fixture.json').read_text(encoding='utf-8'))
    assert json.loads(json.dumps(a)) == archivado


@pytest.mark.parametrize('campo', ['reserva_utilizable_litros', 'tanque_nominal_litros'])
def test_desconocido_conserva_pendiente_y_no_se_convierte_a_cero(campo):
    parametros, base, politica = entradas()
    parametros['perfiles'][2][campo] = None
    r = simular(parametros, base, politica)
    p = r['resumen'][2]
    assert p['estado_demanda'] == 'pendiente'
    if campo == 'reserva_utilizable_litros':
        assert p['demanda_litros'] is None
    else:
        assert p['recepcion_litros'] is None and p['demanda_litros'] == 2000
    n = next(n for n in r['resultado_prioridad']['evaluaciones'] if n['punto_atencion_id'] == p['punto_atencion_id'])
    assert n['puntaje'] is None and n['requiere_revision_urgente']


def test_recepcion_insuficiente_no_recorta_demanda_para_hacerla_caber():
    parametros, base, politica = entradas()
    parametros['perfiles'][2]['tanque_nominal_litros'] = 2500.0
    r = simular(parametros, base, politica)
    assert r['resumen'][2]['recepcion_litros'] == 1975
    assert r['resumen'][2]['demanda_litros'] == 2000
    assert r['resumen'][2]['estado_demanda'] == 'pendiente'


def test_reserva_no_utilizable_no_resta_agua_del_tanque_para_recepcion():
    parametros, base, politica = entradas()
    parametros['perfiles'][0]['reserva_utilizable_litros'] = 100.0
    r = simular(parametros, base, politica)
    assert r['resumen'][0]['demanda_litros'] == 3100
    assert r['resumen'][0]['recepcion_litros'] == 4550


@pytest.mark.parametrize('campo,valor', [
    ('agua_almacenada_litros', 6000.0), ('reserva_utilizable_litros', 1000.0),
    ('personas_atendidas', 1), ('tanque_nominal_litros', True)])
def test_parametros_incoherentes_no_se_aceptan(campo, valor):
    parametros, base, politica = entradas()
    parametros['perfiles'][0][campo] = valor
    with pytest.raises(ValueError):
        simular(parametros, base, politica)


def test_no_acepta_modo_o_confirmacion_de_apariencia_operativa():
    parametros, base, politica = entradas()
    parametros['modo'] = 'operativo'
    with pytest.raises(ValueError):
        simular(parametros, base, politica)
    parametros['modo'] = 'fixture_sintetico'
    parametros['confirmacion_fixture']['motivo'] = 'Aprobación real'
    with pytest.raises(ValueError):
        simular(parametros, base, politica)
