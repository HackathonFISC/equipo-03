"""Ruta de sesión: le dice al panel quién es la persona autenticada y si puede aprobar."""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.auth import UsuarioAutenticado, rol_operativo, usuario_autenticado
from api.dependencias import obtener_db
from api.errores_http import ErrorApi
from contratos.errores import CodigoError, ErrorDominio

router = APIRouter(prefix="/sesion", tags=["sesión"])


class Sesion(BaseModel):
    usuario_id: UUID
    rol: str | None
    activo: bool
    es_coordinador: bool


@router.get(
    "",
    response_model=Sesion,
    responses={
        403: {"model": ErrorDominio, "description": "Sesión ausente, vencida o anónima."},
        503: {"model": ErrorDominio, "description": "No se pudo verificar la sesión."},
    },
    summary="Quién es la persona con sesión y si es coordinador activo",
)
def ver_sesion(usuario: UsuarioAutenticado = Depends(usuario_autenticado), db=Depends(obtener_db)) -> Sesion:
    """El usuario sale del token verificado. Sin fila en `usuarios_operativos` devuelve rol null."""
    fila = rol_operativo(db, usuario.usuario_id)
    rol = fila.get("rol") if fila else None
    activo = bool(fila and fila.get("activo") is True)
    return Sesion(usuario_id=usuario.usuario_id, rol=rol, activo=activo, es_coordinador=rol == "coordinador" and activo)
