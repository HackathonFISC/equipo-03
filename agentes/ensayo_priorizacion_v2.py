"""Paquetes V2 de José con revisión real y dos ámbitos separados, sin inventar reportes."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5
from contratos.modelos import PoliticaPrioridad, EvaluacionNecesidades
from contratos.solicitudes import SolicitudValidarNecesidad
from calculo.demo_escenario_v3 import construir


def preparar_paquetes(coordinador_id, motivo, *, revision_id=None):
    uid=str(UUID(str(coordinador_id)))
    if not motivo or not motivo.strip():
        raise ValueError('Motivo de revisión requerido')
    raiz=UUID(str(revision_id)) if revision_id else uuid4()
    fixture=construir()
    confirmacion=dict(usuario_id=uid,confirmado_en=datetime.now(timezone.utc).isoformat(),
        motivo='ENSAYO SINTÉTICO aprobado exclusivamente para pruebas: '+motivo.strip())
    paquetes=[]
    for caso in ['calculable','reserva_desconocida']:
        ensayo=uuid5(raiz,caso); eid=str(uuid5(ensayo,'ejecucion'))
        dv='oeste-1.0-ensayo-3-v2-'+caso+'-'+ensayo.hex
        politica=deepcopy(fixture['solicitud_prioridad']['politica'])
        politica['politica_version']='oeste-prioridad-apoyo-pa-1-v2-'+ensayo.hex
        politica['confirmacion_activacion']=confirmacion
        politica['fundamento']=politica['fundamento'].replace('Copia activa exclusivamente en fixture local con identidad ficticia.',
            'Copia de ensayo con revisión de coordinadora autorizada; cifras ficticias.')
        politica=PoliticaPrioridad.model_validate(politica).model_dump(mode='json')
        entradas=[]
        necesidades={n['punto_atencion_id']:n for n in fixture['solicitud_prioridad']['necesidades']}
        for solicitud_original in fixture['solicitudes_validacion']:
            solicitud=deepcopy(solicitud_original); pid=solicitud['punto_atencion_id']
            incidente=str(uuid5(ensayo,pid))
            solicitud.update(ejecucion_id=eid,incidente_id=incidente,datos_version=dv)
            solicitud['demanda']['confirmacion']=confirmacion
            if caso=='reserva_desconocida' and 'Burunga' in next(p['nombre'] for p in fixture['solicitud_rutas']['puntos'] if p['punto_atencion_id']==pid):
                solicitud['demanda']['reserva_utilizable_litros']=None
            solicitud=SolicitudValidarNecesidad.model_validate(solicitud).model_dump(mode='json')
            n=deepcopy(necesidades[pid]);n.update(ejecucion_id=eid,incidente_id=incidente,datos_version=dv,politica_version=politica['politica_version'])
            for campo in ['confirmacion_demanda','confirmacion_clase','confirmacion_vulnerabilidad']:
                if n[campo] is not None:n[campo]=confirmacion
            # Es solo entrada al cálculo; nunca publicar el resultado anterior del fixture.
            n.update(estado_prioridad='pendiente',puntaje=None,componentes=None,posicion=None,
                     pendientes=['Requiere ejecutar validate_need y score_needs en este ensayo'])
            n=EvaluacionNecesidades.model_validate(n).model_dump(mode='json')
            entradas.append(dict(version_incidente=1,solicitud_demanda=solicitud,evaluacion=n))
        paquetes.append(dict(ensayo_id=str(ensayo),ejecucion_id=eid,caso=caso,origen='sintetico',revision=confirmacion,
            lote=dict(politica=politica,entradas=entradas)))
    return paquetes
