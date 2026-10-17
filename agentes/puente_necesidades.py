"""Necesidades persistidas → escenario sintético; sin activar políticas ni aprobar."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID, uuid5
from contratos.modelos import EvaluacionNecesidades, PoliticaPrioridad
from postgrest.exceptions import APIError
from contratos.solicitudes import SolicitudResolverRutas

ESCENARIO = Path(__file__).resolve().parents[1]/'datos/escenario/oeste-1.0-ensayo-3/escenario_fixture.json'


class RevisionPuente(ValueError):
    """Motivo controlado; nunca incluir una respuesta cruda de BD o del proveedor."""


def infraestructura_ensayo():
    # Solo infraestructura confirmada por el usuario. No reutilizar sus demandas,
    # política, confirmaciones, población ni identidades de incidentes ficticios.
    fuente = json.loads(ESCENARIO.read_text())['solicitud_rutas']
    return {k: deepcopy(fuente[k]) for k in ('deposito','vehiculos','puntos','matriz','servicios','limite_solver_segundos')}


def construir_solicitud(snapshot):
    e = snapshot['ejecucion']
    if e['origen'] not in {'real','estimado','sintetico'}:
        raise RevisionPuente('Procedencia desconocida; revisar sin sustituir datos.')
    if e['etapa'] != 'priorizacion' or e['estado'] != 'espera_validacion':
        raise RevisionPuente('La ejecución ya no espera el puente de priorización.')
    incidentes = snapshot['incidentes']
    evaluaciones = deepcopy(snapshot['evaluaciones'])
    if not incidentes or not evaluaciones or len(incidentes) != len(evaluaciones):
        raise RevisionPuente('Faltan necesidades persistidas del ámbito completo; no omitir incidentes.')
    ids = {i['incidente_id'] for i in incidentes}
    if ids != {n['incidente_id'] for n in evaluaciones}:
        raise RevisionPuente('Las necesidades no cubren los incidentes vigentes.')
    puntos_ids = [n['punto_atencion_id'] for n in evaluaciones]
    if len(puntos_ids)!=len(set(puntos_ids)) or not 1<=len(puntos_ids)<=6:
        raise RevisionPuente('Resolver episodios duplicados por punto o un ámbito mayor al escenario aprobado.')
    entradas = {f['solicitud_demanda']['incidente_id']: f for f in e['entrada_priorizacion']['entradas']}
    for i in incidentes:
        if i['origen']!=e['origen'] or i['incidente_id'] not in entradas or entradas[i['incidente_id']]['version_incidente']!=i['version']:
            raise RevisionPuente('Incidente desactualizado o de otro origen; revisar el lote antes de planificar.')
    politica_original = {k:deepcopy(v) for k,v in snapshot['politica'].items() if k in PoliticaPrioridad.model_fields}
    politica = PoliticaPrioridad.model_validate(politica_original)
    # Validar sin normalizar las fechas del JSON que la RPC compara con la BD.
    politica_solicitud = politica.model_dump(mode='json')
    politica_solicitud.update(politica_original)
    if politica.estado!='activa' or politica.politica_version!=e['entrada_priorizacion']['politica']['politica_version']:
        raise RevisionPuente('La política revisada dejó de estar activa o cambió de versión.')
    for n in evaluaciones:
        modelo = EvaluacionNecesidades.model_validate(n)
        if str(modelo.ejecucion_id)!=e['ejecucion_id'] or modelo.origen!=e['origen'] or modelo.datos_version!=e['datos_version']:
            raise RevisionPuente('Necesidad de otra ejecución, origen o versión de datos.')
    base = snapshot['infraestructura']
    catalogo = {p['punto_atencion_id']:p for p in snapshot['puntos']}
    permitidos = {p['punto_atencion_id'] for p in base['puntos']}
    if not set(puntos_ids)<=permitidos or not set(puntos_ids)<=set(catalogo):
        raise RevisionPuente('Hay puntos fuera del escenario confirmado o ausentes del catálogo.')
    puntos=[]
    for pid in sorted(puntos_ids):
        p=catalogo[pid]
        if not p['activo']:
            raise RevisionPuente('Un punto de atención dejó de estar activo.')
        puntos.append(dict(punto_atencion_id=pid,sector_id=p['sector_id'],nombre=p['nombre'],origen=p['origen'],
            ubicacion=dict(latitud=p['latitud'],longitud=p['longitud'],fuente=p['fuente_ubicacion'],
                           precision_metros=p['precision_metros'],representa_punto_atencion=p['representa_punto_atencion'])))
    deposito=deepcopy(base['deposito'])
    existente=snapshot.get('deposito')
    if existente:
        if existente['origen']!='sintetico' or not existente['activo']:
            raise RevisionPuente('Depósito incompatible con el ensayo sintético.')
        deposito=dict(deposito_id=existente['deposito_id'],nombre=existente['nombre'],origen=existente['origen'],
            ubicacion=dict(latitud=existente['latitud'],longitud=existente['longitud'],fuente=existente['fuente_ubicacion'],
                           precision_metros=existente['precision_metros'],representa_punto_atencion=None))
    vehiculos=[]
    actuales={v['vehiculo_id']:v for v in snapshot.get('vehiculos',[])}
    for propuesto in base['vehiculos']:
        v=actuales.get(propuesto['vehiculo_id'])
        if v:
            if v['origen']!='sintetico' or v['deposito_id']!=deposito['deposito_id']:
                raise RevisionPuente('Vehículo incompatible con el depósito/origen del ensayo.')
            vehiculos.append(dict(vehiculo_id=v['vehiculo_id'],capacidad_litros=v['capacidad_litros'],disponible=v['disponible'],
                                  turno=dict(inicio=v['turno_inicio'],fin=v['turno_fin']),origen=v['origen']))
        else:
            vehiculos.append(deepcopy(propuesto))
    matriz=deepcopy(base['matriz']); nodos=[deposito['deposito_id'],*sorted(puntos_ids)]
    indices=[matriz['nodos_ids'].index(n) for n in nodos]
    matriz['minutos']=[[matriz['minutos'][a][b] for b in indices] for a in indices]
    matriz['nodos_ids']=nodos
    # El origen de las necesidades sigue siendo el original. El escenario usa
    # recursos inventados y por eso se etiqueta sintético, con modo ensayo en BD.
    solicitud=dict(esquema_version='1.0',ejecucion_id=e['ejecucion_id'],creado_en=e['creado_en'],origen='sintetico',
        plan_id=str(uuid5(UUID(e['ejecucion_id']),'necesidades-v3:'+e['datos_version'])),version=1,
        datos_version=e['datos_version'],politica=politica_solicitud,deposito=deposito,vehiculos=vehiculos,
        puntos=puntos,necesidades=evaluaciones,matriz=matriz,
        servicios=[deepcopy(s) for s in base['servicios'] if s['punto_atencion_id'] in puntos_ids],
        limite_solver_segundos=base['limite_solver_segundos'],recargas_permitidas=False,entregas_parciales_permitidas=False)
    SolicitudResolverRutas.model_validate(solicitud)
    # Mantener fechas y objetos originales para la comparación JSON exacta de la RPC.
    return solicitud


def preparar_puentes(db, limite=20):
    pendientes = db.rpc('ra_puentes_pendientes_v3', {'p_limite':limite}).execute().data
    if not isinstance(pendientes,list):
        raise RuntimeError('Respuesta inválida de la cola de puentes; revisar 0016.')
    resultados=[]
    for fila in pendientes:
        eid=fila['ejecucion_id']
        snapshot=db.rpc('ra_contexto_puente_v3',dict(p_ejecucion_id=eid,p_infraestructura=infraestructura_ensayo())).execute().data
        motivo=None
        try:
            solicitud=construir_solicitud(snapshot)
        except RevisionPuente as error:
            motivo=str(error)
        except (ValueError, KeyError, TypeError):
            motivo='Contexto del puente incompleto o incompatible con los contratos; revisar sin sustituir datos.'
        if motivo is None:
            try:
                resultados.append(db.rpc('ra_registrar_puente_v3',dict(p_ejecucion_id=eid,p_snapshot=snapshot,p_solicitud=solicitud)).execute().data)
                continue
            except APIError as error:
                if str(error.code) not in {'22023','42501','55000'}:
                    # 40001 pide volver a leer; un acuse perdido conserva idempotencia.
                    raise
                motivo='Revisar permisos, escenario ya registrado o infraestructura; preservar historial antes de crear otra versión.'
        resultados.append(db.rpc('ra_revisar_puente_v3',dict(p_ejecucion_id=eid,p_snapshot=snapshot,p_motivo=motivo)).execute().data)
    return resultados
