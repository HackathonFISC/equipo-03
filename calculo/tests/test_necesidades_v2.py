import copy
import itertools
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from calculo.demanda import validate_need
from calculo.prioridad import CALCULO_PENDIENTE, score_needs
from contratos.errores import CodigoError, ExcepcionContrato
from contratos.solicitudes import SolicitudValidarNecesidad, SolicitudPriorizarNecesidades

ROOT = Path(__file__).resolve().parents[2]


def fixture(nombre):
    return json.loads((ROOT / 'contratos/ejemplos' / nombre).read_text(encoding='utf-8'))


def validar(datos):
    return validate_need(SolicitudValidarNecesidad.model_validate(datos))


def priorizar(datos):
    return score_needs(SolicitudPriorizarNecesidades.model_validate(datos))


def lote():
    rutas = fixture('solicitud_resolver_rutas.json')
    resultado = fixture('solicitud_priorizar.json')
    resultado['necesidades'] = rutas['necesidades']
    for n in resultado['necesidades']:
        n.update(estado_prioridad='pendiente', puntaje=None, componentes=None, posicion=None,
                 pendientes=[CALCULO_PENDIENTE])
    return resultado


@pytest.mark.parametrize('archivo,litros', [
    ('solicitud_validar_directa.json', 2500), ('solicitud_validar_formula.json', 1500)])
def test_demanda_confirmada_y_sin_mutacion(archivo, litros):
    entrada = SolicitudValidarNecesidad.model_validate(fixture(archivo))
    original = entrada.model_dump(mode='json')
    resultado = validate_need(entrada)
    assert resultado.estado == 'validada' and resultado.demanda_litros == litros
    assert not resultado.faltantes and not resultado.motivos
    assert resultado.fuente == entrada.demanda.fuente
    assert resultado.supuestos == entrada.supuestos
    assert entrada.model_dump(mode='json') == original
    assert validate_need(entrada) == resultado


@pytest.mark.parametrize('campo', ['personas_atendidas','dotacion_litros_persona_dia',
                                  'dias_cobertura','reserva_utilizable_litros'])
def test_factores_ausentes_no_son_cero(campo):
    datos = fixture('solicitud_validar_formula.json')
    datos['demanda'][campo] = None
    r = validar(datos)
    assert r.estado == 'pendiente' and r.demanda_litros is None
    assert f'demanda.{campo}' in r.faltantes


def test_reserva_y_poblacion_cero_explicitos():
    datos = fixture('solicitud_validar_formula.json')
    datos['demanda']['reserva_utilizable_litros'] = 0.0
    assert validar(datos).demanda_litros == 2000
    datos['demanda']['personas_atendidas'] = 0
    assert validar(datos).demanda_litros == 0
    assert validar(datos).estado == 'validada'


def test_reserva_superior_consumo_no_da_demanda_negativa():
    datos = fixture('solicitud_validar_formula.json')
    datos['demanda']['reserva_utilizable_litros'] = 10000.0
    assert validar(datos).demanda_litros == 0


@pytest.mark.parametrize('archivo', ['solicitud_validar_directa.json','solicitud_validar_formula.json'])
def test_confirmacion_y_recepcion_obligatorias(archivo):
    datos = fixture(archivo)
    datos['demanda']['confirmacion'] = None
    datos['capacidad_recepcion_litros'] = None
    r = validar(datos)
    assert r.estado == 'pendiente' and r.demanda_litros is not None
    assert set(r.faltantes) == {'demanda.confirmacion', 'capacidad_recepcion_litros'}


def test_no_recorta_litros_a_recepcion():
    datos = fixture('solicitud_validar_directa.json')
    datos['capacidad_recepcion_litros'] = 1000.0
    r = validar(datos)
    assert r.estado == 'pendiente' and r.demanda_litros == 2500
    assert 'recepción' in r.motivos[0]


def test_litros_directos_desconocidos():
    datos = fixture('solicitud_validar_directa.json')
    datos['demanda']['litros_declarados'] = None
    assert validar(datos).demanda_litros is None
    assert validar(datos).estado == 'pendiente'


@pytest.mark.parametrize('valor', [-1, True, float('inf'), float('nan')])
def test_cantidades_invalidas_no_llegan_al_calculo(valor):
    datos = fixture('solicitud_validar_directa.json')
    datos['demanda']['litros_declarados'] = valor
    with pytest.raises(ValidationError):
        validar(datos)


def test_formula_extrema_no_emite_infinito():
    datos = fixture('solicitud_validar_formula.json')
    datos['demanda'].update(dotacion_litros_persona_dia=1e308, dias_cobertura=1e308)
    r = validar(datos)
    assert r.estado == 'pendiente' and r.demanda_litros is None
    assert 'numérica' in r.motivos[0]


def test_formula_decimal_sin_error_binario_de_producto():
    datos = fixture('solicitud_validar_formula.json')
    datos['demanda'].update(personas_atendidas=3, dotacion_litros_persona_dia=0.1,
                           dias_cobertura=1.0, reserva_utilizable_litros=0.0)
    assert validar(datos).demanda_litros == 0.3


def test_puntaje_desglosado_y_lote_completo():
    datos = lote()
    entrada = SolicitudPriorizarNecesidades.model_validate(datos)
    original = entrada.model_dump(mode='json')
    r = score_needs(entrada)
    assert len(r.evaluaciones) == 6
    n = next(n for n in r.evaluaciones if n.punto_atencion_id == entrada.necesidades[0].punto_atencion_id)
    assert n.puntaje == pytest.approx(56.628571428571426)
    assert n.componentes.aporte_duracion == pytest.approx(21.428571428571427)
    assert n.componentes.aporte_vulnerabilidad == 30
    assert n.componentes.aporte_poblacion == pytest.approx(5.2)
    assert n.posicion == 1
    assert entrada.model_dump(mode='json') == original
    assert score_needs(entrada) == r


@pytest.mark.parametrize('campo', ['horas_sin_agua','personas_atendidas','vulnerabilidad',
                                  'confirmacion_vulnerabilidad','clase_prioridad','confirmacion_clase'])
def test_factores_prioridad_ausentes_conservan_pendiente(campo):
    datos = lote()
    n = datos['necesidades'][0]
    n[campo] = None
    if campo == 'confirmacion_clase':
        n['clase_prioridad'] = None
    r = priorizar(datos)
    pendiente = next(x for x in r.evaluaciones if str(x.incidente_id) == n['incidente_id'])
    assert pendiente.estado_prioridad == 'pendiente'
    assert pendiente.puntaje is None and pendiente.posicion is None and pendiente.pendientes
    assert len(r.evaluaciones) == 6
    assert sorted(x.posicion for x in r.evaluaciones if x.posicion) == list(range(1,6))


def test_critico_pendiente_requiere_revision():
    datos = lote()
    datos['necesidades'][0] = fixture('evaluacion_pendiente.json')
    r = priorizar(datos)
    p = next(n for n in r.evaluaciones if n.estado_demanda == 'pendiente')
    assert p.requiere_revision_urgente and p.puntaje is None and r.alertas_revision


def test_pendiente_desconocido_no_se_borra():
    datos = lote()
    datos['necesidades'][0]['pendientes'] = ['Revisar evidencia contradictoria.']
    r = priorizar(datos)
    p = next(n for n in r.evaluaciones if n.estado_prioridad == 'pendiente')
    assert 'Revisar evidencia contradictoria.' in p.pendientes


def test_sector_sin_informacion_no_desaparece():
    datos = lote()
    n = datos['necesidades'][0]
    n.update(estado_demanda='pendiente', demanda_litros=None, confirmacion_demanda=None,
             clase_prioridad=None, confirmacion_clase=None, horas_sin_agua=None,
             personas_atendidas=None, vulnerabilidad=None, confirmacion_vulnerabilidad=None,
             requiere_revision_urgente=True, pendientes=['Sector sin información.'])
    r = priorizar(datos)
    assert len(r.evaluaciones) == 6
    p = next(x for x in r.evaluaciones if x.demanda_litros is None)
    assert p.puntaje is None and p.requiere_revision_urgente


def test_clase_critica_precede_a_general_con_puntaje_mayor():
    datos = lote()
    datos['necesidades'][0].update(horas_sin_agua=0.0, personas_atendidas=0,
                                  vulnerabilidad='sin_condicion_identificada')
    datos['necesidades'][1].update(horas_sin_agua=168.0, personas_atendidas=500, vulnerabilidad='alta')
    r = priorizar(datos)
    assert r.evaluaciones[0].clase_prioridad == 'critico' and r.evaluaciones[0].puntaje == 0
    assert r.evaluaciones[1].puntaje == 100


def test_extremo_no_renormaliza_puntajes_previos():
    datos = lote()
    antes = {n.incidente_id:n.puntaje for n in priorizar(datos).evaluaciones}
    datos['necesidades'][-1].update(horas_sin_agua=1e300, personas_atendidas=10**30, vulnerabilidad='alta')
    r = priorizar(datos)
    despues = {n.incidente_id:n.puntaje for n in r.evaluaciones}
    assert all(despues[k] == v for k,v in antes.items() if str(k) != datos['necesidades'][-1]['incidente_id'])
    assert r.alertas_revision
    extremo = next(n for n in r.evaluaciones if n.personas_atendidas == 10**30)
    assert extremo.puntaje == 100 and extremo.horas_sin_agua == 1e300


def test_mas_horas_o_vulnerabilidad_no_reducen_puntaje():
    datos = lote()
    datos['necesidades'] = [datos['necesidades'][1]]
    previo = priorizar(datos).evaluaciones[0].puntaje
    datos['necesidades'][0]['horas_sin_agua'] += 12
    medio = priorizar(datos).evaluaciones[0].puntaje
    datos['necesidades'][0]['vulnerabilidad'] = 'alta'
    assert previo <= medio <= priorizar(datos).evaluaciones[0].puntaje


def test_repeticion_de_quejas_no_es_entrada_del_puntaje():
    datos = lote()
    antes = {n.incidente_id:(n.puntaje,n.posicion,n.primera_deteccion_en) for n in priorizar(datos).evaluaciones}
    datos['necesidades'][0]['supuestos'].append('Se registraron 1000 mensajes repetidos sin nuevos hechos.')
    datos['necesidades'][0]['creado_en'] = '2026-10-16T19:00:00-05:00'
    despues = {n.incidente_id:(n.puntaje,n.posicion,n.primera_deteccion_en) for n in priorizar(datos).evaluaciones}
    assert antes == despues
    datos['necesidades'][0]['numero_quejas'] = 1000
    with pytest.raises(ValidationError):
        priorizar(datos)


def test_duplicado_no_se_suma_como_otra_necesidad():
    datos = lote()
    datos['necesidades'].append(copy.deepcopy(datos['necesidades'][0]))
    with pytest.raises(ValidationError):
        priorizar(datos)


@pytest.mark.parametrize('historial_completo', [True,False])
def test_desempate_invariante_al_orden_y_ausencia_historial(historial_completo):
    datos = lote()
    datos['necesidades'] = datos['necesidades'][1:4]
    for i,n in enumerate(datos['necesidades']):
        n.update(horas_sin_agua=48.0, personas_atendidas=100, vulnerabilidad='alta',
                 primera_deteccion_en=f'2026-10-16T{10+i}:00:00-05:00',
                 ultima_atencion_confirmada_en=f'2026-10-{14-i}T08:00:00-05:00')
    if not historial_completo:
        datos['necesidades'][0]['ultima_atencion_confirmada_en'] = None
    esperados = datos['necesidades'][::-1] if historial_completo else datos['necesidades'][:]
    for permutacion in itertools.permutations(datos['necesidades']):
        datos['necesidades'] = list(permutacion)
        assert [str(n.incidente_id) for n in priorizar(datos).evaluaciones] == [n['incidente_id'] for n in esperados]


def test_desempate_compara_instantes_con_zonas_distintas():
    datos = lote()
    datos['necesidades'] = datos['necesidades'][1:3]
    for n in datos['necesidades']:
        n.update(horas_sin_agua=48.0, personas_atendidas=100, vulnerabilidad='alta')
    datos['necesidades'][0]['ultima_atencion_confirmada_en'] = '2026-10-15T10:00:00+00:00'
    datos['necesidades'][1]['ultima_atencion_confirmada_en'] = '2026-10-15T06:00:00-05:00'
    assert str(priorizar(datos).evaluaciones[0].incidente_id) == datos['necesidades'][0]['incidente_id']


def test_politica_propuesta_produce_error_tipado():
    datos = lote()
    datos['politica'] = fixture('politica_prioridad.json')
    with pytest.raises(ExcepcionContrato) as error:
        priorizar(datos)
    assert error.value.detalle.codigo == CodigoError.POLITICA_NO_ACTIVA


def test_version_mezclada_rechazada():
    datos = lote()
    datos['necesidades'][0]['datos_version'] = 'otra'
    with pytest.raises(ValidationError):
        priorizar(datos)


def test_origen_no_oculta_politica_sintetica():
    datos = lote()
    datos['origen'] = 'real'
    for n in datos['necesidades']:
        n['origen'] = 'real'
    r = priorizar(datos)
    assert r.origen == 'sintetico' and all(n.origen == 'sintetico' for n in r.evaluaciones)


def test_pesos_y_escalas_provienen_de_configuracion():
    datos = lote()
    datos['politica'].update(peso_duracion=1.0, peso_poblacion=0.0, peso_vulnerabilidad=0.0, tope_horas=100.0)
    r = priorizar(datos)
    n = next(n for n in r.evaluaciones if n.clase_prioridad == 'critico')
    assert n.puntaje == 72.0
    assert n.componentes.aporte_poblacion == 0 and n.componentes.aporte_vulnerabilidad == 0


def test_grupos_de_empate_no_encadenan_tolerancias():
    datos = lote()
    datos['politica'].update(peso_duracion=1.0, peso_poblacion=0.0, peso_vulnerabilidad=0.0, tope_horas=100.0)
    datos['necesidades'] = datos['necesidades'][1:4]
    for i,n in enumerate(datos['necesidades']):
        n.update(horas_sin_agua=10.0+i*0.75e-9, primera_deteccion_en=f'2026-10-16T{10+i}:00:00-05:00')
    # C y B empatan respecto de C; A no. No formar un único grupo por la cadena C~B~A.
    esperados = [datos['necesidades'][i]['incidente_id'] for i in (1,2,0)]
    for permutacion in itertools.permutations(datos['necesidades']):
        datos['necesidades'] = list(permutacion)
        assert [str(n.incidente_id) for n in priorizar(datos).evaluaciones] == esperados


def test_recalcula_en_lugar_de_confiar_en_puntaje_previo():
    datos = lote()
    previos = fixture('solicitud_resolver_rutas.json')['necesidades']
    datos['necesidades'] = previos
    datos['necesidades'][1]['horas_sin_agua'] = 168.0
    r = priorizar(datos)
    nuevo = next(n for n in r.evaluaciones if str(n.incidente_id) == previos[1]['incidente_id'])
    assert nuevo.puntaje == pytest.approx(70.6)


def test_demanda_rechazada_no_entra_al_ranking():
    datos = lote()
    datos['necesidades'][0].update(estado_demanda='rechazada', pendientes=['Demanda rechazada tras revisión.'])
    r = priorizar(datos)
    n = next(n for n in r.evaluaciones if n.estado_demanda == 'rechazada')
    assert n.puntaje is None and n.posicion is None
