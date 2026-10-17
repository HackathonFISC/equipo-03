"""Operaciones por sector de V4 con las RPC de la migración 0012 (Emilia).

La API solo traduce: la selección del plan, la habilitación del destino de ensayo y la proyección del estado
las decide la RPC en una transacción. El usuario que decide sale siempre del token verificado.
"""
import logging
from uuid import UUID

from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.errores_http import ErrorApi
from api.esquemas import (
    DestinoEnsayo,
    ResultadoDestinoEnsayo,
    ResultadoSeleccion,
    SeleccionarPlanSector,
)
from api.servicios.aclaraciones import _una_fila
from api.servicios.aprobacion import traducir_error
from contratos.consultas import EstadoSector
from contratos.errores import CodigoError

logger = logging.getLogger("api.sectores")

RPC_SELECCIONAR = "ra_seleccionar_plan_sector_v4"
RPC_DESTINO_ENSAYO = "ra_configurar_destino_ensayo_v4"
RPC_ESTADO = "ra_estado_sector_v4"

# Texto de la RPC (sin secretos ni datos de personas) -> mensaje para quien usa el panel.
REFINAMIENTOS = (
    ("sector inexistente", CodigoError.CONTRATO_INVALIDO, "El sector no existe.", ["sector_id"]),
    ("sector ajeno al plan", CodigoError.CONTRATO_INVALIDO, "El sector no tiene paradas en ese plan.", ["sector_id"]),
    ("destino Telegram autorizado", CodigoError.SIN_PERMISO, "El destino de Telegram aún no está autorizado.", []),
    (
        "sin aprobación vigente",
        CodigoError.VERSION_OBSOLETA,
        "El plan no tiene una aprobación vigente o cambiaron sus entradas. Recarga los planes.",
        [],
    ),
)


def _traducir(error: APIError) -> ErrorApi | None:
    traducido = traducir_error(error)
    if traducido is None:
        return None
    mensaje = str(getattr(error, "message", "") or "")
    for fragmento, codigo, texto, campos in REFINAMIENTOS:
        if fragmento in mensaje:
            return ErrorApi(codigo, texto, campos=list(campos))
    return traducido


def _llamar(db, rpc: str, parametros: dict):
    try:
        return _una_fila(db.rpc(rpc, parametros).execute().data)
    except APIError as error:
        traducido = _traducir(error)
        if traducido is None:
            raise
        raise traducido from None


def _formato_inesperado(rpc: str) -> ErrorApi:
    logger.error("La RPC %s devolvió una forma inesperada", rpc)
    return ErrorApi(
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
        "La base de datos respondió con un formato inesperado.",
        recuperable=False,
    )


def seleccionar_plan(db, usuario_id: UUID, sector_id: UUID, datos: SeleccionarPlanSector) -> ResultadoSeleccion:
    fila = _llamar(
        db,
        RPC_SELECCIONAR,
        {
            "p_usuario_id": str(usuario_id),
            "p_sector_id": str(sector_id),
            "p_plan_id": str(datos.plan_id),
            "p_version": datos.version,
            "p_motivo": datos.motivo,
        },
    )
    try:
        if not isinstance(fila, dict):
            raise ValueError
        return ResultadoSeleccion.model_validate(fila)
    except (ValueError, TypeError, ValidationError):
        raise _formato_inesperado(RPC_SELECCIONAR) from None


def configurar_destino_ensayo(db, usuario_id: UUID, destino_id: UUID, datos: DestinoEnsayo) -> ResultadoDestinoEnsayo:
    fila = _llamar(
        db,
        RPC_DESTINO_ENSAYO,
        {
            "p_usuario_id": str(usuario_id),
            "p_destino_id": str(destino_id),
            "p_habilitado": datos.habilitado,
            "p_motivo": datos.motivo,
        },
    )
    try:
        if not isinstance(fila, dict):
            raise ValueError
        return ResultadoDestinoEnsayo.model_validate(fila)
    except (ValueError, TypeError, ValidationError):
        raise _formato_inesperado(RPC_DESTINO_ENSAYO) from None


def estado_sector(db, sector_id: UUID) -> EstadoSector:
    """Proyección del contrato EstadoSector. Los errores de base no se convierten en 'sin plan vigente'."""
    fila = _llamar(db, RPC_ESTADO, {"p_sector_id": str(sector_id)})
    try:
        if not isinstance(fila, dict):
            raise ValueError
        return EstadoSector.model_validate(fila)
    except (ValueError, TypeError, ValidationError):
        raise _formato_inesperado(RPC_ESTADO) from None
