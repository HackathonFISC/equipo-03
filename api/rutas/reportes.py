"""Rutas de reportes: el bot los crea y el panel los lista."""
import logging

import httpx
from fastapi import APIRouter, Depends, Query, Response
from postgrest.exceptions import APIError

from api.dependencias import obtener_db, verificar_secreto_bot
from api.errores_http import ErrorApi
from api.esquemas import NuevoReporteTelegram, ReporteListado
from api.servicios.reportes import listar_reportes, registrar_reporte_telegram
from contratos.errores import CodigoError, ErrorDominio
from contratos.modelos import ReporteRegistrado

logger = logging.getLogger("api.reportes")

router = APIRouter(prefix="/reportes", tags=["reportes"])

# Para que /docs muestre el cuerpo real de los errores (ErrorDominio) y no el genérico de FastAPI.
RESPUESTAS_ERROR = {
    403: {"model": ErrorDominio, "description": "Secreto del bot ausente o incorrecto."},
    422: {"model": ErrorDominio, "description": "El cuerpo no cumple el formato."},
    503: {"model": ErrorDominio, "description": "Base de datos o secreto no disponibles."},
}

ERRORES_INFRAESTRUCTURA = (APIError, httpx.HTTPError)


def _proveedor_no_disponible(error: Exception) -> ErrorApi:
    # Solo el tipo de error: el mensaje del SDK podría incluir datos de la petición.
    logger.error("Fallo de la base de datos: %s", type(error).__name__)
    return ErrorApi(
        CodigoError.PROVEEDOR_NO_DISPONIBLE,
        "No se pudo completar la operación con la base de datos. Inténtalo de nuevo.",
        recuperable=True,
    )


@router.post(
    "",
    response_model=ReporteRegistrado,
    status_code=201,
    dependencies=[Depends(verificar_secreto_bot)],
    responses=RESPUESTAS_ERROR,
    summary="Registrar un reporte de Telegram (solo el bot)",
)
def crear_reporte(datos: NuevoReporteTelegram, respuesta: Response, db=Depends(obtener_db)):
    """201 si el reporte es nuevo; 200 con el mismo reporte_id si el mensaje ya estaba registrado."""
    try:
        registrado, nuevo = registrar_reporte_telegram(db, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
    if not nuevo:
        respuesta.status_code = 200
    return registrado


@router.get(
    "",
    response_model=list[ReporteListado],
    responses={k: v for k, v in RESPUESTAS_ERROR.items() if k != 403},
    summary="Listar reportes para el panel",
)
def listar(limite: int = Query(50, ge=1, le=200), db=Depends(obtener_db)):
    try:
        return listar_reportes(db, limite)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
