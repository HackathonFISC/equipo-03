"""Comprobaciones físicas del ensayo V1 sin reutilizar la lógica del solver."""
import json
from datetime import timedelta
from pathlib import Path

import pytest

from calculo.solver import solve_routes_minimo
from contratos.errores import CodigoError, ExcepcionContrato
from contratos.solicitudes import SolicitudResolverRutas
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def payload():
    return json.loads((ROOT / 'contratos/ejemplos/solicitud_resolver_rutas.json').read_text(encoding='utf-8'))


def resolver(payload):
    return solve_routes_minimo(SolicitudResolverRutas.model_validate(payload))


def comprobar_fisica(entrada, plan):
    """Aserciones de pruebas; no sustituye verify_plan de V3."""
    vehiculos = {v.vehiculo_id: v for v in entrada.vehiculos}
    necesidades = {n.punto_atencion_id: n for n in entrada.necesidades}
    servicios = {s.punto_atencion_id: s.descarga_minutos for s in entrada.servicios}
    indices = {n: i for i, n in enumerate(entrada.matriz.nodos_ids)}
    vistos = []
    for ruta in plan.rutas:
        v = vehiculos[ruta.vehiculo_id]
        assert v.disponible
        assert v.turno.inicio <= ruta.salida_estimada < ruta.retorno_estimado <= v.turno.fin
        assert sum(p.litros_asignados for p in ruta.paradas) <= v.capacidad_litros
        anterior, fin = entrada.deposito.deposito_id, ruta.salida_estimada
        for p in ruta.paradas:
            n = necesidades[p.punto_atencion_id]
            minutos = entrada.matriz.minutos[indices[anterior]][indices[p.punto_atencion_id]]
            assert minutos is not None
            assert p.llegada_estimada == fin + timedelta(minutes=minutos)
            assert p.inicio_descarga >= p.llegada_estimada
            assert p.fin_descarga - p.inicio_descarga == timedelta(minutes=servicios[p.punto_atencion_id])
            assert n.ventana_atencion.inicio <= p.inicio_descarga < p.fin_descarga <= n.ventana_atencion.fin
            assert p.litros_asignados == n.demanda_litros
            assert p.incidente_id == n.incidente_id
            vistos.append(p.punto_atencion_id)
            anterior, fin = p.punto_atencion_id, p.fin_descarga
        minutos = entrada.matriz.minutos[indices[anterior]][indices[entrada.deposito.deposito_id]]
        assert minutos is not None
        assert ruta.retorno_estimado >= fin + timedelta(minutes=minutos)
    assert len(vistos) == len(set(vistos)) == 6
    assert set(vistos) == set(necesidades)
    assert not plan.no_atendidos
    assert plan.estado_solver == 'factible'
    assert plan.verificacion is None and plan.aprobacion is None and plan.bloqueos_publicacion
    assert (plan.plan_id, plan.version, plan.datos_version, plan.politica_version) == (
        entrada.plan_id, entrada.version, entrada.datos_version, entrada.politica.politica_version)


def test_seis_puntos_cargas_tiempos_y_retorno(payload):
    entrada = SolicitudResolverRutas.model_validate(payload)
    original = entrada.model_dump(mode='json')
    plan = solve_routes_minimo(entrada)
    comprobar_fisica(entrada, plan)
    assert sum(p.litros_asignados for r in plan.rutas for p in r.paradas) == 18000
    assert len(plan.rutas) == 2
    assert entrada.model_dump(mode='json') == original
    assert solve_routes_minimo(entrada).model_dump(mode='json') == plan.model_dump(mode='json')


def test_capacidad_insuficiente_no_oculta_puntos(payload):
    for v in payload['vehiculos']:
        v['capacidad_litros'] = 1000.0
    plan = resolver(payload)
    assert not plan.rutas and len(plan.no_atendidos) == 6
    assert plan.estado_solver == 'error' and plan.bloqueos_publicacion
    assert sum(n.demanda_pendiente_litros for n in plan.no_atendidos) == 18000


@pytest.mark.parametrize('modo', ['ninguno', 'uno'])
def test_no_asigna_vehiculos_indisponibles(payload, modo):
    for v in payload['vehiculos']:
        v['disponible'] = False
    if modo == 'uno':
        payload['vehiculos'][0]['disponible'] = True
    plan = resolver(payload)
    assert not plan.rutas and len(plan.no_atendidos) == 6


def test_ventana_cubre_descarga_completa(payload):
    payload['necesidades'][0]['ventana_atencion']['fin'] = '2026-10-17T08:05:00-05:00'
    plan = resolver(payload)
    assert not plan.rutas and len(plan.no_atendidos) == 6
    assert plan.estado_solver != 'inviabilidad_demostrada'


def test_retorno_dentro_turno(payload):
    for v in payload['vehiculos']:
        v['turno']['fin'] = '2026-10-17T08:25:00-05:00'
    plan = resolver(payload)
    assert not plan.rutas and len(plan.no_atendidos) == 6


def test_espera_hasta_ventana(payload):
    for n in payload['necesidades']:
        n['ventana_atencion'] = dict(inicio='2026-10-17T09:00:00-05:00', fin='2026-10-17T12:00:00-05:00')
    entrada = SolicitudResolverRutas.model_validate(payload)
    plan = solve_routes_minimo(entrada)
    comprobar_fisica(entrada, plan)


def test_matriz_dirigida_arco_bloqueado(payload):
    payload['matriz']['minutos'][1][2] = None
    payload['matriz']['minutos'][2][1] = 17
    entrada = SolicitudResolverRutas.model_validate(payload)
    comprobar_fisica(entrada, solve_routes_minimo(entrada))


def test_sin_acceso_no_produce_ruta(payload):
    for i in range(1, 7):
        payload['matriz']['minutos'][i][0] = None
    plan = resolver(payload)
    assert not plan.rutas and len(plan.no_atendidos) == 6
    assert plan.estado_solver in ('error', 'timeout_sin_solucion')


def test_politica_propuesta_no_es_activada_por_solver(payload):
    payload['politica']['estado'] = 'propuesta_demo'
    payload['politica']['confirmacion_activacion'] = None
    with pytest.raises(ExcepcionContrato) as error:
        resolver(payload)
    assert error.value.detalle.codigo == CodigoError.POLITICA_NO_ACTIVA


def test_necesidades_v0_siguen_pendientes(payload):
    v0 = json.loads((ROOT / 'datos/escenario/demandas.json').read_text(encoding='utf-8'))
    payload['necesidades'] = v0['necesidades']
    with pytest.raises(ExcepcionContrato) as error:
        resolver(payload)
    assert error.value.detalle.codigo == CodigoError.DATOS_INSUFICIENTES


def test_rechaza_uso_no_sintetico(payload):
    payload['origen'] = 'real'
    with pytest.raises(ExcepcionContrato) as error:
        resolver(payload)
    assert error.value.detalle.codigo == CodigoError.CONTRATO_INVALIDO


def test_capacidades_distintas_y_orden_matriz(payload):
    payload['vehiculos'][0]['capacidad_litros'] = 8500.0
    payload['vehiculos'][1]['capacidad_litros'] = 9500.0
    orden = [3, 1, 6, 0, 4, 2, 5]
    matriz = payload['matriz']
    matriz['nodos_ids'] = [matriz['nodos_ids'][i] for i in orden]
    matriz['minutos'] = [[matriz['minutos'][i][j] for j in orden] for i in orden]
    entrada = SolicitudResolverRutas.model_validate(payload)
    comprobar_fisica(entrada, solve_routes_minimo(entrada))


@pytest.mark.parametrize('timeout', [True, False])
def test_sin_solucion_no_inventa_inviabilidad(payload, monkeypatch, timeout):
    # Inyección de un resultado del motor para comprobar su traducción, no un timeout real.
    monkeypatch.setattr(pywrapcp.RoutingModel, 'SolveWithParameters', lambda *args: None)
    estado = (routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL_TIMEOUT if timeout
              else routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL)
    monkeypatch.setattr(pywrapcp.RoutingModel, 'status', lambda *args: estado)
    plan = resolver(payload)
    assert plan.estado_solver == ('timeout_sin_solucion' if timeout else 'error')
    assert not plan.rutas and len(plan.no_atendidos) == 6 and plan.bloqueos_publicacion
