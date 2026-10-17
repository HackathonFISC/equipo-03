import copy
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from ortools.sat.python import cp_model

from calculo.demo_escenario_v3 import construir
from calculo.prioridad import score_needs
from calculo.solver import solve_routes
from calculo.verificador import verify_plan
from contratos.errores import CodigoError, ExcepcionContrato
from contratos.solicitudes import SolicitudPriorizarNecesidades, SolicitudResolverRutas, SolicitudVerificarPlan


def escenario(cantidad=6):
    s = construir()['solicitud_rutas']
    ids = {p['punto_atencion_id'] for p in s['puntos'][:cantidad]}
    s['puntos'] = s['puntos'][:cantidad]
    s['necesidades'] = [n for n in s['necesidades'] if n['punto_atencion_id'] in ids]
    s['servicios'] = [n for n in s['servicios'] if n['punto_atencion_id'] in ids]
    indices = [i for i, pid in enumerate(s['matriz']['nodos_ids']) if pid in ids or pid == s['deposito']['deposito_id']]
    s['matriz']['nodos_ids'] = [s['matriz']['nodos_ids'][i] for i in indices]
    s['matriz']['minutos'] = [[s['matriz']['minutos'][i][j] for j in indices] for i in indices]
    return s


def resolver(datos):
    return solve_routes(SolicitudResolverRutas.model_validate(datos))


def comprobar(datos, p):
    s = SolicitudResolverRutas.model_validate(datos)
    # construct permite comprobar también defensas ante contexto adulterado.
    return verify_plan(SolicitudVerificarPlan.model_construct(esquema_version=s.esquema_version,
        ejecucion_id=s.ejecucion_id, creado_en=s.creado_en, origen=s.origen,
        solicitud_original=s, propuesta=p))


def atendidos(p):
    return {str(n.punto_atencion_id) for r in p.rutas for n in r.paradas}


def test_escenario_base_cobertura_completa_reproducible_y_sin_mutacion():
    s = escenario()
    antes = copy.deepcopy(s)
    p = resolver(s)
    assert s == antes and p == resolver(s)
    assert len(p.rutas) == 2 and len(atendidos(p)) == 6 and not p.no_atendidos
    assert sum(n.litros_asignados for r in p.rutas for n in r.paradas) == 15000
    assert comprobar(s, p).valido
    assert p.estado == 'pendiente_revision' and p.aprobacion is None
    assert p.verificacion is None and p.bloqueos_publicacion


def test_un_camion_conserva_criticos_y_selecciona_parcial_por_ranking():
    s = escenario()
    s['vehiculos'][1]['disponible'] = False
    p = resolver(s)
    esperados = {s['puntos'][i]['punto_atencion_id'] for i in (2, 4, 3, 5)}
    assert p.estado_solver == 'factible' and atendidos(p) == esperados
    assert len(p.no_atendidos) == 2 and all(n.codigo == 'sin_capacidad' for n in p.no_atendidos)
    assert sum(t.litros_asignados for r in p.rutas for t in r.paradas) == 9000
    assert comprobar(s, p).valido


@pytest.mark.parametrize('critico', [False, True])
def test_demanda_mayor_que_cisterna_conserva_litros_y_no_divide(critico):
    s = escenario()
    n = next(n for n in s['necesidades'] if (n['clase_prioridad'] == 'critico') == critico)
    n['demanda_litros'] = 12000.0
    p = resolver(s)
    pendiente = next(x for x in p.no_atendidos if str(x.punto_atencion_id) == n['punto_atencion_id'])
    assert pendiente.codigo == 'demanda_supera_vehiculo' and pendiente.demanda_pendiente_litros == 12000
    assert len(atendidos(p)) == 5
    assert comprobar(s, p).valido == (not critico)


def test_punto_inalcanzable_tiene_diagnostico_sin_descartar_a_los_demas():
    s = escenario()
    pid = s['puntos'][0]['punto_atencion_id']
    i = s['matriz']['nodos_ids'].index(pid)
    for j in range(7):
        if i != j:
            s['matriz']['minutos'][i][j] = None
            s['matriz']['minutos'][j][i] = None
    p = resolver(s)
    assert len(atendidos(p)) == 5 and len(p.no_atendidos) == 1
    assert p.no_atendidos[0].codigo == 'sin_acceso'
    assert comprobar(s, p).valido


def test_ventana_corta_excluye_solo_el_punto_afectado():
    s = escenario()
    n = next(n for n in s['necesidades'] if n['clase_prioridad'] == 'general')
    n['ventana_atencion']['fin'] = '2026-10-17T08:01:00-05:00'
    p = resolver(s)
    assert len(atendidos(p)) == 5 and p.no_atendidos[0].codigo == 'ventana'
    assert comprobar(s, p).valido


def test_pendiente_desconocido_no_se_convierte_en_cero_y_urgencia_bloquea():
    s = escenario()
    n = s['necesidades'][0]
    n.update(estado_demanda='pendiente', demanda_litros=None, confirmacion_demanda=None,
             estado_prioridad='pendiente', puntaje=None, componentes=None, posicion=None,
             pendientes=['Falta reserva utilizable.'], requiere_revision_urgente=True)
    p = resolver(s)
    assert len(atendidos(p)) == 5 and p.no_atendidos[0].demanda_pendiente_litros is None
    assert p.no_atendidos[0].codigo == 'datos_pendientes'
    v = comprobar(s, p)
    assert not v.valido and any(x.codigo == 'cobertura_critica' for x in v.violaciones)


def test_demanda_cero_no_crea_visitas_y_no_es_deficit_critico():
    s = escenario()
    for n in s['necesidades']:
        n['demanda_litros'] = 0.0
    p = resolver(s)
    assert p.estado_solver == 'factible' and not p.rutas
    assert all(n.demanda_pendiente_litros == 0 for n in p.no_atendidos)
    assert comprobar(s, p).valido


def test_sin_flota_disponible_demuestra_imposibilidad_de_entrega_positiva():
    s = escenario()
    for v in s['vehiculos']:
        v['disponible'] = False
    p = resolver(s)
    assert p.estado_solver == 'inviabilidad_demostrada' and not p.rutas
    assert len(p.no_atendidos) == 6 and all(n.codigo == 'sin_capacidad' for n in p.no_atendidos)
    assert not comprobar(s, p).valido


def test_matriz_dirigida_puede_regresar_por_otro_punto():
    s = escenario(2)
    s['matriz']['minutos'] = [[0, 5, None], [None, 0, 5], [5, None, 0]]
    p = resolver(s)
    assert len(p.rutas) == 1 and len(atendidos(p)) == 2
    assert comprobar(s, p).valido


def test_turno_temprano_no_obliga_a_esperar_horas_en_primer_punto():
    s = escenario()
    for v in s['vehiculos']:
        v['turno']['inicio'] = '2026-10-17T06:00:00-05:00'
    p = resolver(s)
    for ruta in p.rutas:
        assert ruta.salida_estimada >= datetime.fromisoformat('2026-10-17T07:00:00-05:00')
        assert ruta.paradas[0].llegada_estimada == ruta.paradas[0].inicio_descarga
    assert comprobar(s, p).valido


def test_ventana_con_microsegundos_no_se_redondea_hasta_perder_factibilidad():
    s = escenario(1)
    for v in s['vehiculos']:
        v['turno']['inicio'] = '2026-10-17T07:00:00-05:00'
    s['necesidades'][0]['ventana_atencion'] = dict(inicio='2026-10-17T08:00:00.123456-05:00', fin='2026-10-17T08:01:00.123456-05:00')
    s['servicios'][0]['descarga_minutos'] = 1
    p = resolver(s)
    assert p.rutas[0].paradas[0].inicio_descarga.microsecond == 123456
    assert comprobar(s, p).valido


def test_reordenar_matriz_y_listas_preserva_rutas_por_uuid():
    s = escenario()
    p = resolver(s)
    s['puntos'].reverse()
    s['necesidades'].reverse()
    s['servicios'].reverse()
    s['matriz']['nodos_ids'].reverse()
    s['matriz']['minutos'] = [list(reversed(fila)) for fila in reversed(s['matriz']['minutos'])]
    q = resolver(s)
    assert q.rutas == p.rutas and q.no_atendidos == p.no_atendidos
    assert comprobar(s, q).valido


def test_timeout_simulado_nunca_se_declara_inviabilidad(monkeypatch):
    import calculo.solver_v3 as modulo
    monkeypatch.setattr(modulo, '_seleccionar', lambda *args: ([], cp_model.UNKNOWN))
    p = resolver(escenario())
    assert p.estado_solver == 'timeout_sin_solucion' and not p.rutas
    assert all(n.codigo == 'timeout' for n in p.no_atendidos)


def test_presupuesto_agotado_durante_enumeracion(monkeypatch):
    import calculo.solver_v3 as modulo
    monkeypatch.setattr(modulo, '_rutas_candidatas', lambda *args: ([], False))
    p = resolver(escenario())
    assert p.estado_solver == 'timeout_sin_solucion' and len(p.no_atendidos) == 6


def test_solucion_factible_sin_optimalidad_se_identifica(monkeypatch):
    import calculo.solver_v3 as modulo
    original = modulo._seleccionar
    def factible(*args):
        seleccion, estado = original(*args)
        return seleccion, cp_model.FEASIBLE
    monkeypatch.setattr(modulo, '_seleccionar', factible)
    p = resolver(escenario())
    assert p.estado_solver == 'factible' and 'No se declara optimalidad global de cobertura.' in p.supuestos


def test_politica_propuesta_es_error_de_dominio():
    s = escenario()
    s['politica'].update(estado='propuesta_demo', confirmacion_activacion=None)
    with pytest.raises(ExcepcionContrato) as error:
        resolver(s)
    assert error.value.detalle.codigo == CodigoError.POLITICA_NO_ACTIVA


def test_no_acepta_fracciones_menores_a_mililitro():
    s = escenario()
    s['necesidades'][0]['demanda_litros'] = 1000.0001
    with pytest.raises(ExcepcionContrato) as error:
        resolver(s)
    assert error.value.detalle.codigo == CodigoError.CONTRATO_INVALIDO


@pytest.mark.parametrize('alteracion,codigo', [
    ('carga', 'capacidad'), ('flota', 'asignacion'), ('ventana', 'ventana'),
    ('viaje', 'horario'), ('politica', 'version'), ('version', 'version')])
def test_verificador_detecta_snapshot_modificado_aun_sin_cambiar_etiquetas(alteracion, codigo):
    s = escenario()
    p = resolver(s)
    if alteracion == 'carga':
        for v in s['vehiculos']:
            v['capacidad_litros'] = 100.0
    elif alteracion == 'flota':
        for v in s['vehiculos']:
            v['disponible'] = False
    elif alteracion == 'ventana':
        for n in s['necesidades']:
            n['ventana_atencion']['fin'] = '2026-10-17T08:01:00-05:00'
    elif alteracion == 'viaje':
        s['matriz']['minutos'] = [[0 if i == j else 100 for j in range(7)] for i in range(7)]
    elif alteracion == 'politica':
        s['politica'].update(peso_duracion=0.2, peso_vulnerabilidad=0.6)
    else:
        s['datos_version'] = 'otra'
        for n in s['necesidades']:
            n['datos_version'] = 'otra'
    r = comprobar(s, p)
    assert not r.valido and any(x.codigo == codigo for x in r.violaciones)
    assert any(x.codigo == 'version' for x in r.violaciones)


@pytest.mark.parametrize('alteracion,codigo', [
    ('litros', 'demanda'), ('duracion', 'horario'), ('retorno', 'retorno'),
    ('incidente', 'asignacion'), ('vehiculo', 'asignacion'), ('omision', 'asignacion'),
    ('duplicado', 'asignacion'), ('huella', 'version')])
def test_verificador_independiente_rechaza_propuesta_adulterada(alteracion, codigo):
    s = escenario()
    p = resolver(s)
    if alteracion == 'litros':
        p.rutas[0].paradas[0].litros_asignados -= 1
    elif alteracion == 'duracion':
        p.rutas[0].paradas[0].inicio_descarga += timedelta(seconds=1)
    elif alteracion == 'retorno':
        p.rutas[0].retorno_estimado += timedelta(minutes=1)
    elif alteracion == 'incidente':
        p.rutas[0].paradas[0].incidente_id = uuid4()
    elif alteracion == 'vehiculo':
        p.rutas[0].vehiculo_id = uuid4()
    elif alteracion == 'omision':
        p.rutas[0].paradas.pop()
    elif alteracion == 'duplicado':
        p.rutas[1].paradas[0].parada_id = p.rutas[0].paradas[0].parada_id
    else:
        p.supuestos = [x for x in p.supuestos if not x.startswith('HUELLA_ENTRADAS_SHA256=')]
    v = comprobar(s, p)
    assert not v.valido and any(x.codigo == codigo for x in v.violaciones)


def test_no_confia_en_informe_valido_adjuntado_previamente():
    s = escenario()
    p = resolver(s)
    p.verificacion = comprobar(s, p)
    p.rutas[0].paradas[0].litros_asignados -= 100
    assert p.verificacion.valido and not comprobar(s, p).valido


def test_verificador_no_invoca_solver_ni_ortools(monkeypatch):
    import calculo.solver_v3 as modulo
    s = escenario()
    p = resolver(s)
    monkeypatch.setattr(modulo, '_seleccionar', lambda *args: pytest.fail('No invocar solver al verificar'))
    assert comprobar(s, p).valido


def test_maximiza_numero_de_criticos_antes_de_preferir_un_critico_grande():
    s = escenario(3)
    s['vehiculos'] = s['vehiculos'][:1]
    s['vehiculos'][0]['capacidad_litros'] = 8000.0
    por_punto = {n['punto_atencion_id']: n for n in s['necesidades']}
    for i, p in enumerate(s['puntos']):
        n = por_punto[p['punto_atencion_id']]
        n.update(clase_prioridad='critico', vulnerabilidad='alta', horas_sin_agua=168.0,
                 personas_atendidas=500 - i * 100, demanda_litros=7000.0 if i == 0 else 4000.0)
    peticion = SolicitudPriorizarNecesidades.model_validate({k: s[k] for k in (
        'esquema_version', 'ejecucion_id', 'creado_en', 'origen', 'datos_version', 'politica', 'necesidades')})
    s['necesidades'] = score_needs(peticion).model_dump(mode='json')['evaluaciones']
    p = resolver(s)
    assert atendidos(p) == {n['punto_atencion_id'] for n in s['puntos'][1:]}
    assert p.no_atendidos[0].demanda_pendiente_litros == 7000
    assert not comprobar(s, p).valido  # Un crítico sin cubrir sigue bloqueando publicación.


def test_ranking_duplicado_se_rechaza():
    s = escenario()
    s['necesidades'][1]['posicion'] = s['necesidades'][0]['posicion']
    with pytest.raises(ExcepcionContrato) as error:
        resolver(s)
    assert error.value.detalle.codigo == CodigoError.CONTRATO_INVALIDO


def test_nadie_cabe_por_ventana_demuestra_imposibilidad_de_servicio_positivo():
    s = escenario()
    for n in s['necesidades']:
        n['ventana_atencion']['fin'] = '2026-10-17T08:01:00-05:00'
    p = resolver(s)
    assert p.estado_solver == 'inviabilidad_demostrada' and not p.rutas
    assert all(n.codigo == 'ventana' for n in p.no_atendidos)


def test_cambiar_la_version_del_plan_se_detecta_sin_confiar_en_el_contexto():
    s = escenario()
    p = resolver(s)
    p.version += 1
    v = comprobar(s, p)
    assert not v.valido and any(x.codigo == 'version' for x in v.violaciones)


def test_datos_todos_pendientes_no_se_declaran_inviables():
    s = escenario()
    for n in s['necesidades']:
        n.update(estado_demanda='pendiente', demanda_litros=None, confirmacion_demanda=None,
                 estado_prioridad='pendiente', puntaje=None, componentes=None, posicion=None,
                 pendientes=['Falta confirmar demanda.'])
    p = resolver(s)
    assert p.estado_solver == 'error' and not p.rutas
    assert all(n.codigo == 'datos_pendientes' and n.demanda_pendiente_litros is None for n in p.no_atendidos)


def test_verificador_no_desborda_con_viajes_o_descargas_extremos():
    s = escenario()
    p = resolver(s)
    s['matriz']['minutos'] = [[0 if i == j else 10**15 for j in range(7)] for i in range(7)]
    for servicio in s['servicios']:
        servicio['descarga_minutos'] = 10**15
    v = comprobar(s, p)
    assert not v.valido and {'horario', 'retorno', 'version'} <= {n.codigo for n in v.violaciones}


def test_camino_que_exige_cargar_dos_puntos_diagnostica_capacidad_no_ventana():
    s = escenario(2)
    s['vehiculos'] = s['vehiculos'][:1]
    s['vehiculos'][0]['capacidad_litros'] = 5000.0
    s['matriz']['minutos'] = [[0, 5, None], [None, 0, 5], [5, None, 0]]
    p = resolver(s)
    assert not p.rutas and p.estado_solver == 'inviabilidad_demostrada'
    assert all(n.codigo == 'sin_capacidad' for n in p.no_atendidos)


def test_estimaciones_cero_sin_validar_no_equivalen_a_ausencia_confirmada_de_demanda():
    s = escenario()
    for n in s['necesidades']:
        n.update(estado_demanda='pendiente', demanda_litros=0.0, confirmacion_demanda=None,
                 estado_prioridad='pendiente', puntaje=None, componentes=None, posicion=None,
                 pendientes=['Estimación cero sin confirmar.'])
    p = resolver(s)
    assert p.estado_solver == 'error' and all(n.codigo == 'datos_pendientes' for n in p.no_atendidos)


@pytest.mark.parametrize('cambio', ['politica', 'orden'])
def test_no_confia_en_ranking_obsoleto_o_manipulado(cambio):
    s = escenario()
    if cambio == 'politica':
        s['politica'].update(peso_duracion=0.1, peso_vulnerabilidad=0.7)
    else:
        s['necesidades'][0]['posicion'], s['necesidades'][1]['posicion'] = (
            s['necesidades'][1]['posicion'], s['necesidades'][0]['posicion'])
    with pytest.raises(ExcepcionContrato) as error:
        resolver(s)
    assert error.value.detalle.codigo == CodigoError.CONTRATO_INVALIDO
