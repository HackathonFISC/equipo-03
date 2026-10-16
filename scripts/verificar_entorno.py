"""Comprueba el entorno de cálculo V0 sin red, secretos ni conexiones a BD."""
import json
import sys
from importlib import import_module
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if sys.version_info < (3, 10):
        raise RuntimeError('Los contratos necesitan Python 3.10 o superior; entorno probado con 3.12.')
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    from contratos.modelos import Deposito, Vehiculo, PuntoAtencion, EvaluacionNecesidades, PoliticaPrioridad
    from contratos.solicitudes import SolicitudValidarNecesidad, TiempoServicio

    def load(name):
        return json.loads((ROOT / 'datos' / 'escenario' / name).read_text(encoding='utf-8-sig'))

    vehicles, demands, policy = (load(name) for name in ('vehiculos.json', 'demandas.json', 'politica_v1.json'))
    Deposito.model_validate(vehicles['deposito'])
    for model, items in (
        (Vehiculo, vehicles['vehiculos']), (PuntoAtencion, demands['puntos']),
        (EvaluacionNecesidades, demands['necesidades']),
        (SolicitudValidarNecesidad, demands['solicitudes_validacion']),
        (TiempoServicio, demands['servicios']),
    ):
        for item in items:
            model.model_validate(item)
    PoliticaPrioridad.model_validate(policy)
    ids = [p['punto_atencion_id'] for p in demands['puntos']]
    if len(ids) != 6 or len(set(ids)) != 6 or len(vehicles['vehiculos']) != 2:
        raise ValueError('V0 base requiere seis puntos únicos y dos vehículos.')
    if vehicles['datos_version'] != demands['datos_version']:
        raise ValueError('Versiones de escenario incompatibles.')
    if demands['politica_version'] != policy['politica_version']:
        raise ValueError('Versión de política incompatible.')
    if vehicles['deposito']['deposito_id'] in ids:
        raise ValueError('El depósito debe tener identificador distinto de los puntos.')
    for key in ('necesidades', 'solicitudes_validacion', 'servicios'):
        actual = [x['punto_atencion_id'] for x in demands[key]]
        if len(actual) != 6 or set(actual) != set(ids):
            raise ValueError(f'Referencias incompletas o duplicadas: {key}')
    for item in demands['necesidades']:
        if item['datos_version'] != demands['datos_version'] or item['politica_version'] != policy['politica_version']:
            raise ValueError('Necesidad con versiones incompatibles.')
    for item in demands['solicitudes_validacion']:
        if item['datos_version'] != demands['datos_version']:
            raise ValueError('Solicitud con versión incompatible.')

    # Comprueba que carga la biblioteca nativa; no calcula rutas ni acredita V1.
    manager = pywrapcp.RoutingIndexManager(2, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    if routing.vehicles() != 1 or routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC <= 0:
        raise RuntimeError('No se pudo inicializar el motor de rutas.')
    for module in ('fastapi', 'uvicorn', 'supabase', 'telegram'):
        import_module(module)
    for name in ('pydantic', 'ortools', 'pytest', 'fastapi', 'uvicorn', 'supabase', 'python-telegram-bot'):
        print(f'{name}: {version(name)}')
    print('OK: motor nativo, escenario V0 e importaciones de API y bot compatibles. Sin uso de credenciales ni red.')
    print(f"Politica: {policy['estado']}; la validacion de formato no activa ni autoriza operaciones.")


if __name__ == '__main__':
    main()
