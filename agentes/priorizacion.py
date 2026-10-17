"""Adaptador a las funciones de José. No estima cantidades ni activa políticas."""
from datetime import datetime, timezone
from contratos.modelos import EvaluacionNecesidades, PoliticaPrioridad
from contratos.solicitudes import (SolicitudValidarNecesidad, ResultadoValidarNecesidad,
    SolicitudPriorizarNecesidades, ResultadoPriorizarNecesidades)


def evaluar_lote(contexto, entradas, politica, herramientas, *, validaciones=None):
    """Entradas revisadas por punto; un solo lote, con pendientes incluidos.

    El backend conserva procedencia, confirmaciones y versiones. Población y
    litros proceden de una entrada consolidada, nunca de sumar mensajes.
    """
    politica = PoliticaPrioridad.model_validate(politica)
    if politica.estado != 'activa':
        raise ValueError('politica_no_activa')
    if not entradas:
        raise ValueError('lote_vacio')
    evaluaciones = []
    for fila in entradas:
        solicitud = SolicitudValidarNecesidad.model_validate({**fila['solicitud_demanda'], **contexto})
        demanda = ResultadoValidarNecesidad.model_validate(herramientas.validate_need(solicitud))
        if (demanda.ejecucion_id, demanda.incidente_id, demanda.punto_atencion_id, demanda.datos_version, demanda.origen, demanda.metodo) != (
                solicitud.ejecucion_id, solicitud.incidente_id, solicitud.punto_atencion_id, solicitud.datos_version, solicitud.origen, solicitud.demanda.metodo):
            raise ValueError('Resultado de demanda con identidad o versión incompatible')
        if validaciones is not None:
            validaciones[str(demanda.incidente_id)] = demanda.model_dump(mode='json')
        evaluaciones.append(EvaluacionNecesidades.model_validate({**fila['evaluacion'], **contexto,
            'incidente_id': demanda.incidente_id, 'punto_atencion_id': demanda.punto_atencion_id,
            'datos_version': demanda.datos_version, 'politica_version': politica.politica_version,
            'estado_demanda': demanda.estado, 'demanda_litros': demanda.demanda_litros,
            'metodo_demanda': demanda.metodo, 'confirmacion_demanda': demanda.confirmacion,
            'estado_prioridad': 'pendiente', 'puntaje': None, 'componentes': None, 'posicion': None,
            'pendientes': list(dict.fromkeys([*demanda.faltantes, *demanda.motivos, *fila.get('pendientes', []), 'prioridad_por_calcular'])),
            'supuestos': demanda.supuestos}))
    peticion = SolicitudPriorizarNecesidades(**contexto, datos_version=evaluaciones[0].datos_version,
                                            politica=politica, necesidades=evaluaciones)
    resultado = ResultadoPriorizarNecesidades.model_validate(herramientas.score_needs(peticion))
    if resultado.ejecucion_id != peticion.ejecucion_id or resultado.datos_version != peticion.datos_version or resultado.politica_version != politica.politica_version:
        raise ValueError('Ranking con contexto incompatible')
    if {e.incidente_id for e in resultado.evaluaciones} != {e.incidente_id for e in evaluaciones}:
        raise ValueError('El ranking omitió o añadió incidentes')
    originales = {e.incidente_id: e for e in evaluaciones}
    modificables = {'estado_prioridad', 'puntaje', 'componentes', 'posicion', 'pendientes', 'requiere_revision_urgente'}
    for evaluacion in resultado.evaluaciones:
        if evaluacion.model_dump(exclude=modificables) != originales[evaluacion.incidente_id].model_dump(exclude=modificables):
            raise ValueError('Priorizar no debe modificar datos consolidados ni demanda')
    return resultado


class HerramientasJose:
    def __init__(self):
        from calculo.demanda import validate_need
        from calculo.prioridad import score_needs
        self.validate_need = validate_need
        self.score_needs = score_needs


def procesar_priorizacion(ejecucion_id, db, trabajador_id, herramientas=None):
    from agentes.lotes_confirmados import preparar_lote_automatico
    preparacion = preparar_lote_automatico(db, ejecucion_id, herramientas)
    if preparacion['estado'] not in {'preparado', 'existente'}:
        return preparacion
    filas = db.rpc('ra_tomar_etapa_v2', {'p_ejecucion_id': str(ejecucion_id),
        'p_trabajador_id': trabajador_id, 'p_etapa': 'priorizacion'}).execute().data
    if filas is None:
        return {'estado': 'no_tomada'}
    pendientes = []
    resultado = None
    validaciones = {}
    if not filas.get('lote_calculo'):
        pendientes.append('Falta lote consolidado y versionado de cálculo; no sumar reportes automáticamente.')
    else:
        actuales = {i['incidente_id']: i for i in filas['incidentes']}
        for entrada in filas['lote_calculo'].get('entradas', []):
            incidente = actuales.get(entrada['solicitud_demanda']['incidente_id'])
            if incidente is None or incidente['version'] != entrada.get('version_incidente'):
                pendientes.append('El incidente cambió; revisar el lote y preparar nueva datos_version.')
                break
        try:
            herramientas = herramientas or HerramientasJose()
        except ImportError:
            pendientes.append('Faltan validate_need y score_needs de José.')
        if not pendientes:
            lote = filas['lote_calculo']
            resultado = evaluar_lote({'esquema_version': '1.0', 'ejecucion_id': str(ejecucion_id),
                'creado_en': datetime.now(timezone.utc).isoformat(), 'origen': filas['ejecucion']['origen']},
                lote['entradas'], lote['politica'], herramientas, validaciones=validaciones).model_dump(mode='json')
    return db.rpc('ra_finalizar_priorizacion_v2', {'p_ejecucion_id': str(ejecucion_id),
        'p_trabajador_id': trabajador_id, 'p_snapshot': filas, 'p_resultado': resultado,
        'p_pendientes': pendientes, 'p_validaciones': validaciones}).execute().data
