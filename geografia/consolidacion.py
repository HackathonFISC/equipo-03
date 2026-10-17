"""Reglas de episodio: mismo punto, origen y problema, con intervalos respaldados."""
from datetime import datetime, timedelta


def periodo_reportado(creado_en, horas_sin_agua):
    fecha = datetime.fromisoformat(creado_en.replace('Z', '+00:00')) if isinstance(creado_en, str) else creado_en
    # El microsegundo hace el extremo derecho inclusivo para el almacenamiento.
    # No es una predicción de cuándo se restablecerá el suministro.
    inicio = fecha - timedelta(hours=horas_sin_agua) if horas_sin_agua is not None else fecha
    return inicio, fecha + timedelta(microseconds=1)


def mismo_episodio(a, b):
    return (a['punto_atencion_id'] == b['punto_atencion_id'] and a['origen'] == b['origen']
            and a['tipo_problema'] == b['tipo_problema'] != 'desconocido'
            and a['episodio_establecido'] and b['episodio_establecido']
            and a['periodo_inicio'] < b['periodo_fin'] and b['periodo_inicio'] < a['periodo_fin'])


def link_reports(ejecucion_id, db, trabajador_id, snapshot, resolucion):
    """Asociación persistida con bloqueo de punto, historial y traza atómicos."""
    return db.rpc('ra_finalizar_territorial', {'p_ejecucion_id': str(ejecucion_id),
        'p_trabajador_id': trabajador_id, 'p_snapshot': snapshot, 'p_resolucion': resolucion}).execute().data
