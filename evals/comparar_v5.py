"""Comparación local reproducible: prioridad frente a antigüedad del incidente."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid5

from calculo.demo_escenario_v3 import construir, simular
from calculo.orden_llegada import solve_routes_orden_llegada
from calculo.prioridad import score_needs
from calculo.replanificacion import simular_retiro
from calculo.solver import solve_routes
from calculo.verificador import verify_plan
from contratos.solicitudes import SolicitudPriorizarNecesidades, SolicitudResolverRutas, SolicitudVerificarPlan
from evals.metricas import medir_plan

RAIZ = Path(__file__).resolve().parents[1]


def _hash(datos):
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _priorizar(datos):
    s = SolicitudResolverRutas.model_validate(datos)
    ranking = score_needs(SolicitudPriorizarNecesidades(esquema_version=s.esquema_version,
        ejecucion_id=s.ejecucion_id, creado_en=s.creado_en, origen=s.origen,
        datos_version=s.datos_version, politica=s.politica, necesidades=s.necesidades))
    d = s.model_dump(mode='json')
    d['necesidades'] = [n.model_dump(mode='json') for n in ranking.evaluaciones]
    return SolicitudResolverRutas.model_validate(d)


def preparar_casos(*, con_fuentes=False):
    fuente_base = construir()
    d = copy.deepcopy(fuente_base['solicitud_rutas'])
    d['version'] = 10
    d['datos_version'] = 'oeste-1.0-v5-comparacion-1'
    # Fijar una cola adversa explícita: generales anteriores a críticos.
    # Los dos métodos reciben exactamente estas fechas; no son reportes reales.
    cola = sorted(d['necesidades'], key=lambda n: (n['clase_prioridad'] == 'critico', n['punto_atencion_id']))
    inicio = datetime(2026, 10, 16, 6, tzinfo=timezone(timedelta(hours=-5)))
    for i, n in enumerate(cola):
        n['primera_deteccion_en'] = (inicio + timedelta(minutes=i)).isoformat()
        n['datos_version'] = d['datos_version']
    base = _priorizar(d)
    retiro = simular_retiro(base, base.vehiculos[1].vehiculo_id, datos_version='oeste-1.0-v5-retiro-1')
    politica_fuente = json.loads((RAIZ/fuente_base['parametros']['politica_fuente']).read_text(encoding='utf-8'))
    pid_critico = next(n.punto_atencion_id for n in base.necesidades if n.clase_prioridad == 'critico')
    parametros_exceso = copy.deepcopy(fuente_base['parametros'])
    parametros_exceso['datos_version'] = 'oeste-1.0-v5-critico-excesivo-1'
    perfil = next(p for p in parametros_exceso['perfiles'] if p['punto_atencion_id'] == str(pid_critico))
    perfil.update(familias_sinteticas=130, personas_atendidas=650,
        reserva_utilizable_litros=1000, agua_almacenada_litros=1000, tanque_nominal_litros=20000)
    parametros_exceso['supuestos'] = [x for x in parametros_exceso['supuestos'] if not x.startswith('Tanques nominales')]
    parametros_exceso['supuestos'].append('Variante adversa ficticia V5: un grupo de 650 personas, reserva de 1000 L y banco de 20 000 L; no es infraestructura medida ni demanda institucional.')
    fuente_exceso = simular(parametros_exceso, base.model_dump(mode='json'), politica_fuente)
    excesiva = fuente_exceso['solicitud_rutas']
    excesiva['plan_id'] = str(uuid5(base.plan_id, 'v5-critico-excesivo'))
    excesiva['ejecucion_id'] = str(uuid5(base.ejecucion_id, 'v5-critico-excesivo'))
    for n in excesiva['necesidades']:
        n['ejecucion_id'] = excesiva['ejecucion_id']
    excesiva['version'] = 12
    parametros_incompletos = copy.deepcopy(fuente_base['parametros'])
    parametros_incompletos['datos_version'] = 'oeste-1.0-v5-datos-insuficientes-1'
    next(p for p in parametros_incompletos['perfiles'] if p['punto_atencion_id'] == str(pid_critico))['reserva_utilizable_litros'] = None
    fuente_incompleta = simular(parametros_incompletos, base.model_dump(mode='json'), politica_fuente)
    incompleta = fuente_incompleta['solicitud_rutas']
    incompleta['plan_id'] = str(uuid5(base.plan_id, 'v5-datos-insuficientes'))
    incompleta['ejecucion_id'] = str(uuid5(base.ejecucion_id, 'v5-datos-insuficientes'))
    for n in incompleta['necesidades']:
        n['ejecucion_id'] = incompleta['ejecucion_id']
    incompleta['version'] = 13
    sin_flota = simular_retiro(retiro, retiro.vehiculos[0].vehiculo_id, datos_version='oeste-1.0-v5-sin-flota-1')
    casos = [('completo', base), ('retiro_cisterna', retiro),
            ('critico_excesivo', _priorizar(excesiva)),
            ('datos_insuficientes', _priorizar(incompleta)), ('sin_flota', sin_flota)]
    fuentes = {nombre: {k: fuente[k] for k in ('parametros', 'solicitudes_validacion', 'validaciones_demanda')}
               for nombre, fuente in [('completo', fuente_base), ('critico_excesivo', fuente_exceso),
                                       ('datos_insuficientes', fuente_incompleta)]}
    return (casos, fuentes) if con_fuentes else casos


def comparar(entrada, *, repeticiones=3):
    if type(repeticiones) is not int or not 1 <= repeticiones <= 20:
        raise ValueError('Repeticiones enteras entre 1 y 20')
    s = SolicitudResolverRutas.model_validate(entrada.model_dump(mode='json'))
    original = s.model_dump(mode='json')
    huella = _hash(original)
    metodos = dict(prioridad=solve_routes, orden_llegada=solve_routes_orden_llegada)
    ejecuciones = {nombre: [] for nombre in metodos}
    for i in range(repeticiones):
        # Alternar primero/segundo para reducir sesgo de calentamiento local.
        for nombre in (list(metodos) if i % 2 == 0 else list(reversed(metodos))):
            peticion = SolicitudResolverRutas.model_validate(original)
            inicio = perf_counter()
            propuesta = metodos[nombre](peticion)
            calculo_ms = (perf_counter()-inicio)*1000
            if peticion.model_dump(mode='json') != original:
                raise AssertionError('El método modificó su entrada')
            inicio = perf_counter()
            informe = verify_plan(SolicitudVerificarPlan(esquema_version=s.esquema_version,
                ejecucion_id=s.ejecucion_id, creado_en=s.creado_en, origen=s.origen,
                solicitud_original=s, propuesta=propuesta))
            verificacion_ms = (perf_counter()-inicio)*1000
            permitidas = {'cobertura_critica'}
            if propuesta.estado_solver != 'factible' and not propuesta.rutas:
                # El verificador informa "otro" porque no existe plan factible.
                # Se conserva ese rechazo, sin tratarlo como ruta física válida.
                permitidas.add('otro')
            estructurales = [v.codigo for v in informe.violaciones if v.codigo not in permitidas]
            if estructurales:
                raise AssertionError(f'Comparación rechazada por violaciones físicas/contexto: {estructurales}')
            if propuesta.aprobacion is not None or propuesta.estado != 'pendiente_revision' or not propuesta.bloqueos_publicacion:
                raise AssertionError('El comparador no puede aprobar ni autorizar publicación')
            ejecuciones[nombre].append(dict(propuesta=propuesta, informe=informe,
                calculo_ms=calculo_ms, verificacion_ms=verificacion_ms))
    resultados = {}
    for nombre, muestras in ejecuciones.items():
        primera = muestras[0]
        cuerpos = [x['propuesta'].model_dump(mode='json') for x in muestras]
        if any(x != cuerpos[0] for x in cuerpos[1:]):
            raise AssertionError('Resultado no reproducible en estas repeticiones')
        p = primera['propuesta']
        if 'HUELLA_ENTRADAS_SHA256=' + huella not in p.supuestos:
            raise AssertionError('Los métodos no utilizaron el mismo snapshot completo')
        resultados[nombre] = dict(propuesta=cuerpos[0], verificacion=primera['informe'].model_dump(mode='json'),
            metricas=medir_plan(s, p), reproducible=True, plan_factible=p.estado_solver == 'factible',
            latencia_calculo_ms=dict(muestras=[round(x['calculo_ms'], 6) for x in muestras],
                mediana=round(median(x['calculo_ms'] for x in muestras), 6)),
            latencia_verificacion_ms=dict(muestras=[round(x['verificacion_ms'], 6) for x in muestras],
                mediana=round(median(x['verificacion_ms'] for x in muestras), 6)))
    if s.model_dump(mode='json') != original:
        raise AssertionError('El snapshot de comparación cambió')
    a, b = resultados['prioridad']['metricas'], resultados['orden_llegada']['metricas']
    return dict(entrada=original, entrada_sha256=huella, repeticiones=repeticiones,
        resultados=resultados, diferencias_prioridad_menos_llegada=dict(
            criticos_atendidos=a['cobertura_critica']['atendidos']-b['cobertura_critica']['atendidos'],
            puntos_atendidos=a['cobertura_puntos']['atendidos']-b['cobertura_puntos']['atendidos'],
            litros_asignados=a['litros_asignados']-b['litros_asignados'],
            deficit_conocido_litros=a['deficit_conocido_litros']-b['deficit_conocido_litros'],
            viaje_total_minutos=a['viaje_total_minutos']-b['viaje_total_minutos']))


def ejecutar(*, repeticiones=3):
    preparados, fuentes = preparar_casos(con_fuentes=True)
    casos = [dict(caso=nombre, **comparar(s, repeticiones=repeticiones)) for nombre, s in preparados]
    retiro = next(c for c in casos if c['caso'] == 'retiro_cisterna')
    if retiro['diferencias_prioridad_menos_llegada']['criticos_atendidos'] <= 0:
        raise AssertionError('El fixture adverso no mostró la diferencia crítica esperada')
    for c in casos:
        if c['caso'] in {'critico_excesivo', 'datos_insuficientes', 'sin_flota'}:
            if any(r['verificacion']['valido'] for r in c['resultados'].values()):
                raise AssertionError('No ocultar un crítico pendiente en el escenario adverso')
    codigo = ('calculo/solver_v3.py', 'calculo/orden_llegada.py', 'calculo/replanificacion.py',
              'calculo/verificador.py', 'evals/metricas.py', 'evals/comparar_v5.py')
    return dict(version='jose-v5-preparacion-1', origen='sintetico',
        registrado_en=datetime.now(timezone.utc).isoformat(), cierre_v4=False, cierre_v5=False,
        alcance='Ensayo local controlado; no acredita mejora general, replanificación persistida ni avisos reales.',
        caso_retiro='Antes de salida; nueva versión/datos/ejecución sin modificar la anterior ni su aprobación histórica.',
        metodologia='Mismo snapshot, restricciones y motor; cambia solo objetivo de cobertura. FIFO por primera detección e ID, no por número de mensajes.',
        latencias_integradas=dict(recepcion_a_propuesta_ms=None, aprobacion_a_envio_ms=None,
                                  motivo='No se ejecutó el recorrido real de API/BD/Telegram'),
        pendientes_integracion=[dict(caso=n, estado='pendiente') for n in (19, 22, 23, 24, 25)],
        construccion_necesidades=fuentes,
        traza=dict(herramientas=['validate_need', 'score_needs', 'solve_routes', 'solve_routes_orden_llegada', 'verify_plan'],
            transformacion='Contextos y fechas de primera detección versionados para la comparación; cantidades, recepción y servicios derivados con validate_need y score_needs reales.',
            sha256_codigo={p: hashlib.sha256((RAIZ/p).read_bytes()).hexdigest() for p in codigo}), casos=casos)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, help='Archivo nuevo de evidencia; no sobrescribe')
    parser.add_argument('--repeticiones', type=int, default=3)
    args = parser.parse_args()
    if args.salida and args.salida.exists():
        parser.error('La evidencia ya existe: elegir un nombre nuevo')
    evidencia = ejecutar(repeticiones=args.repeticiones)
    print('ENSAYO SINTETICO V5: prioridad frente a orden de llegada; sin aprobacion ni envio')
    for caso in evidencia['casos']:
        print(caso['caso'])
        for nombre, r in caso['resultados'].items():
            m = r['metricas']; c = m['cobertura_critica']
            print(f"  {nombre}: {m['cobertura_puntos']['atendidos']}/6 puntos; criticos {c['atendidos']}/{c['total']}; "
                  f"{m['litros_asignados']:g} L; deficit conocido {m['deficit_conocido_litros']:g} L; "
                  f"demanda desconocida en {m['puntos_demanda_desconocida']} puntos; verificacion {r['verificacion']['valido']}")
            if m['deficit_total_litros'] is None:
                print('    Deficit TOTAL desconocido: el deficit conocido no representa la necesidad completa.')
    print('V4 y V5 integradas siguen pendientes; resultados limitados a estos fixtures.')
    if args.salida:
        with args.salida.open('x', encoding='utf-8') as f:
            json.dump(evidencia, f, ensure_ascii=False, indent=2)
            f.write('\n')


if __name__ == '__main__':
    main()
