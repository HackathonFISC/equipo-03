"""Métricas de evaluación: un pendiente nunca cuenta como aprobado."""
from collections import Counter
from decimal import Decimal

from contratos.modelos import PropuestaDistribucion
from contratos.solicitudes import SolicitudResolverRutas


def resumir(resultados):
    estados = Counter(r['estado'] for r in resultados)
    permitidos = {'aprobado', 'fallido', 'pendiente', 'error'}
    if set(estados) - permitidos:
        raise ValueError('Estado de evaluación desconocido')
    total = len(resultados)
    ejecutados = estados['aprobado'] + estados['fallido'] + estados['error']
    return dict(total=total, ejecutados=ejecutados,
                **{e: estados[e] for e in sorted(permitidos)},
                cobertura_ejecucion=ejecutados / total if total else None,
                tasa_exito_ejecutados=estados['aprobado'] / ejecutados if ejecutados else None,
                proporcion_aprobada_total=estados['aprobado'] / total if total else None)


def _cobertura(atendidos, universo):
    return dict(atendidos=len(atendidos & universo), total=len(universo),
                fraccion=len(atendidos & universo) / len(universo) if universo else None)


def medir_plan(entrada: SolicitudResolverRutas, propuesta: PropuestaDistribucion):
    """Métricas del snapshot; desconocidos se cuentan aparte, nunca como demanda cero.

    El llamador debe conservar el informe del verificador independiente. Estas
    sumas no sustituyen comprobaciones físicas, sanitarias o de vigencia en BD.
    """
    s = SolicitudResolverRutas.model_validate(entrada.model_dump(mode='json'))
    p = PropuestaDistribucion.model_validate(propuesta.model_dump(mode='json'))
    if (p.plan_id, p.version, p.datos_version, p.politica_version, p.ejecucion_id, p.origen) != (
            s.plan_id, s.version, s.datos_version, s.politica.politica_version, s.ejecucion_id, s.origen):
        raise ValueError('Métricas requieren la misma versión y ejecución')
    necesidades = {n.punto_atencion_id: n for n in s.necesidades}
    asignados = {pa.punto_atencion_id: Decimal(str(pa.litros_asignados))
                for ruta in p.rutas for pa in ruta.paradas}
    for pid, litros in asignados.items():
        n = necesidades.get(pid)
        if n is None or n.estado_demanda != 'validada' or n.demanda_litros is None or litros != Decimal(str(n.demanda_litros)):
            raise ValueError('No medir como cobertura una cantidad desconocida, parcial o ajena')
    atendidos = set(asignados)
    # No excluir por capacidad/acceso: hacerlo ocultaría la necesidad no cubierta.
    requeridos = {pid for pid, n in necesidades.items()
                  if n.estado_demanda != 'validada' or n.demanda_litros != 0}
    criticos = {pid for pid in requeridos if necesidades[pid].clase_prioridad == 'critico'}
    generales = {pid for pid in requeridos if necesidades[pid].clase_prioridad == 'general'}
    calculables = {pid for pid, n in necesidades.items() if n.estado_demanda == 'validada'
                   and n.estado_prioridad == 'calculada' and n.ventana_atencion is not None
                   and n.demanda_litros is not None and n.demanda_litros > 0}
    conocidas = {pid: Decimal(str(n.demanda_litros)) for pid, n in necesidades.items() if n.demanda_litros is not None}
    deficit = {pid: litros - asignados.get(pid, Decimal(0)) for pid, litros in conocidas.items()}
    indices = {pid: i for i, pid in enumerate(s.matriz.nodos_ids)}
    viaje = 0
    tramos = 0
    for ruta in p.rutas:
        nodos = [s.deposito.deposito_id, *[pa.punto_atencion_id for pa in ruta.paradas], s.deposito.deposito_id]
        for a, b in zip(nodos, nodos[1:]):
            minutos = s.matriz.minutos[indices[a]][indices[b]]
            if minutos is None:
                raise ValueError('No medir un viaje por un arco bloqueado')
            viaje += minutos
            tramos += 1
    servicios = {x.punto_atencion_id: x.descarga_minutos for x in s.servicios}
    def minutos(delta):
        micro = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
        return Decimal(micro) / Decimal(60_000_000)
    return dict(
        cobertura_puntos=_cobertura(atendidos, set(necesidades)),
        cobertura_critica=_cobertura(atendidos, criticos),
        cobertura_critica_calculable=_cobertura(atendidos, criticos & calculables),
        cobertura_clase_general=_cobertura(atendidos, generales),
        puntos_requeridos=len(requeridos), puntos_calculables=len(calculables),
        criticos_sin_datos=len(criticos - calculables),
        puntos_sin_clase=sum(n.clase_prioridad is None for n in necesidades.values()),
        puntos_demanda_desconocida=sum(n.demanda_litros is None for n in necesidades.values()),
        puntos_demanda_no_validada=sum(n.estado_demanda != 'validada' for n in necesidades.values()),
        puntos_sin_visita=len(necesidades) - len(atendidos),
        puntos_demanda_cero_validada=sum(n.estado_demanda == 'validada' and n.demanda_litros == 0 for n in necesidades.values()),
        demanda_conocida_litros=float(sum(conocidas.values(), Decimal(0))),
        demanda_validada_litros=float(sum((Decimal(str(n.demanda_litros)) for n in necesidades.values()
            if n.estado_demanda == 'validada' and n.demanda_litros is not None), Decimal(0))),
        litros_asignados=float(sum(asignados.values(), Decimal(0))),
        deficit_conocido_litros=float(sum(deficit.values(), Decimal(0))),
        deficit_total_litros=(float(sum(deficit.values(), Decimal(0)))
                             if all(n.demanda_litros is not None for n in necesidades.values()) else None),
        deficit_critico_conocido_litros=float(sum((d for pid, d in deficit.items() if pid in criticos), Decimal(0))),
        deficit_total_completo=all(n.demanda_litros is not None for n in necesidades.values()),
        salidas_deposito=len(p.rutas), tramos=tramos,
        viaje_total_minutos=viaje, servicio_total_minutos=sum(servicios[pid] for pid in atendidos),
        duracion_rutas_minutos=float(sum((minutos(r.retorno_estimado-r.salida_estimada) for r in p.rutas), Decimal(0))),
        espera_en_puntos_minutos=float(sum((minutos(pa.inicio_descarga-pa.llegada_estimada)
            for r in p.rutas for pa in r.paradas), Decimal(0))))
