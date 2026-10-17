"""Políticas de prioridad activas, para elegirlas en el panel (sesión válida)."""
import logging

import httpx
from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError
from pydantic import ValidationError

from api.auth import usuario_autenticado
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import PoliticaActiva
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.politicas")

router = APIRouter(
    tags=["priorizacion"],
    responses={
        403: {"model": ErrorDominio, "description": "Sin sesión válida."},
        503: {"model": ErrorDominio, "description": "Base de datos o verificación de sesión no disponibles."},
    },
)

CAMPOS = "politica_version,fundamento,peso_duracion,peso_vulnerabilidad,peso_poblacion,tope_horas,tope_personas,origen"


@router.get(
    "/politicas",
    response_model=list[PoliticaActiva],
    dependencies=[Depends(usuario_autenticado)],
    summary="Políticas de prioridad activas (sesión válida)",
)
def listar_politicas(db=Depends(obtener_db)):
    try:
        filas = db.table("politicas_prioridad").select(CAMPOS).eq("estado", "activa").order("politica_version").execute().data
        return [PoliticaActiva.model_validate(f) for f in filas or []]
    except (APIError, httpx.HTTPError) as error:
        logger.error("Fallo de la base de datos: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudo completar la operación con la base de datos. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
    except ValidationError:
        logger.error("Una política guardada no cumple el formato esperado")
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE, "Una política guardada no tiene el formato esperado.", recuperable=False
        ) from None
