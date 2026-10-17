"""Rutas por sector y destino de V4: seleccionar el plan que se comunica, habilitar el chat de ensayo y
consultar el estado de un sector. Las decisiones solo las toma un coordinador activo con sesión verificada."""
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError

from api.auth import UsuarioAutenticado, coordinador_actual, sesion_o_bot
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import DestinoEnsayo, ResultadoDestinoEnsayo, ResultadoSeleccion, SeleccionarPlanSector
from api.servicios import sectores
from contratos.consultas import EstadoSector
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.sectores")

router = APIRouter(
    tags=["sectores"],
    responses={
        403: {"model": ErrorDominio, "description": "Sin sesión válida (o secreto del bot) o sin ser coordinador activo."},
        409: {"model": ErrorDominio, "description": "El plan no tiene aprobación vigente o cambió."},
        422: {"model": ErrorDominio, "description": "El cuerpo no cumple el formato o el sector no existe."},
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
    "/sectores/{sector_id}/estado",
    response_model=EstadoSector,
    dependencies=[Depends(sesion_o_bot)],
    summary="Estado de un sector: su plan vigente y sus puntos (sesión del panel o secreto del bot)",
)
def estado_del_sector(sector_id: UUID, db=Depends(obtener_db)):
    try:
        return sectores.estado_sector(db, sector_id)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None


@router.post(
    "/sectores/{sector_id}/plan-vigente",
    response_model=ResultadoSeleccion,
    summary="Seleccionar el plan aprobado que se comunica en este sector (coordinador activo)",
)
def seleccionar_plan(
    sector_id: UUID,
    datos: SeleccionarPlanSector,
    usuario: UsuarioAutenticado = Depends(coordinador_actual),
    db=Depends(obtener_db),
):
    try:
        return sectores.seleccionar_plan(db, usuario.usuario_id, sector_id, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None


@router.put(
    "/destinos/{destino_id}/ensayo",
    response_model=ResultadoDestinoEnsayo,
    summary="Habilitar o deshabilitar un destino de Telegram para ensayos sintéticos (coordinador activo)",
)
def destino_de_ensayo(
    destino_id: UUID,
    datos: DestinoEnsayo,
    usuario: UsuarioAutenticado = Depends(coordinador_actual),
    db=Depends(obtener_db),
):
    try:
        return sectores.configurar_destino_ensayo(db, usuario.usuario_id, destino_id, datos)
    except ERRORES_INFRAESTRUCTURA as error:
        raise _proveedor_no_disponible(error) from None
