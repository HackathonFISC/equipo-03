"""Rutas del circuito de aclaración. Solo las usa el bot, con el secreto compartido."""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response
from postgrest.exceptions import APIError

from api.dependencias import obtener_db, verificar_secreto_bot
from api.errores_http import ErrorApi
from api.esquemas import (
    AclaracionPorEnviar,
    ReservaAclaracion,
    RespuestaDelBot,
    ResultadoEnvio,
    ResultadoRespuesta,
)
from api.servicios import aclaraciones
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.aclaraciones")

router = APIRouter(
    prefix="/aclaraciones",
    tags=["aclaraciones"],
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
    response_model=AclaracionPorEnviar,
    responses={204: {"description": "No hay aclaraciones pendientes."}},
    summary="Reservar la siguiente aclaración pendiente para enviarla",
)
def reservar(datos: ReservaAclaracion, db=Depends(obtener_db)):
    try:
        aclaracion = aclaraciones.reservar(db, datos.trabajador_id)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
    if aclaracion is None:
        return Response(status_code=204)
    return aclaracion


@router.post(
    "/{aclaracion_id}/envio",
    status_code=204,
    summary="Registrar el resultado del envío: enviado, fallido o incierto",
)
def registrar_envio(aclaracion_id: UUID, datos: ResultadoEnvio, db=Depends(obtener_db)):
    try:
        aclaraciones.registrar_envio(db, aclaracion_id, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
    return Response(status_code=204)


@router.post(
    "/respuestas",
    response_model=ResultadoRespuesta,
    summary="Entregar el reply de una persona a la pregunta",
)
def responder(datos: RespuestaDelBot, db=Depends(obtener_db)):
    """Siempre 200 con uno de seis resultados; el bot decide qué contestar con cada uno."""
    try:
        return aclaraciones.aceptar_respuesta(db, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
