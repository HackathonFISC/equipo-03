"""Preparar el lote revisado de priorización (V2). Solo un coordinador activo con sesión verificada.

El servidor arma el lote con los incidentes reales y la política elegida; el coordinador solo confirma lo que sabe.
La RPC ra_preparar_priorizacion_v2 decide si lo acepta; después lo recoge el trabajador automático.
"""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from postgrest.exceptions import APIError

from api.auth import UsuarioAutenticado, coordinador_actual
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import PrepararPriorizacion, ResultadoPriorizacion
from api.servicios import priorizacion
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.priorizacion")

router = APIRouter(
    prefix="/ejecuciones",
    tags=["priorizacion"],
    responses={
        403: {"model": ErrorDominio, "description": "Sin sesión válida o sin ser coordinador activo."},
        404: {"description": "No existe una ejecución con ese ID."},
        409: {"model": ErrorDominio, "description": "La ejecución, los incidentes o la política cambiaron."},
        422: {"model": ErrorDominio, "description": "Cuerpo inválido o ámbito que necesita revisión antes de calcular."},
        503: {"model": ErrorDominio, "description": "Base de datos o verificación de sesión no disponibles."},
    },
)

ERRORES_INFRAESTRUCTURA = (APIError, httpx.HTTPError)


@router.post(
    "/{ejecucion_id}/priorizacion",
    response_model=ResultadoPriorizacion,
    status_code=202,
    summary="Preparar el lote revisado de priorización (solo coordinador)",
)
def preparar(
    ejecucion_id: UUID,
    datos: PrepararPriorizacion,
    usuario: UsuarioAutenticado = Depends(coordinador_actual),
    db=Depends(obtener_db),
):
    """202: el lote quedó pendiente de cálculo. Repetir el mismo envío es idempotente (`repetido: true`)."""
    try:
        return priorizacion.preparar_lote(db, usuario.usuario_id, ejecucion_id, datos)
    except priorizacion.EjecucionNoEncontrada:
        raise HTTPException(status_code=404, detail="No existe una ejecución con ese ID.") from None
    except ERRORES_INFRAESTRUCTURA as error:
        logger.error("Fallo de la base de datos: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudo completar la operación con la base de datos. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
