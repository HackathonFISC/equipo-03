"""Ruta de seguimiento: estado de una ejecución y la traza de sus agentes."""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import EjecucionPanel
from api.servicios.ejecuciones import obtener_ejecucion
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.ejecuciones")

router = APIRouter(prefix="/ejecuciones", tags=["ejecuciones"])


@router.get(
    "/{ejecucion_id}",
    response_model=EjecucionPanel,
    responses={
        404: {"description": "No existe una ejecución con ese ID."},
        422: {"model": ErrorDominio, "description": "El ID no es un UUID válido."},
        503: {"model": ErrorDominio, "description": "Base de datos no disponible."},
    },
    summary="Consultar el progreso de una ejecución y su traza",
)
def consultar(ejecucion_id: UUID, db=Depends(obtener_db)):
    try:
        ejecucion = obtener_ejecucion(db, ejecucion_id)
    except (APIError, httpx.HTTPError) as error:
        logger.error("Fallo de la base de datos: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudo consultar la ejecución. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
    if ejecucion is None:
        # D003 no define un código de dominio para "no encontrado"; se usa el 404 estándar.
        raise HTTPException(status_code=404, detail="No existe una ejecución con ese ID.")
    return ejecucion
