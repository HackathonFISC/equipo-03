"""Lectura consistente V4 para la API de Noel; sin permisos tomados del cliente."""
from contratos.consultas import SolicitudEstadoSector, EstadoSector


def consultar_estado_sector(db, solicitud: SolicitudEstadoSector) -> EstadoSector:
    datos = db.rpc('ra_estado_sector_v4', {
        'p_sector_id': str(solicitud.sector_id),
    }).execute().data
    return EstadoSector.model_validate(datos)
