"""Valida los 30 PED y ejecuta solo sus 18 comprobaciones de cálculo locales."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter
from uuid import UUID

from api.esquemas import PrepararPriorizacion
from calculo.demanda import validate_need
from calculo.prioridad import score_needs
from calculo.solver import solve_routes
from calculo.verificador import verify_plan
from contratos.errores import ExcepcionContrato
from contratos.solicitudes import (SolicitudPriorizarNecesidades, SolicitudResolverRutas,
                                  SolicitudValidarNecesidad, SolicitudVerificarPlan)
from evals.metricas import medir_plan, resumir

RAIZ = Path(__file__).resolve().parents[1]
DATASET = RAIZ/'datos/entradas_prueba/escritorio_v1'
LOCALES = {*(f'PED-{n:02d}' for n in range(1, 7)), *(f'PED-{n:02d}' for n in range(13, 25))}


def leer(ruta):
    def duplicada(pares):
        d = {}
        for k, v in pares:
            if k in d:
                raise ValueError('Clave JSON duplicada')
            d[k] = v
        return d
    def no_finito(valor):
        raise ValueError('JSON no finito')
    return json.loads(ruta.read_text(encoding='utf-8-sig'), object_pairs_hook=duplicada,
                      parse_constant=no_finito)


def sha(ruta):
    return hashlib.sha256(ruta.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def exigir(condicion, detalle):
    if not condicion:
        raise AssertionError(detalle)


def validar_dataset(carpeta):
    indice, base = leer(carpeta/'indice.json'), leer(carpeta/'base.json')
    exigir(indice['origen'] == base['origen'] == 'sintetico', 'Conjunto no sintético')
    exigir(indice['formato_huellas'] == base['formato_huellas'] == 'sha256_texto_lf', 'Formato de huellas desconocido')
    exigir(len(indice['casos']) == 30, 'Deben existir treinta casos')
    exigir(set(base['alias']) == {f'P{i}' for i in range(1, 7)}, 'Seis alias requeridos')
    catalogo = {str(p.punto_atencion_id) for p in SolicitudResolverRutas.model_validate(base['solicitud_rutas']).puntos}
    exigir(set(base['alias'].values()) == catalogo, 'No crear otros puntos')
    exigir(sum(p['personas'] for p in base['puntos']) == 860, 'Población base incorrecta')
    for p in base['puntos']:
        datos = p['parametros']
        manual = max(0, datos['personas_atendidas'] * datos['dotacion_litros_persona_dia']
                     * datos['dias_cobertura'] - datos['reserva_utilizable_litros'])
        exigir(manual == p['demanda_esperada_litros'], 'Oráculo de demanda inconsistente')
        libre = datos['tanque_nominal_litros'] * (1-datos['margen_tanque_proporcion']) - datos['agua_almacenada_litros']
        exigir(libre == p['recepcion_libre_litros'], 'Oráculo de recepción inconsistente')
    casos = []
    for n, item in enumerate(indice['casos'], 1):
        cid = f'PED-{n:02d}'
        exigir(item['id'] == cid and item['archivo'] == f'casos/{cid}.json', 'Orden o ruta de caso incorrectos')
        ruta = carpeta/item['archivo']
        exigir(not ruta.is_symlink() and ruta.resolve().is_relative_to(carpeta.resolve()), 'Ruta externa')
        exigir(sha(ruta) == item['sha256'], 'Caso modificado: regenerar manifiesto')
        c = leer(ruta)
        exigir(c['id'] == cid and c['dataset_version'] == indice['dataset_version'], 'Identidad de caso incoherente')
        exigir(c['origen'] == 'sintetico' and c['obtenido']['estado'] == 'no_ejecutado', 'No anticipar resultados')
        exigir(c['base'] == dict(archivo='base.json', sha256=sha(carpeta/'base.json')), 'Base no coincide')
        exigir(c['comprobacion'] == item['comprobacion'], 'Índice no coincide con caso')
        exigir((cid in LOCALES) == (c['operacion_local'] is not None), 'Alcance local cambiado')
        exigir(all(a in base['alias'] for a in c['ambito_puntos']), 'Punto ajeno')
        UUID(c['contexto']['ejecucion_id'])
        PrepararPriorizacion.model_validate(c['revision_simulada'])
        if c['entradas_tools']:
            s = SolicitudResolverRutas.model_validate(c['entradas_tools']['solicitud_rutas'])
            exigir(str(s.ejecucion_id) == c['contexto']['ejecucion_id'], 'Contexto distinto')
            entradas = [SolicitudValidarNecesidad.model_validate(d) for d in c['entradas_tools']['solicitudes_demanda']]
            exigir({d.punto_atencion_id for d in entradas} == {p.punto_atencion_id for p in s.puntos}, 'Validaciones incompletas')
            exigir(all(d.ejecucion_id == s.ejecucion_id and d.datos_version == s.datos_version for d in entradas), 'Versiones mezcladas')
        casos.append(c)
    exigir(len({c['contexto']['ejecucion_id'] for c in casos}) == 30, 'Casos comparten ejecución')
    exigir(len(Counter(c['grupo'] for c in casos)) == 5 and
           set(Counter(c['grupo'] for c in casos).values()) == {6}, 'Cinco grupos de seis casos requeridos')
    return base, casos


def priorizar(caso):
    entradas = deepcopy(caso['entradas_tools'])
    s = entradas['solicitud_rutas']
    validaciones = [validate_need(SolicitudValidarNecesidad.model_validate(d)) for d in entradas['solicitudes_demanda']]
    por_id = {str(v.punto_atencion_id): v for v in validaciones}
    metodos = {d['punto_atencion_id']: d['demanda']['metodo'] for d in entradas['solicitudes_demanda']}
    for n in s['necesidades']:
        r = por_id[n['punto_atencion_id']]
        n.update(estado_demanda=r.estado.value, demanda_litros=r.demanda_litros,
                 metodo_demanda=metodos[n['punto_atencion_id']],
                 confirmacion_demanda=r.confirmacion.model_dump(mode='json') if r.confirmacion else None,
                 estado_prioridad='pendiente', puntaje=None, componentes=None, posicion=None,
                 pendientes=[*r.faltantes, *r.motivos, 'prioridad_por_calcular'])
    solicitud = SolicitudResolverRutas.model_validate(s)
    ranking = score_needs(SolicitudPriorizarNecesidades(
        **{k: getattr(solicitud, k) for k in ('esquema_version', 'ejecucion_id', 'creado_en', 'origen')},
        datos_version=solicitud.datos_version, politica=solicitud.politica, necesidades=solicitud.necesidades))
    s['necesidades'] = [n.model_dump(mode='json') for n in ranking.evaluaciones]
    return SolicitudResolverRutas.model_validate(s), validaciones, ranking


def verificar(s, p):
    return verify_plan(SolicitudVerificarPlan(esquema_version=s.esquema_version,
        ejecucion_id=s.ejecucion_id, creado_en=s.creado_en, origen=s.origen,
        solicitud_original=s, propuesta=p))


def ejecutar_local(caso):
    e = caso['esperado']
    if caso['operacion_local'] == 'politica_inactiva':
        try:
            priorizar(caso)
        except ExcepcionContrato as error:
            exigir(error.detalle.codigo.value == e['error_dominio'], 'Error de dominio incorrecto')
            return dict(error_dominio=error.detalle.codigo.value)
        raise AssertionError('La política no activa fue aceptada')
    s, validaciones, ranking = priorizar(caso)
    obtenido = dict(validaciones=[v.model_dump(mode='json') for v in validaciones],
                    ranking=ranking.model_dump(mode='json'))
    if 'ranking_puntos' in e:
        exigir([str(n.punto_atencion_id) for n in ranking.evaluaciones] == e['ranking_puntos'],
               'Ranking global distinto')
    if 'estado_demanda' in e:
        v, n = validaciones[0], ranking.evaluaciones[0]
        exigir(v.estado.value == e['estado_demanda'], 'Estado de demanda distinto')
        exigir(v.demanda_litros == e['demanda_litros'], 'Litros de demanda distintos')
        exigir(n.estado_prioridad == e['estado_prioridad'], 'Estado de prioridad distinto')
        if 'puntaje' in e:
            exigir(math.isclose(n.puntaje, e['puntaje'], abs_tol=1e-9), 'Puntaje distinto')
    if caso['operacion_local'] in {'plan', 'snapshot_obsoleto'} or 'rutas' in e:
        p = solve_routes(s)
        v = verificar(s, p)
        metricas = medir_plan(s, p)
        obtenido.update(propuesta=p.model_dump(mode='json'), verificacion=v.model_dump(mode='json'), metricas=metricas)
        for campo, real in [('puntos_atendidos', metricas['cobertura_puntos']['atendidos']),
                            ('criticos_atendidos', metricas['cobertura_critica']['atendidos']),
                            ('litros_asignados', metricas['litros_asignados']),
                            ('deficit_litros', metricas['deficit_total_litros']),
                            ('rutas', len(p.rutas)), ('verificacion_valida', v.valido)]:
            if campo in e:
                exigir(real == e[campo], 'Oráculo no cumplido: '+campo)
        if 'punto_no_atendido' in e:
            pendiente = [n for n in p.no_atendidos if str(n.punto_atencion_id) == e['punto_no_atendido']]
            exigir(len(pendiente) == 1 and bool(pendiente[0].motivo.strip()), 'Falta motivo del punto pendiente')
        if caso['operacion_local'] == 'snapshot_obsoleto':
            cambiado = s.model_dump(mode='json')
            cambiado['vehiculos'][0]['capacidad_litros'] = 9000.0
            nuevo = SolicitudResolverRutas.model_validate(cambiado)
            despues = verificar(nuevo, p)
            exigir(v.valido == e['verificacion_antes'], 'Propuesta original inválida')
            exigir(despues.valido == e['verificacion_despues'], 'Snapshot obsoleto aceptado')
            exigir(any(x.codigo == e['codigo_violacion'] for x in despues.violaciones), 'Falta violación de versión')
            obtenido['snapshot_cambiado'] = nuevo.model_dump(mode='json')
            obtenido['verificacion_despues'] = despues.model_dump(mode='json')
    return obtenido


def ejecutar_dataset(carpeta, salida):
    # Validar TODO antes de ejecutar un caso. El destino siempre es nuevo.
    base, casos = validar_dataset(carpeta)
    salida.mkdir(parents=True, exist_ok=False)
    resultados = []
    for c in casos:
        inicio = perf_counter()
        if c['operacion_local'] is None:
            estado, obtenido = 'pendiente', dict(motivo='Caso de integración diseñado, no ejecutado; requiere proveedor/BD/Auth controlados.')
        else:
            try:
                obtenido = ejecutar_local(c)
                estado = 'aprobado'
            except AssertionError as error:
                estado, obtenido = 'fallido', dict(tipo_error=type(error).__name__, detalle=str(error))
            except Exception as error:
                estado, obtenido = 'error', dict(tipo_error=type(error).__name__,
                    detalle='Error inesperado de ejecución; revisar antes de repetir.')
        resultado = dict(id=c['id'], estado=estado, alcance=c['comprobacion'], esperado=c['esperado'],
                         obtenido=obtenido, duracion_ms=round((perf_counter()-inicio)*1000))
        with (salida/(c['id']+'.json')).open('x', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
        resultados.append(dict(id=c['id'], estado=estado, evidencia=c['id']+'.json'))
    informe = dict(esquema='escritorio-resultados-1', dataset_version=base['dataset_version'],
        registrado_en=datetime.now(timezone.utc).isoformat(), origen='sintetico',
        indice_sha256=sha(carpeta/'indice.json'), base_sha256=sha(carpeta/'base.json'),
        huellas_codigo={p:sha(RAIZ/p) for p in ('evals/escritorio.py', 'calculo/demanda.py',
            'calculo/prioridad.py', 'calculo/solver_v3.py', 'calculo/verificador.py')},
        cierre_integrado=False, resumen=resumir(resultados), casos=resultados)
    with (salida/'informe.json').open('x', encoding='utf-8') as f:
        json.dump(informe, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return informe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=DATASET)
    parser.add_argument('--salida', type=Path)
    parser.add_argument('--validar', action='store_true', help='Solo validar estructura/manifiesto/contratos')
    args = parser.parse_args()
    if args.validar:
        _, casos = validar_dataset(args.dataset)
        print(f'OK: {len(casos)} casos; validar datos no significa ejecutarlos.')
    else:
        if not args.salida:
            parser.error('--salida nueva es obligatoria para guardar resultados')
        r = ejecutar_dataset(args.dataset, args.salida)
        print(json.dumps(r['resumen'], ensure_ascii=False))
        raise SystemExit(1 if r['resumen']['fallido'] or r['resumen']['error'] else 2 if r['resumen']['pendiente'] else 0)
