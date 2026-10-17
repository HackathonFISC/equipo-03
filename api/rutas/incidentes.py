"""Ruta de consulta de incidentes para la página Necesidades (V2).

La corrección de agrupaciones (separar un reporte) llega después, con la sesión del coordinador.
"""
import logging

import httpx
from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError

from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import IncidentePanel
from api.servicios.incidentes import listar_incidentes
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.incidentes")

router = APIRouter(prefix="/incidentes", tags=["incidentes"])


@router.get(
    "",
    response_model=list[IncidentePanel],
    responses={503: {"model": ErrorDominio, "description": "Base de datos no disponible."}},
    summary="Listar incidentes con su necesidad o sus pendientes",
)
def listar(db=Depends(obtener_db)):
    try:
        return listar_incidentes(db)
    except (APIError, httpx.HTTPError) as error:
        logger.error("Fallo de la base de datos: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudieron consultar los incidentes. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
