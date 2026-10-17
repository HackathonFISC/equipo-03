"""Rutas de decisión sobre planes. Solo un coordinador activo con sesión verificada."""
import logging
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Path
from postgrest.exceptions import APIError

from api.auth import UsuarioAutenticado, coordinador_actual, usuario_autenticado
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import AprobarPlan, PlanPanel, RechazarPlan, ResultadoPlan
from api.servicios import aprobacion, planes
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.planes")

router = APIRouter(
    prefix="/planes",
    tags=["planes"],
    responses={
        403: {"model": ErrorDominio, "description": "Sin sesión válida o sin ser coordinador activo."},
        409: {"model": ErrorDominio, "description": "El plan cambió, no está verificado o ya fue resuelto."},
        422: {"model": ErrorDominio, "description": "El cuerpo no cumple el formato o faltan bloqueos por reconocer."},
        503: {"model": ErrorDominio, "description": "Base de datos o verificación de sesión no disponibles."},
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


@router.get(
    "",
    response_model=list[PlanPanel],
    dependencies=[Depends(usuario_autenticado)],
    summary="Planes guardados con sus rutas y paradas (sesión válida)",
)
def listar(db=Depends(obtener_db)):
    try:
        return planes.listar_planes(db)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None


@router.post(
    "/{plan_id}/versiones/{version}/aprobar",
    response_model=ResultadoPlan,
    summary="Aprobar una versión del plan (coordinador activo)",
)
def aprobar(
    plan_id: UUID,
    version: Annotated[int, Path(gt=0)],
    datos: AprobarPlan,
    usuario: UsuarioAutenticado = Depends(coordinador_actual),
    db=Depends(obtener_db),
):
    try:
        return aprobacion.aprobar(db, usuario.usuario_id, plan_id, version, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None


@router.post(
    "/{plan_id}/versiones/{version}/rechazar",
    response_model=ResultadoPlan,
    summary="Rechazar una versión pendiente del plan (coordinador activo)",
)
def rechazar(
    plan_id: UUID,
    version: Annotated[int, Path(gt=0)],
    datos: RechazarPlan,
    usuario: UsuarioAutenticado = Depends(coordinador_actual),
    db=Depends(obtener_db),
):
    try:
        return aprobacion.rechazar(db, usuario.usuario_id, plan_id, version, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
