"""Rutas de la bandeja de salida. Solo las usa el bot, con el secreto compartido."""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response
from postgrest.exceptions import APIError

from api.dependencias import obtener_db, verificar_secreto_bot
from api.errores_http import ErrorApi
from api.esquemas import AvisoPorEnviar, ReservaAclaracion, ResultadoEnvio
from api.servicios import bandeja_salida
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.avisos")

router = APIRouter(
    prefix="/avisos",
    tags=["avisos"],
    dependencies=[Depends(verificar_secreto_bot)],
    responses={
        403: {"model": ErrorDominio, "description": "Secreto del bot ausente o incorrecto."},
        422: {"model": ErrorDominio, "description": "El cuerpo no cumple el formato."},
        503: {"model": ErrorDominio, "description": "Base de datos no disponible."},
    },
)

ERRORES_INFRAESTRUCTURA = (APIError, httpx.HTTPError)


def _proveedor_no_disponible(error: Exception) -> ErrorApi:
    logger.error("Fallo de la base de datos: %s", type(error).__name__)
    return ErrorApi(
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
        "No se pudo completar la operación con la base de datos. Inténtalo de nuevo.",
        recuperable=True,
    )


@router.post(
    "/reservar",
    response_model=AvisoPorEnviar,
    responses={204: {"description": "No hay avisos pendientes."}},
    summary="Reservar el siguiente aviso vigente para enviarlo",
)
def reservar(datos: ReservaAclaracion, db=Depends(obtener_db)):
    try:
        aviso = bandeja_salida.reservar(db, datos.trabajador_id)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
    if aviso is None:
        return Response(status_code=204)
    return aviso


@router.post(
    "/{aviso_id}/envio",
    status_code=204,
    summary="Registrar el resultado del envío: enviado, fallido o incierto",
)
def registrar_envio(aviso_id: UUID, datos: ResultadoEnvio, db=Depends(obtener_db)):
    try:
        bandeja_salida.registrar_envio(db, aviso_id, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
    return Response(status_code=204)
