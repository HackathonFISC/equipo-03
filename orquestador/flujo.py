"""Un paso por ejecución: no esperar respuestas humanas dentro de un proceso."""
from uuid import UUID, uuid4
from agentes.ingesta import PersistenciaIngesta, procesar_ejecucion
from agentes.territorial import procesar_territorial
from agentes.priorizacion import procesar_priorizacion


def avanzar(ejecucion, db, extractor, herramientas=None, decisor_planificacion=None, *, trabajador_id=None):
    eid = UUID(ejecucion['ejecucion_id'])
    etapa = ejecucion['etapa']
    if etapa == 'ingesta':
        return procesar_ejecucion(eid, PersistenciaIngesta(db), extractor, trabajador_id=trabajador_id)
    trabajador = trabajador_id or f'{etapa}:{uuid4()}'
    if etapa == 'territorial':
        return procesar_territorial(eid, db, trabajador)
    if etapa == 'priorizacion':
        return procesar_priorizacion(eid, db, trabajador, herramientas)
    if etapa == 'planificacion':
        from agentes.planificacion import procesar_planificacion
        from agentes.planificacion_gemini import DecisorGeminiPlanificacion
        return procesar_planificacion(eid, db, trabajador,
            decisor=decisor_planificacion or DecisorGeminiPlanificacion())
    if etapa == 'comunicacion':
        from agentes.comunicacion import procesar_comunicacion
        return procesar_comunicacion(eid, db, trabajador)
    return {'estado': 'etapa_no_soportada'}
