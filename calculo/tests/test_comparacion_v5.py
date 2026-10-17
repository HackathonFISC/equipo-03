import copy
from uuid import uuid4

import pytest
from ortools.sat.python import cp_model
from pydantic import ValidationError

from calculo.orden_llegada import solve_routes_orden_llegada
from calculo.replanificacion import simular_retiro
from calculo.solver import solve_routes
from contratos.errores import ExcepcionContrato
from contratos.solicitudes import SolicitudResolverRutas, SolicitudVerificarPlan
from evals.comparar_v5 import _priorizar, comparar, ejecutar, preparar_casos
from evals.metricas import medir_plan


@pytest.fixture(scope='module')
def casos():
    return dict(preparar_casos())


def seleccion(p):
    return {pa.punto_atencion_id for r in p.rutas for pa in r.paradas}


def test_completo_mismos_recursos_y_cobertura(casos):
    r = comparar(casos['completo'], repeticiones=2)
    for x in r['resultados'].values():
        assert x['metricas']['cobertura_puntos'] == dict(atendidos=6, total=6, fraccion=1)
        assert x['metricas']['litros_asignados'] == 15000
        assert x['metricas']['deficit_total_litros'] == 0
        assert x['verificacion']['valido'] and x['reproducible']
    assert r['diferencias_prioridad_menos_llegada']['criticos_atendidos'] == 0


def test_retiro_muestra_costo_y_beneficio_sin_ocultar_deficit(casos):
    s = casos['retiro_cisterna']
    antes = s.model_dump(mode='json')
    r = comparar(s, repeticiones=2)
    a, b = r['resultados']['prioridad'], r['resultados']['orden_llegada']
    assert a['metricas']['cobertura_critica']['atendidos'] == 2
    assert b['metricas']['cobertura_critica']['atendidos'] == 0
    assert a['metricas']['litros_asignados'] == 9000
    assert b['metricas']['litros_asignados'] == 10000
    assert a['metricas']['deficit_conocido_litros'] == 6000
    assert b['metricas']['deficit_conocido_litros'] == 5000
    assert a['verificacion']['valido'] and not b['verificacion']['valido']
    assert all(v['codigo'] == 'cobertura_critica' for v in b['verificacion']['violaciones'])
    assert s.model_dump(mode='json') == antes
    for x in (a, b):
        assert 'HUELLA_ENTRADAS_SHA256='+r['entrada_sha256'] in x['propuesta']['supuestos']
        assert x['propuesta']['aprobacion'] is None and x['propuesta']['bloqueos_publicacion']


def test_fifo_elige_incidente_antiguo_sin_modificar_puntaje(casos):
    s = casos['retiro_cisterna']
    antes = s.model_dump(mode='json')
    p = solve_routes_orden_llegada(s)
    criticos = {n.punto_atencion_id for n in s.necesidades if n.clase_prioridad == 'critico'}
    assert not seleccion(p) & criticos
    d = copy.deepcopy(antes)
    # Solo cambia antigüedad: crítico primero, todos los demás conservan factores.
    n = next(n for n in d['necesidades'] if n['clase_prioridad'] == 'critico')
    n['primera_deteccion_en'] = '2026-10-15T06:00:00-05:00'
    otra = _priorizar(d)
    assert n['punto_atencion_id'] in {str(x) for x in seleccion(solve_routes_orden_llegada(otra))}
    assert s.model_dump(mode='json') == antes


def test_fifo_invariante_al_orden_de_listas_y_nodos(casos):
    s = casos['retiro_cisterna']
    p = solve_routes_orden_llegada(s)
    d = s.model_dump(mode='json')
    for campo in ('vehiculos', 'necesidades', 'puntos', 'servicios'):
        d[campo].reverse()
    d['matriz']['nodos_ids'].reverse()
    d['matriz']['minutos'] = [list(reversed(f)) for f in reversed(d['matriz']['minutos'])]
    otra = solve_routes_orden_llegada(SolicitudResolverRutas.model_validate(d))
    assert p.rutas == otra.rutas and p.no_atendidos == otra.no_atendidos


def test_fifo_desempata_instante_igual_por_uuid(casos):
    s = casos['retiro_cisterna']
    d = s.model_dump(mode='json')
    for n in d['necesidades']:
        n['primera_deteccion_en'] = '2026-10-16T06:00:00-05:00'
    a = _priorizar(d)
    p = solve_routes_orden_llegada(a)
    d['necesidades'].reverse()
    assert p == solve_routes_orden_llegada(_priorizar(d))


def test_deficit_desconocido_no_se_convierte_en_cero(casos):
    r = comparar(casos['datos_insuficientes'], repeticiones=1)
    for x in r['resultados'].values():
        m = x['metricas']
        assert m['puntos_demanda_desconocida'] == 1
        assert m['deficit_conocido_litros'] == 0 and m['deficit_total_litros'] is None
        assert not m['deficit_total_completo']
        assert m['criticos_sin_datos'] == 1 and m['cobertura_critica']['total'] == 2
        assert m['cobertura_critica_calculable']['total'] == 1
        assert not x['verificacion']['valido']


def test_critico_excesivo_sigue_en_denominador_y_deficit(casos):
    r = comparar(casos['critico_excesivo'], repeticiones=1)
    for x in r['resultados'].values():
        assert x['metricas']['cobertura_critica'] == dict(atendidos=1, total=2, fraccion=.5)
        assert x['metricas']['deficit_critico_conocido_litros'] == 12000
        assert not x['verificacion']['valido']


def test_sin_flota_es_diagnostico_sin_plan_valido(casos):
    r = comparar(casos['sin_flota'], repeticiones=1)
    for x in r['resultados'].values():
        assert x['propuesta']['estado_solver'] == 'inviabilidad_demostrada'
        assert not x['plan_factible'] and not x['verificacion']['valido']
        assert x['metricas']['deficit_total_litros'] == 15000


def test_metricas_viaje_incluye_regreso_y_separa_servicio(casos):
    s = casos['completo']
    p = solve_routes(s)
    m = medir_plan(s, p)
    indices = {x: i for i, x in enumerate(s.matriz.nodos_ids)}
    esperado = 0
    for r in p.rutas:
        nodos = [s.deposito.deposito_id, *[pa.punto_atencion_id for pa in r.paradas], s.deposito.deposito_id]
        esperado += sum(s.matriz.minutos[indices[a]][indices[b]] for a, b in zip(nodos,nodos[1:]))
    assert m['viaje_total_minutos'] == esperado
    assert m['tramos'] == 6 + m['salidas_deposito']
    assert m['duracion_rutas_minutos'] == pytest.approx(m['viaje_total_minutos']+m['servicio_total_minutos']+m['espera_en_puntos_minutos'])


def test_sin_criticos_denominador_cero_no_es_cien_por_ciento(casos):
    d = casos['completo'].model_dump(mode='json')
    for n in d['necesidades']:
        n['clase_prioridad'] = 'general'
    s = _priorizar(d)
    m = medir_plan(s, solve_routes(s))
    assert m['cobertura_critica'] == dict(atendidos=0, total=0, fraccion=None)


def test_cero_validado_no_exige_visita_ni_deficit(casos):
    d = casos['completo'].model_dump(mode='json')
    n = next(n for n in d['necesidades'] if n['clase_prioridad'] == 'critico')
    n['demanda_litros'] = 0
    s = _priorizar(d)
    m = medir_plan(s, solve_routes(s))
    assert m['puntos_demanda_cero_validada'] == 1
    assert m['cobertura_puntos']['atendidos'] == 5 and m['cobertura_puntos']['total'] == 6
    assert m['cobertura_critica']['total'] == 1 and m['deficit_total_litros'] == 0


def test_metricas_rechazan_snapshot_de_otra_version(casos):
    with pytest.raises(ValueError):
        medir_plan(casos['retiro_cisterna'], solve_routes(casos['completo']))


def test_retiro_nueva_version_ejecucion_y_original_intacto(casos):
    s = casos['completo']
    antes = s.model_dump(mode='json')
    nueva = simular_retiro(s, s.vehiculos[0].vehiculo_id, datos_version='retiro-unitario-1')
    assert nueva.plan_id == s.plan_id and nueva.version == s.version+1
    assert nueva.datos_version != s.datos_version and nueva.ejecucion_id != s.ejecucion_id
    assert sum(v.disponible for v in nueva.vehiculos) == 1
    assert s.model_dump(mode='json') == antes
    with pytest.raises(ValidationError):
        SolicitudVerificarPlan(ejecucion_id=nueva.ejecucion_id, creado_en=nueva.creado_en, origen=nueva.origen,
            solicitud_original=nueva, propuesta=solve_routes(s))
    nueva_propuesta = solve_routes(nueva)
    assert nueva_propuesta.aprobacion is None and nueva_propuesta.estado == 'pendiente_revision'


@pytest.mark.parametrize('version', ['', 'oeste-1.0-v5-comparacion-1', ' oeste-1.0-v5-comparacion-1 '])
def test_retiro_rechaza_version_ausente_o_reutilizada(casos, version):
    s = casos['completo']
    with pytest.raises(ValueError):
        simular_retiro(s, s.vehiculos[0].vehiculo_id, datos_version=version)


def test_retiro_rechaza_vehiculo_inexistente_o_ya_retirado(casos):
    s = casos['retiro_cisterna']
    for ident in (uuid4(), next(v.vehiculo_id for v in s.vehiculos if not v.disponible)):
        with pytest.raises(ValueError):
            simular_retiro(s, ident, datos_version='nuevo-retiro-2')


def test_fifo_conserva_rechazo_de_politica_inactiva(casos):
    d = casos['completo'].model_dump(mode='json')
    d['politica'].update(estado='propuesta_demo',confirmacion_activacion=None)
    with pytest.raises(ExcepcionContrato):
        solve_routes_orden_llegada(SolicitudResolverRutas.model_validate(d))


@pytest.mark.parametrize('bloqueo', ['ventana', 'arcos'])
def test_ambos_metodos_respetan_la_misma_restriccion_adversa(casos, bloqueo):
    d = casos['completo'].model_dump(mode='json')
    n = next(n for n in d['necesidades'] if n['clase_prioridad'] == 'general')
    pid = n['punto_atencion_id']
    if bloqueo == 'ventana':
        n['ventana_atencion']['fin'] = '2026-10-17T08:01:00-05:00'
    else:
        indice = d['matriz']['nodos_ids'].index(pid)
        for i in range(len(d['matriz']['nodos_ids'])):
            if i != indice:
                d['matriz']['minutos'][i][indice] = None
                d['matriz']['minutos'][indice][i] = None
    r = comparar(SolicitudResolverRutas.model_validate(d), repeticiones=1)
    for x in r['resultados'].values():
        assert pid not in {p['punto_atencion_id'] for ruta in x['propuesta']['rutas'] for p in ruta['paradas']}
        assert x['verificacion']['valido']


def test_metricas_no_cuentan_entrega_parcial_como_cobertura(casos):
    p = solve_routes(casos['completo']).model_copy(deep=True)
    p.rutas[0].paradas[0].litros_asignados += .001
    with pytest.raises(ValueError):
        medir_plan(casos['completo'], p)


def test_timeout_de_fifo_no_se_convierte_en_inviabilidad(casos, monkeypatch):
    import calculo.solver_v3 as motor
    monkeypatch.setattr(motor, '_seleccionar', lambda *a, **k: ([], cp_model.UNKNOWN))
    p = solve_routes_orden_llegada(casos['completo'])
    assert p.estado_solver == 'timeout_sin_solucion' and not p.rutas


@pytest.mark.parametrize('repeticiones', [0, True, 21])
def test_presupuesto_de_repeticiones_valido(casos, repeticiones):
    with pytest.raises(ValueError):
        comparar(casos['completo'], repeticiones=repeticiones)


def test_evidencia_no_declara_cierre_ni_latencias_integradas():
    e = ejecutar(repeticiones=1)
    assert not e['cierre_v4'] and not e['cierre_v5']
    assert len(e['casos']) == 5
    assert e['latencias_integradas']['aprobacion_a_envio_ms'] is None
    assert all(x['estado'] == 'pendiente' for x in e['pendientes_integracion'])
    assert {'validate_need', 'score_needs', 'solve_routes', 'verify_plan'} <= set(e['traza']['herramientas'])
    assert len({(c['entrada']['plan_id'], c['entrada']['version']) for c in e['casos']}) == 5
    fuente = e['construccion_necesidades']['critico_excesivo']
    validada = next(n for n in fuente['validaciones_demanda'] if n['demanda_litros'] == 12000)
    solicitud = next(n for n in fuente['solicitudes_validacion'] if n['punto_atencion_id'] == validada['punto_atencion_id'])
    assert validada['estado'] == 'validada' and solicitud['capacidad_recepcion_litros'] == 18000
