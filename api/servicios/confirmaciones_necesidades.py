"""Reutilización por incidente de revisiones humanas persistidas, nunca del navegador."""
from copy import deepcopy


def ambito_individual(ambito, incidente_id):
    incidentes = [i for i in ambito.get('incidentes', []) if i['incidente_id'] == incidente_id]
    puntos = {i.get('punto_atencion_id') for i in incidentes}
    return {
        'origen': ambito.get('origen'), 'ensayo_id': ambito.get('ensayo_id'),
        'incidentes': incidentes,
        'puntos': [p for p in ambito.get('puntos', []) if p['punto_atencion_id'] in puntos],
        'reportes': [r for r in ambito.get('reportes', []) if r['incidente_id'] == incidente_id],
    }


def entradas_confirmadas(db, ejecucion_id, politica):
    snapshot = db.rpc('ra_contexto_lote_confirmado_v2', {'p_ejecucion_id': str(ejecucion_id)}).execute().data
    if not isinstance(snapshot, dict) or not snapshot.get('revision') or not snapshot.get('ambito'):
        return {}
    revision = snapshot['revision']
    if revision['lote']['politica'] != politica:
        return {}
    resultado = {}
    for entrada in revision['lote']['entradas']:
        iid = entrada['solicitud_demanda']['incidente_id']
        actual = ambito_individual(snapshot['ambito'], iid)
        anterior = ambito_individual(revision['ambito'], iid)
        if not actual['incidentes'] or actual != anterior:
            continue
        # La guarda existente comprueba política, coordinadores activos, conflictos,
        # demanda, recepción y vigencia de ventana. No se fabrica otra confirmación.
        parcial = deepcopy(snapshot)
        parcial['ambito'] = actual
        parcial['politica'] = politica
        parcial['revision']['ambito'] = anterior
        parcial['revision']['lote']['entradas'] = [entrada]
        motivo = db.rpc('ra_motivo_lote_confirmado_v2', {'s': parcial}).execute().data
        if motivo is None:
            resultado[iid] = deepcopy(entrada)
    return resultado


def adaptar_entrada(entrada, ejecucion_id, datos_version, ahora):
    nueva = deepcopy(entrada)
    for campo in ('solicitud_demanda', 'evaluacion'):
        nueva[campo].update(ejecucion_id=str(ejecucion_id), datos_version=datos_version,
                            creado_en=ahora.isoformat())
    return nueva
