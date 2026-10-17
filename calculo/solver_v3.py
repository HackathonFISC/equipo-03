"""Rutas del MVP (hasta seis puntos) y selección de cobertura con OR-Tools CP-SAT."""
import hashlib
import itertools
import json
import time
from datetime import timedelta, timezone
from decimal import Decimal
from uuid import uuid5

from ortools.sat.python import cp_model

from contratos.errores import CodigoError, ErrorDominio, ExcepcionContrato
from contratos.modelos import PropuestaDistribucion
from contratos.solicitudes import SolicitudPriorizarNecesidades, SolicitudResolverRutas
from .prioridad import score_needs


def _error(s, codigo, mensaje, campos):
    raise ExcepcionContrato(ErrorDominio(esquema_version=s.esquema_version, ejecucion_id=s.ejecucion_id,
        creado_en=s.creado_en, origen=s.origen, codigo=codigo, mensaje=mensaje,
        recuperable=True, campos=campos))


def _cantidad(litros):
    valor = Decimal(str(litros)) * 1000
    if valor != valor.to_integral_value() or valor > 10**15:
        raise ValueError('Cantidades hasta mililitros y máximo 10^12 litros por valor.')
    return int(valor)


def _us(delta):
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _rutas_candidatas(s, vehiculos, elegibles, deadline, ignorar_capacidad=False):
    """Enumeración finita exacta; guarda la mejor ruta por vehículo y subconjunto."""
    deposito = s.deposito.deposito_id
    indices = {ident: i for i, ident in enumerate(s.matriz.nodos_ids)}
    servicios = {v.punto_atencion_id: v.descarga_minutos * 60_000_000 for v in s.servicios}
    base = min(v.turno.inicio for v in vehiculos).astimezone(timezone.utc)

    def viaje(a, b):
        minutos = s.matriz.minutos[indices[a]][indices[b]]
        return None if minutos is None else minutos * 60_000_000

    mejores = {}
    orden = sorted(elegibles, key=str)
    for v in vehiculos:
        capacidad = _cantidad(v.capacidad_litros)
        desde, hasta = _us(v.turno.inicio - base), _us(v.turno.fin - base)
        for longitud in range(1, len(orden) + 1):
            for secuencia in itertools.permutations(orden, longitud):
                if time.monotonic() >= deadline:
                    return list(mejores.values()), False
                if not ignorar_capacidad and sum(_cantidad(elegibles[p].demanda_litros) for p in secuencia) > capacidad:
                    continue
                reloj, anterior, inicios = desde, deposito, []
                for pid in secuencia:
                    tramo = viaje(anterior, pid)
                    if tramo is None:
                        break
                    n = elegibles[pid]
                    inicio = max(reloj + tramo, _us(n.ventana_atencion.inicio - base))
                    reloj = inicio + servicios[pid]
                    if reloj > _us(n.ventana_atencion.fin - base) or reloj > hasta:
                        break
                    inicios.append(inicio)
                    anterior = pid
                if len(inicios) != len(secuencia):
                    continue
                regreso = viaje(secuencia[-1], deposito)
                if regreso is None or reloj + regreso > hasta:
                    continue
                retorno = reloj + regreso
                # Retorno más temprano; luego salida más tardía compatible con él.
                limite = reloj
                tardios = [0] * len(secuencia)
                for i in range(len(secuencia) - 1, -1, -1):
                    pid = secuencia[i]
                    tardios[i] = min(limite, _us(elegibles[pid].ventana_atencion.fin - base)) - servicios[pid]
                    if i:
                        limite = tardios[i] - viaje(secuencia[i - 1], pid)
                salida = tardios[0] - viaje(deposito, secuencia[0])
                paradas, reloj, anterior = [], salida, deposito
                fecha = lambda valor: base + timedelta(microseconds=valor)
                for i, pid in enumerate(secuencia):
                    fin = tardios[i] + servicios[pid]
                    paradas.append(dict(parada_id=uuid5(s.plan_id, f'v3:{s.version}:{v.vehiculo_id}:{pid}'),
                        punto_atencion_id=pid, incidente_id=elegibles[pid].incidente_id, orden=i + 1,
                        litros_asignados=elegibles[pid].demanda_litros,
                        llegada_estimada=fecha(reloj + viaje(anterior, pid)),
                        inicio_descarga=fecha(tardios[i]), fin_descarga=fecha(fin), estado='programada'))
                    reloj, anterior = fin, pid
                ruta = dict(vehiculo_id=v.vehiculo_id, deposito_id=deposito,
                            salida_estimada=fecha(salida), retorno_estimado=fecha(retorno), paradas=paradas)
                clave = (v.vehiculo_id, frozenset(secuencia))
                criterio = (retorno - salida, retorno, -salida, tuple(map(str, secuencia)))
                candidato = dict(ruta=ruta, puntos=frozenset(secuencia), coste=retorno - salida, criterio=criterio)
                if clave not in mejores or criterio < mejores[clave]['criterio']:
                    mejores[clave] = candidato
    return sorted(mejores.values(), key=lambda c: (str(c['ruta']['vehiculo_id']),
                  tuple(str(p['punto_atencion_id']) for p in c['ruta']['paradas']))), True


def _seleccionar(candidatas, elegibles, vehiculos, segundos):
    inicio_modelo = time.monotonic()
    modelo = cp_model.CpModel()
    decisiones = [modelo.new_bool_var(f'ruta_{i}') for i in range(len(candidatas))]
    for v in vehiculos:
        modelo.add(sum(x for x, c in zip(decisiones, candidatas) if c['ruta']['vehiculo_id'] == v.vehiculo_id) <= 1)
    for pid in elegibles:
        modelo.add(sum(x for x, c in zip(decisiones, candidatas) if pid in c['puntos']) <= 1)
    modelo.add(sum(decisiones) >= 1)
    # Máximo número de críticos; después lexicografía del ranking; finalmente duración.
    ordenadas = sorted(elegibles.values(), key=lambda n: (n.clase_prioridad != 'critico', n.posicion, str(n.incidente_id)))
    dominante = 2 ** len(ordenadas)
    pesos = {n.punto_atencion_id: (dominante if n.clase_prioridad == 'critico' else 0)
             + 2 ** (len(ordenadas) - i - 1) for i, n in enumerate(ordenadas)}
    max_coste = sum(max((c['coste'] for c in candidatas if c['ruta']['vehiculo_id'] == v.vehiculo_id), default=0)
                    for v in vehiculos) + 1
    modelo.maximize(sum(x * (sum(pesos[p] for p in c['puntos']) * max_coste - c['coste'])
                        for x, c in zip(decisiones, candidatas)))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    restante = segundos - (time.monotonic() - inicio_modelo)
    if restante <= 0:
        return [], cp_model.UNKNOWN
    solver.parameters.max_time_in_seconds = restante
    estado = solver.solve(modelo)
    seleccion = [c for x, c in zip(decisiones, candidatas) if solver.value(x)] if estado in (cp_model.OPTIMAL, cp_model.FEASIBLE) else []
    return seleccion, estado


def solve_routes(entrada: SolicitudResolverRutas) -> PropuestaDistribucion:
    inicio = time.monotonic()
    s = SolicitudResolverRutas.model_validate(entrada.model_dump(mode='json'))
    if s.politica.estado != 'activa':
        _error(s, CodigoError.POLITICA_NO_ACTIVA, 'La política necesita activación explícita.', ['politica.estado'])
    posiciones = [n.posicion for n in s.necesidades if n.estado_prioridad == 'calculada']
    if len(posiciones) != len(set(posiciones)):
        _error(s, CodigoError.CONTRATO_INVALIDO, 'Ranking con posiciones calculadas duplicadas.', ['necesidades.posicion'])
    recalculadas = score_needs(SolicitudPriorizarNecesidades(
        esquema_version=s.esquema_version, ejecucion_id=s.ejecucion_id,
        creado_en=s.creado_en, origen=s.origen, datos_version=s.datos_version,
        politica=s.politica, necesidades=s.necesidades)).evaluaciones
    previas = {n.incidente_id: n for n in s.necesidades if n.estado_prioridad == 'calculada'}
    esperadas = {n.incidente_id: n for n in recalculadas}
    if any(esperadas[ident].estado_prioridad != 'calculada'
           or n.puntaje != esperadas[ident].puntaje or n.componentes != esperadas[ident].componentes
           for ident, n in previas.items()) or [n.incidente_id for n in sorted(previas.values(), key=lambda n: n.posicion)] != [
               n.incidente_id for n in recalculadas if n.incidente_id in previas]:
        _error(s, CodigoError.CONTRATO_INVALIDO,
               'Puntajes, componentes u orden no corresponden a los factores y política del snapshot; volver a priorizar.',
               ['necesidades', 'politica'])
    vehiculos = sorted((v for v in s.vehiculos if v.disponible), key=lambda v: str(v.vehiculo_id))
    if vehiculos and _us(max(v.turno.fin for v in vehiculos) - min(v.turno.inicio for v in vehiculos)) > 10**13:
        _error(s, CodigoError.CONTRATO_INVALIDO, 'Horizonte de planificación excesivo para el MVP.', ['vehiculos.turno'])
    try:
        for v in s.vehiculos:
            _cantidad(v.capacidad_litros)
        for n in s.necesidades:
            if n.demanda_litros is not None:
                _cantidad(n.demanda_litros)
    except ValueError as error:
        _error(s, CodigoError.CONTRATO_INVALIDO, str(error), ['demanda_litros', 'capacidad_litros'])
    huella = hashlib.sha256(json.dumps(s.model_dump(mode='json'), sort_keys=True,
                                      separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
    razones, elegibles = {}, {}
    for n in s.necesidades:
        pid = n.punto_atencion_id
        if n.estado_demanda != 'validada' or n.estado_prioridad != 'calculada' or n.ventana_atencion is None:
            razones[pid] = ('datos_pendientes', 'Faltan demanda validada, prioridad calculada o ventana de atención; revisar evidencia.')
        elif n.demanda_litros == 0:
            razones[pid] = ('otro', 'Demanda neta cero: no necesita visita ni se inventan litros asignados.')
        elif not vehiculos:
            razones[pid] = ('sin_capacidad', 'No hay cisternas disponibles en esta versión de flota.')
        elif n.demanda_litros > max(v.capacidad_litros for v in vehiculos):
            razones[pid] = ('demanda_supera_vehiculo', 'Demanda indivisible mayor que cualquier cisterna disponible; sin dividir ni recargar.')
        else:
            elegibles[pid] = n
    deadline = inicio + s.limite_solver_segundos
    seleccion, completa, estado = [], True, 'factible'
    candidatas = []
    if elegibles:
        candidatas, completa = _rutas_candidatas(s, vehiculos, elegibles, deadline)
        restante = deadline - time.monotonic()
        if not completa or restante <= 0:
            estado = 'timeout_sin_solucion'
        elif candidatas:
            seleccion, estado_cp = _seleccionar(candidatas, elegibles, vehiculos, restante)
            if estado_cp == cp_model.UNKNOWN:
                estado = 'timeout_sin_solucion'
            elif estado_cp not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                estado = 'error'
        else:
            estado_cp = None
            estado = 'inviabilidad_demostrada'
    else:
        estado_cp = None
        if any(r[0] == 'datos_pendientes' for r in razones.values()):
            estado = 'error'
        elif any(n.demanda_litros is None or n.demanda_litros > 0 for n in s.necesidades):
            estado = 'inviabilidad_demostrada'
    atendidos = set().union(*(c['puntos'] for c in seleccion)) if seleccion else set()
    rutas_posibles = set().union(*(c['puntos'] for c in candidatas)) if candidatas else set()
    indices = {pid: i for i, pid in enumerate(s.matriz.nodos_ids)}

    def conectado(pid):
        # Diagnóstico estructural, distinto de factibilidad temporal/capacidad conjunta.
        nodos = {s.deposito.deposito_id, *elegibles}
        def alcanza(origen, destino):
            vistos, cola = {origen}, [origen]
            while cola:
                a = cola.pop()
                for b in nodos - vistos:
                    if s.matriz.minutos[indices[a]][indices[b]] is not None:
                        vistos.add(b)
                        cola.append(b)
            return destino in vistos
        return alcanza(s.deposito.deposito_id, pid) and alcanza(pid, s.deposito.deposito_id)

    # Separar imposibilidad temporal de caminos que necesitan cargar otros puntos
    # y solo fallan por capacidad. No atribuir a una ventana un fallo de capacidad.
    relajadas, diagnostico_completo = [], False
    if completa and estado not in ('timeout_sin_solucion', 'error') and any(
            p not in rutas_posibles and conectado(p) for p in elegibles):
        relajadas, diagnostico_completo = _rutas_candidatas(s, vehiculos, elegibles, deadline, True)
    posibles_sin_capacidad = set().union(*(c['puntos'] for c in relajadas)) if relajadas else set()

    pendientes = []
    for n in sorted(s.necesidades, key=lambda n: str(n.punto_atencion_id)):
        pid = n.punto_atencion_id
        if pid in atendidos:
            continue
        if pid in razones:
            codigo, motivo = razones[pid]
        elif estado == 'timeout_sin_solucion':
            codigo, motivo = 'timeout', 'Presupuesto agotado sin propuesta; no demuestra inviabilidad del punto.'
        elif estado == 'error':
            codigo, motivo = 'otro', 'Error del modelo de selección; no se afirma inviabilidad.'
        elif pid not in rutas_posibles:
            if not conectado(pid):
                codigo, motivo = 'sin_acceso', 'Sin recorrido dirigido desde el depósito y de regreso en los arcos permitidos.'
            elif diagnostico_completo and pid not in posibles_sin_capacidad:
                codigo, motivo = 'ventana', 'Ninguna ruta cumple turnos, ventana y descarga incluso relajando capacidad, con la matriz indicada.'
            elif diagnostico_completo:
                codigo, motivo = 'sin_capacidad', 'El punto admite recorrido temporal al relajar capacidad, pero ninguno con la carga indivisible de la flota disponible.'
            else:
                codigo, motivo = 'otro', 'Sin ruta factible para el punto; diagnóstico adicional no completado dentro del presupuesto. No se atribuye una causa individual no probada.'
        else:
            cargas = {v.vehiculo_id: _cantidad(v.capacidad_litros) for v in vehiculos}
            for c in seleccion:
                cargas[c['ruta']['vehiculo_id']] -= sum(_cantidad(elegibles[p].demanda_litros) for p in c['puntos'])
            codigo = 'sin_capacidad' if _cantidad(n.demanda_litros) > max(cargas.values(), default=0) else 'otro'
            motivo = ('No cabe íntegramente en la capacidad restante de las rutas elegidas por prioridad.'
                      if codigo == 'sin_capacidad' else 'Tiene rutas individuales factibles; queda fuera de la combinación elegida por prioridad y restricciones conjuntas. No implica imposibilidad individual.')
        pendientes.append(dict(incidente_id=n.incidente_id, punto_atencion_id=pid, clase_prioridad=n.clase_prioridad,
                               demanda_pendiente_litros=n.demanda_litros, codigo=codigo, motivo=motivo))
    bloqueos = ['Sin verificación independiente ni aprobación autorizada de esta versión.',
                'Política sintética: el cálculo no acredita autorización operativa ni calidad del agua.']
    if any((n.clase_prioridad == 'critico' and n.demanda_litros != 0) or
           (n.requiere_revision_urgente and n.estado_prioridad == 'pendiente')
           for n in s.necesidades if n.punto_atencion_id not in atendidos):
        bloqueos.append('Cobertura crítica o posible urgencia pendiente: escalar y bloquear publicación.')
    if estado != 'factible':
        bloqueos.append(f'Estado del solver: {estado}; sin reparto positivo autorizado.')
    optimo = bool(elegibles and completa and candidatas and estado == 'factible' and estado_cp == cp_model.OPTIMAL)
    return PropuestaDistribucion.model_validate(dict(esquema_version=s.esquema_version,
        ejecucion_id=s.ejecucion_id, creado_en=s.creado_en, origen=s.origen,
        plan_id=s.plan_id, version=s.version, datos_version=s.datos_version,
        politica_version=s.politica.politica_version, estado='pendiente_revision', estado_solver=estado,
        rutas=[c['ruta'] for c in seleccion], no_atendidos=pendientes, verificacion=None, aprobacion=None,
        bloqueos_publicacion=bloqueos, supuestos=[
            'Una salida por vehículo, sin recargas ni entregas divididas; matriz dirigida por UUID y descarga completa dentro de ventana.',
            'Objetivo: máximo número de críticos cubiertos, luego orden lexicográfico del ranking, luego mínima duración total de rutas.',
            'Óptimo demostrado para ese objetivo en este snapshot.' if optimo else 'No se declara optimalidad global de cobertura.',
            f'Matriz {s.matriz.matriz_version}, origen {s.matriz.origen}; no certifica acceso vial, recepción ni condiciones sanitarias.',
            'Cantidades exactas hasta mililitros; fechas y viajes con precisión de microsegundos.',
            'HUELLA_ENTRADAS_SHA256=' + huella]))
