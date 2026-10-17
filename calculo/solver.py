"""Prueba de rutas V1: cobertura completa de entradas sintéticas validadas.

No es todavía solve_routes de V3: no selecciona cobertura parcial por prioridad,
no verifica independientemente ni autoriza publicación.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import ceil, floor
from uuid import uuid5

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from contratos.errores import CodigoError, ErrorDominio, ExcepcionContrato
from contratos.modelos import PropuestaDistribucion
from contratos.solicitudes import SolicitudResolverRutas


def _error(entrada, codigo, mensaje, campos):
    raise ExcepcionContrato(ErrorDominio(
        esquema_version=entrada.esquema_version, ejecucion_id=entrada.ejecucion_id,
        creado_en=entrada.creado_en, origen=entrada.origen, codigo=codigo,
        mensaje=mensaje, recuperable=True, campos=campos,
    ))


def _mililitros(litros):
    valor = Decimal(str(litros)) * 1000
    if valor != valor.to_integral_value() or valor > 10**15:
        raise ValueError('V1 admite cantidades exactas hasta mililitros y hasta 10^12 litros.')
    return int(valor)


def solve_routes_minimo(entrada: SolicitudResolverRutas) -> PropuestaDistribucion:
    """Resuelve el ensayo V1 completo; no cambia la entrada ni usa red o BD.

    Exige origen sintético, política de ensayo activa y necesidades confirmadas
    en el fixture. Esas confirmaciones de prueba no acreditan permisos reales.
    Si no cubre todos los puntos, conserva todos como pendientes y bloquea salida.
    """
    entrada = SolicitudResolverRutas.model_validate(entrada.model_dump(mode='json'))
    if entrada.origen != 'sintetico' or entrada.matriz.origen != 'sintetico' or any(
        x.origen != 'sintetico'
        for x in [entrada.deposito, *entrada.vehiculos, *entrada.puntos, *entrada.necesidades]
    ):
        _error(entrada, CodigoError.CONTRATO_INVALIDO,
               'El solver mínimo V1 solo admite ensayos sintéticos.', ['origen'])
    if entrada.politica.estado != 'activa':
        _error(entrada, CodigoError.POLITICA_NO_ACTIVA,
               'Se requiere activación explícita de la política en el fixture de prueba.', ['politica'])
    if any(n.estado_demanda != 'validada' or n.estado_prioridad != 'calculada'
           or not n.demanda_litros or n.ventana_atencion is None for n in entrada.necesidades):
        _error(entrada, CodigoError.DATOS_INSUFICIENTES,
               'V1 requiere demandas positivas validadas, ranking y ventanas para todos los puntos.',
               ['necesidades'])

    contexto = dict(esquema_version=entrada.esquema_version,
                    ejecucion_id=entrada.ejecucion_id, creado_en=entrada.creado_en,
                    origen=entrada.origen, plan_id=entrada.plan_id, version=entrada.version,
                    datos_version=entrada.datos_version,
                    politica_version=entrada.politica.politica_version)

    def resultado(rutas, estado, motivo=None):
        return PropuestaDistribucion.model_validate({
            **contexto, 'estado': 'pendiente_revision', 'estado_solver': estado,
            'rutas': rutas,
            'no_atendidos': [] if motivo is None else [dict(
                incidente_id=n.incidente_id, punto_atencion_id=n.punto_atencion_id,
                clase_prioridad=n.clase_prioridad, demanda_pendiente_litros=n.demanda_litros,
                codigo='timeout' if estado == 'timeout_sin_solucion' else 'otro', motivo=motivo,
            ) for n in entrada.necesidades],
            'verificacion': None, 'aprobacion': None,
            'supuestos': [
                'Ensayo V1 sintético; no acredita flota, ubicaciones ni confirmaciones reales.',
                'Cobertura completa obligatoria: no selecciona reparto parcial por prioridad; V3 pendiente.',
                'Matriz sintética en minutos; descarga completa dentro de ventana y retorno dentro de turno.',
                'Cantidades exactas en mililitros; límites de tiempo redondeados conservadoramente a segundos.',
            ],
            'bloqueos_publicacion': ['Ensayo V1: falta verificador independiente e integración autorizada.']
                + ([motivo] if motivo else []),
        })

    vehiculos = sorted((v for v in entrada.vehiculos if v.disponible), key=lambda v: str(v.vehiculo_id))
    if not vehiculos:
        return resultado([], 'error', 'Sin vehículos disponibles; ensayo completo no resuelto.')
    ids = [entrada.deposito.deposito_id] + sorted(
        (p.punto_atencion_id for p in entrada.puntos), key=str)
    posiciones = {ident: i for i, ident in enumerate(entrada.matriz.nodos_ids)}
    matriz = [[entrada.matriz.minutos[posiciones[a]][posiciones[b]] for b in ids] for a in ids]
    necesidades = {n.punto_atencion_id: n for n in entrada.necesidades}
    servicios = {s.punto_atencion_id: s.descarga_minutos * 60 for s in entrada.servicios}
    carga = [0] + [_mililitros(necesidades[x].demanda_litros) for x in ids[1:]]
    capacidades = [_mililitros(v.capacidad_litros) for v in vehiculos]
    descarga = [0] + [servicios[x] for x in ids[1:]]
    if sum(carga) > sum(capacidades) or max(carga) > max(capacidades):
        return resultado([], 'error', 'Capacidad insuficiente para cobertura completa V1; selección parcial pendiente de V3.')

    base = min(v.turno.inicio for v in vehiculos).astimezone(timezone.utc).replace(microsecond=0)
    segundos = lambda fecha: (fecha.astimezone(timezone.utc) - base).total_seconds()
    horizonte = floor(max(segundos(v.turno.fin) for v in vehiculos))
    if horizonte > 10**9:
        _error(entrada, CodigoError.CONTRATO_INVALIDO, 'Horizonte de ensayo V1 excesivo.', ['vehiculos.turno'])
    ventanas = [(0, horizonte)]
    for ident in ids[1:]:
        ventana = necesidades[ident].ventana_atencion
        inicio = max(0, ceil(segundos(ventana.inicio)))
        fin = min(horizonte - servicios[ident], floor(segundos(ventana.fin) - servicios[ident]))
        if inicio > fin:
            return resultado([], 'error', 'Ventana insuficiente para descarga completa dentro del horizonte V1.')
        ventanas.append((inicio, fin))

    manager = pywrapcp.RoutingIndexManager(len(ids), len(vehiculos), 0)
    routing = pywrapcp.RoutingModel(manager)

    def transito(a, b):
        i, j = manager.IndexToNode(a), manager.IndexToNode(b)
        viaje = matriz[i][j]
        return (viaje * 60 if viaje is not None else horizonte + 1) + descarga[i]

    transit = routing.RegisterTransitCallback(transito)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    demanda = routing.RegisterUnaryTransitCallback(lambda i: carga[manager.IndexToNode(i)])
    routing.AddDimensionWithVehicleCapacity(demanda, 0, capacidades, True, 'Carga')
    routing.AddDimension(transit, horizonte, horizonte, False, 'Tiempo')
    tiempo = routing.GetDimensionOrDie('Tiempo')
    for node in range(1, len(ids)):
        tiempo.CumulVar(manager.NodeToIndex(node)).SetRange(*ventanas[node])
    for v, vehiculo in enumerate(vehiculos):
        inicio, fin = ceil(segundos(vehiculo.turno.inicio)), floor(segundos(vehiculo.turno.fin))
        if inicio > fin:
            return resultado([], 'error', 'Turno sin intervalo representable en segundos.')
        tiempo.CumulVar(routing.Start(v)).SetRange(inicio, fin)
        tiempo.CumulVar(routing.End(v)).SetRange(inicio, fin)
    # Primero fija los retornos tempranos para las rutas elegidas. Después,
    # retrasa las salidas sin posponer esos retornos y reduce la espera inicial.
    # Maximizar Start antes de fijar End empujaría las rutas al final del turno.
    for v in range(len(vehiculos)):
        routing.AddVariableMinimizedByFinalizer(tiempo.CumulVar(routing.End(v)))
    for v in range(len(vehiculos)):
        routing.AddVariableMaximizedByFinalizer(tiempo.CumulVar(routing.Start(v)))
    # null es arco bloqueado, también hacia los índices de retorno de cada camión.
    destinos = list(range(routing.Size())) + [routing.End(v) for v in range(len(vehiculos))]
    for a in range(routing.Size()):
        for b in destinos:
            if matriz[manager.IndexToNode(a)][manager.IndexToNode(b)] is None:
                routing.NextVar(a).RemoveValue(b)
    parametros = pywrapcp.DefaultRoutingSearchParameters()
    parametros.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parametros.time_limit.seconds = entrada.limite_solver_segundos
    solucion = routing.SolveWithParameters(parametros)
    if solucion is None:
        timeout = routing.status() == routing_enums_pb2.RoutingSearchStatus.ROUTING_FAIL_TIMEOUT
        return resultado([], 'timeout_sin_solucion' if timeout else 'error',
                         'Tiempo agotado sin solución.' if timeout else
                         'No se encontró cobertura completa V1; no se afirma inviabilidad del reparto parcial.')

    fecha = lambda valor: base + timedelta(seconds=valor)
    rutas = []
    for v, vehiculo in enumerate(vehiculos):
        index = routing.Start(v)
        salida = solucion.Value(tiempo.CumulVar(index))
        ultimo_fin, anterior, paradas = salida, 0, []
        index = solucion.Value(routing.NextVar(index))
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            n = necesidades[ids[node]]
            inicio = solucion.Value(tiempo.CumulVar(index))
            fin = inicio + descarga[node]
            paradas.append(dict(
                parada_id=uuid5(entrada.plan_id, f'v1:{entrada.version}:{vehiculo.vehiculo_id}:{ids[node]}'),
                punto_atencion_id=ids[node], incidente_id=n.incidente_id, orden=len(paradas) + 1,
                litros_asignados=n.demanda_litros,
                llegada_estimada=fecha(ultimo_fin + matriz[anterior][node] * 60),
                inicio_descarga=fecha(inicio), fin_descarga=fecha(fin), estado='programada',
            ))
            ultimo_fin, anterior = fin, node
            index = solucion.Value(routing.NextVar(index))
        if paradas:
            rutas.append(dict(vehiculo_id=vehiculo.vehiculo_id, deposito_id=entrada.deposito.deposito_id,
                              salida_estimada=fecha(salida),
                              retorno_estimado=fecha(solucion.Value(tiempo.CumulVar(index))), paradas=paradas))
    return resultado(rutas, 'factible')
