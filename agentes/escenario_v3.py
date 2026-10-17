"""Identidades exclusivas de ensayo; no modifica los reportes de Telegram."""
from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5
from calculo.demo_escenario_v3 import construir
from contratos.solicitudes import SolicitudResolverRutas


def preparar_escenario(*, escenario_id=None, coordinador_id=None, motivo=None):
    """Con coordinador registra revisión del ENSAYO, jamás validación de campo."""
    namespace = UUID(str(escenario_id)) if escenario_id else uuid4()
    s = construir()['solicitud_rutas']
    eid = str(uuid5(namespace, 'ejecucion'))
    s['plan_id'] = str(uuid5(namespace, 'plan'))
    s['ejecucion_id'] = eid
    s['version'] = 1
    s['datos_version'] += '-' + namespace.hex
    s['politica']['politica_version'] += '-' + namespace.hex
    antiguo = s['deposito']['deposito_id']
    nuevo = str(uuid5(namespace, 'deposito'))
    s['deposito']['deposito_id'] = nuevo
    s['matriz']['nodos_ids'] = [nuevo if x == antiguo else x for x in s['matriz']['nodos_ids']]
    s['matriz']['matriz_version'] += '-' + namespace.hex
    for v in s['vehiculos']:
        v['vehiculo_id'] = str(uuid5(namespace, v['vehiculo_id']))
    confirmacion = None
    if coordinador_id:
        if not motivo or not motivo.strip():
            raise ValueError('La revisión del coordinador exige motivo explícito')
        confirmacion = dict(usuario_id=str(UUID(str(coordinador_id))),
            confirmado_en=datetime.now(timezone.utc).isoformat(),
            motivo='ENSAYO SINTÉTICO revisado, sin autorización operativa: ' + motivo.strip())
        s['politica']['confirmacion_activacion'] = confirmacion
        s['politica']['fundamento'] = s['politica']['fundamento'].replace(
            'Copia activa exclusivamente en fixture local con identidad ficticia.',
            'Copia exclusiva de ensayo con revisión de coordinador; las cifras siguen siendo ficticias.')
    for n in s['necesidades']:
        n['ejecucion_id'] = eid
        n['incidente_id'] = str(uuid5(namespace, n['punto_atencion_id']))
        n['datos_version'] = s['datos_version']
        n['politica_version'] = s['politica']['politica_version']
        if confirmacion:
            for campo in ['confirmacion_demanda', 'confirmacion_clase', 'confirmacion_vulnerabilidad']:
                if n[campo] is not None:
                    n[campo] = confirmacion
    return SolicitudResolverRutas.model_validate(s)
