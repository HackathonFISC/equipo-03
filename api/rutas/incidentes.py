"""Ruta de consulta de incidentes para la página Necesidades (V2).

Requiere sesión válida. Validar el lugar de un incidente es una acción humana del coordinador activo, con evidencia
y auditoría (migración 0021); nunca la dispara un texto de Telegram.
"""
import logging

import httpx
from uuid import UUID

from fastapi import APIRouter, Depends
from postgrest.exceptions import APIError

from api.auth import UsuarioAutenticado, coordinador_actual, usuario_autenticado
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from api.esquemas import IncidentePanel, ResultadoLugar, ValidarLugar
from api.servicios.incidentes import listar_incidentes
from api.servicios.lugar import validar_lugar
from contratos.errores import CodigoError, ErrorDominio

logger = logging.getLogger("api.incidentes")

router = APIRouter(prefix="/incidentes", tags=["incidentes"])


@router.get(
    "",
    response_model=list[IncidentePanel],
    dependencies=[Depends(usuario_autenticado)],
    responses={
        403: {"model": ErrorDominio, "description": "Falta una sesión válida."},
        503: {"model": ErrorDominio, "description": "Base de datos no disponible."},
    },
    summary="Listar incidentes con su necesidad o sus pendientes (requiere sesión)",
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


@router.post(
    "/{incidente_id}/validar-lugar",
    response_model=ResultadoLugar,
    responses={
        403: {"model": ErrorDominio, "description": "Solo un coordinador activo puede validar un lugar."},
        409: {"model": ErrorDominio, "description": "La versión del incidente cambió o el lugar ya estaba resuelto."},
        503: {"model": ErrorDominio, "description": "Base de datos no disponible."},
    },
    summary="Validar el lugar de un incidente con evidencia (coordinador activo)",
)
def validar_el_lugar(
    incidente_id: UUID,
    datos: ValidarLugar,
    usuario: UsuarioAutenticado = Depends(coordinador_actual),
    db=Depends(obtener_db),
):
    try:
        return validar_lugar(db, usuario.usuario_id, incidente_id, datos)
    except (APIError, httpx.HTTPError) as error:
        logger.error("Fallo de la base de datos: %s", type(error).__name__)
        raise ErrorApi(
            CodigoError.PROVEEDOR_NO_DISPONIBLE,
            "No se pudo validar el lugar. Inténtalo de nuevo.",
            recuperable=True,
        ) from None
