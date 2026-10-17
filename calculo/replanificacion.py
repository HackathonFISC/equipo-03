"""Preparación pura de un retiro ANTES de salida en el ensayo sintético V5."""
from uuid import UUID, uuid5

from contratos.solicitudes import SolicitudResolverRutas


def simular_retiro(entrada: SolicitudResolverRutas, vehiculo_id: UUID, *, datos_version: str):
    s = SolicitudResolverRutas.model_validate(entrada.model_dump(mode='json'))
    if s.origen != 'sintetico':
        raise ValueError('Esta función solo prepara ensayos sintéticos, no modifica flota real')
    if not isinstance(datos_version, str):
        raise ValueError('datos_version debe ser texto')
    datos_version = datos_version.strip()
    if not datos_version or datos_version == s.datos_version:
        raise ValueError('El retiro requiere una nueva datos_version explícita')
    vehiculo_id = UUID(str(vehiculo_id))
    elegido = next((v for v in s.vehiculos if v.vehiculo_id == vehiculo_id), None)
    if elegido is None or not elegido.disponible:
        raise ValueError('El vehículo debe existir y estar disponible antes del retiro')
    d = s.model_dump(mode='json')
    d['version'] += 1
    d['datos_version'] = datos_version
    d['ejecucion_id'] = str(uuid5(s.ejecucion_id, f"retiro-v5:{d['version']}:{datos_version}:{vehiculo_id}"))
    for v in d['vehiculos']:
        if v['vehiculo_id'] == str(vehiculo_id):
            v['disponible'] = False
    for n in d['necesidades']:
        n['datos_version'] = datos_version
        n['ejecucion_id'] = d['ejecucion_id']
    return SolicitudResolverRutas.model_validate(d)
