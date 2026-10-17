"""Reutiliza un lote humano vigente sin fabricar confirmaciones ni autorizar planes."""
from copy import deepcopy
from hashlib import md5
from pydantic import ValidationError
from contratos.errores import ExcepcionContrato
from contratos.modelos import EvaluacionNecesidades, PoliticaPrioridad
from contratos.solicitudes import SolicitudValidarNecesidad
from agentes.priorizacion import HerramientasJose


def construir_lote_confirmado(snapshot, herramientas=None):
    e = snapshot['ejecucion']
    revision = snapshot['revision']
    lote = deepcopy(revision['lote'])
    PoliticaPrioridad.model_validate(lote['politica'])
    dv = 'auto-' + md5((e['ejecucion_id'] + revision['evento_id']).encode()).hexdigest()
    herramientas = herramientas or HerramientasJose()
    for entrada in lote['entradas']:
        for campo in ('solicitud_demanda', 'evaluacion'):
            entrada[campo].update(ejecucion_id=e['ejecucion_id'], datos_version=dv, creado_en=e['creado_en'])
        solicitud = SolicitudValidarNecesidad.model_validate(entrada['solicitud_demanda'])
        EvaluacionNecesidades.model_validate(entrada['evaluacion'])
        resultado = herramientas.validate_need(solicitud)
        if resultado.estado != 'validada' or resultado.faltantes or resultado.motivos:
            raise ValueError('La demanda o recepción requieren revisión.')
    # Devolver el JSON original adaptado al contexto nuevo: confirma lo mismo,
    # con las identidades y fechas originales del coordinador, sin nuevos valores.
    return lote


def preparar_lote_automatico(db, ejecucion_id, herramientas=None):
    parametros = {'p_ejecucion_id': str(ejecucion_id)}
    snapshot = db.rpc('ra_contexto_lote_confirmado_v2', parametros).execute().data
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('ejecucion'), dict):
        raise RuntimeError('Contexto inválido de preparación automática; revisar 0017.')
    e = snapshot['ejecucion']
    if e.get('entrada_priorizacion') is not None:
        return {'estado': 'existente'}
    if e['etapa'] != 'priorizacion' or e['estado'] not in {'pendiente', 'espera_revision', 'espera_validacion'}:
        return {'estado': 'no_disponible'}
    motivo = db.rpc('ra_motivo_lote_confirmado_v2', {'s': snapshot}).execute().data
    lote = None
    if motivo is None:
        try:
            lote = construir_lote_confirmado(snapshot, herramientas)
        except (ValidationError, ExcepcionContrato, ValueError, KeyError, TypeError):
            motivo = 'Datos revisados incompatibles con demanda, recepción o contratos; requiere revisión.'
    # Errores de transporte/40001 se propagan. Nunca reintentar con un snapshot viejo.
    return db.rpc('ra_registrar_lote_confirmado_v2', {
        **parametros, 'p_snapshot': snapshot, 'p_lote': lote, 'p_motivo': motivo,
    }).execute().data
